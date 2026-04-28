"""LinkedInRapidAPISource — Phase 3 implementation.

Fetches a public LinkedIn profile via a RapidAPI bridge and maps the response
to the EDRA `Profile` schema. Per TASK.md §14, this module is intentionally
isolated: no module under `backend/{memory, clustering, induction, pitch,
monitor, reflection, factory, orchestrator}` is allowed to import from here.
The DI plumbing in `backend/app.py` is the single place that picks this
implementation when `LIVE_MODE=true` and `RAPIDAPI_KEY` is set.

Privacy posture:
  - Live profiles are stamped with `ttl_seconds=3600` so the Phase 3 purge
    job can find and delete them.
  - The fetched payload is NOT cached locally — we re-fetch on demand.
  - The mapping below extracts only what EDRA needs (role, domain, headline,
    seniority hint, recent_signals snippets); we do not persist photos,
    phone numbers, education history, or other RapidAPI fields.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from backend.profile_source import (
    Profile,
    ProfileNotFound,
    ProfileSourceUnavailable,
)


log = logging.getLogger(__name__)


DEFAULT_HOST = "fresh-linkedin-profile-data.p.rapidapi.com"
DEFAULT_TIMEOUT = 10.0
LIVE_TTL_SECONDS = 3600  # purge job removes live profiles older than this

# Sentinel key for booth dev/demo without a real RapidAPI subscription. When
# `RAPIDAPI_KEY=mock`, fetch() bypasses HTTP and returns the hand-crafted
# author profile below. Useful for end-to-end UI smoke without burning quota.
MOCK_KEY_SENTINEL = "mock"

# The author's own LinkedIn URL — used as the canonical mock identifier so
# the booth UX can be demoed end-to-end ("paste my URL → see my profile") on
# a laptop that has no RapidAPI key. Any other identifier in mock mode also
# resolves to this payload, since the point of the mode is to exercise the
# wiring rather than serve real data.
_AUTHOR_LINKEDIN_URL = "https://www.linkedin.com/in/danil-onishchenko-30876037a/"

_MOCK_AUTHOR_PAYLOAD: dict[str, Any] = {
    "data": {
        "full_name": "Danil Onishchenko",
        "first_name": "Danil",
        "last_name": "Onishchenko",
        "headline": "Software engineer · building research-liaison agents at Defy.group",
        "job_title": "Software Engineer",
        "industry": "Computer Software",
        "years_of_experience": 4,
        "company": {"name": "Defy.group", "industry": "Computer Software"},
        "experiences": [
            {
                "title": "Software Engineer",
                "description": "EDRA — agent framework that learns rules from booth visit episodes.",
                "duration": {"years": 2},
            }
        ],
        "posts": [
            {"text": "Shipped EDRA Phase 1B — multi-turn pitch sessions with hybrid static/dynamic rules."},
            {"text": "Reading: Lin et al. on retrieval-augmented agents, and the latest MetaFlowLLM paper."},
            {"text": "Looking for collaborators on adaptive-rule research — DM me on the Defy floor."},
        ],
    }
}


class LinkedInRapidAPISource:
    """Resolves a LinkedIn URL or vanity handle to a Profile via RapidAPI.

    Construction takes only configuration; no network call is made until
    `fetch()` is awaited. A missing or empty `api_key` makes `fetch()` raise
    `ProfileSourceUnavailable` immediately so the booth UI can offer the
    synthetic fallback.
    """

    def __init__(
        self,
        api_key: str | None = None,
        host: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self._api_key = (api_key or "").strip()
        self._host = host or DEFAULT_HOST
        self._timeout = timeout

    @property
    def source_kind(self) -> str:
        return "linkedin_rapidapi"

    async def fetch(self, identifier: str) -> Profile:
        if not self._api_key:
            raise ProfileSourceUnavailable("RAPIDAPI_KEY not configured")

        # Mock-key sentinel — bypass HTTP, return the author's pre-baked
        # profile. Lets the booth show the live-mode UI flow end-to-end
        # without a real RapidAPI subscription. Any identifier passed in is
        # remapped to the canonical author URL so the resulting Profile.id
        # is stable across runs.
        if self._api_key == MOCK_KEY_SENTINEL:
            log.info("LinkedInRapidAPISource: returning mock author profile")
            return _map_payload_to_profile(_AUTHOR_LINKEDIN_URL, _MOCK_AUTHOR_PAYLOAD)

        url = f"https://{self._host}/get-linkedin-profile"
        headers = {
            "X-RapidAPI-Key": self._api_key,
            "X-RapidAPI-Host": self._host,
        }
        params = {
            "linkedin_url": identifier,
            "include_skills": "false",
            "include_certifications": "false",
            "include_publications": "false",
            "include_honors": "false",
            "include_volunteers": "false",
            "include_projects": "false",
            "include_patents": "false",
            "include_courses": "false",
            "include_organizations": "false",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, headers=headers, params=params)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as e:
            raise ProfileSourceUnavailable(f"network: {e.__class__.__name__}") from e
        except httpx.HTTPError as e:
            raise ProfileSourceUnavailable(f"http: {e.__class__.__name__}") from e

        if response.status_code == 404:
            raise ProfileNotFound(f"LinkedIn profile not found: {identifier}")
        if response.status_code == 429:
            raise ProfileSourceUnavailable("rate-limited by RapidAPI (HTTP 429)")
        if response.status_code >= 500:
            raise ProfileSourceUnavailable(
                f"RapidAPI upstream error (HTTP {response.status_code})"
            )
        if response.status_code != 200:
            raise ProfileSourceUnavailable(
                f"unexpected RapidAPI status: HTTP {response.status_code}"
            )

        try:
            payload = response.json()
        except ValueError as e:
            raise ProfileSourceUnavailable(f"malformed JSON from RapidAPI: {e}") from e

        return _map_payload_to_profile(identifier, payload)


# ── Mapping helpers ──────────────────────────────────────────────────────


def _map_payload_to_profile(identifier: str, payload: dict[str, Any]) -> Profile:
    """Map a RapidAPI fresh-linkedin-profile-data response to a Profile.

    The endpoint returns a top-level `data` object with a fairly standard
    shape. We're defensive about missing fields — RapidAPI bridges change
    keys without warning, and a ProfileSourceUnavailable on a missing
    headline is friendlier than a ValidationError 500.
    """
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise ProfileSourceUnavailable("RapidAPI response missing `data` object")

    full_name = (data.get("full_name") or "").strip()
    if not full_name:
        first = (data.get("first_name") or "").strip()
        last = (data.get("last_name") or "").strip()
        full_name = f"{first} {last}".strip()
    if not full_name:
        full_name = identifier

    headline = (data.get("headline") or data.get("about") or "").strip()
    job_title = (data.get("job_title") or "").strip()
    role = job_title or _role_from_headline(headline) or "professional"
    domain = _domain_from_data(data)
    seniority = _seniority_from_data(data, role, headline)
    recent_signals = _recent_signals_from_data(data)
    archetype_summary = _archetype_summary(role, domain, headline)

    # Profile.id is stable per source_identifier so re-fetching the same
    # LinkedIn URL upserts rather than duplicates. We slugify lightly.
    profile_id = f"li:{_slugify(identifier)}"

    return Profile(
        id=profile_id,
        source_kind="linkedin_rapidapi",
        source_identifier=identifier,
        name=full_name,
        role=role,
        domain=domain,
        seniority=seniority,
        headline=headline or "(no headline)",
        recent_signals=recent_signals,
        archetype_summary=archetype_summary,
        embedding=None,
        fetched_at=datetime.utcnow(),
        ttl_seconds=LIVE_TTL_SECONDS,
    )


def _role_from_headline(headline: str) -> str:
    if not headline:
        return ""
    head = headline.split("|")[0].split("·")[0].split(" at ")[0]
    return head.strip()


def _domain_from_data(data: dict[str, Any]) -> str:
    company = data.get("company") or {}
    if isinstance(company, dict):
        industry = (company.get("industry") or "").strip()
        if industry:
            return industry
    industry = (data.get("industry") or "").strip()
    if industry:
        return industry
    experiences = data.get("experiences") or []
    if isinstance(experiences, list) and experiences:
        first = experiences[0]
        if isinstance(first, dict):
            for key in ("industry", "company_industry"):
                val = (first.get(key) or "").strip()
                if val:
                    return val
    return "unspecified"


def _seniority_from_data(
    data: dict[str, Any], role: str, headline: str
) -> str:
    """Map years-of-experience or title hints to early/mid/senior.

    Heuristic, intentionally simple: titles trump tenure when both are
    present (a 'Director with 4 years' is senior; a 'Junior Director with
    20 years' parses as senior anyway because we look at "Director").
    """
    role_lc = role.lower() + " " + (headline or "").lower()
    senior_markers = (
        "director", "vp", "vice president", "head of", "principal",
        "chief", "founder", "partner", "professor", "lead",
    )
    early_markers = ("intern", "junior", "associate", "phd student", "graduate")

    if any(m in role_lc for m in senior_markers):
        return "senior"
    if any(m in role_lc for m in early_markers):
        return "early"

    years = _years_experience(data)
    if years is not None:
        if years >= 10:
            return "senior"
        if years <= 3:
            return "early"
    return "mid"


def _years_experience(data: dict[str, Any]) -> int | None:
    years = data.get("years_of_experience")
    if isinstance(years, (int, float)):
        return int(years)
    experiences = data.get("experiences") or []
    if not isinstance(experiences, list):
        return None
    total = 0
    for exp in experiences:
        if not isinstance(exp, dict):
            continue
        duration = exp.get("duration") or {}
        if isinstance(duration, dict):
            y = duration.get("years")
            if isinstance(y, (int, float)):
                total += int(y)
    return total if total > 0 else None


def _recent_signals_from_data(data: dict[str, Any]) -> list[str]:
    """Pull a few recent-activity snippets to ground rule induction.

    Tries `posts`, then `activities`, then falls back to the latest experience
    bullet. We cap at three short strings — anything longer adds noise to
    the induction prompt without changing the rule.
    """
    signals: list[str] = []
    for key in ("posts", "activities", "recent_activities"):
        items = data.get(key)
        if not isinstance(items, list):
            continue
        for item in items[:5]:
            text = ""
            if isinstance(item, dict):
                text = item.get("text") or item.get("title") or item.get("summary") or ""
            elif isinstance(item, str):
                text = item
            text = (text or "").strip()
            if text:
                signals.append(_truncate(text, 140))
            if len(signals) >= 3:
                return signals

    experiences = data.get("experiences") or []
    if isinstance(experiences, list):
        for exp in experiences[:1]:
            if not isinstance(exp, dict):
                continue
            bullet = exp.get("description") or exp.get("title") or ""
            bullet = (bullet or "").strip()
            if bullet:
                signals.append(_truncate(bullet, 140))
                break
    return signals


def _archetype_summary(role: str, domain: str, headline: str) -> str:
    parts = [role]
    if domain and domain != "unspecified":
        parts.append(f"in {domain}")
    summary = " ".join(parts).strip()
    if not summary and headline:
        summary = _truncate(headline, 120)
    return summary or "live LinkedIn visitor"


def _slugify(s: str) -> str:
    out = []
    for ch in s.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in "-_/":
            out.append("-")
    return "".join(out).strip("-")[:64] or "unknown"


def _truncate(s: str, n: int) -> str:
    s = s.strip()
    if len(s) <= n:
        return s
    return s[: n - 1].rstrip() + "…"
