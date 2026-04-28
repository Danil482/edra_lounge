"""Episode listing. Phase 1A: read-only.

Phase 1B introduces full Episode creation through the multi-turn sessions API
(`POST /sessions/start` → `/turn` → `/end`); direct POST /episodes is not
exposed since synthesising an episode without going through a Session would
bypass the dialogue contract and the preference function.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.db import get_session
from backend.memory import store


router = APIRouter(prefix="/episodes", tags=["episodes"])


@router.get("", response_model=list[schemas.Episode])
async def list_episodes(
    limit: int = 20,
    order: str = "desc",
    session: AsyncSession = Depends(get_session),
):
    return await store.list_episodes(session, limit=limit, order=order)
