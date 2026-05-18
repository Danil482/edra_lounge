import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_session
from backend.memory.models import VisitorRow

router = APIRouter(prefix="/api/visitors", tags=["visitors"])

EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$")


class VisitorIn(BaseModel):
    email: str


class VisitorOut(BaseModel):
    id: int
    email: str
    created_at: str


@router.post("", response_model=VisitorOut)
async def register_visitor(
    body: VisitorIn,
    db: AsyncSession = Depends(get_session),
):
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="invalid email format")

    result = await db.execute(select(VisitorRow).where(VisitorRow.email == email))
    existing = result.scalar_one_or_none()
    if existing:
        return VisitorOut(
            id=existing.id,
            email=existing.email,
            created_at=existing.created_at.isoformat(),
        )

    visitor = VisitorRow(email=email, created_at=datetime.utcnow())
    db.add(visitor)
    await db.commit()
    await db.refresh(visitor)

    return VisitorOut(
        id=visitor.id,
        email=visitor.email,
        created_at=visitor.created_at.isoformat(),
    )
