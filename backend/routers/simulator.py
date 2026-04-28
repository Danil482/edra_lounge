"""Simulator + drift control surface (TASK.md §8).

`POST /simulator/pause`               — freeze / unfreeze the orchestrator tick loop
`POST /simulator/drift/{drift_id}`    — manually fire a scripted drift
`POST /simulator/inject_archetype`    — push a spawnable archetype to the queue
"""

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel


router = APIRouter(prefix="/simulator", tags=["simulator"])


class InjectIn(BaseModel):
    archetype_id: str


class PauseIn(BaseModel):
    paused: bool


@router.post("/pause")
async def pause(body: PauseIn, request: Request):
    request.app.state.orchestrator.paused = body.paused
    return {"paused": body.paused}


@router.post("/drift/{drift_id}")
async def fire_drift(drift_id: Literal["ai_bubble_pops", "postdoc_burnout"]):
    from backend.simulator import drift

    handler = drift.DRIFT_REGISTRY.get(drift_id)
    if handler is None:
        raise HTTPException(status_code=404, detail=f"unknown drift: {drift_id}")
    if callable(handler):
        handler()
    else:
        # GradualPostdocShift instance — advance one step.
        handler.advance()
    return {"ok": True, "drift": drift_id}


@router.post("/inject_archetype")
async def inject_archetype(body: InjectIn, request: Request):
    request.app.state.orchestrator.inject_archetype(body.archetype_id)
    return {"ok": True, "archetype_id": body.archetype_id}
