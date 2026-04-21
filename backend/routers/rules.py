from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.db import get_session
from backend.memory import store
from backend.memory.ids import short_id

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=list[schemas.Rule])
async def list_rules(
    status: schemas.RULE_STATUS | None = None,
    session: AsyncSession = Depends(get_session),
):
    return await store.list_rules(session, status=status)


@router.post("/induce", response_model=schemas.Rule)
async def induce(
    cluster_id: str,
    session: AsyncSession = Depends(get_session),
):
    # TODO(phase1): load cluster + episodes, call induction.induce_rule,
    # persist, return. On NotEligible → 409 with reason.
    raise HTTPException(status_code=409, detail="not-eligible (phase1 stub)")


@router.get("/{rule_id}/consistency")
async def consistency_of(
    rule_id: str,
    session: AsyncSession = Depends(get_session),
):
    # TODO(phase1): load rule + its cluster episodes, return
    # {score, post_induction_episodes, recent_history, revision_needed}.
    raise HTTPException(status_code=501, detail="phase1 stub")


@router.post("/{rule_id}/revise", response_model=schemas.Revision)
async def revise(
    rule_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Triggers a revision. Synchronous: creates a pending Revision row and
    returns its id. The LLM reasoning is streamed separately via
    `GET /reflections/stream/{revision_id}`.
    """
    # TODO(phase1): load rule, load contradicting episodes, persist Revision row
    # with status=pending and placeholder proposed_rule, return it.
    rule = next(
        (r for r in await store.list_rules(session) if r.id == rule_id),
        None,
    )
    if rule is None:
        raise HTTPException(status_code=404, detail=f"rule {rule_id} not found")

    revision_id = short_id("rev")
    proposed_placeholder = rule.model_copy(update={"status": "under_revision"})
    return schemas.Revision(
        id=revision_id,
        rule_id=rule_id,
        triggered_at=datetime.utcnow(),
        contradicting_episode_ids=[],  # TODO(phase1): fill from CS window
        llm_reasoning="",
        proposed_rule=proposed_placeholder,
        decision="pending",
        resolved_at=None,
    )
