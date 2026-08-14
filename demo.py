"""The poisoned invoice, in a terminal.

Runs with no credentials and no cloud project. The ledger falls back to memory
and the connectors run against an in memory world, so this is the fastest way
to see the whole loop.

    python demo.py

Same scenario the dashboard runs, imported from the same module, because two
copies of a demo drift and they drift at the worst possible moment.
"""

from __future__ import annotations

import asyncio
import logging
import sys

sys.path.insert(0, "src")

# Warnings are useful in the api, they are noise in a scripted walkthrough.
logging.basicConfig(level=logging.ERROR, format="%(message)s")

from palinode.agents.herald import get_herald  # noqa: E402
from palinode.agents.regret import RegretAgent  # noqa: E402
from palinode.agents.verifier import Verifier  # noqa: E402
from palinode.connectors.base import run_tool  # noqa: E402
from palinode.ledger.store import get_ledger  # noqa: E402
from palinode.scenarios import poisoned_invoice  # noqa: E402
from palinode.types import ActionState  # noqa: E402

GREEN, AMBER, RED, DIM, OFF = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"


def line(colour: str, mark: str, text: str) -> None:
    print(f"  {colour}{mark}{OFF} {text}")


async def main() -> None:
    ledger = get_ledger()

    print(f"\n{DIM}the fleet does its job{OFF}\n")
    await poisoned_invoice.reset()
    run_id = await poisoned_invoice.run()

    for record in await ledger.by_run(run_id):
        held = f" {DIM}held{OFF}" if record.release_at else ""
        line(DIM, "-", f"{record.agent} {record.tool} {DIM}[{record.tier.value}]{OFF}{held}")

    print(f"\n{RED}the invoice was poisoned. the beneficiary is not the vendor.{OFF}\n")
    print(f"{DIM}palinode undo {run_id}{OFF}\n")

    regret = RegretAgent(run_tool=run_tool)
    plan = await regret.plan(run_id=run_id)
    outcome = await regret.execute(plan, verifier=Verifier(run_tool=run_tool))

    for action_id in outcome["reversed"]:
        record = await ledger.get(action_id)
        assert record is not None
        reversed_cleanly = record.state is ActionState.REVERSED
        line(
            GREEN if reversed_cleanly else AMBER,
            "v",
            f"{record.tool} {DIM}[{record.tier.value}]{OFF} "
            f"{'reversed' if reversed_cleanly else 'compensated'}",
        )

    herald = get_herald()
    for record in await regret.unrecoverable_records(plan):
        line(RED, "!", f"{record.tool} {DIM}[{record.tier.value}]{OFF} cannot be reversed")
        report = await herald.disclose(record)
        print(f"\n{DIM}    disclosure drafted for {report['affected_parties']}{OFF}")

    print(f"\n{DIM}{'-' * 58}{OFF}")
    print(f"  reversed or compensated  {len(outcome['reversed'])}")
    print(f"  {RED}unrecoverable{OFF}            {len(outcome['unrecoverable'])}")
    print(f"  {RED}exposure{OFF}                 ${outcome['exposure_usd']:,.2f}")
    print(f"{DIM}{'-' * 58}{OFF}\n")


if __name__ == "__main__":
    asyncio.run(main())
