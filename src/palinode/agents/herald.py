"""Herald. Handles what cannot be undone.

Every other part of this system is about reversal. This part exists because
some things do not reverse, and a recovery tool that quietly skips those is
worse than no tool at all, since it leaves people believing they are whole.

Herald does three things for a T3 action: says who was affected, writes the
disclosure, and puts a number on the damage.
"""

from __future__ import annotations

import logging
from typing import Optional

from ..config import settings
from ..types import ActionRecord

log = logging.getLogger("palinode.herald")

_PROMPT = """Write a short disclosure about an automated action that cannot be reversed.

Audience: the affected party named below. Tone: direct, factual, no apologising
twice, no marketing language. Say what happened, what it means for them, what
is already being done, and who to contact. Six sentences at most.

action: {tool}
details: {args}
amount at risk: ${exposure:,.2f}
affected party: {party}
what makes it unrecoverable: {reason}"""


class Herald:
    def __init__(self) -> None:
        self._client = None

    def _model(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client()
        return self._client

    async def disclose(self, record: ActionRecord) -> dict:
        contract = record.contract
        parties = contract.affected_parties if contract else []
        exposure = record.cost()

        body = await self._draft(record, parties[0] if parties else "the account holder")

        report = {
            "action_id": record.id,
            "tool": record.tool,
            "agent": record.agent,
            "exposure_usd": round(exposure, 2),
            "affected_parties": parties,
            "reason": record.tier_reason,
            "disclosure": body,
        }
        log.warning(
            "unrecoverable action %s by %s, exposure $%.2f", record.id, record.agent, exposure
        )
        return report

    async def _draft(self, record: ActionRecord, party: str) -> str:
        try:
            client = self._model()
            response = await client.aio.models.generate_content(
                model=settings.planner_model,
                contents=_PROMPT.format(
                    tool=record.tool,
                    args=str(record.args)[:500],
                    exposure=record.cost(),
                    party=party,
                    reason=record.tier_reason or "no reversal path exists",
                ),
                # Room for the model to think and still finish the sentence.
                # At 400 the thinking budget ate the disclosure and the
                # affected party got half of one.
                config={"temperature": 0.2, "max_output_tokens": 2000},
            )
            return (response.text or "").strip()
        except Exception as exc:  # noqa: BLE001
            log.error("could not draft disclosure for %s: %s", record.id, exc)
            # Falling back to a plain statement of fact. An incident is the
            # wrong moment to have no message because a model was unavailable.
            return (
                f"An automated process performed {record.tool} on your account. "
                f"This action cannot be reversed. Amount affected: "
                f"${record.cost():,.2f}. We have opened an incident and will "
                f"contact you directly."
            )

    async def summarise(self, records: list[ActionRecord]) -> dict:
        total = sum(r.cost() for r in records)
        return {
            "unrecoverable_count": len(records),
            "total_exposure_usd": round(total, 2),
            "actions": [{"id": r.id, "tool": r.tool, "usd": r.cost()} for r in records],
        }


_herald: Optional[Herald] = None


def get_herald() -> Herald:
    global _herald
    if _herald is None:
        _herald = Herald()
    return _herald
