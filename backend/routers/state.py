"""GET /state — single consolidated snapshot for the UI poll loop.

The frontend hits this every 1000ms (TASK.md §2 / §10.6); response shape is
defined by `schemas.StateSnapshot`. Surfaces the orchestrator's clock, the
in-flight session (if any), the most recent episodes, active rules, the
latest pending revision (if any), and the registered agents.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.db import get_session
from backend.memory import store
from backend.sessions.store import get_active_session


router = APIRouter(tags=["state"])


@router.get("/state", response_model=schemas.StateSnapshot)
async def state(request: Request, session: AsyncSession = Depends(get_session)):
    orch = getattr(request.app.state, "orchestrator", None)
    clock = orch.clock if orch is not None else schemas.Clock(day=1, time="09:00")

    # Prefer the live HTTP-driven session if one is active; otherwise fall
    # back to the synthetic session pointer the orchestrator maintains.
    active = get_active_session()
    snapshot = (
        active.to_snapshot()
        if active is not None
        else (orch.active_session if orch is not None else None)
    )
    interest = snapshot.interest if snapshot is not None else None

    pending_revision = await store.latest_pending_revision(session)

    return schemas.StateSnapshot(
        clock=clock,
        current_session=snapshot,
        recent_episodes=await store.list_episodes(session, limit=20),
        clusters_viz=[],
        rules=await store.list_rules(session, status="active"),
        active_revision=pending_revision,
        agents=await store.list_agents(session),
        interest_gauge=interest,
        total_episodes=await store.count_episodes(session),
    )
