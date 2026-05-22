"""Multi-turn pitch sessions — TASK.md §1.2 / §8.

A Session is the in-flight state of one outreach dialogue: profile, classified
cluster, applicable rule, accumulated DialogueSteps, current interest gauge.
The same lifecycle is driven from two surfaces:

  - HTTP — `backend/routers/sessions.py` exposes /sessions/start, /turn, /end
    for the booth-visitor flow (synthetic + live).
  - Orchestrator — `backend/orchestrator.py` calls `run_synthetic_session`
    every tick to play through one synthetic visitor against the preference
    function, persisting the resulting Episode.

State lives in a process-local dict, no TTL — Phase 3 will add cleanup. There
is at most one *active* session at a time (the booth has one screen); the
manager exposes that pointer to the /state polling endpoint.
"""

from backend.sessions.lifecycle import (
    end_session,
    resolve_session,
    run_synthetic_session,
    start_session,
    take_turn,
)
from backend.sessions.store import (
    MAX_TURNS,
    Session,
    SessionStore,
    get_active_session,
    session_store,
)


__all__ = [
    "MAX_TURNS",
    "Session",
    "SessionStore",
    "end_session",
    "get_active_session",
    "resolve_session",
    "run_synthetic_session",
    "session_store",
    "start_session",
    "take_turn",
]
