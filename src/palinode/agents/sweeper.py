"""Sweeper. Reassesses history against what has been learned since.

Sentinel decides in the moment, and in the moment the only alarming shape is an
irreversible action where there should not be one. That is the poisoned
invoice, and it is caught in about twenty seconds.

The other case is slower and more common. Every action was ordinary. Nothing
was irreversible. Nobody was alarmed, correctly, because at the time there was
nothing to be alarmed about. Then three weeks later the vendor turns out to be
fraudulent, and somebody has to unwind every action ever taken on their behalf
without a list of what those actions were.

Nothing about that run changed. What changed is what we know.

So the Sweeper runs on a schedule with no request in flight and nobody waiting,
walks the runs that were never taken back, and scores each one again against
the intel store. A run that was fine when it happened and is not fine now gets
reversed, and the first anyone hears about it is the disclosure.

This is the part of Palinode that is genuinely long running. Everything else
finishes inside the request that started it.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..telemetry import annotate, span
from ..types import ActionState, Tier

log = logging.getLogger("palinode.sweeper")

# How far back a sweep looks. Far enough for a vendor to be found out, short
# enough that the job stays cheap when it finds nothing, which is most days.
DEFAULT_WINDOW_DAYS = 45


class Sweeper:
    """Walks open runs and hands the ones that now look wrong to Sentinel."""

    def __init__(self, sentinel, ledger, verifier=None) -> None:
        self.sentinel = sentinel
        self.ledger = ledger
        self.verifier = verifier
        # Who this sweep is, for the claim it takes on each run. The
        # revision is in the environment on Cloud Run and the suffix
        # separates two containers of the same revision, which is exactly
        # the case that bit us.
        self.holder = f"{os.getenv('K_REVISION', 'local')}/{uuid.uuid4().hex[:8]}"

    async def release(self, run_tool=None) -> list[dict]:
        """Let go of anything whose cooling off window has passed.

        The Warden holds T2 and T3 actions briefly so there is a window in
        which somebody, or Sentinel, can catch them before they land. Until
        now nothing ever ended that window, which made the hold a one way
        door: an action went in and only a reversal took it out.

        This is the other side of it. If the window closed and nobody
        objected, the action proceeds, and the ledger says so.
        """
        released = []
        for record in await self.ledger.due():
            result = None
            if run_tool is not None:
                try:
                    result = await run_tool(record.tool, record.args)
                except Exception as exc:  # noqa: BLE001
                    log.error("release of %s failed: %s", record.id, exc)
                    await self.ledger.advance(
                        record.id, ActionState.FAILED, error=str(exc)[:160]
                    )
                    continue

            state = (
                ActionState.UNRECOVERABLE
                if record.tier is Tier.T3_UNRECOVERABLE
                else ActionState.EXECUTED
            )
            await self.ledger.advance(record.id, state, result=result)
            released.append({"action_id": record.id, "tool": record.tool, "state": state.value})
            log.info("released %s after its cooling off window", record.id)

        return released

    async def sweep(
        self,
        *,
        days: int = DEFAULT_WINDOW_DAYS,
        limit: int = 50,
        act: bool = True,
    ) -> dict:
        """Score every open run in the window. Reverse the ones that now clear.

        act=False makes this a dry run, which is what you want the first time
        you point it at a ledger that has real history in it.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)

        with span("palinode.sweeper.sweep", window_days=days, acting=act) as sweep:
            runs = (await self.ledger.open_runs(since))[:limit]

            examined: list[dict] = []
            reversed_runs: list[dict] = []

            for run_id in runs:
                # No model call here. A scheduled job that walks fifty runs and
                # asks Gemini about each one costs fifty inferences to answer a
                # question the intel store already answers, and the signal this
                # exists for is a fact rather than a judgement.
                assessment = await self.sentinel.assess(run_id, use_model=False)
                entry = {
                    "run_id": run_id,
                    "score": assessment.score,
                    "signals": [s.name for s in assessment.signals],
                    "rationale": assessment.rationale,
                }
                examined.append(entry)

                if not assessment.should_reverse:
                    continue

                log.warning(
                    "sweep reversing %s, nobody asked and nobody is waiting: %s",
                    run_id,
                    assessment.summary(),
                )
                if not act:
                    entry["would_reverse"] = True
                    continue

                # Cloud Scheduler delivers at least once and Cloud Run answers
                # from more than one container. Two sweeps found this same run
                # in the same second once, and the second revert came back 422
                # from GitHub because the ref had already moved. Stripe would
                # not have complained. It would have refunded twice.
                if not await self.ledger.claim(run_id, self.holder):
                    log.info("%s is already being handled by another sweep", run_id)
                    entry["claimed_elsewhere"] = True
                    continue

                try:
                    outcome = await self.sentinel.watch(run_id, verifier=self.verifier)
                    outcome["found_by"] = "sweeper"
                    reversed_runs.append(outcome)
                finally:
                    await self.ledger.release(run_id)

            annotate(
                sweep,
                examined=len(examined),
                reversed=len(reversed_runs),
            )

        log.info(
            "sweep looked at %d run(s) in the last %d days, reversed %d",
            len(examined), days, len(reversed_runs),
        )
        return {
            "window_days": days,
            "examined": examined,
            "reversed": reversed_runs,
            "acted": act,
        }
