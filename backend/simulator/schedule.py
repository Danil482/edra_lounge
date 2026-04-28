"""Visitor schedule loader — reads `seeded_run.yaml` and yields scheduled
visits. The schedule fixes archetype ids and game-clock times so the booth
demo replays the same trajectory every time (TASK.md §5.4).

Drift triggers (e.g. `day_3_drift_a_triggers_at`) are surfaced separately so
the orchestrator can fire them at the right point in the timeline.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml


SEEDED_YAML = Path(__file__).parent.parent.parent / "seeded_run.yaml"


@dataclass(frozen=True)
class Visit:
    day: int
    time: str
    archetype_id: str


def load_schedule(path: Path | None = None) -> list[Visit]:
    path = path or SEEDED_YAML
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    visits: list[Visit] = []
    for key, entries in data.items():
        if not key.startswith("day_"):
            continue
        # Skip drift-marker entries like `day_3_drift_a_triggers_at`.
        if "drift" in key:
            continue
        try:
            day = int(key.removeprefix("day_"))
        except ValueError:
            continue
        if not isinstance(entries, list):
            continue
        for e in entries:
            archetype = e.get("archetype") or e.get("persona")
            if not archetype:
                continue
            visits.append(Visit(day=day, time=e["time"], archetype_id=archetype))
    visits.sort(key=lambda v: (v.day, v.time))
    return visits


def drift_triggers(path: Path | None = None) -> dict[str, str]:
    """Return the keys whose name signals a scheduled drift event."""
    path = path or SEEDED_YAML
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {k: v for k, v in data.items() if "drift" in k}
