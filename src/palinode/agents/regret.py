"""Regret. Plans and runs the reversal.

Nothing in here asks a human for permission. That is the whole proposition: by
the time somebody notices an agent has gone wrong, the useful window has
usually closed, so the recovery has to be able to start without them.

The plan is built from contracts that already exist. Regret does not invent a
way to undo anything, it reads what was written down when the action was
authorised and puts those in the right order. Ordering is where the judgement
is, and getting it backwards is how you refund an invoice that has already been
cancelled and end up owing money twice.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable, Optional

from ..ledger.store import get_ledger
from ..types import (
    ActionRecord,
    ActionState,
    ReversalPlan,
    ReversalStep,
    Tier,
)

log = logging.getLogger("palinode.regret")

ToolRunner = Callable[[str, dict], Awaitable[dict]]


class RegretAgent:
    def __init__(self, run_tool: ToolRunner) -> None:
        self.ledger = get_ledger()
        self.run_tool = run_tool

    # ------------------------------------------------------------- planning

    async def plan(self, *, run_id: str, from_action: Optional[str] = None) -> ReversalPlan:
        """Build a reversal for a whole run, or for one action and its fallout."""
        if from_action:
            scope = await self.ledger.blast_radius(from_action)
        else:
            scope = await self.ledger.by_run(run_id)

        touched = [
            r
            for r in scope
            if r.state in (ActionState.EXECUTED, ActionState.UNRECOVERABLE, ActionState.HELD)
        ]
        ordered = await self.ledger.reverse_order(touched)

        plan = ReversalPlan(run_id=run_id)
        previous: Optional[str] = None

        for record in ordered:
            if record.tier is Tier.T3_UNRECOVERABLE:
                plan.unrecoverable.append(record.id)
                plan.exposure_usd += record.cost()
                continue

            if record.contract is None:
                # Should not happen, the Warden refuses these. If it does, the
                # honest move is to treat it as unrecoverable rather than guess.
                log.error("action %s has no contract, cannot reverse", record.id)
                plan.unrecoverable.append(record.id)
                continue

            step = ReversalStep(
                action_id=record.id,
                tool=record.contract.tool,
                args={**record.contract.args, **record.contract.snapshot},
                verify=record.contract.verify,
                depends_on=[previous] if previous else [],
            )
            plan.steps.append(step)
            previous = record.id

        log.info("planned reversal for %s: %s", run_id, plan.summary())
        return plan

    # ------------------------------------------------------------ execution

    async def execute(self, plan: ReversalPlan, verifier=None) -> dict:
        """Run the plan in order, verifying as it goes.

        Sequential on purpose for now. Parallelising steps that share no
        dependency is an easy win on paper and a good way to double refund a
        customer in practice, so it waits until the dependency graph is
        inferred rather than declared.
        """
        reversed_ids: list[str] = []
        failed: list[dict] = []

        for step in plan.steps:
            try:
                result = await self.run_tool(step.tool, step.args)
            except Exception as exc:  # noqa: BLE001
                log.exception("reversal step failed for %s", step.action_id)
                await self.ledger.advance(step.action_id, ActionState.FAILED, error=str(exc))
                failed.append({"action_id": step.action_id, "error": str(exc)})
                continue

            confirmed = True
            if verifier is not None and step.verify:
                confirmed = await verifier.confirm(step, result)

            if confirmed:
                record = await self.ledger.get(step.action_id)
                state = (
                    ActionState.REVERSED
                    if record and record.tier is Tier.T0_REVERSIBLE
                    else ActionState.COMPENSATED
                )
                await self.ledger.advance(step.action_id, state, result=result)
                reversed_ids.append(step.action_id)
            else:
                await self.ledger.advance(
                    step.action_id,
                    ActionState.FAILED,
                    error="compensation did not verify",
                )
                failed.append({"action_id": step.action_id, "error": "verification failed"})

        return {
            "run_id": plan.run_id,
            "reversed": reversed_ids,
            "failed": failed,
            "unrecoverable": plan.unrecoverable,
            "exposure_usd": round(plan.exposure_usd, 2),
        }

    async def unrecoverable_records(self, plan: ReversalPlan) -> list[ActionRecord]:
        records = [await self.ledger.get(aid) for aid in plan.unrecoverable]
        return [r for r in records if r is not None]
