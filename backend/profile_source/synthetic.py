"""SyntheticProfileSource — fetches Profiles from the seeded archetype YAML.

Used in synthetic mode (TASK.md §1.4) and as a fallback when live mode is
unavailable (TASK.md Phase 3 / §11). Fully offline.

The archetype YAML is the source of truth for everything about the synthetic
visitor population: their Profile fields, their hidden preference function,
and which two are spawnable rather than in-rotation.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from backend.profile_source import (
    Profile,
    ProfileNotFound,
)


DEFAULT_ARCHETYPES_PATH = Path(__file__).parent.parent / "data" / "archetypes.yaml"


class SyntheticProfileSource:
    """Reads `archetypes.yaml` and returns a Profile per archetype id.

    The YAML is loaded lazily on first fetch and cached; mutate the file and
    call `reload()` to pick up edits in dev.
    """

    def __init__(self, archetypes_path: Path | None = None):
        self._path = archetypes_path or DEFAULT_ARCHETYPES_PATH
        self._archetypes: dict[str, dict[str, Any]] | None = None

    @property
    def source_kind(self) -> str:
        return "synthetic"

    def reload(self) -> None:
        self._archetypes = None

    def _ensure_loaded(self) -> dict[str, dict[str, Any]]:
        if self._archetypes is None:
            data = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
            archetypes = data.get("archetypes") or {}
            if not isinstance(archetypes, dict):
                raise ValueError(
                    f"archetypes.yaml must have a top-level 'archetypes' mapping; "
                    f"got {type(archetypes).__name__}"
                )
            self._archetypes = archetypes
        return self._archetypes

    def list_ids(self, *, include_spawnable: bool = True) -> list[str]:
        archetypes = self._ensure_loaded()
        return [
            aid
            for aid, spec in archetypes.items()
            if include_spawnable or not spec.get("spawnable", False)
        ]

    def is_spawnable(self, archetype_id: str) -> bool:
        archetypes = self._ensure_loaded()
        spec = archetypes.get(archetype_id)
        return bool(spec and spec.get("spawnable", False))

    async def fetch(self, identifier: str) -> Profile:
        archetypes = self._ensure_loaded()
        spec = archetypes.get(identifier)
        if spec is None:
            raise ProfileNotFound(f"unknown archetype id: {identifier}")

        profile_data = spec.get("profile") or {}
        return Profile(
            id=identifier,
            source_kind=self.source_kind,
            source_identifier=identifier,
            name=profile_data.get("name", identifier),
            role=profile_data["role"],
            domain=profile_data["domain"],
            seniority=profile_data["seniority"],
            headline=profile_data.get("headline", ""),
            recent_signals=list(profile_data.get("recent_signals") or []),
            archetype_summary=profile_data.get("archetype_summary", ""),
            embedding=None,
            fetched_at=datetime.utcnow(),
            ttl_seconds=None,  # synthetic profiles never expire
        )
