from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.db import get_session
from backend.memory import store

router = APIRouter(tags=["state"])


@router.get("/state", response_model=schemas.StateSnapshot)
async def state(session: AsyncSession = Depends(get_session)):
    """Consolidated snapshot for UI — polled every 1s by the frontend."""
    # TODO(phase1): fill clock from orchestrator, clusters_viz from UMAP projection,
    # current_visitor from in-flight tick, active_revision from revisions table.
    return schemas.StateSnapshot(
        clock=schemas.Clock(day=1, time="09:00"),
        current_visitor=None,
        recent_episodes=await store.list_episodes(session, limit=20),
        clusters_viz=[],
        rules=await store.list_rules(session, status="active"),
        active_revision=None,
        agents=[],
    )
