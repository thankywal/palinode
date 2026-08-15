"""Tests for the part that decides weeks later.

Sentinel reads the shape of a run while it is happening, so everything it looks
at is a heuristic about shape. The Sweeper reads history against a fact that
arrived afterwards, and the run it is meant to catch has no odd shape at all.
That distinction is what these tests hold in place, because the easy mistake is
to let the new signal inherit the old one's scoping and quietly never fire.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, "src")

from palinode.agents.regret import RegretAgent  # noqa: E402
from palinode.agents.sentinel import Sentinel  # noqa: E402
from palinode.agents.sweeper import Sweeper  # noqa: E402
from palinode.connectors.base import reset_world, run_tool  # noqa: E402
from palinode.intel import get_intel, reset_intel  # noqa: E402
from palinode.ledger.store import get_ledger  # noqa: E402
from palinode.types import (  # noqa: E402
    ActionRecord,
    ActionState,
    CompensationContract,
    Tier,
)


@pytest.fixture(autouse=True)
def clean():
    reset_world()
    reset_intel()
    ledger = get_ledger()
    ledger._mem.clear()
    ledger._outcomes.clear()
    ledger._tips.clear()
    # Claims outlive a run on purpose, so the fixture has to drop them or one
    # test leaves the next one locked out of a run id they happen to share.
    ledger._claims.clear()
    yield


async def _quiet_run(run: str, party: str, days_ago: int = 23):
    """A run with nothing wrong with it.

    Reversible and compensable actions only, an ordinary counterparty, and
    dated back so it is the sort of thing a sweep would find rather than the
    sort a request would. Sentinel should score this at zero.
    """
    ledger = get_ledger()
    when = datetime.now(timezone.utc) - timedelta(days=days_ago)

    charged = await run_tool(
        "stripe_charge", {"customer": party, "amount_usd": 8400.0}
    )
    first = ActionRecord(
        run_id=run,
        agent="renewals",
        tool="db_write",
        args={"table": "vendors", "key": "v-3310"},
        tier=Tier.T0_REVERSIBLE,
        state=ActionState.EXECUTED,
        contract=CompensationContract(
            tool="db_restore", args={"table": "vendors", "key": "v-3310"}
        ),
        created_at=when,
    )
    await ledger.append(first)

    second = ActionRecord(
        run_id=run,
        agent="renewals",
        tool="stripe_charge",
        args={"customer": party, "amount_usd": 8400.0},
        tier=Tier.T1_COMPENSABLE,
        state=ActionState.EXECUTED,
        contract=CompensationContract(
            tool="stripe_refund", args={"charge_id": charged["charge_id"]}
        ),
        caused_by=[first.id],
        created_at=when,
    )
    await ledger.append(second)
    return first, second


def _sweeper():
    sentinel = Sentinel(regret=RegretAgent(run_tool=run_tool))
    sentinel.known_counterparties = {"cus_meridian"}
    return Sweeper(sentinel=sentinel, ledger=get_ledger()), sentinel


@pytest.mark.asyncio
async def test_a_quiet_run_scores_nothing_at_the_time():
    """The premise. If this run looked wrong, the Sweeper would be pointless."""
    await _quiet_run("r_quiet", "cus_meridian")
    _, sentinel = _sweeper()

    assessment = await sentinel.assess("r_quiet", use_model=False)
    assert assessment.score == 0.0
    assert not assessment.should_reverse


@pytest.mark.asyncio
async def test_intel_arriving_later_makes_the_same_run_reversible():
    """Nothing about the run changed. What changed is what we know."""
    await _quiet_run("r_quiet", "cus_meridian")
    _, sentinel = _sweeper()

    await get_intel().flag("cus_meridian", source="acquiring bank")

    assessment = await sentinel.assess("r_quiet", use_model=False)
    assert assessment.should_reverse
    assert "flagged_beneficiary" in [s.name for s in assessment.signals]


@pytest.mark.asyncio
async def test_the_flag_is_not_scoped_to_irreversible_actions():
    """The regression this file exists for.

    Every other signal only looks at T3 actions, because in the moment an
    irreversible action is the only alarming thing. Inheriting that scoping
    here would mean the signal never fires on exactly the run it was written
    for, which has no T3 action anywhere in it.
    """
    _, second = await _quiet_run("r_quiet", "cus_meridian")
    assert second.tier is Tier.T1_COMPENSABLE

    _, sentinel = _sweeper()
    await get_intel().flag("cus_meridian", source="acquiring bank")

    signals, trigger = await sentinel._flagged_signals(
        await get_ledger().by_run("r_quiet")
    )
    assert [s.name for s in signals] == ["flagged_beneficiary"]
    assert trigger is not None


@pytest.mark.asyncio
async def test_the_sweep_reverses_what_it_finds_and_leaves_the_rest():
    await _quiet_run("r_bad", "cus_meridian")
    await _quiet_run("r_fine", "cus_apex_logistics")

    sweeper, _ = _sweeper()
    await get_intel().flag("cus_meridian", source="acquiring bank")

    result = await sweeper.sweep(days=45)

    assert {e["run_id"] for e in result["examined"]} == {"r_bad", "r_fine"}
    assert [o["run_id"] for o in result["reversed"]] == ["r_bad"]

    ledger = get_ledger()
    settled = await ledger.by_run("r_bad")
    assert all(a.state is not ActionState.EXECUTED for a in settled)

    untouched = await ledger.by_run("r_fine")
    assert all(a.state is ActionState.EXECUTED for a in untouched)


@pytest.mark.asyncio
async def test_a_dry_run_touches_nothing():
    await _quiet_run("r_bad", "cus_meridian")
    sweeper, _ = _sweeper()
    await get_intel().flag("cus_meridian", source="acquiring bank")

    result = await sweeper.sweep(days=45, act=False)

    assert result["reversed"] == []
    assert result["examined"][0]["would_reverse"] is True
    assert all(
        a.state is ActionState.EXECUTED for a in await get_ledger().by_run("r_bad")
    )


@pytest.mark.asyncio
async def test_the_window_excludes_what_is_older_than_it():
    """A sweep that walks the whole ledger every hour gets slower forever."""
    await _quiet_run("r_ancient", "cus_meridian", days_ago=200)
    sweeper, _ = _sweeper()
    await get_intel().flag("cus_meridian", source="acquiring bank")

    result = await sweeper.sweep(days=45)
    assert result["examined"] == []
    assert result["reversed"] == []


@pytest.mark.asyncio
async def test_a_run_already_taken_back_is_not_swept_again():
    """Open means nobody undid it. Reversing twice is its own incident."""
    await _quiet_run("r_bad", "cus_meridian")
    sweeper, _ = _sweeper()
    await get_intel().flag("cus_meridian", source="acquiring bank")

    first = await sweeper.sweep(days=45)
    assert len(first["reversed"]) == 1

    second = await sweeper.sweep(days=45)
    assert second["examined"] == []
    assert second["reversed"] == []


@pytest.mark.asyncio
async def test_two_sweeps_at_once_reverse_the_run_once():
    """The defect the live scheduler found, held down by a test.

    Cloud Scheduler delivers at least once and Cloud Run answers from more than
    one container, so two sweeps saw the same three week old fraud in the same
    second. Both called Regret. GitHub refused the second revert with a 422
    because the ref had moved underneath it, which is the only reason anyone
    noticed. Stripe would not have refused. It would have refunded twice.
    """
    import asyncio

    await _quiet_run("r_bad", "cus_meridian")
    await get_intel().flag("cus_meridian", source="acquiring bank")

    one, _ = _sweeper()
    two, _ = _sweeper()
    assert one.holder != two.holder

    first, second = await asyncio.gather(
        one.sweep(days=45), two.sweep(days=45)
    )

    assert len(first["reversed"]) + len(second["reversed"]) == 1

    # Two things can save us here and either is fine. The loser either got
    # there late enough that the run was no longer open, or it got there in
    # time and the claim turned it away. What must not happen is both of them
    # calling Regret.
    loser = first if not first["reversed"] else second
    assert loser["examined"] == [] or loser["examined"][0].get("claimed_elsewhere")


@pytest.mark.asyncio
async def test_a_claim_is_exclusive_and_expires():
    """The lock itself, without a sweep around it."""
    ledger = get_ledger()
    assert await ledger.claim("r_bad", "container-one") is True
    assert await ledger.claim("r_bad", "container-two") is False

    # A container that died mid reversal must not hold the run forever.
    assert await ledger.claim("r_bad", "container-two", ttl_seconds=0) is True


@pytest.mark.asyncio
async def test_a_claim_is_released_even_when_the_reversal_throws():
    """A sweep that dies holding a claim must not lock the run out forever."""
    await _quiet_run("r_bad", "cus_meridian")
    await get_intel().flag("cus_meridian", source="acquiring bank")

    sweeper, sentinel = _sweeper()

    async def boom(run_id, verifier=None):
        raise RuntimeError("connector fell over")

    sentinel.watch = boom
    with pytest.raises(RuntimeError):
        await sweeper.sweep(days=45)

    # The next sweep, from a different container, can still pick it up.
    other, _ = _sweeper()
    assert await get_ledger().claim("r_bad", other.holder) is True
