"""ProfileSource — the abstraction boundary between EDRA and any external
profile-fetching service.

This module defines the contract; concrete implementations live alongside it
(`synthetic.py`, `linkedin_rapidapi.py`). Per TASK.md §4.1 and §14, this
abstraction is the *only* coupling point between EDRA core and external
services. Modules under `backend/{memory, clustering, induction, pitch,
monitor, reflection, factory, orchestrator}` MUST NOT import any concrete
ProfileSource implementation directly — they receive a ProfileSource
instance via dependency injection from the FastAPI app or orchestrator.

The protocol is intentionally minimal: one async fetch method + a stable
source kind identifier. Auth, rate-limiting, retries, and caching are all
the implementation's responsibility.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.schemas import Profile


__all__ = [
    "Profile",
    "ProfileSource",
    "ProfileNotFound",
    "ProfileSourceUnavailable",
]


class ProfileNotFound(Exception):
    """Identifier did not resolve to a profile (404-equivalent)."""


class ProfileSourceUnavailable(Exception):
    """Transient failure: timeout, rate limit, network error, etc.

    Callers should treat this as an opportunity to fall back (e.g. offer the
    visitor a synthetic archetype) rather than as a fatal error.
    """


@runtime_checkable
class ProfileSource(Protocol):
    """Any service capable of resolving an identifier to a Profile.

    Implementations are responsible for handling their own auth, rate
    limiting, error recovery, and caching. EDRA core is unaware of these
    concerns — it only sees the Profile that comes back, or one of the two
    exceptions above.
    """

    @property
    def source_kind(self) -> str:
        """Short stable identifier, e.g. 'linkedin_rapidapi', 'synthetic'."""
        ...

    async def fetch(self, identifier: str) -> Profile:
        """Resolve an identifier to a Profile.

        Raises ProfileNotFound for unrecoverable lookup failures.
        Raises ProfileSourceUnavailable for transient errors (timeouts, etc).
        """
        ...
