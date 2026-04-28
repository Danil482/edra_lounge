"""Agent Factory surface (TASK.md §8).

Phase 1A: list_agents reads from AgentRow (none yet). Evaluate / spawn are
stubs until Phase 1B wires the orchestrator's `_evaluate_factory`.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.db import get_session
from backend.memory import models


router = APIRouter(prefix="/factory", tags=["factory"])


class EvalResult(BaseModel):
    spawn_needed: bool
    uncovered_cluster_id: str | None = None


class SpawnIn(BaseModel):
    cluster_id: str
    description: str


@router.get("/agents", response_model=list[schemas.Agent])
async def list_agents(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(models.AgentRow))
    return [
        schemas.Agent(
            id=r.id,
            cluster_id=r.cluster_id,
            zone_description=r.zone_description,
            created_at=r.created_at,
            is_active=r.is_active,
        )
        for r in result.scalars()
    ]


@router.post("/evaluate", response_model=EvalResult)
async def evaluate(session: AsyncSession = Depends(get_session)):
    return EvalResult(spawn_needed=False)


@router.post("/spawn", response_model=schemas.Agent)
async def spawn(body: SpawnIn, session: AsyncSession = Depends(get_session)):
    raise HTTPException(status_code=501, detail="phase1B-stub: factory spawn not wired yet")
