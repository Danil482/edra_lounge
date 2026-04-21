from pydantic import BaseModel

from fastapi import APIRouter, Depends
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
    # TODO(phase1): update revision row, deprecate old rule with pointer if accepted.
    raise NotImplementedError
