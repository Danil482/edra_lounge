"""Agent Factory surface (TASK.md §8).

  GET  /factory/agents     list registered agents
  POST /factory/evaluate   on-demand uncovered-cluster check (manual probe)
  POST /factory/spawn      spawn an agent for a specific cluster id
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.db import get_session
from backend.factory import factory as factory_mod
from backend.memory import store


router = APIRouter(prefix="/factory", tags=["factory"])


class EvalResult(BaseModel):
    spawn_needed: bool
    uncovered_cluster_id: str | None = None


class SpawnIn(BaseModel):
    cluster_id: str
    description: str = ""


@router.get("/agents", response_model=list[schemas.Agent])
async def list_agents(session: AsyncSession = Depends(get_session)):
    return await store.list_agents(session)


@router.post("/evaluate", response_model=EvalResult)
async def evaluate(session: AsyncSession = Depends(get_session)):
    clusters = await store.list_clusters(session)
    rules = await store.list_rules(session, status="active")
    uncovered = factory_mod.find_uncovered_cluster(clusters, rules)
    if uncovered is None:
        return EvalResult(spawn_needed=False)
    return EvalResult(spawn_needed=True, uncovered_cluster_id=uncovered.id)


@router.post("/spawn", response_model=schemas.Agent)
async def spawn(body: SpawnIn, session: AsyncSession = Depends(get_session)):
    cluster = await store.get_cluster(session, body.cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail=f"unknown cluster: {body.cluster_id}")
    if await store.cluster_has_agent(session, cluster.id):
        raise HTTPException(
            status_code=409,
            detail=f"cluster {cluster.id} already has an agent",
        )
    description = body.description or f"specialist for cluster {cluster.id}"
    agent = factory_mod.spawn_agent(cluster, description=description)
    await store.save_agent(session, agent)
    return agent
