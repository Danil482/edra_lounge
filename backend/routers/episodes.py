from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.clustering.cluster import embed
from backend.db import get_session
from backend.memory import store
from backend.memory.ids import short_id

router = APIRouter(prefix="/episodes", tags=["episodes"])


@router.post("", response_model=schemas.Episode)
async def create_episode(
    body: schemas.EpisodeCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Direct episode creation (e.g. manual injection, tests). Persists and
    fires orchestrator.on_new_episode — same fan-out as a scheduled tick."""
    persona = await store.get_persona(session, body.persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"persona {body.persona_id} not found")

    # TODO(phase1): generate summary via llm; for now, a trivial placeholder.
    summary = (
        f"{persona.display_name} received "
        f"{body.offer.topic}/{body.offer.style}/{body.offer.drink} "
        f"→ {body.outcome}"
    )
    embedding = embed([summary])[0]

    ep = schemas.Episode(
        id=short_id("ep"),
        timestamp=datetime.utcnow(),
        day=body.day,
        visitor_persona_id=body.persona_id,
        context={
            "role": persona.role,
            "domain": persona.domain,
            "vibe": persona.vibe,
        },
        offer=body.offer,
        outcome=body.outcome,
        outcome_score=body.outcome_score,
        summary=summary,
        summary_embedding=embedding,
        cluster_id=None,
        rule_applied=None,
    )
    await store.save_episode(session, ep)

    orch = request.app.state.orchestrator
    await orch.on_new_episode(ep)
    return ep


@router.get("", response_model=list[schemas.Episode])
async def list_episodes(
    limit: int = 20,
    order: str = "desc",
    session: AsyncSession = Depends(get_session),
):
    return await store.list_episodes(session, limit=limit, order=order)
