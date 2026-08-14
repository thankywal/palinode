"""Control plane API and dashboard. This is what runs on Cloud Run.

Small on purpose. The interesting logic belongs to the Warden and to Regret,
and an HTTP layer that starts making decisions of its own is a layer you end up
debugging during an incident.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
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
from ..scenarios import poisoned_invoice
from ..telemetry import configure as configure_tracing
from ..warden.registry import get_registry

app = FastAPI(title="Palinode", version="0.1.0")

# Spans go to Cloud Trace when a project is configured. ADK already traces the
# agent runs and tool calls, so what we add is the part it cannot know: why an
# action got the tier it did and what happened when the reversal ran.
configure_tracing(settings.project)

STATIC = Path(__file__).parent / "static"
if STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

# Outcome of the most recent reversal, so the dashboard can show disclosures
# without holding the request open while Regret works.
_last_outcome: dict = {}


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


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


@app.get("/registry")
async def registry() -> dict:
    """Agent cataloging. Who is registered, what they may touch, what it costs."""
    return {
        "agents": [
            {
                "name": card.name,
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
            }
            for a in actions
        ],
        "outcome": _last_outcome if _last_outcome.get("run_id") == run_id else None,
    }


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
    global _last_outcome
    _last_outcome = {}
    await poisoned_invoice.reset()
    return {"ok": True}


@app.post("/demo/screen/{invoice_key}")
async def screen(invoice_key: str) -> dict:
    """Run an invoice past Model Armor. Nothing executes either way."""
    return await poisoned_invoice.screen(invoice_key)


@app.post("/demo/seed")
async def seed() -> dict:
    """Reset and replay the poisoned invoice scenario."""
    global _last_outcome
    _last_outcome = {}
    await poisoned_invoice.reset()
    run_id = await poisoned_invoice.run()
    return {"run_id": run_id}


async def _reverse(run_id: str, from_action: Optional[str]) -> None:
    global _last_outcome
    regret = RegretAgent(run_tool=run_tool)
    plan = await regret.plan(run_id=run_id, from_action=from_action)
    outcome = await regret.execute(plan, verifier=Verifier(run_tool=run_tool))

    herald = get_herald()
    outcome["disclosures"] = [
        await herald.disclose(r) for r in await regret.unrecoverable_records(plan)
    ]
    outcome["run_id"] = run_id
    _last_outcome = outcome


@app.post("/undo")
async def undo(request: UndoRequest, background: BackgroundTasks) -> dict:
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

    # Kicked into the background so the dashboard can watch states change
    # rather than staring at a spinner until the whole reversal is done.
    background.add_task(_reverse, request.run_id, request.from_action)
    return {"started": True, "planned": plan.summary()}


@app.post("/undo/sync")
async def undo_sync(request: UndoRequest) -> dict:
    """Same thing, but waits. Easier to script against."""
    await _reverse(request.run_id, request.from_action)
    return _last_outcome


def _sentinel() -> Sentinel:
    regret = RegretAgent(run_tool=run_tool)
    sentinel = Sentinel(regret=regret, herald=get_herald())
    # Counterparties this fleet has dealt with before. In a real deployment
    # this is the vendor master, not a literal.
    sentinel.known_counterparties = {"cus_northwind", "ap@northwind.example"}
    return sentinel


@app.get("/sentinel/{run_id}")
async def sentinel_assess(run_id: str) -> dict:
    """What Sentinel thinks of a run, without acting on it."""
    assessment = await _sentinel().assess(run_id)
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


async def _sentinel_watch(run_id: str) -> None:
    global _last_outcome
    outcome = await _sentinel().watch(run_id, verifier=Verifier(run_tool=run_tool))
    if outcome.get("triggered"):
        _last_outcome = outcome


@app.post("/sentinel/{run_id}/watch")
async def sentinel_watch(run_id: str, background: BackgroundTasks) -> dict:
    """Hand the run to Sentinel and let it decide. No approval step."""
    assessment = await _sentinel().assess(run_id)
    background.add_task(_sentinel_watch, run_id)
    return {
        "watching": run_id,
        "score": assessment.score,
        "will_reverse": assessment.should_reverse,
        "signals": [s.name for s in assessment.signals],
    }
