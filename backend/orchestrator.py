"""Orchestrator — all background coordination lives here as asyncio tasks.

Replaces what would have been an external workflow engine. Three loops + one
reactive hook (TASK.md §6). Each loop wraps its body in try/except so a
single-iteration failure does not kill the loop (acceptance §14).

  - tick loop          : spawn one synthetic session every `tick_seconds` while
                          no live booth-visitor session is in flight
  - consistency loop    : per active rule, compute CS over recent post-induction
                          episodes; on `should_revise` create a pending Revision
                          (the LLM stream itself runs when the operator opens
                          /reflections/stream/{revision_id})
  - factory loop        : detect clusters not covered by any active rule and
                          spawn an Agent stub once per cluster

The reactive `on_new_episode` hook re-clusters and re-checks induction
eligibility immediately after each new Episode lands; this is what gives the
demo its "rule appears mid-arc" beat (TASK.md §9).
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend import schemas
from backend.config import settings
from backend.memory import models as orm
from backend.memory import store as memory_store
from backend.memory.ids import short_id
from backend.profile_source import ProfileSource
from backend.simulator import drift as drift_mod
from backend.simulator import schedule as schedule_mod

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


class Orchestrator:
    """Owns the event loops and game-clock state for a running demo."""

    def __init__(
        self,
        session_factory: async_sessionmaker,
        profile_source: ProfileSource | None = None,
    ):
        self.session_factory = session_factory
        # ProfileSource is injected by `backend/app.py` at lifespan startup —
        # NOT defaulted here, so the orchestrator stays decoupled from any
        # concrete implementation (TASK.md §14 isolation acceptance).
        self.profile_source: ProfileSource | None = profile_source

        self.paused = False
        self._tasks: list[asyncio.Task] = []

        # Game clock + visit queue loaded from seeded_run.yaml on first start().
        self._visits: deque[schedule_mod.Visit] = deque()
        self._clock_day: int = 1
        self._clock_time: str = "09:00"

        # Drift schedulers that advance automatically from game clock.
        self._gradual_postdoc = drift_mod.GradualPostdocShift()
        self._drift_a_fired = False

        # Operator-injected archetypes (spawnable archetype rotation).
        self._injected_archetypes: list[str] = []

        # In-flight session + revision (for /reflections/stream and /state).
        self.active_revision_id: str | None = None
        self.active_session: schemas.SessionSnapshot | None = None
        self.live_session_active: bool = False

    # ── lifecycle ────────────────────────────────────────────────────────

    async def start(self) -> None:
        self._visits = deque(schedule_mod.load_schedule())
        if self._visits:
            head = self._visits[0]
            self._clock_day = head.day
            self._clock_time = head.time

        self._tasks = [
            asyncio.create_task(self._tick_loop(), name="tick"),
            asyncio.create_task(self._consistency_loop(), name="consistency"),
            asyncio.create_task(self._factory_loop(), name="factory"),
        ]
        log.info("Orchestrator started — %d visits queued", len(self._visits))

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []

    # ── public state ─────────────────────────────────────────────────────

    @property
    def clock(self) -> schemas.Clock:
        return schemas.Clock(day=self._clock_day, time=self._clock_time)

    def inject_archetype(self, archetype_id: str) -> None:
        """Add a spawnable archetype to the front of the visit queue.

        Used by the `👤+ New Segment` operator button to introduce a previously-
        unseen archetype mid-demo. The Agent Factory should pick up the new
        cluster within ~3 episodes (TASK.md §14).
        """
        self._injected_archetypes.append(archetype_id)

    # ── loops ────────────────────────────────────────────────────────────

    async def _tick_loop(self) -> None:
        while True:
            try:
                if not self.paused and not self.live_session_active:
                    await self.advance_one_visit()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("tick loop iteration failed")
            await asyncio.sleep(settings.tick_seconds)

    async def _consistency_loop(self) -> None:
        while True:
            try:
                await self._check_all_rule_cs()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("consistency loop iteration failed")
            await asyncio.sleep(10)

    async def _factory_loop(self) -> None:
        while True:
            try:
                await self._evaluate_factory()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("factory loop iteration failed")
            await asyncio.sleep(30)

    # ── reactive hook ────────────────────────────────────────────────────

    async def on_new_episode(self, ep: schemas.Episode) -> None:
        """Called after an episode is persisted. Triggers recluster + induction checks."""
        async with self.session_factory() as session:
            total = await _count_episodes(session)
            if settings.recluster_every and total % settings.recluster_every == 0:
                await self._recluster(session)
            else:
                # Always at least sync the cluster row for the episode that just landed,
                # so induction has up-to-date counts even between recluster passes.
                if ep.cluster_id is not None:
                    await self._sync_cluster_for(session, ep.cluster_id)
            await self._try_induce_all(session)

    # ── visit advancement ────────────────────────────────────────────────

    async def advance_one_visit(self) -> schemas.Episode | None:
        """Advance the game clock by one visit and run a synthetic session."""
        if self._injected_archetypes:
            archetype_id = self._injected_archetypes.pop(0)
            visit = schedule_mod.Visit(
                day=self._clock_day,
                time=self._clock_time,
                archetype_id=archetype_id,
            )
        elif self._visits:
            visit = self._visits.popleft()
            self._clock_day = visit.day
            self._clock_time = visit.time
        else:
            return None

        self._maybe_fire_scheduled_drift()

        if self.profile_source is None:
            log.debug(
                "tick: day=%d time=%s archetype=%s (no profile_source — skip)",
                visit.day,
                visit.time,
                visit.archetype_id,
            )
            return None

        # Lazy import — keeps this module out of any potential cycle and lets
        # tests construct an Orchestrator without dragging the sessions module.
        from backend.sessions import lifecycle as session_lifecycle

        async with self.session_factory() as db:
            episode = await session_lifecycle.run_synthetic_session(
                db=db,
                profile_source=self.profile_source,
                archetype_id=visit.archetype_id,
                day=visit.day,
                on_new_episode=self.on_new_episode,
            )
        log.info(
            "tick: day=%d time=%s archetype=%s episode=%s outcome=%s interest=%+d",
            visit.day,
            visit.time,
            visit.archetype_id,
            episode.id,
            episode.outcome,
            episode.final_interest,
        )
        # Clear active_session pointer after synthetic session ends.
        self.active_session = None
        return episode

    def _maybe_fire_scheduled_drift(self) -> None:
        if (
            not self._drift_a_fired
            and self._clock_day == 3
            and self._clock_time >= "10:00"
        ):
            drift_mod.ai_bubble_pops()
            self._drift_a_fired = True
            log.info("Drift A fired (ai_bubble_pops) at day=3 %s", self._clock_time)

        # Drift B is per-episode; advance one step if we're past its start.
        if self._clock_day > 2 or (self._clock_day == 2 and self._clock_time >= "14:00"):
            self._gradual_postdoc.advance()

    # ── clustering / induction / consistency / factory ───────────────────

    async def _recluster(self, session) -> None:
        """Recompute ClusterRow rows from the latest episode set.

        Phase 1B grouping is by `cluster_id` already attached to each episode
        (synthetic profiles classify into archetype-keyed pseudo-clusters via
        `pitch.classify`). Real HDBSCAN is only required when episodes arrive
        with cluster_id=None (live mode). Until then we keep the path
        deterministic and LLM-free.
        """
        episodes = await memory_store.all_episodes(session)
        by_cid: dict[str, list[schemas.Episode]] = {}
        for ep in episodes:
            if ep.cluster_id is None:
                continue
            by_cid.setdefault(ep.cluster_id, []).append(ep)

        for cid, eps in by_cid.items():
            await self._upsert_cluster_from_episodes(session, cid, eps)

    async def _sync_cluster_for(self, session, cluster_id: str) -> None:
        episodes = [
            ep
            for ep in await memory_store.all_episodes(session)
            if ep.cluster_id == cluster_id
        ]
        if episodes:
            await self._upsert_cluster_from_episodes(session, cluster_id, episodes)

    async def _upsert_cluster_from_episodes(
        self, session, cluster_id: str, episodes: list[schemas.Episode]
    ) -> None:
        from backend.clustering import cluster as clustering_mod

        existing = await memory_store.get_cluster(session, cluster_id)
        accepted = sum(1 for ep in episodes if ep.outcome == "accepted")
        rejected = sum(1 for ep in episodes if ep.outcome == "rejected")
        success_ratio = (
            accepted / (accepted + rejected) if (accepted + rejected) > 0 else 0.0
        )

        # Centroid: mean of available episode embeddings; zero-vec when none.
        embeds = [ep.summary_embedding for ep in episodes if ep.summary_embedding]
        centroid: list[float] = []
        if embeds:
            n = len(embeds[0])
            centroid = [
                sum(e[i] for e in embeds) / len(embeds) for i in range(n)
            ]

        label = existing.label if existing and existing.label else cluster_id

        cluster = schemas.Cluster(
            id=cluster_id,
            label=label,
            profile_ids=sorted({ep.profile_id for ep in episodes}),
            episode_ids=[ep.id for ep in episodes],
            centroid_embedding=centroid,
            # `size` is number of *episodes* in the cluster — TASK.md §2 says
            # induction needs n_min=5 episodes, not 5 distinct profiles. The
            # synthetic demo runs the same archetype repeatedly, so distinct-
            # profile counts stay at 1 even after many episodes.
            size=len(episodes),
            success_ratio=success_ratio,
            created_at=existing.created_at if existing else datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )
        await memory_store.upsert_cluster(session, cluster)
        # success_ratio is the consumer the test below is referencing.
        _ = clustering_mod  # imported for the live path; kept reachable.

    async def _try_induce_all(self, session) -> None:
        """For every cluster with no active rule, induce one if eligible."""
        from backend.induction import induce as induce_mod

        clusters = await memory_store.list_clusters(session)
        active_rules = await memory_store.list_rules(session, status="active")
        covered = {r.cluster_id for r in active_rules}

        for cluster in clusters:
            if cluster.id in covered:
                continue
            try:
                induce_mod.check_eligibility(cluster)
            except induce_mod.NotEligible:
                continue

            cluster_eps = await memory_store.episodes_for_cluster(session, cluster.id)
            existing_ids = await memory_store.existing_rule_ids(session)
            try:
                rule = await induce_mod.induce_rule(
                    cluster=cluster,
                    cluster_episodes=cluster_eps,
                    existing_rule_ids=existing_ids,
                )
            except Exception:  # noqa: BLE001
                log.exception("LLM induction failed for cluster=%s; using fallback", cluster.id)
                rule = _fallback_induce(cluster, cluster_eps, existing_ids)

            await memory_store.save_rule(session, rule)
            log.info("induced rule=%s cluster=%s", rule.id, cluster.id)

    async def _check_all_rule_cs(self) -> None:
        """Per active rule → compute CS → if should_revise and no pending
        revision exists, create a pending Revision row (the LLM stream itself
        runs lazily when the SSE endpoint is hit)."""
        from backend.monitor import consistency as monitor_mod

        async with self.session_factory() as session:
            active_rules = await memory_store.list_rules(session, status="active")
            for rule in active_rules:
                cluster_eps = await memory_store.episodes_for_cluster(
                    session, rule.cluster_id
                )
                cs = monitor_mod.compute_cs(rule, cluster_eps)
                if not monitor_mod.should_revise(rule, cluster_eps):
                    continue
                if await memory_store.pending_revision_for_rule(session, rule.id):
                    continue

                contradicting = [
                    ep
                    for ep in cluster_eps
                    if ep.timestamp > rule.induced_at
                    and ep.outcome != "accepted"
                ][-settings.cs_window:]

                rev = schemas.Revision(
                    id=short_id("rev"),
                    rule_id=rule.id,
                    triggered_at=datetime.utcnow(),
                    contradicting_episode_ids=[ep.id for ep in contradicting],
                    llm_reasoning="",
                    proposed_rule=rule.model_copy(),
                    decision="pending",
                    resolved_at=None,
                )
                await memory_store.save_revision(session, rev)
                await memory_store.update_rule(
                    session, rule.id, status="under_revision"
                )
                self.active_revision_id = rev.id
                log.info(
                    "consistency loop: rule=%s cs=%.2f → revision=%s",
                    rule.id,
                    cs,
                    rev.id,
                )

    async def _evaluate_factory(self) -> None:
        """Per cluster with no active rule and no agent → spawn AgentRow."""
        from backend.factory import factory as factory_mod

        async with self.session_factory() as session:
            clusters = await memory_store.list_clusters(session)
            active_rules = await memory_store.list_rules(session, status="active")
            uncovered = factory_mod.find_uncovered_cluster(clusters, active_rules)
            if uncovered is None:
                return
            if await memory_store.cluster_has_agent(session, uncovered.id):
                return
            agent = factory_mod.spawn_agent(
                uncovered,
                description=f"specialist for cluster {uncovered.id}",
            )
            await memory_store.save_agent(session, agent)
            log.info(
                "factory: spawned agent=%s for cluster=%s",
                agent.id,
                uncovered.id,
            )


# ── Fallback induction (LLM-free) ─────────────────────────────────────────

def _fallback_induce(
    cluster: schemas.Cluster,
    cluster_episodes: list[schemas.Episode],
    existing_rule_ids: list[str],
) -> schemas.Rule:
    """Most-frequent slot value among accepted episodes → a static rule.

    Used when the LLM is offline or returns malformed JSON. Demos still
    progress; rules look human-induced because they reflect the cluster's
    most-common winning combo.
    """
    from backend.memory.ids import next_rule_id

    accepted = [ep for ep in cluster_episodes if ep.outcome == "accepted"]
    pool = accepted or cluster_episodes

    def _mode(field: str) -> str:
        from collections import Counter

        counter: Counter[str] = Counter(getattr(ep.pitch_strategy, field) for ep in pool)
        return counter.most_common(1)[0][0]

    slots = [
        schemas.RuleSlot(name="framing", kind="static", value=_mode("framing")),
        schemas.RuleSlot(name="tone", kind="static", value=_mode("tone")),
        schemas.RuleSlot(name="opener_type", kind="static", value=_mode("opener_type")),
        schemas.RuleSlot(name="word_target", kind="static", value=_mode("word_target")),
        schemas.RuleSlot(name="ask_size", kind="static", value=_mode("ask_size")),
    ]
    return schemas.Rule(
        id=next_rule_id(existing_rule_ids),
        cluster_id=cluster.id,
        slots=slots,
        induced_at=datetime.utcnow(),
        induced_from_episode_ids=[ep.id for ep in pool],
        status="active",
        deprecated_by=None,
        cs_history=[],
    )


# ── small helpers ─────────────────────────────────────────────────────────

async def _count_episodes(session) -> int:
    result = await session.execute(select(orm.EpisodeRow.id))
    return len(result.scalars().all())
