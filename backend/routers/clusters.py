"""Clusters listing + recompute trigger.

Phase 1A: listing reads any persisted ClusterRows (none yet — the orchestrator
will start writing them in Phase 1B). Recompute is a 501 stub until clustering
is wired into the orchestrator.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.db import get_session
from backend.memory import models


router = APIRouter(prefix="/clusters", tags=["clusters"])


@router.get("", response_model=list[schemas.Cluster])
async def list_clusters(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(models.ClusterRow))
    return [
        schemas.Cluster(
            id=r.id,
            label=r.label,
            profile_ids=r.profile_ids or [],
            episode_ids=r.episode_ids or [],
            centroid_embedding=r.centroid_embedding or [],
            size=r.size,
            success_ratio=r.success_ratio,
            created_at=r.created_at,
            last_updated=r.last_updated,
        )
        for r in result.scalars()
    ]


@router.post("/recompute", response_model=list[schemas.Cluster])
async def recompute_clusters(session: AsyncSession = Depends(get_session)):
    raise HTTPException(status_code=501, detail="phase1B-stub: clustering pipeline not wired yet")
