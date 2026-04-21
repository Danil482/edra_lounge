"""Visitor schedule loader — reads seeded_run.yaml and exposes an iterator
over (day, time, persona_id) entries. Pre-recorded for reproducibility.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml


SEEDED_YAML = Path(__file__).parent.parent.parent / "seeded_run.yaml"


@dataclass
class Visit:
    day: int
    time: str
    persona_id: str


def load_schedule(path: Path | None = None) -> list[Visit]:
    path = path or SEEDED_YAML
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    visits: list[Visit] = []
    for key, entries in data.items():
        if not key.startswith("day_"):
            continue
        try:
            day = int(key.removeprefix("day_"))
        except ValueError:
            continue
        for e in entries:
            visits.append(Visit(day=day, time=e["time"], persona_id=e["persona"]))
    return visits


def drift_triggers(path: Path | None = None) -> dict[str, str]:
    """Pull drift schedule entries (keys starting with day_N_drift_..._triggers_at)."""
    path = path or SEEDED_YAML
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if "drift" in k}
