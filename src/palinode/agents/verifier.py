"""Verifier.

The least interesting component and the one most likely to save you. Writing a
compensation is easy. Knowing it worked is not. Stripe reports a refund as
succeeded well before the money is anywhere near the customer, and a Postgres
inverse write will happily apply to a row somebody else changed in the meantime.

So a 200 response is treated as a claim, not a fact.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from ..types import ReversalStep

log = logging.getLogger("palinode.verifier")

ToolRunner = Callable[[str, dict], Awaitable[dict]]

ATTEMPTS = 3
BACKOFF_SECONDS = (1, 3, 8)


class Verifier:
    def __init__(self, run_tool: ToolRunner) -> None:
        self.run_tool = run_tool

    async def confirm(self, step: ReversalStep, result: dict) -> bool:
        if not step.verify:
            # No verification tool means we take the API at its word, which is
            # recorded as such rather than dressed up as confirmation.
            log.info("no verifier for %s, accepting reported result", step.action_id)
            return True

        for attempt in range(ATTEMPTS):
            try:
                check = await self.run_tool(step.verify, {**step.args, "result": result})
            except Exception as exc:  # noqa: BLE001
                log.warning("verify attempt %d failed for %s: %s", attempt + 1, step.action_id, exc)
                check = {"confirmed": False}

            if check.get("confirmed"):
                return True

            if attempt < ATTEMPTS - 1:
                await asyncio.sleep(BACKOFF_SECONDS[attempt])

        log.error("could not confirm reversal of %s after %d attempts", step.action_id, ATTEMPTS)
        return False
