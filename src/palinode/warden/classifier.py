"""Reversibility classification.

This sits inline in front of every tool call every agent in the fleet makes. If
it is slow, the whole fleet is slow and nobody deploys this. The budget is
about 80ms, which shapes two decisions:

  1. Known tools skip the model entirely and hit a static table.
  2. Everything else goes to Flash with a tiny prompt and a fixed schema.

The static table is not a shortcut, it is the correct answer. You do not need a
language model to know that a Stripe charge is compensable.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from ..config import settings
from ..types import Tier

log = logging.getLogger("palinode.classifier")

# Tools we already understand. Matched on the tool name, longest pattern first.
KNOWN: dict[str, tuple[Tier, str]] = {
    "db_write": (Tier.T0_REVERSIBLE, "row level write with a captured prior value"),
    "db_update": (Tier.T0_REVERSIBLE, "row level update with a captured prior value"),
    "db_delete": (Tier.T0_REVERSIBLE, "soft delete, prior row is snapshotted"),
    "stripe_charge": (Tier.T1_COMPENSABLE, "card charges can be refunded through the API"),
    "stripe_refund": (Tier.T0_REVERSIBLE, "refund of a refund is a fresh charge"),
    "github_merge": (Tier.T1_COMPENSABLE, "a merge can be reverted as a new commit"),
    "github_pr_open": (Tier.T0_REVERSIBLE, "a pull request can be closed"),
    "slack_post": (Tier.T2_SOCIAL, "chat.delete works for our own messages but people saw it"),
    "email_send": (Tier.T2_SOCIAL, "smtp has no recall, only a retraction after delivery"),
    "wire_transfer": (Tier.T3_UNRECOVERABLE, "settled funds do not come back on request"),
    "ach_debit": (Tier.T3_UNRECOVERABLE, "reversal windows are not guaranteed"),
    "public_post": (Tier.T3_UNRECOVERABLE, "deletion does not undo distribution"),
}

_PROMPT = """You classify how reversible a single tool call is. Answer with JSON only.

T0 an exact inverse exists and restores prior state, for example a database write
T1 the effect can be returned through an API, for example a refund or a git revert
T2 a person has already seen it, the best available action is a correction
T3 nothing brings this back, for example settled funds or public distribution

Choose the worst tier that honestly applies. When unsure between two, pick the
less recoverable one. Being wrong towards caution costs a held action. Being
wrong the other way costs money that does not come back.

tool: {tool}
arguments: {args}

Reply as {{"tier": "T0"|"T1"|"T2"|"T3", "reason": "under 15 words"}}"""


def _static(tool: str) -> Optional[tuple[Tier, str]]:
    name = tool.lower()
    if name in KNOWN:
        return KNOWN[name]
    for pattern, verdict in sorted(KNOWN.items(), key=lambda kv: -len(kv[0])):
        if pattern in name:
            return verdict
    return None


def _parse(text: str) -> Optional[tuple[Tier, str]]:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
        return Tier(payload["tier"]), str(payload.get("reason", ""))[:120]
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


class ReversibilityClassifier:
    def __init__(self) -> None:
        self._model = None

    def _client(self):
        if self._model is None:
            from google import genai

            self._model = genai.Client()
        return self._model

    async def classify(self, tool: str, args: dict[str, Any]) -> tuple[Tier, str]:
        hit = _static(tool)
        if hit is not None:
            return hit

        try:
            client = self._client()
            response = await client.aio.models.generate_content(
                model=settings.classifier,
                contents=_PROMPT.format(tool=tool, args=json.dumps(args, default=str)[:600]),
                config={
                    "temperature": 0,
                    "max_output_tokens": 80,
                    "response_mime_type": "application/json",
                    # Thinking off. Gemini 3.5 Flash spends thinking tokens out
                    # of max_output_tokens, so an 80 token budget produced 76
                    # tokens of reasoning, no output at all, and a MAX_TOKENS
                    # finish that looked exactly like the model being broken.
                    # It also costs latency this call does not have: the whole
                    # point of the tier being decided inline is that it is
                    # cheap enough to sit in front of every tool call.
                    "thinking_config": {"thinking_budget": 0},
                },
            )
            parsed = _parse(response.text or "")
            if parsed is not None:
                return parsed
            log.warning("classifier returned unparseable output for %s", tool)
        except Exception as exc:  # noqa: BLE001
            log.warning("classifier failed for %s, defaulting to T3: %s", tool, exc)

        # Failing closed is the only defensible default. An unknown tool that we
        # could not classify is treated as unrecoverable, which means it gets
        # held rather than quietly executed.
        return Tier.T3_UNRECOVERABLE, "classification unavailable, failing closed"


_classifier: Optional[ReversibilityClassifier] = None


def get_classifier() -> ReversibilityClassifier:
    global _classifier
    if _classifier is None:
        _classifier = ReversibilityClassifier()
    return _classifier
