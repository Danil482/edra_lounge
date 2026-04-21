from typing import Literal

from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.db import get_session

router = APIRouter(prefix="/simulator", tags=["simulator"])


class TickIn(BaseModel):
    persona_id: str | None = None


class InjectIn(BaseModel):
    persona_id: str


class PauseIn(BaseModel):
    paused: bool


@router.post("/tick", response_model=schemas.Episode)
async def tick(body: TickIn, request: Request):
    """Advance one visit manually. Normally the orchestrator does this every 20s."""
    orch = request.app.state.orchestrator
    ep = await orch.advance_one_visit()
    if ep is None:
        raise HTTPException(status_code=409, detail="no more scheduled visits")
    return ep


@router.post("/pause")
async def pause(body: PauseIn, request: Request):
    """Freeze/unfreeze the orchestrator tick loop."""
    request.app.state.orchestrator.paused = body.paused
    return {"paused": body.paused}


@router.post("/drift/{drift_id}")
async def fire_drift(drift_id: Literal["ai_bubble_pops", "gradual_postdoc"]):
    from backend.simulator import drift

    handler = drift.DRIFT_REGISTRY[drift_id]
    if callable(handler):
        handler()
    else:
        handler.advance()
    return {"ok": True, "drift": drift_id}


@router.post("/inject_persona")
async def inject_persona(body: InjectIn, request: Request):
    request.app.state.orchestrator.inject_persona(body.persona_id)
    return {"ok": True, "persona_id": body.persona_id}
