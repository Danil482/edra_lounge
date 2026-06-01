"""Multi-turn pitch sessions — TASK.md §1.2 / §8.

Drives the lifecycle module directly (no FastAPI) against an in-memory SQLite
DB to keep tests fast and offline. Verifies:
  - start_session resolves a synthetic Profile, classifies, persists, and
    returns the first DialogueStep
  - take_turn applies visitor_choice + interest_delta_override correctly
  - termination at ±5 interest produces the right outcome
  - run_synthetic_session plays a full episode through to persistence and
    fires the on_new_episode hook
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import schemas
from backend.memory.models import Base
from backend.profile_source.synthetic import SyntheticProfileSource
from backend.sessions import lifecycle, store as session_store_mod


@pytest.fixture
async def db_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture(autouse=True)
def reset_store():
    session_store_mod.session_store.reset()
    yield
    session_store_mod.session_store.reset()


@pytest.fixture
def profile_source():
    return SyntheticProfileSource()


@pytest.fixture(autouse=True)
def stub_llm(monkeypatch):
    """Block any actual LLM call for the entire session test suite."""

    async def _no_complete(*args, **kwargs):
        raise RuntimeError("LLM disabled in tests")

    async def _no_stream(*args, **kwargs):
        raise RuntimeError("LLM disabled in tests")
        yield  # keep generator-shaped

    monkeypatch.setattr("backend.pitch.generate.llm.complete", _no_complete)
    monkeypatch.setattr("backend.sessions.lifecycle.llm.complete", _no_complete)
    yield


# ── start_session ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_session_returns_first_step_and_persists_profile(db_factory, profile_source):
    async with db_factory() as db:
        sess, first_step = await lifecycle.start_session(
            db=db,
            profile_source=profile_source,
            source_kind="synthetic",
            identifier="arch_phd_nlp_introvert",
            day=1,
        )
    assert sess.profile.id == "arch_phd_nlp_introvert"
    assert sess.cluster_id is None  # cold start: no rules → KNN returns None → improvise
    assert sess.applicable_rule_id is None
    assert first_step.turn == 1
    assert first_step.agent_reply  # template path filled it
    assert sess.dialogue == [first_step]
    # active session pointer set
    assert session_store_mod.session_store.active_id == sess.id


@pytest.mark.asyncio
async def test_start_session_unknown_archetype_raises(db_factory, profile_source):
    from backend.profile_source import ProfileNotFound

    async with db_factory() as db:
        with pytest.raises(ProfileNotFound):
            await lifecycle.start_session(
                db=db,
                profile_source=profile_source,
                source_kind="synthetic",
                identifier="arch_does_not_exist",
                day=1,
            )


@pytest.mark.asyncio
async def test_start_session_kind_mismatch_raises_unavailable(db_factory, profile_source):
    from backend.profile_source import ProfileSourceUnavailable

    async with db_factory() as db:
        with pytest.raises(ProfileSourceUnavailable):
            await lifecycle.start_session(
                db=db,
                profile_source=profile_source,
                source_kind="linkedin_rapidapi",  # active is synthetic
                identifier="arch_phd_nlp_introvert",
                day=1,
            )


# ── take_turn ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_take_turn_records_choice_and_advances(db_factory, profile_source):
    async with db_factory() as db:
        sess, _first = await lifecycle.start_session(
            db=db,
            profile_source=profile_source,
            source_kind="synthetic",
            identifier="arch_phd_nlp_introvert",
            day=1,
        )
        sess, step, terminated = await lifecycle.take_turn(
            db=db,
            session_id=sess.id,
            visitor_choice="positive",
            interest_delta_override=1,
        )
    assert not terminated
    assert step.turn == 2
    assert sess.interest == 1
    # First step now has visitor_choice + interest_delta written through.
    assert sess.dialogue[0].visitor_choice == "positive"
    assert sess.dialogue[0].interest_delta == 1


@pytest.mark.asyncio
async def test_take_turn_terminates_at_plus_five(db_factory, profile_source):
    async with db_factory() as db:
        sess, _ = await lifecycle.start_session(
            db=db,
            profile_source=profile_source,
            source_kind="synthetic",
            identifier="arch_phd_nlp_introvert",
            day=1,
        )
        terminated = False
        for _ in range(5):
            sess, _step, terminated = await lifecycle.take_turn(
                db=db,
                session_id=sess.id,
                visitor_choice="positive",
                interest_delta_override=1,
            )
            if terminated:
                break
    assert terminated
    assert sess.interest == 5
    assert sess.outcome == "accepted"


@pytest.mark.asyncio
async def test_take_turn_terminates_at_minus_five(db_factory, profile_source):
    async with db_factory() as db:
        sess, _ = await lifecycle.start_session(
            db=db,
            profile_source=profile_source,
            source_kind="synthetic",
            identifier="arch_phd_nlp_introvert",
            day=1,
        )
        terminated = False
        for _ in range(5):
            sess, _step, terminated = await lifecycle.take_turn(
                db=db,
                session_id=sess.id,
                visitor_choice="negative",
                interest_delta_override=-1,
            )
            if terminated:
                break
    assert terminated
    assert sess.interest == -5
    assert sess.outcome == "rejected"


@pytest.mark.asyncio
async def test_take_turn_unknown_session_raises(db_factory):
    async with db_factory() as db:
        with pytest.raises(lifecycle.SessionNotFound):
            await lifecycle.take_turn(
                db=db,
                session_id="sess_nope",
                visitor_choice="positive",
            )


# ── end_session ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_end_session_persists_episode_and_fires_hook(db_factory, profile_source):
    fired: list[schemas.Episode] = []

    async def hook(ep: schemas.Episode) -> None:
        fired.append(ep)

    async with db_factory() as db:
        sess, _ = await lifecycle.start_session(
            db=db,
            profile_source=profile_source,
            source_kind="synthetic",
            identifier="arch_phd_nlp_introvert",
            day=2,
        )
        for _ in range(5):
            sess, _step, terminated = await lifecycle.take_turn(
                db=db,
                session_id=sess.id,
                visitor_choice="positive",
                interest_delta_override=1,
            )
            if terminated:
                break
        episode = await lifecycle.end_session(
            db=db,
            session_id=sess.id,
            on_new_episode=hook,
        )

    assert episode.day == 2
    assert episode.outcome == "accepted"
    assert episode.final_interest == 5
    assert len(episode.dialogue) >= 5
    assert episode.summary  # fallback summary kicked in
    assert fired == [episode]
    # active pointer cleared
    assert session_store_mod.session_store.active_id is None


# ── run_synthetic_session ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_synthetic_session_drives_full_episode(db_factory, profile_source):
    """Driver runs the visit through preferences end-to-end and persists the Episode.

    With no rule applicable the agent uses the improvise default strategy,
    which is intentionally a "moderately curious researcher" baseline — not
    the archetype-best combo. So PhD accumulates positive turns early but
    fatigue (-0.1 per past step) drags later turns, and the demo ends in
    `exploring` or `abandoned` rather than `accepted`. That mismatch is the
    very signal a future induced rule is supposed to fix.
    """
    async with db_factory() as db:
        episode = await lifecycle.run_synthetic_session(
            db=db,
            profile_source=profile_source,
            archetype_id="arch_phd_nlp_introvert",
            day=1,
        )
    assert episode.outcome in ("accepted", "exploring", "abandoned", "rejected")
    assert -5 <= episode.final_interest <= 5
    assert 1 <= len(episode.dialogue) <= 7
    for step in episode.dialogue:
        assert step.visitor_choice is not None
    # Persistence sanity — the episode landed in the DB with summary text.
    assert episode.summary
    assert episode.profile_id == "arch_phd_nlp_introvert"


@pytest.mark.asyncio
async def test_run_synthetic_session_with_best_combo_accepts(db_factory, profile_source):
    """If an active rule pinned the archetype-best combo, the session accepts.

    We pre-seed a static Rule for arch_phd_nlp_introvert with the
    knowledge-share/socratic/question/medium/co-author combination
    (+0.40 combo bonus → +2 interest per turn before fatigue).
    """
    from datetime import datetime
    from backend.memory import store as memory_store

    rule = schemas.Rule(
        id="R.01",
        cluster_id="arch_phd_nlp_introvert",
        slots=[
            schemas.RuleSlot(name="framing", kind="static", value="knowledge-share"),
            schemas.RuleSlot(name="tone", kind="static", value="socratic"),
            schemas.RuleSlot(name="opener_type", kind="static", value="question"),
            schemas.RuleSlot(name="word_target", kind="static", value="medium"),
            schemas.RuleSlot(name="ask_size", kind="static", value="co-author"),
        ],
        induced_at=datetime.utcnow(),
    )
    async with db_factory() as db:
        await memory_store.save_rule(db, rule)
        episode = await lifecycle.run_synthetic_session(
            db=db,
            profile_source=profile_source,
            archetype_id="arch_phd_nlp_introvert",
            day=1,
        )
    assert episode.outcome == "accepted"
    assert episode.final_interest == 5
    assert episode.rule_applied_top == "R.01"


# ── repeated sessions (booth: start → end → start) ─────────────────────────

@pytest.mark.asyncio
async def test_start_end_start_same_profile_succeeds(db_factory, profile_source):
    """The booth runs back-to-back live visits: a session must be startable
    again with the SAME identifier after the previous one ended. Regression
    guard for the second-conversation bug — `upsert_profile` must not collide
    and the active-session pointer must be reusable."""
    async with db_factory() as db:
        sess1, first1 = await lifecycle.start_session(
            db=db,
            profile_source=profile_source,
            source_kind="synthetic",
            identifier="arch_phd_nlp_introvert",
            day=1,
        )
        assert session_store_mod.session_store.active_id == sess1.id

        await lifecycle.end_session(db=db, session_id=sess1.id)
        assert session_store_mod.session_store.active_id is None

        sess2, first2 = await lifecycle.start_session(
            db=db,
            profile_source=profile_source,
            source_kind="synthetic",
            identifier="arch_phd_nlp_introvert",
            day=1,
        )

    assert sess2.id != sess1.id
    assert first2.turn == 1
    assert first2.agent_reply
    assert session_store_mod.session_store.active_id == sess2.id


@pytest.mark.asyncio
async def test_start_resolve_start_same_profile_succeeds(db_factory, profile_source):
    """Same as above but the first session ends via explicit resolve(accept)."""
    async with db_factory() as db:
        sess1, _ = await lifecycle.start_session(
            db=db,
            profile_source=profile_source,
            source_kind="synthetic",
            identifier="arch_postdoc_cv_ambitious",
            day=1,
        )
        episode, outcome = await lifecycle.resolve_session(
            db=db,
            session_id=sess1.id,
            decision="accept",
        )
        assert outcome == "accepted"
        assert session_store_mod.session_store.active_id is None

        sess2, first2 = await lifecycle.start_session(
            db=db,
            profile_source=profile_source,
            source_kind="synthetic",
            identifier="arch_postdoc_cv_ambitious",
            day=1,
        )

    assert sess2.id != sess1.id
    assert first2.agent_reply
    assert session_store_mod.session_store.active_id == sess2.id


@pytest.mark.asyncio
async def test_run_synthetic_session_rejects_non_synthetic_source(db_factory):
    from backend.profile_source.linkedin_rapidapi import LinkedInRapidAPISource

    src = LinkedInRapidAPISource()
    async with db_factory() as db:
        with pytest.raises(ValueError):
            await lifecycle.run_synthetic_session(
                db=db,
                profile_source=src,
                archetype_id="arch_phd_nlp_introvert",
                day=1,
            )
