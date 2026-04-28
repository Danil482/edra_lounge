"""LinkedInRapidAPISource — Phase 3 implementation, stubbed in Phase 1A.

This module is intentionally isolated: per TASK.md §14 acceptance,
no module under `backend/{memory, clustering, induction, pitch, monitor,
reflection, factory, orchestrator}` imports anything from here. The DI plumbing
in `backend/app.py` is the single place that picks an implementation.

When `LIVE_MODE=true` and `RAPIDAPI_KEY` is set, the orchestrator wires this
class as the active ProfileSource. Otherwise SyntheticProfileSource is used.
"""

from __future__ import annotations

from backend.profile_source import (
    Profile,
    ProfileSourceUnavailable,
)


class LinkedInRapidAPISource:
    """Resolves a LinkedIn URL or handle to a Profile via RapidAPI.

    Phase 1A: stub. Raises `ProfileSourceUnavailable` on every fetch so the
    booth can fall back to a synthetic archetype while the implementation is
    pending. Phase 3 wires the actual HTTP client, retry, timeout, and
    privacy purge.
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self._api_key = api_key
        self._base_url = base_url

    @property
    def source_kind(self) -> str:
        return "linkedin_rapidapi"

    async def fetch(self, identifier: str) -> Profile:
        # TODO(phase3): real RapidAPI call + Profile mapping.
        raise ProfileSourceUnavailable(
            "LinkedInRapidAPISource is not implemented yet (Phase 3)."
        )
