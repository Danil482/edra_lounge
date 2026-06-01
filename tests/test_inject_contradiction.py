"""Demo-theater contradiction injection — reversible live-revision trigger.

The seeded demo DB has real clusters whose episodes are all PRE-induction, so
`should_revise` never fires on its own. `POST /simulator/inject_contradiction`
inserts post-induction rejected episodes against a seeded rule's current
strategy, pushing CS below theta so the consistency loop WILL open a revision.
`POST /simulator/reset_injection` undoes it.

Tests drive the router functions directly against an in-memory SQLite DB with a
minimal fake orchestrator carrying just the state the endpoints touch.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import schemas
from backend.config import settings
from backend.memory import store
from backend.memory.models import Base
from backend.monitor import consistency
from backend.routers import simulator


@pytest.fixture
async def db_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


class FakeOrchestrator:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.injected_episode_ids: list[str] = []
        self.injected_rule_id: str | None = None
        self.active_revision_id: str | None = None


class FakeApp:
    def __init__(self, orch):
        self.state = type("S", (), {"orchestrator": orch})()


class FakeRequest:
    def __init__(self, orch):
        self.app = FakeApp(orch)


CLUSTER_ID = "3"
RULE_ID = "R.03"


def _strategy() -> schemas.PitchStrategy:
    return schemas.PitchStrategy(
        framing="knowledge-share",
        tone="warm",
        opener_type="reference-to-signal",
        word_target="medium",
        ask_size="trial",
    )


def _slots() -> list[schemas.RuleSlot]:
    s = _strategy()
    return [
        schemas.RuleSlot(name="framing", kind="static", value=s.framing),
        schemas.RuleSlot(name="tone", kind="static", value=s.tone),
        schemas.RuleSlot(name="opener_type", kind="static", value=s.opener_type),
        schemas.RuleSlot(name="word_target", kind="static", value=s.word_target),
        schemas.RuleSlot(name="ask_size", kind="static", value=s.ask_size),
    ]


async def _seed(factory, *, with_episodes: bool = True, with_rule: bool = True):
    """Seed one cluster, an active rule induced in the past, and PRE-induction
    accepted episodes (mirrors seed_from_eval: all episodes predate induced_at)."""
    induced_at = datetime.utcnow()
    past = induced_at - timedelta(days=1)
    async with factory() as db:
        await store.upsert_profile(db, schemas.Profile(
            id="eval:0",
            source_kind="synthetic",
            source_identifier="seed:0",
            name="seed",
            role="Director",
            domain="ACME",
            seniority="senior",
            headline="Director at ACME",
            archetype_summary="seed segment",
            fetched_at=past,
            cluster_id=CLUSTER_ID,
        ))
        if with_rule:
            await store.save_rule(db, schemas.Rule(
                id=RULE_ID,
                cluster_id=CLUSTER_ID,
                slots=_slots(),
                induced_at=induced_at,
                induced_from_episode_ids=[],
                status="active",
            ))
        if with_episodes:
            for i in range(4):
                await store.save_episode(db, schemas.Episode(
                    id=f"eval_ep:{i}",
                    timestamp=past,
                    day=1,
                    profile_id="eval:0",
                    cluster_id=CLUSTER_ID,
                    pitch_strategy=_strategy(),
                    dialogue=[],
                    final_interest=4,
                    outcome="accepted",
                    summary="seeded pre-induction win",
                    summary_embedding=[0.1] * 8,
                    rule_applied_top=RULE_ID,
                ))
    return induced_at


# ── inject_contradiction ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_inject_inserts_post_induction_rejected_episodes(db_factory):
    await _seed(db_factory)
    orch = FakeOrchestrator(db_factory)

    result = await simulator.inject_contradiction(
        simulator.InjectContradictionIn(cluster_id=CLUSTER_ID),
        FakeRequest(orch),
    )

    assert result["ok"] is True
    assert result["cluster_id"] == CLUSTER_ID
    assert result["rule_id"] == RULE_ID
    assert result["n"] == settings.cs_window
    assert len(result["injected_episode_ids"]) == settings.cs_window
    assert orch.injected_episode_ids == result["injected_episode_ids"]
    assert orch.injected_rule_id == RULE_ID

    async with db_factory() as db:
        rule = await store.get_rule(db, RULE_ID)
        eps = await store.episodes_for_cluster(db, CLUSTER_ID)
    injected = [e for e in eps if e.id in result["injected_episode_ids"]]
    assert len(injected) == settings.cs_window
    for e in injected:
        assert e.outcome == "rejected"
        assert e.final_interest < 0
        assert e.timestamp > rule.induced_at
        assert e.cluster_id == CLUSTER_ID
        assert e.profile_id == "eval:0"
        assert e.summary_embedding  # carried a plausible embedding


@pytest.mark.asyncio
async def test_inject_makes_should_revise_true(db_factory):
    await _seed(db_factory)
    orch = FakeOrchestrator(db_factory)

    async with db_factory() as db:
        rule = await store.get_rule(db, RULE_ID)
        eps_before = await store.episodes_for_cluster(db, CLUSTER_ID)
    assert consistency.should_revise(rule, eps_before) is False

    await simulator.inject_contradiction(
        simulator.InjectContradictionIn(cluster_id=CLUSTER_ID),
        FakeRequest(orch),
    )

    async with db_factory() as db:
        eps_after = await store.episodes_for_cluster(db, CLUSTER_ID)
    assert consistency.should_revise(rule, eps_after) is True


@pytest.mark.asyncio
async def test_inject_no_cluster_picks_largest_ruled_cluster(db_factory):
    """With cluster_id omitted, inject targets the active-ruled cluster that
    has the most episodes."""
    induced_at = await _seed(db_factory)  # cluster "3", rule R.03, 4 episodes

    # A second active-ruled cluster with MORE episodes — should be chosen.
    big_cluster = "7"
    big_rule = "R.07"
    past = induced_at - timedelta(days=1)
    async with db_factory() as db:
        await store.save_rule(db, schemas.Rule(
            id=big_rule,
            cluster_id=big_cluster,
            slots=_slots(),
            induced_at=induced_at,
            induced_from_episode_ids=[],
            status="active",
        ))
        for i in range(9):
            await store.save_episode(db, schemas.Episode(
                id=f"big_ep:{i}",
                timestamp=past,
                day=1,
                profile_id="eval:0",
                cluster_id=big_cluster,
                pitch_strategy=_strategy(),
                dialogue=[],
                final_interest=4,
                outcome="accepted",
                summary="big cluster win",
                summary_embedding=[0.2] * 8,
                rule_applied_top=big_rule,
            ))

    orch = FakeOrchestrator(db_factory)
    result = await simulator.inject_contradiction(
        simulator.InjectContradictionIn(),  # no cluster_id
        FakeRequest(orch),
    )

    assert result["ok"] is True
    assert result["cluster_id"] == big_cluster
    assert result["rule_id"] == big_rule
    assert orch.injected_rule_id == big_rule

    async with db_factory() as db:
        eps = await store.episodes_for_cluster(db, big_cluster)
    injected = [e for e in eps if e.id in result["injected_episode_ids"]]
    assert len(injected) == settings.cs_window
    for e in injected:
        assert e.outcome == "rejected"
        assert e.cluster_id == big_cluster


@pytest.mark.asyncio
async def test_inject_no_cluster_404_when_no_ruled_cluster(db_factory):
    await _seed(db_factory, with_rule=False)  # episodes exist but no active rule
    orch = FakeOrchestrator(db_factory)
    with pytest.raises(HTTPException) as exc:
        await simulator.inject_contradiction(
            simulator.InjectContradictionIn(),
            FakeRequest(orch),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_inject_respects_explicit_n(db_factory):
    await _seed(db_factory)
    orch = FakeOrchestrator(db_factory)
    result = await simulator.inject_contradiction(
        simulator.InjectContradictionIn(cluster_id=CLUSTER_ID, n=3),
        FakeRequest(orch),
    )
    assert result["n"] == 3
    assert len(result["injected_episode_ids"]) == 3


@pytest.mark.asyncio
async def test_inject_404_unknown_cluster(db_factory):
    await _seed(db_factory)
    orch = FakeOrchestrator(db_factory)
    with pytest.raises(HTTPException) as exc:
        await simulator.inject_contradiction(
            simulator.InjectContradictionIn(cluster_id="999"),
            FakeRequest(orch),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_inject_404_cluster_without_active_rule(db_factory):
    await _seed(db_factory, with_rule=False)
    orch = FakeOrchestrator(db_factory)
    with pytest.raises(HTTPException) as exc:
        await simulator.inject_contradiction(
            simulator.InjectContradictionIn(cluster_id=CLUSTER_ID),
            FakeRequest(orch),
        )
    assert exc.value.status_code == 404


# ── reset_injection ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reset_deletes_only_injected_episodes(db_factory):
    await _seed(db_factory)
    orch = FakeOrchestrator(db_factory)
    inject = await simulator.inject_contradiction(
        simulator.InjectContradictionIn(cluster_id=CLUSTER_ID),
        FakeRequest(orch),
    )
    injected_ids = set(inject["injected_episode_ids"])

    result = await simulator.reset_injection(FakeRequest(orch))

    assert result["deleted_episodes"] == settings.cs_window
    assert orch.injected_episode_ids == []
    assert orch.injected_rule_id is None

    async with db_factory() as db:
        eps = await store.episodes_for_cluster(db, CLUSTER_ID)
    remaining = {e.id for e in eps}
    assert injected_ids.isdisjoint(remaining)
    assert remaining == {f"eval_ep:{i}" for i in range(4)}


@pytest.mark.asyncio
async def test_reset_deletes_pending_revision_and_restores_rule(db_factory):
    induced_at = await _seed(db_factory)
    orch = FakeOrchestrator(db_factory)
    await simulator.inject_contradiction(
        simulator.InjectContradictionIn(cluster_id=CLUSTER_ID),
        FakeRequest(orch),
    )

    # Simulate the consistency loop having opened a pending revision.
    async with db_factory() as db:
        rev = schemas.Revision(
            id="rev_abc",
            rule_id=RULE_ID,
            triggered_at=datetime.utcnow(),
            contradicting_episode_ids=list(orch.injected_episode_ids),
            llm_reasoning="",
            proposed_rule=schemas.Rule(
                id=RULE_ID, cluster_id=CLUSTER_ID, slots=_slots(), induced_at=induced_at
            ),
            decision="pending",
        )
        await store.save_revision(db, rev)
        await store.update_rule(db, RULE_ID, status="under_revision")
    orch.active_revision_id = "rev_abc"

    result = await simulator.reset_injection(FakeRequest(orch))

    assert result["deleted_revision"] == "rev_abc"
    assert result["restored_rule"] == RULE_ID
    assert orch.active_revision_id is None

    async with db_factory() as db:
        rule = await store.get_rule(db, RULE_ID)
        rev_gone = await store.get_revision(db, "rev_abc")
    assert rule.status == "active"
    assert rev_gone is None


@pytest.mark.asyncio
async def test_reset_idempotent(db_factory):
    await _seed(db_factory)
    orch = FakeOrchestrator(db_factory)
    await simulator.inject_contradiction(
        simulator.InjectContradictionIn(cluster_id=CLUSTER_ID),
        FakeRequest(orch),
    )
    first = await simulator.reset_injection(FakeRequest(orch))
    assert first["deleted_episodes"] == settings.cs_window

    second = await simulator.reset_injection(FakeRequest(orch))
    assert second["deleted_episodes"] == 0
    assert second["deleted_revision"] is None
    assert second["restored_rule"] is None


@pytest.mark.asyncio
async def test_reset_409_when_revision_already_resolved(db_factory):
    induced_at = await _seed(db_factory)
    orch = FakeOrchestrator(db_factory)
    await simulator.inject_contradiction(
        simulator.InjectContradictionIn(cluster_id=CLUSTER_ID),
        FakeRequest(orch),
    )

    async with db_factory() as db:
        await store.save_revision(db, schemas.Revision(
            id="rev_done",
            rule_id=RULE_ID,
            triggered_at=datetime.utcnow(),
            contradicting_episode_ids=[],
            llm_reasoning="",
            proposed_rule=schemas.Rule(
                id=RULE_ID, cluster_id=CLUSTER_ID, slots=_slots(), induced_at=induced_at
            ),
            decision="accepted",
        ))

    with pytest.raises(HTTPException) as exc:
        await simulator.reset_injection(FakeRequest(orch))
    assert exc.value.status_code == 409

    # Episodes still cleaned up despite the raise.
    async with db_factory() as db:
        eps = await store.episodes_for_cluster(db, CLUSTER_ID)
    assert {e.id for e in eps} == {f"eval_ep:{i}" for i in range(4)}
    assert orch.injected_episode_ids == []
    assert orch.injected_rule_id is None
