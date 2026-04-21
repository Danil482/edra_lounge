from pydantic import BaseModel

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.db import get_session

router = APIRouter(prefix="/factory", tags=["factory"])


class EvalResult(BaseModel):
    spawn_needed: bool
    uncovered_cluster_id: str | None = None


class SpawnIn(BaseModel):
    cluster_id: str
    description: str


@router.get("/agents", response_model=list[schemas.Agent])
async def list_agents(session: AsyncSession = Depends(get_session)):
    # TODO(phase1): return AgentRow rows
    return []


@router.post("/evaluate", response_model=EvalResult)
async def evaluate(session: AsyncSession = Depends(get_session)):
    # TODO(phase1): pull clusters + active rules, call factory.find_uncovered_cluster
    return EvalResult(spawn_needed=False)


@router.post("/spawn", response_model=schemas.Agent)
async def spawn(body: SpawnIn, session: AsyncSession = Depends(get_session)):
    # TODO(phase1): factory.spawn_agent + persist
    raise NotImplementedError
