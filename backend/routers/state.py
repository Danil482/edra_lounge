"""GET /state — single consolidated snapshot for the UI poll loop.

The frontend hits this every 1000ms (TASK.md §2 / §10.6); response shape is
defined by `schemas.StateSnapshot`. Phase 1A returns a minimal-but-valid
snapshot: clock from the orchestrator, recent episodes from the DB, no
in-flight session, no clusters_viz, no agents — those land in Phase 1B/2.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.db import get_session
from backend.memory import store


router = APIRouter(tags=["state"])


@router.get("/state", response_model=schemas.StateSnapshot)
async def state(request: Request, session: AsyncSession = Depends(get_session)):
    orch = getattr(request.app.state, "orchestrator", None)
    clock = orch.clock if orch is not None else schemas.Clock(day=1, time="09:00")
    current_session = orch.active_session if orch is not None else None
    return schemas.StateSnapshot(
        clock=clock,
        current_session=current_session,
        recent_episodes=await store.list_episodes(session, limit=20),
        clusters_viz=[],
        rules=await store.list_rules(session, status="active"),
        active_revision=None,
        agents=[],
        interest_gauge=current_session.interest if current_session is not None else None,
    )
