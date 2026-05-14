"""CSV-to-Profile mapper for the 502-row research_profiles_master.csv dataset.

Reads CSV rows and produces thin Profile objects (source_kind="csv_research")
suitable for outreach batch selection. LinkedIn enrichment is a separate,
optional step handled by enrich.py (Phase O.4).

The seniority heuristic reuses the same title-marker logic from
linkedin_rapidapi._seniority but operates only on the CSV's `Current role`
field (no experience date spans available).
"""

from __future__ import annotations

import csv
import logging
from datetime import UTC, datetime
from pathlib import Path

from backend.config import PROJECT_ROOT
from backend.profile_source.linkedin_rapidapi import _username_from_input
from backend.schemas import Profile

log = logging.getLogger(__name__)

DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "research_profiles" / "research_profiles_master.csv"

_SENIOR_MARKERS = (
    "director", "vp", "vice president", "head of", "principal",
    "chief", "ceo", "cto", "cfo", "founder", "partner", "professor", "lead",
)
_EARLY_MARKERS = ("intern", "junior", "associate", "phd student", "graduate")


def _seniority_from_role(role_text: str) -> str:
    text = role_text.lower()
    if any(m in text for m in _SENIOR_MARKERS):
        return "senior"
    if any(m in text for m in _EARLY_MARKERS):
        return "early"
    return "mid"


def _parse_role_and_domain(current_role: str) -> tuple[str, str]:
    if "," in current_role:
        parts = current_role.split(",", 1)
        return parts[0].strip(), parts[1].strip()
    return current_role.strip(), "unspecified"


def load_profiles(
    csv_path: Path | None = None,
    *,
    min_confidence: str = "Medium",
) -> list[Profile]:
    """Load all qualifying CSV rows as thin Profile objects.

    Args:
        csv_path: Override path to the CSV file. Defaults to the repo's
            data/research_profiles/research_profiles_master.csv.
        min_confidence: Minimum confidence level to include. "High" means
            only High rows; "Medium" means High + Medium; "Low" means all.

    Returns:
        List of Profile objects, one per qualifying CSV row.
    """
    path = csv_path or DEFAULT_CSV_PATH
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")

    confidence_levels = _confidence_set(min_confidence)
    profiles: list[Profile] = []
    skipped = 0

    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            conf = (row.get("Conf.") or "").strip()
            if conf not in confidence_levels:
                skipped += 1
                continue

            profile = _row_to_profile(row)
            if profile is None:
                skipped += 1
                continue
            profiles.append(profile)

    log.info("Loaded %d profiles from CSV (%d skipped)", len(profiles), skipped)
    return profiles


def _confidence_set(min_confidence: str) -> set[str]:
    levels = ["High", "Medium", "Low"]
    try:
        idx = levels.index(min_confidence)
    except ValueError:
        return {"High", "Medium"}
    return set(levels[: idx + 1])


def _row_to_profile(row: dict[str, str]) -> Profile | None:
    linkedin_url = (row.get("LinkedIn") or "").strip()
    handle = _username_from_input(linkedin_url)
    if not handle:
        log.warning("Skipping row %r: could not extract LinkedIn handle", row.get("Name"))
        return None

    name = (row.get("Name") or "").strip()
    if not name:
        log.warning("Skipping row with handle %s: missing Name", handle)
        return None

    current_role = (row.get("Current role") or "").strip()
    role, domain = _parse_role_and_domain(current_role)
    why_included = (row.get("Why included") or "").strip()

    return Profile(
        id=f"csv:{handle}",
        source_kind="csv_research",
        source_identifier=linkedin_url,
        name=name,
        role=role,
        domain=domain,
        seniority=_seniority_from_role(current_role),
        headline=current_role,
        recent_signals=[f"Why included: {why_included}"] if why_included else [],
        archetype_summary=why_included or f"{role} at {domain}",
        avatar_url=None,
        embedding=None,
        fetched_at=datetime.now(UTC),
        ttl_seconds=None,
    )


def load_csv_metadata(
    csv_path: Path | None = None,
    *,
    min_confidence: str = "Medium",
) -> list[dict[str, str]]:
    """Load raw CSV rows as dicts, filtered by confidence.

    Returns the original CSV fields (Name, Segment, Geo, Conf., etc.)
    that are not stored in the Profile but are needed by OutreachRow
    (segment, geo, confidence).
    """
    path = csv_path or DEFAULT_CSV_PATH
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")

    confidence_levels = _confidence_set(min_confidence)
    rows: list[dict[str, str]] = []

    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            conf = (row.get("Conf.") or "").strip()
            if conf not in confidence_levels:
                continue
            handle = _username_from_input((row.get("LinkedIn") or "").strip())
            if not handle or not (row.get("Name") or "").strip():
                continue
            rows.append(dict(row))

    return rows
