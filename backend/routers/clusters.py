"""Clusters listing + recompute trigger.

Listing reads ClusterRow directly. Recompute hits the orchestrator's
`_recluster` path so synthetic and live both go through the same code.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.db import get_session
from backend.memory import store


router = APIRouter(prefix="/clusters", tags=["clusters"])


@router.get("", response_model=list[schemas.Cluster])
async def list_clusters(session: AsyncSession = Depends(get_session)):
    return await store.list_clusters(session)


@router.post("/recompute", response_model=list[schemas.Cluster])
async def recompute_clusters(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    orch = getattr(request.app.state, "orchestrator", None)
    if orch is None:
        raise HTTPException(status_code=503, detail="orchestrator not running")
    await orch._recluster(session)
    return await store.list_clusters(session)
