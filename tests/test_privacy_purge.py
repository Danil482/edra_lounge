"""Privacy purge — TASK.md acceptance §14: PII fetched from a non-synthetic
ProfileSource (LinkedIn / RapidAPI) MUST NOT live in SQLite past its TTL.

The implementation lives in `backend/memory/store.py::purge_expired_live_profiles`
and runs from the orchestrator's factory loop. The tests below verify the
behaviour at the store layer (deterministic, no orchestrator timing).

Test matrix:
  - synthetic profile, any age → kept
  - live profile, age < ttl     → kept
  - live profile, age >= ttl    → deleted
  - live profile, ttl_seconds=None → kept (TTL-opt-out, per row)
  - mixed corpus → only the expired live ones disappear; ids returned match
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import schemas
from backend.memory import store as memory_store
from backend.memory.models import Base


@pytest.fixture
async def db_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


def _profile(
    *,
    id_: str,
    source_kind: str,
    fetched_at: datetime,
    ttl_seconds: int | None,
) -> schemas.Profile:
    return schemas.Profile(
        id=id_,
        source_kind=source_kind,
        source_identifier=id_,
        name=f"name-{id_}",
        role="researcher",
        domain="ml",
        seniority="mid",
        headline="-",
        recent_signals=[],
        archetype_summary="-",
        embedding=None,
        fetched_at=fetched_at,
        ttl_seconds=ttl_seconds,
    )


@pytest.mark.asyncio
async def test_purge_keeps_synthetic_regardless_of_age(db_factory):
    now = datetime.utcnow()
    async with db_factory() as session:
        await memory_store.upsert_profile(
            session,
            _profile(
                id_="arch_old",
                source_kind="synthetic",
                fetched_at=now - timedelta(days=30),
                ttl_seconds=None,
            ),
        )
        purged = await memory_store.purge_expired_live_profiles(session, now=now)
        assert purged == []
        kept = await memory_store.get_profile(session, "arch_old")
        assert kept is not None


@pytest.mark.asyncio
async def test_purge_keeps_fresh_live_profile(db_factory):
    now = datetime.utcnow()
    async with db_factory() as session:
        await memory_store.upsert_profile(
            session,
            _profile(
                id_="li:fresh",
                source_kind="linkedin_rapidapi",
                fetched_at=now - timedelta(seconds=60),
                ttl_seconds=3600,
            ),
        )
        purged = await memory_store.purge_expired_live_profiles(session, now=now)
        assert purged == []
        kept = await memory_store.get_profile(session, "li:fresh")
        assert kept is not None


@pytest.mark.asyncio
async def test_purge_deletes_expired_live_profile(db_factory):
    now = datetime.utcnow()
    async with db_factory() as session:
        await memory_store.upsert_profile(
            session,
            _profile(
                id_="li:expired",
                source_kind="linkedin_rapidapi",
                fetched_at=now - timedelta(hours=2),
                ttl_seconds=3600,
            ),
        )
        purged = await memory_store.purge_expired_live_profiles(session, now=now)
        assert purged == ["li:expired"]
        gone = await memory_store.get_profile(session, "li:expired")
        assert gone is None


@pytest.mark.asyncio
async def test_purge_keeps_live_profile_with_null_ttl(db_factory):
    """A NULL ttl_seconds means "no expiry"; some operators may want this for
    a long-running pilot. The purge filter must skip such rows."""
    now = datetime.utcnow()
    async with db_factory() as session:
        await memory_store.upsert_profile(
            session,
            _profile(
                id_="li:no_ttl",
                source_kind="linkedin_rapidapi",
                fetched_at=now - timedelta(days=7),
                ttl_seconds=None,
            ),
        )
        purged = await memory_store.purge_expired_live_profiles(session, now=now)
        assert purged == []
        kept = await memory_store.get_profile(session, "li:no_ttl")
        assert kept is not None


@pytest.mark.asyncio
async def test_purge_mixed_corpus_only_expired_live_disappear(db_factory):
    now = datetime.utcnow()
    async with db_factory() as session:
        # synthetic — always kept
        await memory_store.upsert_profile(
            session,
            _profile(
                id_="arch_phd",
                source_kind="synthetic",
                fetched_at=now - timedelta(days=10),
                ttl_seconds=None,
            ),
        )
        # live, fresh
        await memory_store.upsert_profile(
            session,
            _profile(
                id_="li:fresh",
                source_kind="linkedin_rapidapi",
                fetched_at=now - timedelta(seconds=120),
                ttl_seconds=3600,
            ),
        )
        # live, expired
        await memory_store.upsert_profile(
            session,
            _profile(
                id_="li:expired_a",
                source_kind="linkedin_rapidapi",
                fetched_at=now - timedelta(hours=4),
                ttl_seconds=3600,
            ),
        )
        await memory_store.upsert_profile(
            session,
            _profile(
                id_="li:expired_b",
                source_kind="linkedin_rapidapi",
                fetched_at=now - timedelta(days=1),
                ttl_seconds=3600,
            ),
        )

        purged = await memory_store.purge_expired_live_profiles(session, now=now)
        assert sorted(purged) == ["li:expired_a", "li:expired_b"]

        survivors = sorted(p.id for p in await memory_store.list_profiles(session))
        assert survivors == ["arch_phd", "li:fresh"]


@pytest.mark.asyncio
async def test_purge_runs_clean_on_empty_db(db_factory):
    async with db_factory() as session:
        purged = await memory_store.purge_expired_live_profiles(session)
        assert purged == []
