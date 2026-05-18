"""Feature 3: Email auth / visitors — POST /api/visitors.

Tests the visitor registration endpoint: valid creation, upsert on duplicate,
email normalization, validation of invalid formats, and the VisitorRow ORM model.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.memory.models import Base, VisitorRow
from backend.routers.visitors import EMAIL_RE, VisitorIn, VisitorOut, register_visitor


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


# ── POST /api/visitors — valid email ────────────────────────────────────

@pytest.mark.asyncio
async def test_register_visitor_valid_email(db_session):
    body = VisitorIn(email="alice@example.com")
    result = await register_visitor(body=body, db=db_session)
    assert isinstance(result, VisitorOut)
    assert result.email == "alice@example.com"
    assert result.id >= 1
    assert result.created_at


@pytest.mark.asyncio
async def test_register_visitor_returns_id_email_created_at(db_session):
    body = VisitorIn(email="bob@example.com")
    result = await register_visitor(body=body, db=db_session)
    assert hasattr(result, "id")
    assert hasattr(result, "email")
    assert hasattr(result, "created_at")


# ── Duplicate email → upsert ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_visitor_duplicate_returns_existing(db_session):
    body = VisitorIn(email="dup@example.com")
    first = await register_visitor(body=body, db=db_session)
    second = await register_visitor(body=body, db=db_session)
    assert first.id == second.id
    assert first.email == second.email


# ── Email normalization ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_visitor_normalizes_uppercase(db_session):
    body = VisitorIn(email="Alice@Example.COM")
    result = await register_visitor(body=body, db=db_session)
    assert result.email == "alice@example.com"


@pytest.mark.asyncio
async def test_register_visitor_strips_whitespace(db_session):
    body = VisitorIn(email="  carol@example.com  ")
    result = await register_visitor(body=body, db=db_session)
    assert result.email == "carol@example.com"


@pytest.mark.asyncio
async def test_register_visitor_uppercase_duplicate_matches_lowercase(db_session):
    body_lower = VisitorIn(email="dedup@example.com")
    first = await register_visitor(body=body_lower, db=db_session)
    body_upper = VisitorIn(email="DEDUP@EXAMPLE.COM")
    second = await register_visitor(body=body_upper, db=db_session)
    assert first.id == second.id


# ── Invalid email → 422 ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_visitor_invalid_no_at_sign(db_session):
    from fastapi import HTTPException
    body = VisitorIn(email="notanemail")
    with pytest.raises(HTTPException) as exc_info:
        await register_visitor(body=body, db=db_session)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_register_visitor_invalid_no_domain(db_session):
    from fastapi import HTTPException
    body = VisitorIn(email="user@")
    with pytest.raises(HTTPException) as exc_info:
        await register_visitor(body=body, db=db_session)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_register_visitor_invalid_no_tld(db_session):
    from fastapi import HTTPException
    body = VisitorIn(email="user@domain")
    with pytest.raises(HTTPException) as exc_info:
        await register_visitor(body=body, db=db_session)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_register_visitor_invalid_empty_string(db_session):
    from fastapi import HTTPException
    body = VisitorIn(email="")
    with pytest.raises(HTTPException) as exc_info:
        await register_visitor(body=body, db=db_session)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_register_visitor_invalid_spaces_only(db_session):
    from fastapi import HTTPException
    body = VisitorIn(email="   ")
    with pytest.raises(HTTPException) as exc_info:
        await register_visitor(body=body, db=db_session)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_register_visitor_invalid_double_at(db_session):
    from fastapi import HTTPException
    body = VisitorIn(email="user@@example.com")
    with pytest.raises(HTTPException) as exc_info:
        await register_visitor(body=body, db=db_session)
    assert exc_info.value.status_code == 422


# ── EMAIL_RE regex ──────────────────────────────────────────────────────

def test_email_regex_accepts_standard_email():
    assert EMAIL_RE.match("user@example.com")


def test_email_regex_accepts_dotted_local():
    assert EMAIL_RE.match("first.last@example.com")


def test_email_regex_accepts_plus_addressing():
    assert EMAIL_RE.match("user+tag@example.com")


def test_email_regex_rejects_no_at():
    assert not EMAIL_RE.match("userexample.com")


def test_email_regex_rejects_no_tld():
    assert not EMAIL_RE.match("user@domain")


def test_email_regex_rejects_empty():
    assert not EMAIL_RE.match("")


def test_email_regex_rejects_single_char_tld():
    assert not EMAIL_RE.match("user@domain.a")


# ── VisitorRow model ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_visitor_row_created_in_db(db_session):
    visitor = VisitorRow(email="dbtest@example.com", created_at=datetime.utcnow())
    db_session.add(visitor)
    await db_session.commit()
    await db_session.refresh(visitor)
    assert visitor.id is not None
    assert visitor.email == "dbtest@example.com"
    assert visitor.name is None
    assert visitor.session_id is None


@pytest.mark.asyncio
async def test_visitor_row_email_unique_constraint(db_session):
    from sqlalchemy.exc import IntegrityError
    v1 = VisitorRow(email="unique@example.com", created_at=datetime.utcnow())
    db_session.add(v1)
    await db_session.commit()

    v2 = VisitorRow(email="unique@example.com", created_at=datetime.utcnow())
    db_session.add(v2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
