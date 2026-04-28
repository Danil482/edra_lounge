"""POST /revisions/{id}/decision — operator's accept / reject / edit verdict.

Default acceptance behaviour is deprecate-with-pointer (TASK.md §15 #3): the
old rule's status flips to `deprecated`, `deprecated_by` points at the new
rule, and the new rule is persisted with a fresh monotonic id.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.db import get_session
from backend.memory import store
from backend.memory.ids import next_rule_id


router = APIRouter(prefix="/revisions", tags=["revisions"])


class DecisionIn(BaseModel):
    decision: schemas.REVISION_DECISION
    edited_rule: schemas.Rule | None = None


@router.post("/{revision_id}/decision", response_model=schemas.Revision)
async def decide(
    revision_id: str,
    body: DecisionIn,
    session: AsyncSession = Depends(get_session),
):
    rev = await store.get_revision(session, revision_id)
    if rev is None:
        raise HTTPException(status_code=404, detail=f"unknown revision: {revision_id}")
    if rev.decision != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"revision {revision_id} already resolved ({rev.decision})",
        )

    original = await store.get_rule(session, rev.rule_id)
    if original is None:
        raise HTTPException(status_code=404, detail=f"unknown rule: {rev.rule_id}")

    now = datetime.utcnow()

    if body.decision == "rejected":
        # Keep the old rule active, drop the under_revision flag.
        await store.update_rule(session, original.id, status="active")
        updated = await store.update_revision(
            session,
            revision_id,
            decision="rejected",
            resolved_at=now,
        )
        return updated  # type: ignore[return-value]

    # accepted or edited — install the new rule, deprecate the old one.
    new_slots = (
        body.edited_rule.slots if body.decision == "edited" and body.edited_rule
        else rev.proposed_rule.slots
    )

    existing_ids = await store.existing_rule_ids(session)
    new_rule = schemas.Rule(
        id=next_rule_id(existing_ids),
        cluster_id=original.cluster_id,
        slots=new_slots,
        induced_at=now,
        induced_from_episode_ids=list(original.induced_from_episode_ids),
        status="active",
        deprecated_by=None,
        cs_history=[],
    )
    await store.save_rule(session, new_rule)
    await store.update_rule(
        session,
        original.id,
        status="deprecated",
        deprecated_by=new_rule.id,
    )
    updated = await store.update_revision(
        session,
        revision_id,
        decision=body.decision,
        proposed_rule=new_rule,
        resolved_at=now,
    )
    return updated  # type: ignore[return-value]
