"""A reversal of something that happened three weeks ago.

The poisoned invoice demo runs in about a minute, which makes it easy to
believe the ledger is a short lived thing that holds a request together. It is
not. The reason compensation contracts are written at authorisation time is
precisely so they still work later, when the agent that wrote one is gone, the
session it ran in has expired, and nobody remembers what the state was before.

So this seeds a run dated twenty three days ago and reverses it today. Nothing
about the reversal path is different. That is the point: the contract, the
snapshot and the causal edges were all written down at the time, so recovering
from a three week old mistake costs the same as recovering from a three minute
old one.

Where this shows up in practice: a vendor is found to be fraudulent weeks after
the invoices cleared, and somebody has to unwind every action taken on their
behalf without a list of what those actions were.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from ..ledger.store import get_ledger
from ..types import (
    ActionRecord,
    ActionState,
    CompensationContract,
    Tier,
)
from ..warden.registry import AgentCard, RuntimeMode, get_registry

RUN_ID = "run_cold_case"
DAYS_AGO = 23


def _fleet() -> None:
    registry = get_registry()
    card = registry.get("renewals")
    if card is None:
        registry.register(
            AgentCard(
                name="renewals",
                owner="procurement",
                description="processes recurring vendor renewals",
                tools={"db_write", "stripe_charge", "email_send", "github_merge"},
                budget_usd_per_hour=2500,
            )
        )
    else:
        card.mode = RuntimeMode.AUTONOMOUS


async def _aged(
    tool: str,
    args: dict,
    tier: Tier,
    contract: Optional[CompensationContract],
    minutes_into_the_day: int,
    parent: Optional[str],
) -> str:
    """Write a record as though it had been made three weeks ago.

    The Warden is bypassed here on purpose. This is seeding history, not
    replaying it, and pretending otherwise would mean backdating the clock the
    Warden reads.
    """
    when = datetime.now(timezone.utc) - timedelta(days=DAYS_AGO)
    when = when.replace(hour=9, minute=0, second=0, microsecond=0)
    when += timedelta(minutes=minutes_into_the_day)

    card = get_registry().get("renewals")
    record = ActionRecord(
        run_id=RUN_ID,
        agent="renewals",
        actor=card.identity if card else "",
        tool=tool,
        args=args,
        tier=tier,
        tier_reason="classified at the time the action ran",
        contract=contract,
        state=(
            ActionState.UNRECOVERABLE
            if tier is Tier.T3_UNRECOVERABLE
            else ActionState.EXECUTED
        ),
        caused_by=[parent] if parent else [],
    )
    record.created_at = when
    record.executed_at = when + timedelta(seconds=4)

    await get_ledger().append(record)
    return record.id


async def run() -> dict:
    """Seed a renewal run dated three weeks back."""
    _fleet()

    from ..connectors.base import WORLD, run_tool

    WORLD["db"]["vendors:v-3310"] = {"status": "renewed"}
    merge = await run_tool("github_merge", {"repo": "vendor-config", "pr": 214})
    charge = await run_tool(
        "stripe_charge",
        {
            "customer": "cus_meridian",
            "amount_usd": 8400.00,
            "idempotency_key": "ch_renewal3310_meridian",
        },
    )

    last = await _aged(
        "db_write",
        {"table": "vendors", "key": "v-3310", "value": {"status": "renewed"}},
        Tier.T0_REVERSIBLE,
        CompensationContract(
            tool="db_restore",
            args={"table": "vendors", "key": "v-3310"},
            snapshot={"prior": {"status": "under_review"}},
            notes="prior row captured before the write, twenty three days ago",
        ),
        0,
        None,
    )
    last = await _aged(
        "github_merge",
        {"repo": "vendor-config", "pr": 214},
        Tier.T1_COMPENSABLE,
        CompensationContract(
            tool="github_revert",
            args={"repo": "vendor-config", "merge_sha": merge["merge_sha"]},
        ),
        7,
        last,
    )
    last = await _aged(
        "email_send",
        {
            "to": "billing@meridian.example",
            "subject": "Renewal 3310 confirmed",
            "body": "...",
        },
        Tier.T2_SOCIAL,
        CompensationContract(
            tool="email_retract",
            args={
                "to": "billing@meridian.example",
                "original_subject": "Renewal 3310 confirmed",
            },
        ),
        19,
        last,
    )
    charge_action = await _aged(
        "stripe_charge",
        {"customer": "cus_meridian", "amount_usd": 8400.00},
        Tier.T1_COMPENSABLE,
        CompensationContract(
            tool="stripe_refund",
            args={"charge_id": "ch_renewal3310_meridian", "amount_usd": 8400.00},
            verify="stripe_confirm_refund",
        ),
        26,
        last,
    )

    # The world these actions touched has to exist for the compensations to
    # have something to act on. In a real deployment that is the vendor's own
    # systems, still holding state from three weeks ago. Here the artifacts are
    # created now and only the ledger entries are dated back, because a commit
    # cannot be made to have happened in July.
    #
    # This used to seed made up ids straight into the ledger, which worked
    # perfectly until the connectors became real and then failed with Not Found
    # on a sha that had never existed anywhere.
    ledger = get_ledger()
    actions = await ledger.by_run(RUN_ID)
    oldest = min(a.created_at for a in actions)
    age = datetime.now(timezone.utc) - oldest

    return {
        "run_id": RUN_ID,
        "actions": len(actions),
        "oldest_action_age_days": round(age.total_seconds() / 86400, 1),
        "charge_id": charge_action,
        "note": (
            "Every contract here was written twenty three days ago. Nothing "
            "about reversing them today is different."
        ),
    }


async def reset() -> None:
    ledger = get_ledger()
    await ledger.clear_run(RUN_ID)
    await ledger.clear_outcome(RUN_ID)
