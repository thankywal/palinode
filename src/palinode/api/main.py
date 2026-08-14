"""Control plane API. This is what runs on Cloud Run.

Small on purpose. The interesting logic belongs to the Warden and to Regret,
and an HTTP layer that starts making decisions of its own is a layer you end up
debugging during an incident.
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ..agents.herald import get_herald
from ..agents.regret import RegretAgent
from ..agents.verifier import Verifier
from ..connectors.base import run_tool
from ..ledger.store import get_ledger
from ..warden.registry import get_registry

app = FastAPI(title="Palinode", version="0.1.0")


class UndoRequest(BaseModel):
    run_id: str
    from_action: Optional[str] = None
    dry_run: bool = False


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
                "tier": a.tier.value,
                "state": a.state.value,
                "caused_by": a.caused_by,
                "exposure_usd": a.cost(),
            }
            for a in actions
        ],
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


@app.post("/undo")
async def undo(request: UndoRequest) -> dict:
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

    outcome = await regret.execute(plan, verifier=Verifier(run_tool=run_tool))

    herald = get_herald()
    disclosures = [await herald.disclose(r) for r in await regret.unrecoverable_records(plan)]
    outcome["disclosures"] = disclosures
    return outcome
