"""Rules CRUD + induction trigger + revision trigger.

Phase 1A: only listing is wired. Induction, consistency lookup, and revision
trigger are stubs returning 501 until Phase 1B fills the orchestrator's
internal hooks (`_try_induce_all`, `_check_all_rule_cs`).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.db import get_session
from backend.memory import store


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
    raise HTTPException(status_code=501, detail="phase1B-stub: induction not wired yet")


@router.get("/{rule_id}/consistency")
async def consistency_of(
    rule_id: str,
    session: AsyncSession = Depends(get_session),
):
    raise HTTPException(status_code=501, detail="phase1B-stub: CS lookup not wired yet")


@router.post("/{rule_id}/revise", response_model=schemas.Revision)
async def revise(
    rule_id: str,
    session: AsyncSession = Depends(get_session),
):
    raise HTTPException(status_code=501, detail="phase1B-stub: revision not wired yet")
