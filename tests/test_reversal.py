"""Tests for the parts that would hurt most if they were wrong.

Ordering and the T3 path. Everything else is plumbing.
"""

from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "src")

from palinode.agents.regret import RegretAgent  # noqa: E402
from palinode.connectors.base import WORLD, reset_world, run_tool  # noqa: E402
from palinode.ledger.store import get_ledger  # noqa: E402
from palinode.types import (  # noqa: E402
    ActionRecord,
    ActionState,
    CompensationContract,
    Tier,
)
from palinode.warden.registry import AgentCard, RuntimeMode, get_registry  # noqa: E402


@pytest.fixture(autouse=True)
def clean():
    reset_world()
    ledger = get_ledger()
    ledger._mem.clear()
    yield


async def _record(run: str, tool: str, tier: Tier, contract=None, parent=None):
    ledger = get_ledger()
    rec = ActionRecord(
        run_id=run,
        agent="test",
        tool=tool,
        tier=tier,
        state=ActionState.EXECUTED,
        contract=contract,
        caused_by=[parent] if parent else [],
    )
    await ledger.append(rec)
    return rec


@pytest.mark.asyncio
async def test_reversal_runs_newest_first():
    """Undoing in creation order would compensate an effect before its cause."""
    a = await _record(
        "r1", "db_write", Tier.T0_REVERSIBLE,
        CompensationContract(tool="db_restore", args={"table": "t", "key": "k"}),
    )
    b = await _record(
        "r1", "stripe_charge", Tier.T1_COMPENSABLE,
        CompensationContract(tool="stripe_refund", args={"charge_id": "ch_1"}),
        parent=a.id,
    )

    plan = await RegretAgent(run_tool=run_tool).plan(run_id="r1")
    assert [s.action_id for s in plan.steps] == [b.id, a.id]


@pytest.mark.asyncio
async def test_t3_is_never_planned_as_reversible():
    await _record(
        "r2", "wire_transfer", Tier.T3_UNRECOVERABLE,
        CompensationContract(estimated_exposure_usd=4200.0, tool=""),
    )

    plan = await RegretAgent(run_tool=run_tool).plan(run_id="r2")
    assert plan.steps == []
    assert plan.exposure_usd == 4200.0


@pytest.mark.asyncio
async def test_blast_radius_follows_declared_causality():
    a = await _record("r3", "email_send", Tier.T2_SOCIAL)
    b = await _record("r3", "db_write", Tier.T0_REVERSIBLE, parent=a.id)
    c = await _record("r3", "stripe_charge", Tier.T1_COMPENSABLE, parent=b.id)
    await _record("r3", "slack_post", Tier.T2_SOCIAL)  # unrelated branch

    scope = await get_ledger().blast_radius(a.id)
    assert {r.id for r in scope} == {a.id, b.id, c.id}


@pytest.mark.asyncio
async def test_refund_cannot_exceed_original_charge():
    charged = await run_tool("stripe_charge", {"customer": "c", "amount_usd": 100.0})
    ok = await run_tool("stripe_refund", {"charge_id": charged["charge_id"], "amount_usd": 100.0})
    assert ok["ok"]

    again = await run_tool(
        "stripe_refund", {"charge_id": charged["charge_id"], "amount_usd": 100.0}
    )
    assert not again["ok"]


@pytest.mark.asyncio
async def test_delivered_email_cannot_be_recalled():
    """The demo used to claim otherwise. It was wrong and this stops it."""
    sent = await run_tool(
        "email_send", {"to": "a@b.example", "subject": "s", "body": "b"}
    )
    recall = await run_tool("email_recall", {"message_id": sent["message_id"]})
    assert not recall["ok"]
    assert "smtp" in recall["reason"]


def test_registry_denies_ungranted_tools():
    registry = get_registry()
    card = registry.register(AgentCard(name="narrow", owner="t", tools={"db_write"}))
    assert card.may_use("db_write")
    assert not card.may_use("wire_transfer")


def test_downgrade_is_one_way():
    registry = get_registry()
    registry.register(AgentCard(name="spender", owner="t", tools={"wire_transfer"}))
    registry.downgrade("spender", "budget exhausted")
    assert registry.get("spender").mode is RuntimeMode.PROPOSE_ONLY
    registry.downgrade("spender", "again")
    assert registry.get("spender").mode is RuntimeMode.PROPOSE_ONLY
