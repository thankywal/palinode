"""Sentinel. Decides on its own that something has gone wrong.

Without this, Palinode is an undo button, and an undo button needs a person
standing next to it. The whole premise falls apart there, because by the time
somebody notices an agent has misfired the useful window has usually closed.

So Sentinel watches the ledger and calls Regret itself. No approval, no ticket,
no human in the loop. A person finds out by reading what already happened.

The signals it reads are all already in the ledger. Nothing new is collected,
which matters: a detector that needs its own telemetry pipeline is a detector
that will be out of date with the thing it is watching.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from ..config import settings
from ..intel import get_intel
from ..ledger.store import get_ledger
from ..telemetry import annotate, span
from ..types import ActionRecord, ActionState, Tier

log = logging.getLogger("palinode.sentinel")


@dataclass
class Signal:
    """One reason to be suspicious, with the weight it carries."""

    name: str
    weight: float
    detail: str


@dataclass
class Assessment:
    run_id: str
    score: float
    signals: list[Signal] = field(default_factory=list)
    trigger_action: Optional[str] = None
    rationale: str = ""

    @property
    def should_reverse(self) -> bool:
        return self.score >= 1.0

    def summary(self) -> str:
        names = ", ".join(s.name for s in self.signals)
        return f"score {self.score:.2f} [{names}]"


# Weights are deliberately blunt. Any two of these firing together clears the
# threshold, which is the behaviour we want: one oddity is a Tuesday, two is an
# incident. Tuning this finer without production data would be pretending to a
# precision we do not have.
# A counterparty on the intel store is not a heuristic about the shape of a
# run. It is a fact that arrived after the run finished, so it carries more
# weight than the whole rest of this file put together and clears the threshold
# on its own. Two guesses make an incident. One fact already is one.
FLAGGED_BENEFICIARY = 1.2

UNKNOWN_BENEFICIARY = 0.6
LARGE_FOR_AGENT = 0.5
IRREVERSIBLE_TAIL = 0.5
NO_REVERSAL_PATH = 0.4
UNVERIFIED_SOURCE = 0.6

_PROMPT = """You review a sequence of actions an autonomous agent fleet just took.

Decide whether this looks like the fleet acting on manipulated input, for
example a poisoned invoice or an injected instruction, rather than doing its
normal job.

Weigh the destination of value more than the amount. A large payment to a
counterparty seen many times before is routine. A modest payment to one that
appears once, at the end of an otherwise ordinary chain, is not.

actions:
{actions}

