"""Orchestrator — all background coordination lives here as asyncio tasks.

Replaces what would have been an external workflow engine. Kept deliberately
small: three loops + one reactive hook (TASK.md §6). Each loop wraps its body
in try/except so a single-iteration failure does not kill the loop (acceptance
§14).

Phase 1A surface: lifecycle, game-clock advancement, drift schedule, and the
public hooks `on_new_episode` / `inject_archetype`. Multi-turn synthetic
session generation lands in Phase 1B (`spawn_synthetic_session`); for now
`advance_one_visit` only advances the clock.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend import schemas
from backend.config import settings
from backend.memory import models as orm
from backend.profile_source import ProfileSource
from backend.simulator import drift as drift_mod
from backend.simulator import schedule as schedule_mod

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
            if settings.recluster_every and total % settings.recluster_every == 0:
                await self._recluster(session)
            await self._try_induce_all(session)

    # ── visit advancement ────────────────────────────────────────────────

    async def advance_one_visit(self) -> schemas.Episode | None:
        """Advance the game clock by one visit. Phase 1A: clock-only.

        Phase 1B replaces this with a full synthetic session — fetch the
        archetype's Profile via `self.profile_source`, run a multi-turn
        dialogue against the preference function, persist the Episode, and
        fan out via `on_new_episode`.
        """
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
        # TODO(phase1B): generate Episode via simulator.session.run_synthetic.
        log.debug(
            "tick: day=%d time=%s archetype=%s (Phase 1A clock-only)",
            visit.day,
            visit.time,
            visit.archetype_id,
        )
        return None

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

    # ── internals (Phase 1B will fill these) ─────────────────────────────

    async def _recluster(self, session) -> None:
        """TODO(phase1B): pull all episodes, run clustering, upsert ClusterRows."""
        log.debug("recluster requested")

    async def _try_induce_all(self, session) -> None:
        """TODO(phase1B): for each eligible cluster, induce a rule via LLM."""

    async def _check_all_rule_cs(self) -> None:
        """TODO(phase1B): per active rule → CS → if should_revise, create pending Revision."""

    async def _evaluate_factory(self) -> None:
        """TODO(phase1B): pull clusters + active rules → find_uncovered_cluster → spawn."""


# ── small helpers ─────────────────────────────────────────────────────────

async def _count_episodes(session) -> int:
    result = await session.execute(select(orm.EpisodeRow.id))
    return len(result.scalars().all())
