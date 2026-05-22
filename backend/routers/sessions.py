"""Multi-turn pitch session HTTP surface (TASK.md §8).

  GET  /sessions/sources       → { active_kind, synthetic_archetypes[] }
  POST /sessions/start         body: { source_kind, identifier }
                               → { session_id, profile_id, classified_cluster_id,
                                   applicable_rule_id, first_step }
  POST /sessions/{id}/turn     body: { visitor_choice }
                               → DialogueStep + { terminated, interest, outcome }
  POST /sessions/{id}/end      finalise + persist Episode + fire on_new_episode

The router is a thin shell — all logic lives in `backend/sessions/lifecycle.py`
so the orchestrator's synthetic tick loop can call the same code path.

The active ProfileSource is held on `app.state.profile_source` (set in
`app.lifespan`); the router reads it per-request rather than holding a stale
reference.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.db import get_session
from backend.profile_source import ProfileNotFound, ProfileSourceUnavailable
from backend.profile_source.synthetic import SyntheticProfileSource
from backend.sessions import lifecycle


router = APIRouter(prefix="/sessions", tags=["sessions"])


# ── Request / response models ────────────────────────────────────────────

class StartIn(BaseModel):
    source_kind: str
    identifier: str


class StartOut(BaseModel):
    session_id: str
    profile_id: str
    classified_cluster_id: str | None
    applicable_rule_id: str | None
    first_step: schemas.DialogueStep
    interest: int
    pitch_strategy: schemas.PitchStrategy


class TurnIn(BaseModel):
    visitor_choice: schemas.VISITOR_CHOICE


class TurnOut(BaseModel):
    step: schemas.DialogueStep
    interest: int
    terminated: bool
    outcome: schemas.OUTCOME | None = None


class ResolveIn(BaseModel):
    decision: Literal["accept", "decline"]


class ResolveOut(BaseModel):
    episode_id: str
    summary: str
    final_interest: int
    outcome: schemas.OUTCOME
    terminated: bool = True


class EndOut(BaseModel):
    episode_id: str
    summary: str
    final_interest: int
    outcome: schemas.OUTCOME


class SourcesOut(BaseModel):
    active_kind: str
    live_mode: bool
    synthetic_archetypes: list[str]


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get("/sources", response_model=SourcesOut)
async def sources(request: Request):
    """Surface active ProfileSource kind + synthetic fallback archetype list.

    The frontend hits this on boot to decide whether to show the live-URL form
    and which archetype options to offer in the Wi-Fi-fallback dialog. The
    fallback list is read from `archetypes.yaml` directly so it stays accurate
    even when the active source is LinkedIn (which can't list synthetic ids).
    """
    profile_source = request.app.state.profile_source
    fallback = SyntheticProfileSource()
    return SourcesOut(
        active_kind=profile_source.source_kind,
        live_mode=profile_source.source_kind != "synthetic",
        synthetic_archetypes=fallback.list_ids(include_spawnable=True),
    )

@router.post("/start", response_model=StartOut)
async def start(
    body: StartIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    profile_source = request.app.state.profile_source
    orch = getattr(request.app.state, "orchestrator", None)
    day = orch.clock.day if orch is not None else 1

    try:
        sess, first_step = await lifecycle.start_session(
            db=db,
            profile_source=profile_source,
            source_kind=body.source_kind,
            identifier=body.identifier,
            day=day,
        )
    except ProfileNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ProfileSourceUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    if orch is not None:
        # Pause synthetic-tick visitor spawns while a live session is in flight.
        orch.live_session_active = True
        orch.active_session = sess.to_snapshot()

    return StartOut(
        session_id=sess.id,
        profile_id=sess.profile.id,
        classified_cluster_id=sess.cluster_id,
        applicable_rule_id=sess.applicable_rule_id,
        first_step=first_step,
        interest=sess.interest,
        pitch_strategy=sess.pitch_strategy,
    )


@router.post("/{session_id}/turn", response_model=TurnOut)
async def turn(
    session_id: str,
    body: TurnIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    try:
        sess, step, terminated = await lifecycle.take_turn(
            db=db,
            session_id=session_id,
            visitor_choice=body.visitor_choice,
        )
    except lifecycle.SessionNotFound:
        raise HTTPException(status_code=404, detail="session not found")
    except lifecycle.SessionAlreadyEnded:
        raise HTTPException(status_code=409, detail="session already ended")

    orch = getattr(request.app.state, "orchestrator", None)
    if orch is not None:
        orch.active_session = sess.to_snapshot()

    return TurnOut(
        step=step,
        interest=sess.interest,
        terminated=terminated,
        outcome=sess.outcome,
    )


@router.post("/{session_id}/resolve", response_model=ResolveOut)
async def resolve(
    session_id: str,
    body: ResolveIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    orch = getattr(request.app.state, "orchestrator", None)
    on_new_episode = orch.on_new_episode if orch is not None else None

    try:
        episode, outcome = await lifecycle.resolve_session(
            db=db,
            session_id=session_id,
            decision=body.decision,
            on_new_episode=on_new_episode,
        )
    except lifecycle.SessionNotFound:
        raise HTTPException(status_code=404, detail="session not found")
    except lifecycle.SessionAlreadyEnded:
        raise HTTPException(status_code=409, detail="session already ended")

    if orch is not None:
        orch.live_session_active = False
        orch.active_session = None

    return ResolveOut(
        episode_id=episode.id,
        summary=episode.summary,
        final_interest=episode.final_interest,
        outcome=outcome,
    )


@router.post("/{session_id}/end", response_model=EndOut)
async def end(
    session_id: str,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    orch = getattr(request.app.state, "orchestrator", None)
    on_new_episode = orch.on_new_episode if orch is not None else None

    try:
        episode = await lifecycle.end_session(
            db=db,
            session_id=session_id,
            on_new_episode=on_new_episode,
        )
    except lifecycle.SessionNotFound:
        raise HTTPException(status_code=404, detail="session not found")

    if orch is not None:
        orch.live_session_active = False
        orch.active_session = None

    return EndOut(
        episode_id=episode.id,
        summary=episode.summary,
        final_interest=episode.final_interest,
        outcome=episode.outcome,
    )
