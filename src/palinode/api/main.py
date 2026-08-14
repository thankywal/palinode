"""Control plane API and dashboard. This is what runs on Cloud Run.

Small on purpose. The interesting logic belongs to the Warden and to Regret,
and an HTTP layer that starts making decisions of its own is a layer you end up
debugging during an incident.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..agents.herald import get_herald
from ..agents.regret import RegretAgent
from ..agents.sentinel import Sentinel
from ..agents.verifier import Verifier
from ..connectors.base import run_tool
from ..ledger.store import get_ledger
from ..config import settings
from ..scenarios import cold_case, poisoned_invoice
from ..telemetry import configure as configure_tracing
from ..warden.registry import get_registry

# Uvicorn configures the root logger and leaves ours at WARNING, so every
# log.info in this codebase went nowhere. That includes the Stripe charge and
# refund ids, which are the operational record of what the reversal actually
# did, and the first thing anyone would look for in the logs.
logging.getLogger("palinode").setLevel(logging.INFO)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")

app = FastAPI(title="Palinode", version="0.1.0")

# Spans go to Cloud Trace when a project is configured. ADK already traces the
# agent runs and tool calls, so what we add is the part it cannot know: why an
# action got the tier it did and what happened when the reversal ran.
configure_tracing(settings.project)

STATIC = Path(__file__).parent / "static"
if STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

# Reversal outcomes live in the ledger, not in this process. Cloud Run runs
# more than one container and the dashboard has no idea which one it is talking
# to, so a module global here means the disclosure shows up for some viewers
# and not others.


class UndoRequest(BaseModel):
    run_id: str
    from_action: Optional[str] = None
    dry_run: bool = False


@app.get("/")
async def dashboard():
    index = STATIC / "index.html"
    if not index.is_file():
        return {"service": "palinode", "dashboard": "not built"}
    return FileResponse(index)


@app.get("/status")
async def status() -> dict:
    """Liveness.

    Not /healthz. The Google frontend answers that path itself on run.app
    domains and the request never reaches the container, which looks exactly
    like the service being down.
    """
    from ..connectors import stripe_live

    try:
        stripe = "test mode" if stripe_live.enabled() else "simulated"
    except Exception:  # noqa: BLE001
        stripe = "refused, key is not sk_test_"

    return {"ok": True, "service": "palinode", "stripe": stripe}


@app.get("/registry")
async def registry() -> dict:
    """Agent cataloging. Who is registered, what they may touch, what it costs."""
    return {
        "agents": [
            {
                "name": card.name,
                "identity": card.identity,
                "version": card.version,
                "owner": card.owner,
                "description": card.description,
                "mode": card.mode.value,
                "tools": sorted(card.tools),
                "budget_usd_per_hour": card.budget_usd_per_hour,
            }
            for card in get_registry().all()
        ]
    }


@app.get("/runs/{run_id}")
async def run_detail(run_id: str) -> dict:
    actions = await get_ledger().by_run(run_id)
    if not actions:
        raise HTTPException(status_code=404, detail="no actions for that run")
    return {
        "run_id": run_id,
        "actions": [
            {
                "id": a.id,
                "agent": a.agent,
                "tool": a.tool,
                "args": a.args,
                "tier": a.tier.value,
                "tier_reason": a.tier_reason,
                "state": a.state.value,
                "caused_by": a.caused_by,
                "exposure_usd": a.cost(),
                "reverses_with": a.contract.tool if a.contract else None,
                "actor": a.actor,
                "entry_hash": a.entry_hash[:12],
                "created_at": a.created_at.isoformat(),
                "age_days": round(
                    (datetime.now(timezone.utc) - a.created_at).total_seconds() / 86400,
                    1,
                ),
            }
            for a in actions
        ],
        "outcome": await get_ledger().get_outcome(run_id),
    }


@app.get("/runs/{run_id}/verify")
async def verify_run(run_id: str) -> dict:
    """Has this audit trail been edited since it was written?

    Recomputes the hash chain. Every entry commits to the one before it, so an
    action that was changed or removed after the fact shows up here as a break
    at a named entry rather than as a trail that quietly reads clean.
    """
    report = await get_ledger().verify(run_id)
    if report.length == 0:
        raise HTTPException(status_code=404, detail="no actions for that run")
    return report.as_dict()


@app.get("/actions/{action_id}/blast-radius")
async def blast_radius(action_id: str) -> dict:
    """Everything that has to be undone along with this, before touching it."""
    scope = await get_ledger().blast_radius(action_id)
    if not scope:
        raise HTTPException(status_code=404, detail="unknown action")
    return {
        "root": action_id,
        "size": len(scope),
        "actions": [{"id": a.id, "tool": a.tool, "tier": a.tier.value} for a in scope],
    }


@app.post("/demo/reset")
async def reset() -> dict:
    """Clear the world and the ledger. Puts the dashboard back to empty."""
    await get_ledger().clear_outcome(poisoned_invoice.RUN_ID)
    await poisoned_invoice.reset()
    return {"ok": True}


@app.post("/demo/screen/{invoice_key}")
async def screen(invoice_key: str) -> dict:
    """Run an invoice past Model Armor. Nothing executes either way."""
    return await poisoned_invoice.screen(invoice_key)


@app.post("/demo/cold-case")
async def seed_cold_case() -> dict:
    """Seed a run dated three weeks back, then reverse it.

    The Fleet track asks for context held across weeks of asynchronous
    operation. This is that, end to end: contracts written twenty three days
    ago, executed today, with nothing in the reversal path aware of the gap.
    """
    await cold_case.reset()
    seeded = await cold_case.run()

    regret = RegretAgent(run_tool=run_tool)
    plan = await regret.plan(run_id=cold_case.RUN_ID)
    outcome = await regret.execute(plan, verifier=Verifier(run_tool=run_tool))
    outcome["run_id"] = cold_case.RUN_ID
    outcome["triggered_by"] = "operator"
    await get_ledger().save_outcome(cold_case.RUN_ID, outcome)

    return {**seeded, "reversal": outcome}


@app.post("/demo/seed")
async def seed() -> dict:
    """Reset and replay the poisoned invoice scenario."""
    await get_ledger().clear_outcome(poisoned_invoice.RUN_ID)
    await poisoned_invoice.reset()
    run_id = await poisoned_invoice.run()
    return {"run_id": run_id}


async def _reverse(run_id: str, from_action: Optional[str]) -> None:
    regret = RegretAgent(run_tool=run_tool)
    plan = await regret.plan(run_id=run_id, from_action=from_action)
    outcome = await regret.execute(plan, verifier=Verifier(run_tool=run_tool))

    herald = get_herald()
    outcome["disclosures"] = [
        await herald.disclose(r) for r in await regret.unrecoverable_records(plan)
    ]
    outcome["run_id"] = run_id
    outcome["triggered_by"] = "operator"
    await get_ledger().save_outcome(run_id, outcome)


@app.post("/undo")
async def undo(request: UndoRequest) -> dict:
    """Plan and run the reversal, and wait for it.

    This used to hand the work to a FastAPI background task so the response
    could return immediately. On Cloud Run that is a trap: CPU is only
    allocated while a request is in flight, so the background task stalls the
    moment the response goes out and the reversal silently never finishes.
    Keeping it in the request is both correct and cheaper, because the service
    can then scale to zero instead of holding an instance warm.
    """
    regret = RegretAgent(run_tool=run_tool)
    plan = await regret.plan(run_id=request.run_id, from_action=request.from_action)

    if request.dry_run:
        return {
            "dry_run": True,
            "summary": plan.summary(),
            "steps": [s.model_dump() for s in plan.steps],
            "unrecoverable": plan.unrecoverable,
            "exposure_usd": round(plan.exposure_usd, 2),
        }

    await _reverse(request.run_id, request.from_action)
    return await get_ledger().get_outcome(request.run_id) or {}


def _sentinel() -> Sentinel:
    regret = RegretAgent(run_tool=run_tool)
    sentinel = Sentinel(regret=regret, herald=get_herald())
    # Counterparties this fleet has dealt with before. In a real deployment
    # this is the vendor master, not a literal.
    sentinel.known_counterparties = {"cus_northwind", "ap@northwind.example"}
    return sentinel


@app.get("/sentinel/{run_id}")
async def sentinel_assess(run_id: str) -> dict:
    """What Sentinel thinks of a run, without acting on it.

    Static signals only. This is a read the dashboard makes several times a
    second, and it has no business calling a model to do it.
    """
    assessment = await _sentinel().assess(run_id, use_model=False)
    return {
        "run_id": run_id,
        "score": assessment.score,
        "threshold": 1.0,
        "would_reverse": assessment.should_reverse,
        "trigger_action": assessment.trigger_action,
        "signals": [
            {"name": s.name, "weight": s.weight, "detail": s.detail}
            for s in assessment.signals
        ],
    }


@app.post("/sentinel/{run_id}/watch")
async def sentinel_watch(run_id: str) -> dict:
    """Hand the run to Sentinel and let it decide. No approval step."""
    outcome = await _sentinel().watch(run_id, verifier=Verifier(run_tool=run_tool))
    if outcome.get("triggered"):
        await get_ledger().save_outcome(run_id, outcome)
    return outcome
