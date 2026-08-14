"""Tests for the parts that would hurt most if they were wrong.

Ordering and the T3 path. Everything else is plumbing.
"""

from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "src")

from palinode.agents.regret import RegretAgent  # noqa: E402
from palinode.agents.verifier import Verifier  # noqa: E402
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


# ---------------------------------------------------------------- sentinel


async def _seeded_run(run: str, beneficiary: str):
    """A run shaped like the poisoned invoice: ordinary chain, odd tail."""
    from palinode.types import CompensationContract

    a = await _record(
        run, "db_write", Tier.T0_REVERSIBLE,
        CompensationContract(tool="db_restore", args={"table": "t", "key": "k"}),
    )
    b = await _record(
        run, "stripe_charge", Tier.T1_COMPENSABLE,
        CompensationContract(tool="stripe_refund", args={"charge_id": "ch_1"}),
        parent=a.id,
    )
    rec = await _record(
        run, "wire_transfer", Tier.T3_UNRECOVERABLE,
        CompensationContract(tool="", estimated_exposure_usd=4200.0),
        parent=b.id,
    )
    rec.args = {"beneficiary": beneficiary, "amount_usd": 4200.0}
    # Matches what the Warden records in production. A T3 that has run is
    # unrecoverable, not merely executed.
    rec.state = ActionState.UNRECOVERABLE
    b.args = {"customer": "cus_northwind", "amount_usd": 1180.0}
    return rec


@pytest.mark.asyncio
async def test_sentinel_reverses_without_being_asked():
    from palinode.agents.sentinel import Sentinel

    await _seeded_run("s1", "acct-unknown-77")

    regret = RegretAgent(run_tool=run_tool)
    sentinel = Sentinel(regret=regret)
    sentinel.known_counterparties = {"cus_northwind"}

    outcome = await sentinel.watch("s1")
    assert outcome["triggered"] is True
    assert outcome["triggered_by"] == "sentinel"
    assert outcome["exposure_usd"] == 4200.0

    # The wire is the symptom and it is last, so scoping the reversal to its
    # blast radius would quietly reverse nothing. Everything reversible in the
    # run has to come back.
    assert len(outcome["reversed"]) == 2, outcome
    states = {r.tool: r.state for r in await get_ledger().by_run("s1")}
    assert states["db_write"] is ActionState.REVERSED
    assert states["stripe_charge"] is ActionState.COMPENSATED
    assert states["wire_transfer"] is ActionState.UNRECOVERABLE


@pytest.mark.asyncio
async def test_sentinel_leaves_a_normal_run_alone():
    """A known counterparty at a normal size is a Tuesday, not an incident."""
    from palinode.agents.sentinel import Sentinel

    rec = await _seeded_run("s2", "cus_northwind")
    rec.args["amount_usd"] = 1200.0
    rec.contract.tool = "wire_recall"

    sentinel = Sentinel(regret=RegretAgent(run_tool=run_tool))
    sentinel.known_counterparties = {"cus_northwind"}

    assessment = await sentinel.assess("s2")
    assert not assessment.should_reverse


@pytest.mark.asyncio
async def test_sentinel_survives_losing_gemini():
    """Static signals have to stand on their own when the model is gone."""
    from palinode.agents.sentinel import Sentinel

    await _seeded_run("s3", "acct-unknown-77")
    sentinel = Sentinel(regret=RegretAgent(run_tool=run_tool))
    sentinel.known_counterparties = {"cus_northwind"}

    assessment = await sentinel.assess("s3")
    assert assessment.should_reverse
    assert all(s.name != "model_review" for s in assessment.signals)


# --------------------------------------------------------------- telemetry


def test_spans_carry_the_decision(monkeypatch):
    """A span with no attributes is a span nobody can audit from."""
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    import palinode.telemetry as tel

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(tel, "_tracer", provider.get_tracer("test"))
    monkeypatch.setattr(tel, "_enabled", True)

    with tel.span("palinode.test", tier="T3") as current:
        tel.annotate(current, verdict="escalate")

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].attributes["palinode.tier"] == "T3"
    assert spans[0].attributes["palinode.verdict"] == "escalate"


def test_telemetry_is_optional():
    """Losing the sdk must not take the system with it."""
    import palinode.telemetry as tel

    saved_tracer, saved_enabled = tel._tracer, tel._enabled
    tel._tracer, tel._enabled = None, False
    try:
        with tel.span("palinode.test", tier="T0") as current:
            assert current is None
            tel.annotate(current, verdict="allow")
    finally:
        tel._tracer, tel._enabled = saved_tracer, saved_enabled


@pytest.mark.asyncio
async def test_ledger_survives_firestore_falling_over():
    """A 403 mid incident must not turn into a 500 on the recovery tool."""
    from palinode.ledger.store import LedgerStore

    class Exploding:
        def collection(self, _):
            raise RuntimeError("403 Missing or insufficient permissions")

    store = LedgerStore()
    store._client = Exploding()

    record = ActionRecord(
        run_id="f1", agent="test", tool="db_write", tier=Tier.T0_REVERSIBLE
    )
    assert await store.append(record) is record
    assert store._client is None          # demoted, not retried forever
    assert (await store.get(record.id)) is record   # memory copy still correct


