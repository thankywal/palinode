"""End to end scenario: a procurement fleet acts on a poisoned invoice.

Runs with no credentials and no cloud project. The ledger falls back to memory
and the connectors run against an in memory world, so this is the fastest way
to see the whole loop.

    python demo.py

What it shows, in order: three agents do five real things, one of which should
never have happened, and then Regret takes it all back except the part that
cannot be taken back.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone

sys.path.insert(0, "src")

# Warnings are useful in the api, they are noise in a scripted walkthrough.
logging.basicConfig(level=logging.ERROR, format="%(message)s")

from palinode.agents.herald import get_herald  # noqa: E402
from palinode.agents.regret import RegretAgent  # noqa: E402
from palinode.agents.verifier import Verifier  # noqa: E402
from palinode.connectors.base import WORLD, run_tool  # noqa: E402
from palinode.ledger.store import get_ledger  # noqa: E402
from palinode.types import ActionState, CompensationContract, Tier  # noqa: E402
from palinode.warden.interceptor import get_warden  # noqa: E402
from palinode.warden.registry import AgentCard, get_registry  # noqa: E402

RUN = "run_poisoned_invoice"

GREEN = "\033[32m"
AMBER = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"
OFF = "\033[0m"


def line(colour: str, mark: str, text: str) -> None:
    print(f"  {colour}{mark}{OFF} {text}")


async def act(agent: str, tool: str, args: dict, contract: CompensationContract | None):
    """One supervised action. This is what the ADK callback does for real."""
    warden = get_warden()
    ledger = get_ledger()

    decision, record = await warden.evaluate(
        agent=agent, tool=tool, args=args, contract=contract
    )
    if not decision.allowed:
        line(RED, "x", f"{agent} blocked on {tool}: {decision.reason}")
        return None

    assert record is not None
    record.run_id = RUN
    previous = getattr(act, "_last", None)
    if previous:
        record.caused_by = [previous]
    await ledger.append(record)
    act._last = record.id  # type: ignore[attr-defined]

    result = await run_tool(tool, args)
    record.executed_at = datetime.now(timezone.utc)
    state = (
        ActionState.UNRECOVERABLE
        if record.tier is Tier.T3_UNRECOVERABLE
        else ActionState.EXECUTED
    )
    await ledger.advance(record.id, state, result=result)

    held = f" {DIM}held {decision.hold_seconds}s{OFF}" if decision.hold_seconds else ""
    line(DIM, "-", f"{agent} {tool} {DIM}[{record.tier.value}]{OFF}{held}")
    return record.id


def setup_fleet() -> None:
    registry = get_registry()
    registry.register(
        AgentCard(
            name="sourcing",
            owner="procurement",
            tools={"db_write", "slack_post", "email_send"},
        )
    )
    registry.register(
        AgentCard(
            name="invoice",
            owner="procurement",
            tools={"db_write", "github_merge", "email_send"},
        )
    )
    registry.register(
        AgentCard(
            name="payables",
            owner="finance",
            tools={"stripe_charge", "wire_transfer", "email_send"},
            budget_usd_per_hour=5000,
        )
    )


async def main() -> None:
    setup_fleet()

    print(f"\n{DIM}the fleet does its job{OFF}\n")

    await act(
        "sourcing",
        "db_write",
        {"table": "vendors", "key": "v-8842", "value": {"status": "approved"}},
        CompensationContract(tool="db_restore", args={"table": "vendors", "key": "v-8842"}),
    )
    await act(
        "sourcing",
        "slack_post",
        {"channel": "#procurement", "text": "Vendor v-8842 approved, invoice clearing now."},
        CompensationContract(tool="slack_delete", args={"channel": "#procurement"}),
    )
    await act(
        "invoice",
        "email_send",
        {"to": "ap@northwind.example", "subject": "Invoice 4821 approved", "body": "..."},
        CompensationContract(
            tool="email_retract",
            args={"to": "ap@northwind.example", "original_subject": "Invoice 4821 approved"},
        ),
    )
    charge = await act(
        "payables",
        "stripe_charge",
        {"customer": "cus_northwind", "amount_usd": 1180.00},
        CompensationContract(
            tool="stripe_refund",
            args={"amount_usd": 1180.00},
            verify="stripe_confirm_refund",
        ),
    )
    # The contract carries the charge id the refund will need. In the ADK path
    # the Warden captures this from the tool response instead.
    ledger = get_ledger()
    record = await ledger.get(charge) if charge else None
    if record and record.contract:
        record.contract.args["charge_id"] = (record.result or {}).get("charge_id")

    await act(
        "payables",
        "wire_transfer",
        {"beneficiary": "acct-unknown-77", "amount_usd": 4200.00},
        CompensationContract(
            tool="",
            disclosure_required=True,
            affected_parties=["ap@northwind.example"],
            estimated_exposure_usd=4200.00,
        ),
    )

    print(f"\n{RED}the invoice was poisoned. the beneficiary is not the vendor.{OFF}\n")
    print(f"{DIM}palinode undo {RUN}{OFF}\n")

    regret = RegretAgent(run_tool=run_tool)
    plan = await regret.plan(run_id=RUN)
    outcome = await regret.execute(plan, verifier=Verifier(run_tool=run_tool))

    for action_id in outcome["reversed"]:
        rec = await ledger.get(action_id)
        assert rec is not None
        colour = GREEN if rec.state is ActionState.REVERSED else AMBER
        word = "reversed" if rec.state is ActionState.REVERSED else "compensated"
        line(colour, "v", f"{rec.tool} {DIM}[{rec.tier.value}]{OFF} {word}")

    herald = get_herald()
    for rec in await regret.unrecoverable_records(plan):
        line(RED, "!", f"{rec.tool} {DIM}[{rec.tier.value}]{OFF} cannot be reversed")
        report = await herald.disclose(rec)
        print(f"\n{DIM}    disclosure drafted for {report['affected_parties']}{OFF}")

    print(f"\n{DIM}{'-' * 58}{OFF}")
    print(f"  reversed or compensated  {len(outcome['reversed'])}")
    print(f"  {RED}unrecoverable{OFF}            {len(outcome['unrecoverable'])}")
    print(f"  {RED}exposure{OFF}                 ${outcome['exposure_usd']:,.2f}")
    print(f"{DIM}{'-' * 58}{OFF}")
    print(f"\n{DIM}world state: {sum(len(v) for v in WORLD.values())} objects touched{OFF}\n")


if __name__ == "__main__":
    asyncio.run(main())
