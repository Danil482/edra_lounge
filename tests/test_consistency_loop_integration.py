"""Integration: the full live-revision trigger path runs green in-process.

`tests/test_inject_contradiction.py` proves `should_revise` flips True after
injection, but it stops at the predicate — it never drives the orchestrator's
consistency check, which is the step that actually calls `save_revision`. That
is exactly where the datetime-serialization bug lived (a `Revision` with a
`datetime` field that failed to persist).

This test exercises the whole chain end-to-end, minus the LLM:

  1. seed one cluster + one ACTIVE rule (induced in the past) + enough
     PRE-induction accepted episodes that the rule is established,
  2. hit the REAL FastAPI route `POST /simulator/inject_contradiction` through
     an in-process ASGI transport, against a REAL `Orchestrator` mounted on
     `app.state` (same event loop, so the in-memory SQLite engine is shared),
  3. call `orchestrator._check_all_rule_cs()` ONCE (the single check method, not
     the infinite `_consistency_loop`) — this is the in-process `save_revision`
     call site,
  4. assert a pending Revision persisted and is retrievable via
     `store.latest_pending_revision` (what `/state` returns), the rule flipped
     to "under_revision", and `orchestrator.active_revision_id` points at it,
  5. hit `POST /simulator/reset_injection` and assert the revision is gone, the
     rule is back to "active", and the injected episodes are deleted.

`_check_all_rule_cs` needs no LLM/network: it only creates a pending Revision
with `llm_reasoning=""` (the LLM runs lazily later in the SSE stream at
`/reflections/stream/{id}`). So nothing is stubbed here.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import schemas
from backend.config import settings
from backend.memory import store
from backend.memory.models import Base
from backend.monitor import consistency
from backend.orchestrator import Orchestrator
from backend.routers import simulator


CLUSTER_ID = "3"
RULE_ID = "R.03"


@pytest.fixture
async def db_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


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


async def _seed(factory) -> datetime:
    """One cluster, an active rule induced a day ago, and PRE-induction accepted
    episodes (mirrors seed_from_eval: episodes predate induced_at, so the rule is
    established but `should_revise` is False until contradictions are injected)."""
    induced_at = datetime.utcnow() - timedelta(hours=1)
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
        await store.save_rule(db, schemas.Rule(
            id=RULE_ID,
            cluster_id=CLUSTER_ID,
            slots=_slots(),
            induced_at=induced_at,
            induced_from_episode_ids=[],
            status="active",
        ))
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


def _build_app(orch: Orchestrator) -> FastAPI:
    """Minimal app mounting only the route under test, with a real orchestrator
    on app.state — the exact attribute the simulator router reads."""
    app = FastAPI()
    app.include_router(simulator.router)
    app.state.orchestrator = orch
    return app


@pytest.mark.asyncio
async def test_full_consistency_trigger_path_runs_green(db_factory):
    await _seed(db_factory)
    # A real Orchestrator bound to the in-memory engine. Constructed but NOT
    # start()ed — we invoke the single check method by hand, never the loop.
    orch = Orchestrator(session_factory=db_factory, profile_source=None)
    app = _build_app(orch)
    transport = ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # ── 2. hit the REAL route ───────────────────────────────────────────
        resp = await client.post(
            "/simulator/inject_contradiction", json={"cluster_id": CLUSTER_ID}
        )
        assert resp.status_code == 200, resp.text
        inject = resp.json()
        assert inject["rule_id"] == RULE_ID
        assert inject["n"] == settings.cs_window
        injected_ids = inject["injected_episode_ids"]
        assert len(injected_ids) == settings.cs_window
        # Route mutated the real orchestrator's tracking state.
        assert orch.injected_rule_id == RULE_ID
        assert orch.injected_episode_ids == injected_ids

        # Pre-condition: injection actually pushes the rule below theta.
        async with db_factory() as db:
            rule = await store.get_rule(db, RULE_ID)
            eps = await store.episodes_for_cluster(db, CLUSTER_ID)
        assert consistency.should_revise(rule, eps) is True

        # ── 3. the in-process save_revision call site ───────────────────────
        # Single check, NOT the infinite _consistency_loop. No LLM/network.
        await orch._check_all_rule_cs()

        # ── 4. assert the revision persisted without the datetime crash ─────
        async with db_factory() as db:
            pending = await store.latest_pending_revision(db)
            rule_after = await store.get_rule(db, RULE_ID)
        assert pending is not None, "save_revision must have persisted a pending Revision"
        assert pending.decision == "pending"
        assert pending.rule_id == RULE_ID
        assert pending.llm_reasoning == ""  # LLM runs lazily in the SSE stream
        assert rule_after.status == "under_revision"
        assert orch.active_revision_id == pending.id

        revision_id = pending.id

        # ── 5. reset via the REAL route — revision gone, rule restored ──────
        resp = await client.post("/simulator/reset_injection")
        assert resp.status_code == 200, resp.text
        reset = resp.json()
        assert reset["deleted_revision"] == revision_id
        assert reset["restored_rule"] == RULE_ID
        assert reset["deleted_episodes"] == settings.cs_window

    async with db_factory() as db:
        rule_final = await store.get_rule(db, RULE_ID)
        rev_gone = await store.get_revision(db, revision_id)
        eps_final = await store.episodes_for_cluster(db, CLUSTER_ID)
    assert rule_final.status == "active"
    assert rev_gone is None
    assert orch.active_revision_id is None
    assert orch.injected_episode_ids == []
    assert orch.injected_rule_id is None
    # Only the original pre-induction episodes remain.
    assert {e.id for e in eps_final} == {f"eval_ep:{i}" for i in range(4)}