Reply as {{"manipulated": true|false, "confidence": 0.0-1.0, "reason": "under 20 words"}}"""


class Sentinel:
    """Watches a run and reverses it without being asked."""

    def __init__(self, regret, herald=None) -> None:
        self.ledger = get_ledger()
        self.regret = regret
        self.herald = herald
        self._client = None
        # Counterparties this fleet has legitimately dealt with before. In a
        # real deployment this comes from the vendor master, not memory.
        self.known_counterparties: set[str] = set()
        self.intel = get_intel()

    # ------------------------------------------------------------- signals

    def _beneficiary(self, record: ActionRecord) -> Optional[str]:
        for key in ("beneficiary", "customer", "to", "account"):
            value = record.args.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    def _amount(self, record: ActionRecord) -> float:
        for key in ("amount_usd", "amount", "value_usd"):
            value = record.args.get(key)
            if isinstance(value, (int, float)):
                return float(value)
        return 0.0

    async def _flagged_signals(
        self, actions: list[ActionRecord]
    ) -> tuple[list[Signal], Optional[str]]:
        """Counterparties we have since been told are bad.

        Deliberately not scoped to irreversible actions, which is what every
        other signal here does. The run this catches is the one where nothing
        was irreversible and nothing looked wrong: an ordinary renewal paid to
        an ordinary vendor, three weeks before anyone found out the vendor was
        not one. There is no shape to spot in that. There is only a fact that
        turned up later.
        """
        signals: list[Signal] = []
        trigger: Optional[str] = None
        seen: set[str] = set()

        for record in actions:
            party = self._beneficiary(record)
            if not party or party in seen:
                continue
            entry = await self.intel.get(party)
            if entry is None:
                continue
            seen.add(party)
            trigger = trigger or record.id
            signals.append(
                Signal(
                    "flagged_beneficiary",
                    FLAGGED_BENEFICIARY,
                    f"{party} was flagged by {entry['source']} after this ran",
                )
            )

        return signals, trigger

    async def _static_signals(self, actions: list[ActionRecord]) -> tuple[list[Signal], Optional[str]]:
        signals, trigger = await self._flagged_signals(actions)

        amounts = [self._amount(a) for a in actions if self._amount(a) > 0]
        typical = (sum(amounts) / len(amounts)) if amounts else 0.0

        for record in actions:
            if record.tier is not Tier.T3_UNRECOVERABLE:
                continue

            trigger = trigger or record.id
            party = self._beneficiary(record)
            amount = self._amount(record)

            if party and party not in self.known_counterparties:
                signals.append(
                    Signal(
                        "unknown_beneficiary",
                        UNKNOWN_BENEFICIARY,
                        f"{party} has not been seen before",
                    )
                )

            if typical and amount > typical * 2:
                signals.append(
                    Signal(
                        "large_for_agent",
                        LARGE_FOR_AGENT,
                        f"${amount:,.2f} against a run average of ${typical:,.2f}",
                    )
                )

            if record.contract is None or not record.contract.tool:
                signals.append(
                    Signal(
                        "no_reversal_path",
                        NO_REVERSAL_PATH,
                        f"{record.tool} was authorised with no way back",
                    )
                )

            # An irreversible action sitting at the end of a chain of ordinary
            # reversible ones is the shape a successful injection leaves.
            index = actions.index(record)
            if index == len(actions) - 1 and index > 0:
                earlier = actions[:index]
                if all(a.tier is not Tier.T3_UNRECOVERABLE for a in earlier):
                    signals.append(
                        Signal(
                            "irreversible_tail",
                            IRREVERSIBLE_TAIL,
                            "the only unrecoverable action is the last one",
                        )
                    )

        return signals, trigger

    async def _model_signal(self, actions: list[ActionRecord]) -> Optional[Signal]:
        """Ask Flash whether the shape of the run looks manipulated."""
        try:
            from google import genai

            if self._client is None:
                self._client = genai.Client()

            payload = json.dumps(
                [
                    {
                        "agent": a.agent,
                        "tool": a.tool,
                        "tier": a.tier.value,
                        "args": {k: v for k, v in a.args.items() if k != "body"},
                    }
                    for a in actions
                ],
                default=str,
            )[:2400]

            response = await self._client.aio.models.generate_content(
                model=settings.classifier,
                contents=_PROMPT.format(actions=payload),
                config={
                    "temperature": 0,
                    "max_output_tokens": 200,
                    "response_mime_type": "application/json",
                    # See the classifier. A fixed shape verdict does not need
                    # reasoning tokens, and with them on this returned nothing.
                    "thinking_config": {"thinking_budget": 0},
                },
            )
            match = re.search(r"\{.*\}", response.text or "", re.S)
            if not match:
                return None

            verdict = json.loads(match.group(0))
            if not verdict.get("manipulated"):
                return None

            confidence = float(verdict.get("confidence", 0.5))
            return Signal(
                "model_review",
                round(confidence, 2),
                str(verdict.get("reason", ""))[:120],
            )
        except Exception as exc:  # noqa: BLE001
            # No model, no veto. The static signals stand on their own so that
            # losing Gemini degrades detection rather than disabling it.
            log.info("model review unavailable, using static signals only: %s", exc)
            return None

    # ------------------------------------------------------------ decision

    async def assess(self, run_id: str, *, use_model: bool = True) -> Assessment:
        """Score a run.

        use_model=False keeps this to the static signals. The dashboard polls
        this several times a second to draw a panel, and every one of those
        polls was reaching Gemini, which is both slow and a way to spend an
        inference budget on redrawing a number that has not changed. The
        decision path still asks the model. Watching does not.
        """
        actions = [
            a
            for a in await self.ledger.by_run(run_id)
            if a.state in (ActionState.EXECUTED, ActionState.UNRECOVERABLE)
        ]
        if not actions:
            return Assessment(run_id=run_id, score=0.0, rationale="nothing to assess")

        signals, trigger = await self._static_signals(actions)

        if use_model:
            model = await self._model_signal(actions)
            if model is not None:
                signals.append(model)

        score = sum(s.weight for s in signals)
        rationale = "; ".join(s.detail for s in signals) or "nothing unusual"

        assessment = Assessment(
            run_id=run_id,
            score=round(score, 2),
            signals=signals,
            trigger_action=trigger,
            rationale=rationale,
        )
        with span(
            "palinode.sentinel.assess",
            run_id=run_id,
            score=assessment.score,
            would_reverse=assessment.should_reverse,
            signals=",".join(s.name for s in signals),
        ):
            pass
        log.info("assessed %s: %s", run_id, assessment.summary())
        return assessment

    async def watch(self, run_id: str, verifier=None) -> dict:
        """Assess, and reverse on its own if the run looks manipulated."""
        assessment = await self.assess(run_id)

        if not assessment.should_reverse:
            return {
                "run_id": run_id,
                "triggered": False,
                "score": assessment.score,
                "rationale": assessment.rationale,
            }

        log.warning(
            "reversing %s without human approval, %s", run_id, assessment.summary()
        )

        # Whole run, not just the action that gave it away. The wire is the
        # symptom and it is usually last, so scoping to its blast radius
        # reverses nothing at all: everything it depends on came before it.
        # When the fleet has been acting on manipulated input, the manipulated
        # input is upstream of all of it.
        plan = await self.regret.plan(run_id=run_id)
        outcome = await self.regret.execute(plan, verifier=verifier)

        if self.herald is not None:
            outcome["disclosures"] = [
                await self.herald.disclose(r)
                for r in await self.regret.unrecoverable_records(plan)
            ]

        outcome["triggered"] = True
        outcome["triggered_by"] = "sentinel"
        outcome["score"] = assessment.score
        outcome["signals"] = [
            {"name": s.name, "weight": s.weight, "detail": s.detail}
            for s in assessment.signals
        ]
        outcome["rationale"] = assessment.rationale
        outcome["run_id"] = run_id
        return outcome
