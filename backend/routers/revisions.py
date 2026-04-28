"""POST /revisions/{id}/decision — operator's accept / reject / edit verdict.

Phase 1A stub. Phase 1B wires the deprecate-with-pointer behaviour for
`decision == "accepted"` (default per TASK.md §15) and persists the edited
rule when `decision == "edited"`.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.db import get_session


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
    raise HTTPException(status_code=501, detail="phase1B-stub: revision decision not wired yet")