@pytest.mark.asyncio
async def test_reset_actually_clears_the_run():
    """Replaying the demo twice must not read back both runs."""
    await _record("r9", "db_write", Tier.T0_REVERSIBLE)
    await _record("r9", "slack_post", Tier.T2_SOCIAL)
    assert len(await get_ledger().by_run("r9")) == 2

    await get_ledger().clear_run("r9")
    assert await get_ledger().by_run("r9") == []


@pytest.mark.asyncio
async def test_outcomes_outlive_the_request():
    """Cloud Run has more than one container. A module global does not travel."""
    ledger = get_ledger()
    await ledger.save_outcome("r10", {"run_id": "r10", "exposure_usd": 4200.0})
    assert (await ledger.get_outcome("r10"))["exposure_usd"] == 4200.0
    await ledger.clear_outcome("r10")
    assert await ledger.get_outcome("r10") is None


# --------------------------------------------------------------- cold case


@pytest.mark.asyncio
async def test_a_three_week_old_action_still_reverses():
    """Contracts are written to outlive the session that wrote them."""
    from palinode.scenarios import cold_case

    await cold_case.reset()
    seeded = await cold_case.run()
    assert seeded["oldest_action_age_days"] >= 22

    plan = await RegretAgent(run_tool=run_tool).plan(run_id=cold_case.RUN_ID)
    outcome = await RegretAgent(run_tool=run_tool).execute(
        plan, verifier=Verifier(run_tool=run_tool)
    )

    assert outcome["failed"] == []
    assert len(outcome["reversed"]) == 4

    states = {r.tool: r.state for r in await get_ledger().by_run(cold_case.RUN_ID)}
    assert states["db_write"] is ActionState.REVERSED
    assert states["stripe_charge"] is ActionState.COMPENSATED

    # The refund has to have actually moved, not just been reported.
    from palinode.connectors.base import WORLD
    assert WORLD["charges"]["ch_cold_1"]["refunded"] == 8400.00


@pytest.mark.asyncio
async def test_cold_case_reverses_newest_first_across_weeks():
    """Ordering has to hold when every timestamp is old, not just recent ones."""
    from palinode.scenarios import cold_case

    await cold_case.reset()
    await cold_case.run()

    plan = await RegretAgent(run_tool=run_tool).plan(run_id=cold_case.RUN_ID)
    tools = [s.tool for s in plan.steps]
    assert tools == ["stripe_refund", "email_retract", "github_revert", "db_restore"]


# ---------------------------------------------------------------- identity


def test_workload_id_is_spiffe_shaped():
    from palinode.identity import workload_id

    assert (
        workload_id("proj-1", "finance", "payables")
        == "spiffe://palinode/proj-1/finance/payables"
    )


@pytest.mark.asyncio
async def test_the_chain_catches_an_edited_action():
    """An id on a record means nothing if the record can be edited after."""
    from palinode.identity import verify_chain

    ledger = get_ledger()
    a = await _record("c1", "db_write", Tier.T0_REVERSIBLE)
    await _record("c1", "stripe_charge", Tier.T1_COMPENSABLE, parent=a.id)
    await _record("c1", "wire_transfer", Tier.T3_UNRECOVERABLE)

    assert (await ledger.verify("c1")).intact

    # Someone quietly changes where the money went.
    a.args = {"beneficiary": "somewhere-else"}
    report = await ledger.verify("c1")
    assert not report.intact
    assert report.broken_at == a.id
    assert "changed after it was written" in report.reason


@pytest.mark.asyncio
async def test_the_chain_catches_a_removed_action():
    ledger = get_ledger()
    a = await _record("c2", "db_write", Tier.T0_REVERSIBLE)
    b = await _record("c2", "email_send", Tier.T2_SOCIAL, parent=a.id)
    await _record("c2", "wire_transfer", Tier.T3_UNRECOVERABLE, parent=b.id)
    assert (await ledger.verify("c2")).intact

    # Delete the middle entry and the trail should not read clean.
    ledger._mem.pop(b.id)
    report = await ledger.verify("c2")
    assert not report.intact
    assert "removed or reordered" in report.reason


def test_registry_versions_on_changed_grants():
    registry = get_registry()
    first = registry.register(AgentCard(name="v", owner="t", tools={"db_write"}))
    assert first.version == 1

    same = registry.register(AgentCard(name="v", owner="t", tools={"db_write"}))
    assert same.version == 1, "re-registering an unchanged agent is not a new version"

    wider = registry.register(
        AgentCard(name="v", owner="t", tools={"db_write", "wire_transfer"})
    )
    assert wider.version == 2
    assert len(registry.history("v")) == 2


@pytest.mark.asyncio
async def test_the_scenario_never_edits_a_written_entry():
    """The chain is only worth having if the happy path does not break it.

    This caught a real defect: the charge id was written back into the
    compensation contract after the action had already been recorded, which is
    the exact mutation an append only ledger exists to prevent.
    """
    from palinode.scenarios import poisoned_invoice

    await poisoned_invoice.reset()
    run_id = await poisoned_invoice.run()

    report = await get_ledger().verify(run_id)
    assert report.intact, report.reason
    assert report.length == 5
