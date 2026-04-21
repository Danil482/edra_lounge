from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.db import get_session

router = APIRouter(prefix="/clusters", tags=["clusters"])


@router.get("", response_model=list[schemas.Cluster])
async def list_clusters(session: AsyncSession = Depends(get_session)):
    # TODO(phase1): read persisted ClusterRows
    return []


@router.post("/recompute", response_model=list[schemas.Cluster])
async def recompute_clusters(session: AsyncSession = Depends(get_session)):
    # TODO(phase1): run clustering.cluster_episodes, persist, return
    raise NotImplementedError
