"""The scenario both the terminal walkthrough and the dashboard run.

A procurement fleet processes an invoice. The invoice is poisoned, so the last
action pays an attacker instead of the vendor. Five actions land, four of them
come back, one does not.

Kept in one place so the demo and the control plane cannot drift apart, which
they would, and always at the worst possible moment.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from ..connectors.base import reset_world, run_tool
from ..ledger.store import get_ledger
from ..types import ActionState, CompensationContract, Tier
from ..warden.interceptor import get_warden
from ..warden.registry import AgentCard, RuntimeMode, get_registry

RUN_ID = "run_poisoned_invoice"


def setup_fleet() -> None:
    registry = get_registry()
    for card in (
        AgentCard(
            name="sourcing",
            owner="procurement",
            description="approves vendors and announces them",
            tools={"db_write", "slack_post", "email_send"},
        ),
        AgentCard(
            name="invoice",
            owner="procurement",
            description="matches invoices to purchase orders",
            tools={"db_write", "github_merge", "email_send"},
        ),
        AgentCard(
            name="payables",
            owner="finance",
            description="settles approved invoices",
            tools={"stripe_charge", "wire_transfer", "email_send"},
            budget_usd_per_hour=5000,
        ),
    ):
        existing = registry.get(card.name)
        if existing is None:
            registry.register(card)
        else:
            # A rerun should not silently inherit a downgrade from last time.
            existing.mode = RuntimeMode.AUTONOMOUS


async def _act(
    agent: str,
    tool: str,
    args: dict,
    contract: Optional[CompensationContract],
    parent: Optional[str],
) -> Optional[str]:
    warden = get_warden()
    ledger = get_ledger()

    decision, record = await warden.evaluate(
        agent=agent, tool=tool, args=args, contract=contract
    )
    if not decision.allowed or record is None:
        return None

    record.run_id = RUN_ID
    if parent:
        record.caused_by = [parent]
    await ledger.append(record)

    result = await run_tool(tool, args)
    record.executed_at = datetime.now(timezone.utc)
    state = (
        ActionState.UNRECOVERABLE
        if record.tier is Tier.T3_UNRECOVERABLE
        else ActionState.EXECUTED
    )
    await ledger.advance(record.id, state, result=result)
    return record.id


async def screen(invoice_key: str = "quiet") -> dict:
    """Run the invoice past Model Armor before the fleet ever sees it.

    Returns the verdict. A caught invoice never reaches an agent, which is the
    correct outcome and the cheapest one. The interesting case is the invoice
    that passes.
    """
    from ..warden.armor import get_armor
    from .invoices import INVOICES

    invoice = INVOICES.get(invoice_key, INVOICES["quiet"])
    verdict = await get_armor().screen(invoice.text)

    return {
        "invoice": invoice.key,
        "label": invoice.label,
        "note": invoice.note,
        "armor": verdict.as_dict(),
        "blocked": verdict.blocked,
        "describe": verdict.describe(),
    }


async def run() -> str:
    """Play the scenario forward. Returns the run id."""
    setup_fleet()

    last = await _act(
        "sourcing",
        "db_write",
        {"table": "vendors", "key": "v-8842", "value": {"status": "approved"}},
        CompensationContract(tool="db_restore", args={"table": "vendors", "key": "v-8842"}),
        None,
    )
    last = await _act(
        "sourcing",
        "slack_post",
        {"channel": "#procurement", "text": "Vendor v-8842 approved, invoice clearing now."},
        CompensationContract(tool="slack_delete", args={"channel": "#procurement"}),
        last,
    )
    last = await _act(
        "invoice",
        "email_send",
        {"to": "ap@northwind.example", "subject": "Invoice 4821 approved", "body": "..."},
        CompensationContract(
            tool="email_retract",
            args={"to": "ap@northwind.example", "original_subject": "Invoice 4821 approved"},
        ),
        last,
    )
    # The agent names the charge before making it, so the contract can point at
    # it up front. Waiting for the id and patching the contract afterwards
    # meant editing a ledger entry that had already been written, which is
    # exactly what an append only ledger is supposed to make impossible.
    # Named after the invoice, not the run. Deriving it from RUN_ID put the
    # word "poisoned" in the idempotency key, and Sentinel's model review
    # promptly cited that as evidence. Handing the detector the answer in the
    # data it is meant to judge is not detection.
    charge_key = "ch_inv4821_northwind"
    charge = await _act(
        "payables",
        "stripe_charge",
        {
            "customer": "cus_northwind",
            "amount_usd": 1180.00,
            "idempotency_key": charge_key,
        },
        CompensationContract(
            tool="stripe_refund",
            args={"charge_id": charge_key, "amount_usd": 1180.00},
            verify="stripe_confirm_refund",
        ),
        last,
    )

    await _act(
        "payables",
        "wire_transfer",
        {"beneficiary": "acct-unknown-77", "amount_usd": 4200.00},
        CompensationContract(
            tool="",
            disclosure_required=True,
            affected_parties=["ap@northwind.example"],
            estimated_exposure_usd=4200.00,
        ),
        charge,
    )

    return RUN_ID


async def reset() -> None:
    """Wipe the world and the run so the scenario can be played again.

    Clearing the in memory copy is not enough once Firestore is behind the
    ledger. The previous run is still there, and the next read returns ten
    actions instead of five.
    """
    reset_world()
    ledger = get_ledger()
    await ledger.clear_run(RUN_ID)
    await ledger.clear_outcome(RUN_ID)
