"""Orchestrator — all background coordination lives here as asyncio tasks.

Replaces what would have been an external workflow engine. Kept deliberately
small: three loops + one reactive hook. Each loop wraps its body in try/except
so a single-iteration failure does not kill the loop (see acceptance §14).
"""

import asyncio
import logging
from collections import deque
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend import schemas
from backend.clustering import cluster as clustering
from backend.config import settings
from backend.factory import factory
from backend.induction import induce as induction
from backend.memory import models as orm
from backend.memory import store
from backend.memory.ids import short_id
from backend.monitor import consistency
from backend.simulator import drift as drift_mod
from backend.simulator import schedule as schedule_mod
from backend.simulator import tick as sim_tick

log = logging.getLogger(__name__)


class Orchestrator:
    """Owns the event loops and game-clock state for a running demo."""

    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory
        self.paused = False
        self._tasks: list[asyncio.Task] = []

        # Game clock + visit queue loaded from seeded_run.yaml on first call to
        # start(); kept as a deque so advance / peek is O(1).
        self._visits: deque[schedule_mod.Visit] = deque()
        self._clock_day: int = 1
        self._clock_time: str = "09:00"

        # Drift schedulers that advance automatically from game clock.
        self._gradual_postdoc = drift_mod.GradualPostdocShift()
        self._drift_a_fired = False

        # Injected-at-runtime personas (e.g. VC-investor after "New Segment").
        self._injected_personas: set[str] = set()

        # In-flight revision (for /reflections/stream).
        self.active_revision_id: str | None = None

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

    def inject_persona(self, persona_id: str) -> None:
        self._injected_personas.add(persona_id)

    # ── loops ────────────────────────────────────────────────────────────

    async def _tick_loop(self) -> None:
        while True:
            try:
                if not self.paused:
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
            if total % settings.recluster_every == 0:
                await self._recluster(session)
            await self._try_induce_all(session)

    # ── visit advancement ────────────────────────────────────────────────

    async def advance_one_visit(self) -> schemas.Episode | None:
        """Pop next scheduled visit, fire a simulator tick, persist, fan out."""
        if not self._visits:
            return None
        visit = self._visits.popleft()
        self._clock_day = visit.day
        self._clock_time = visit.time

        self._maybe_fire_scheduled_drift()

        async with self.session_factory() as session:
            persona = await store.get_persona(session, visit.persona_id)
            if persona is None:
                log.warning("unknown persona_id in schedule: %s", visit.persona_id)
                return None

            active_rule = await self._pick_rule_for_persona(session, persona.id)
            ep = await sim_tick.tick_once(visit, persona, active_rule)
            await store.save_episode(session, ep)

        await self.on_new_episode(ep)
        return ep

    def _maybe_fire_scheduled_drift(self) -> None:
        if (
            not self._drift_a_fired
            and self._clock_day == 3
            and self._clock_time >= "10:00"
        ):
            drift_mod.ai_bubble_pops()
            self._drift_a_fired = True
            log.info("Drift A fired (ai_bubble_pops) at day=3 %s", self._clock_time)

        # Drift B is per-episode advancement; advance one step if we're past its start.
        if self._clock_day > 2 or (self._clock_day == 2 and self._clock_time >= "14:00"):
            self._gradual_postdoc.advance()

    # ── internals ────────────────────────────────────────────────────────

    async def _pick_rule_for_persona(
        self, session, persona_id: str
    ) -> schemas.Rule | None:
        """TODO(phase1): walk persona → cluster → active rule. For now: None → improvise."""
        return None

    async def _recluster(self, session) -> None:
        """TODO(phase1): pull all episodes, run clustering.cluster_episodes, upsert ClusterRows."""
        log.debug("recluster triggered")

    async def _try_induce_all(self, session) -> None:
        """TODO(phase1): iterate clusters, check eligibility, call induction.induce_rule, persist."""
        pass

    async def _check_all_rule_cs(self) -> None:
        """TODO(phase1): per active rule → compute CS → if should_revise, create pending Revision row."""
        pass

    async def _evaluate_factory(self) -> None:
        """TODO(phase1): pull clusters + active rules, find_uncovered_cluster, spawn."""
        pass


# ── small helpers (kept here to avoid polluting store.py) ─────────────────

async def _count_episodes(session) -> int:
    result = await session.execute(select(orm.EpisodeRow.id))
    return len(result.scalars().all())
