"""In-memory session store + active-session pointer.

A Session holds everything we need to render the next turn and ultimately
persist an Episode: profile, cluster classification, applicable rule, the
chosen pitch strategy, the accumulated DialogueSteps, and the current
interest gauge.

`MAX_TURNS = 7` matches TASK.md §4.4 ("a typical session has 3–7 dialogue
steps before reaching ±5 interest or being abandoned"). Sessions hitting the
cap end with `outcome="exploring"` (positive momentum) or `"abandoned"`.

The store is a process-local dict — no DB, no TTL. Phase 3 adds cleanup of
sessions older than the live-mode TTL. Concurrency: a single asyncio loop
drives both the HTTP handlers and the orchestrator, so dict access is safe
without a lock.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime

from backend import schemas


MAX_TURNS = 7


@dataclass
class Session:
    """Mutable in-flight session state."""

    id: str
    profile: schemas.Profile
    cluster_id: str | None
    applicable_rule_id: str | None
    pitch_strategy: schemas.PitchStrategy
    dialogue: list[schemas.DialogueStep] = field(default_factory=list)
    interest: int = 0
    started_at: datetime = field(default_factory=datetime.utcnow)
    day: int = 1
    ended: bool = False
    outcome: schemas.OUTCOME | None = None
    used_categories: list[str] = field(default_factory=list)

    def to_snapshot(self) -> schemas.SessionSnapshot:
        return schemas.SessionSnapshot(
            id=self.id,
            profile=self.profile,
            cluster_id=self.cluster_id,
            applicable_rule_id=self.applicable_rule_id,
            interest=self.interest,
            dialogue=list(self.dialogue),
        )


class SessionStore:
    """Holds every in-flight Session plus a pointer to the currently-active one.

    `active_session_id` is set by `start_session` and cleared by `end_session`;
    `/state` reads it via `get_active_session()`.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._active_id: str | None = None
        self._lock = threading.Lock()

    def add(self, session: Session, *, active: bool = True) -> None:
        with self._lock:
            self._sessions[session.id] = session
            if active:
                self._active_id = session.id

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def discard_active(self, session_id: str) -> None:
        with self._lock:
            if self._active_id == session_id:
                self._active_id = None

    @property
    def active_id(self) -> str | None:
        return self._active_id

    def active(self) -> Session | None:
        sid = self._active_id
        return self._sessions.get(sid) if sid else None

    def reset(self) -> None:
        """Drop all in-flight sessions. Used by tests."""
        with self._lock:
            self._sessions.clear()
            self._active_id = None


# Module-level singleton — both the HTTP routers and the orchestrator hold
# a reference to the same store, so /state and /sessions/* share state.
session_store = SessionStore()


def get_active_session() -> Session | None:
    return session_store.active()
