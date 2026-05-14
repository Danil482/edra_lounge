"""OutreachRow model + CRUD for the outreach campaign state table.

Each row tracks a single outreach message through its lifecycle:
draft -> reviewed -> sent -> response_received/cutoff_expired -> classified -> ingested

Uses a separate SQLAlchemy Base so the outreach table can live in its own
database file (outreach.db) without polluting the booth demo's edra_lounge.db.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Sequence

from sqlalchemy import JSON, DateTime, Integer, String, Text, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from backend.config import PROJECT_ROOT


VALID_STATUSES = frozenset({
    "draft",
    "reviewed",
    "sent",
    "response_received",
    "cutoff_expired",
    "classified",
    "ingested",
})

_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "draft": ("reviewed",),
    "reviewed": ("sent",),
    "sent": ("response_received", "cutoff_expired"),
    "response_received": ("classified",),
    "cutoff_expired": ("classified",),
    "classified": ("ingested",),
    "ingested": (),
}


class OutreachBase(DeclarativeBase):
    pass


class OutreachRow(OutreachBase):
    __tablename__ = "outreach_campaigns"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    profile_id: Mapped[str] = mapped_column(String, index=True)
    csv_name: Mapped[str] = mapped_column(String)
    linkedin_url: Mapped[str] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    segment: Mapped[str] = mapped_column(String)
    geo: Mapped[str] = mapped_column(String)
    confidence: Mapped[str] = mapped_column(String)
    iteration: Mapped[int] = mapped_column(Integer)
    batch_id: Mapped[str] = mapped_column(String, index=True)
    strategy_source: Mapped[str] = mapped_column(String)
    pitch_strategy: Mapped[dict] = mapped_column(JSON)
    outreach_text: Mapped[str] = mapped_column(Text)
    platform: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="draft")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    response_classification: Mapped[str | None] = mapped_column(String, nullable=True)
    edra_outcome: Mapped[str | None] = mapped_column(String, nullable=True)
    edra_final_interest: Mapped[int | None] = mapped_column(Integer, nullable=True)
    episode_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class InvalidTransition(Exception):
    pass


# ── Database init ────────────────────────────────────────────────────────

DEFAULT_OUTREACH_DB = PROJECT_ROOT / "outreach.db"


def outreach_engine(db_path: str | None = None):
    url = f"sqlite+aiosqlite:///{db_path or DEFAULT_OUTREACH_DB}"
    return create_async_engine(url, echo=False, future=True)


def outreach_session_factory(db_path: str | None = None) -> async_sessionmaker[AsyncSession]:
    engine = outreach_engine(db_path)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_outreach_db(db_path: str | None = None) -> None:
    engine = outreach_engine(db_path)
    async with engine.begin() as conn:
        await conn.run_sync(OutreachBase.metadata.create_all)
    await engine.dispose()


# ── CRUD ─────────────────────────────────────────────────────────────────

async def create_outreach_row(session: AsyncSession, row: OutreachRow) -> OutreachRow:
    now = datetime.now(UTC)
    if row.created_at is None:
        row.created_at = now
    if row.updated_at is None:
        row.updated_at = now
    if row.status is None:
        row.status = "draft"
    session.add(row)
    await session.commit()
    return row


async def get_outreach_row(session: AsyncSession, row_id: str) -> OutreachRow | None:
    return await session.get(OutreachRow, row_id)


async def list_by_batch(session: AsyncSession, batch_id: str) -> Sequence[OutreachRow]:
    stmt = select(OutreachRow).where(OutreachRow.batch_id == batch_id)
    result = await session.execute(stmt)
    return result.scalars().all()


async def list_by_status(session: AsyncSession, status: str) -> Sequence[OutreachRow]:
    stmt = select(OutreachRow).where(OutreachRow.status == status)
    result = await session.execute(stmt)
    return result.scalars().all()


async def list_by_profile(session: AsyncSession, profile_id: str) -> Sequence[OutreachRow]:
    stmt = select(OutreachRow).where(OutreachRow.profile_id == profile_id)
    result = await session.execute(stmt)
    return result.scalars().all()


async def update_status(
    session: AsyncSession,
    row_id: str,
    new_status: str,
    **fields: object,
) -> OutreachRow:
    """Transition an outreach row to a new status with optional field updates.

    Validates the state machine transition. Extra keyword arguments are set
    as attributes on the row (e.g., sent_at, response_text, etc.).

    Raises InvalidTransition if the transition is not allowed.
    Raises ValueError if the row does not exist.
    """
    row = await session.get(OutreachRow, row_id)
    if row is None:
        raise ValueError(f"OutreachRow {row_id!r} not found")

    allowed = _TRANSITIONS.get(row.status, ())
    if new_status not in allowed:
        raise InvalidTransition(
            f"Cannot transition {row_id!r} from {row.status!r} to {new_status!r} "
            f"(allowed: {allowed})"
        )

    row.status = new_status
    row.updated_at = datetime.now(UTC)

    for key, value in fields.items():
        if not hasattr(row, key):
            raise AttributeError(f"OutreachRow has no attribute {key!r}")
        setattr(row, key, value)

    await session.commit()
    return row


async def list_sent_before(session: AsyncSession, before_dt: datetime) -> Sequence[OutreachRow]:
    """Return sent rows with sent_at earlier than *before_dt* (for cutoff checking)."""
    stmt = (
        select(OutreachRow)
        .where(OutreachRow.status == "sent")
        .where(OutreachRow.sent_at <= before_dt)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def contacted_profile_ids(session: AsyncSession) -> set[str]:
    """Return the set of profile_ids that have already been contacted
    (status is not 'draft')."""
    stmt = select(OutreachRow.profile_id).where(OutreachRow.status != "draft")
    result = await session.execute(stmt)
    return {pid for (pid,) in result.all()}
