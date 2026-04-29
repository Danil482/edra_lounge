"""LinkedInRapidAPISource — Phase 4 implementation.

Two RapidAPI calls per fresh fetch on linkedin-data-api.p.rapidapi.com:
  1. /get-profile-data-by-url?url=<linkedin-url>  → profile data + vanity username
  2. /get-profile-posts?username=<username>         → recent posts

Quota: free RapidAPI plan caps at 50 requests/month. Each successful full
  fetch burns 2 (profile + posts). The on-disk cache at data/linkedin_cache/
  re-uses raw responses for repeated lookups during dev — cache hits cost
  zero quota. Cache is opt-in via the `cache_dir` constructor arg; tests
  leave it None.

Privacy: live-fetched Profile rows in SQLite are stamped with
  ttl_seconds=3600 so the Phase 3 purge job removes them. The on-disk
  cache is *separate* from that and currently has no TTL — manual cleanup
  before booth events if privacy-sensitive. The TTL plumbing is in place
  (`cache_ttl_seconds`); flip it to 86400 once a booth date is locked.

Per TASK.md §14, this module is intentionally isolated: no module under
`backend/{memory, clustering, induction, pitch, monitor, reflection,
factory, orchestrator}` is allowed to import from here. The DI plumbing
in `backend/app.py` is the single place that picks this implementation
when `LIVE_MODE=true` and `RAPIDAPI_KEY` is set.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from backend.profile_source import (
    Profile,
    ProfileNotFound,
    ProfileSourceUnavailable,
)


log = logging.getLogger(__name__)


DEFAULT_HOST = "linkedin-data-api.p.rapidapi.com"
DEFAULT_TIMEOUT = 10.0
LIVE_TTL_SECONDS = 3600  # SQLite Profile row TTL — see purge_expired_live_profiles

# Sentinel for booth without subscription. RAPIDAPI_KEY=mock → no HTTP, no cache,
# returns the hand-crafted author profile via the same mapper used for real data.
MOCK_KEY_SENTINEL = "mock"

_AUTHOR_LINKEDIN_URL = "https://www.linkedin.com/in/danil-onishchenko-30876037a/"

_MOCK_AUTHOR_PROFILE_PAYLOAD: dict[str, Any] = {
    "firstName": "Danil",
    "lastName": "Onishchenko",
    "username": "danil-onishchenko-30876037a",
    "headline": "Software engineer · building research-liaison agents at Defy.group",
    "summary": (
        "Building EDRA at Defy.group — an agent framework that learns rules "
        "from booth visit episodes. Looking for collaborators on adaptive-rule "
        "research."
    ),
    "geo": {"country": "Russia", "city": "Saint Petersburg"},
    "position": [
        {
            "title": "Software Engineer",
            "companyName": "Defy.group",
            "companyIndustry": "Computer Software",
            "description": "EDRA — agent framework that learns rules from booth visit episodes.",
            "start": {"year": 2024, "month": 1, "day": 0},
            "end": {"year": 0, "month": 0, "day": 0},
        }
    ],
}

_MOCK_AUTHOR_POSTS_PAYLOAD: dict[str, Any] = {
    "success": True,
    "data": [
        {
            "text": "Shipped EDRA Phase 1B — multi-turn pitch sessions with hybrid static/dynamic rules.",
            "postedDateTimestamp": 1714000000000,
            "totalReactionCount": 12,
            "reposted": False,
        },
        {
            "text": "Reading: Lin et al. on retrieval-augmented agents, and the latest MetaFlowLLM paper.",
            "postedDateTimestamp": 1713800000000,
            "totalReactionCount": 5,
            "reposted": False,
        },
        {
            "text": "Looking for collaborators on adaptive-rule research — DM me on the Defy floor.",
            "postedDateTimestamp": 1713600000000,
            "totalReactionCount": 18,
            "reposted": False,
        },
    ],
}


class LinkedInRapidAPISource:
    """Resolves a LinkedIn URL to a Profile via two RapidAPI calls.

    Each successful real fetch costs two requests against the free 50/mo
    quota — see module docstring. Pass `cache_dir` to enable on-disk cache;
    leaving it None (the default) disables the cache (used in tests).
    """

    def __init__(
        self,
        api_key: str | None = None,
        host: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        cache_dir: Path | None = None,
        cache_ttl_seconds: int | None = None,
    ):
        self._api_key = (api_key or "").strip()
        self._host = host or DEFAULT_HOST
        self._timeout = timeout
        self._cache_dir = cache_dir
        # cache_ttl_seconds=None means cache never expires. Flip to 86400 once
        # a booth event date is locked so post-event privacy posture matches
        # the SQLite TTL.
        self._cache_ttl = cache_ttl_seconds

    @property
    def source_kind(self) -> str:
        return "linkedin_rapidapi"

    async def fetch(self, identifier: str) -> Profile:
        if not self._api_key:
            raise ProfileSourceUnavailable("RAPIDAPI_KEY not configured")

        if self._api_key == MOCK_KEY_SENTINEL:
            log.info("LinkedInRapidAPISource: returning mock author profile")
            return _map_to_profile(
                _AUTHOR_LINKEDIN_URL,
                _MOCK_AUTHOR_PROFILE_PAYLOAD,
                _MOCK_AUTHOR_POSTS_PAYLOAD,
            )

        cached = self._cache_load(identifier)
        if cached is not None:
            log.info("LinkedInRapidAPISource: cache hit for %s", identifier)
            return _map_to_profile(
                identifier,
                cached["profile_data"],
                cached.get("posts_data") or {},
            )

        # Profile is mandatory — failures propagate. Posts is best-effort —
        # if the posts call fails we still return a Profile, falling back
        # to summary + position descriptions for recent_signals.
        profile_data = await self._fetch_profile_data(identifier)
        username = (profile_data.get("username") or "").strip()
        posts_data: dict[str, Any] = {}
        if username:
            try:
                posts_data = await self._fetch_posts(username)
            except (ProfileSourceUnavailable, ProfileNotFound) as e:
                log.warning(
                    "LinkedInRapidAPISource: posts fetch failed for %s — %s "
                    "(falling back to profile-only signals)",
                    username, e,
                )

        self._cache_save(identifier, profile_data, posts_data)
        return _map_to_profile(identifier, profile_data, posts_data)

    async def _fetch_profile_data(self, linkedin_url: str) -> dict[str, Any]:
        url = f"https://{self._host}/get-profile-data-by-url"
        payload = await self._http_get(url, params={"url": linkedin_url})
        if not isinstance(payload, dict) or not payload.get("firstName"):
            raise ProfileSourceUnavailable("RapidAPI profile response missing firstName")
        return payload

    async def _fetch_posts(self, username: str) -> dict[str, Any]:
        url = f"https://{self._host}/get-profile-posts"
        payload = await self._http_get(url, params={"username": username})
        if not isinstance(payload, dict):
            raise ProfileSourceUnavailable("RapidAPI posts response not a dict")
        return payload

    async def _http_get(self, url: str, params: dict[str, str]) -> Any:
        headers = {
            "x-rapidapi-key": self._api_key,
            "x-rapidapi-host": self._host,
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, headers=headers, params=params)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as e:
            raise ProfileSourceUnavailable(f"network: {e.__class__.__name__}") from e
        except httpx.HTTPError as e:
            raise ProfileSourceUnavailable(f"http: {e.__class__.__name__}") from e

        if response.status_code == 404:
            raise ProfileNotFound(f"profile not found: {url}")
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
            return response.json()
        except ValueError as e:
            raise ProfileSourceUnavailable(f"malformed JSON from RapidAPI: {e}") from e

    # ── Cache ────────────────────────────────────────────────────────────

    def _cache_path(self, linkedin_url: str) -> Path | None:
        if self._cache_dir is None:
            return None
        return self._cache_dir / f"{_slugify(linkedin_url)}.json"

    def _cache_load(self, linkedin_url: str) -> dict | None:
        path = self._cache_path(linkedin_url)
        if path is None or not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as e:
            log.warning("cache read failed for %s: %s — refetching", path, e)
            return None
        if self._cache_ttl is not None:
            cached_at_iso = data.get("cached_at")
            if not cached_at_iso:
                return None
            try:
                cached_at = datetime.fromisoformat(cached_at_iso)
            except ValueError:
                return None
            age = (datetime.utcnow() - cached_at).total_seconds()
            if age > self._cache_ttl:
                log.info(
                    "cache expired for %s (age=%.0fs > ttl=%ds)",
                    linkedin_url, age, self._cache_ttl,
                )
                return None
        return data

    def _cache_save(
        self,
        linkedin_url: str,
        profile_data: dict[str, Any],
        posts_data: dict[str, Any],
    ) -> None:
        path = self._cache_path(linkedin_url)
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            body = {
                "cached_at": datetime.utcnow().isoformat(),
                "ttl_seconds": self._cache_ttl,
                "url": linkedin_url,
                "profile_data": profile_data,
                "posts_data": posts_data,
            }
            path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        except OSError as e:
            log.warning("cache write failed for %s: %s", path, e)


# ── Mapping helpers ──────────────────────────────────────────────────────


def _map_to_profile(
    identifier: str,
    profile_data: dict[str, Any],
    posts_data: dict[str, Any],
) -> Profile:
    """Combine profile + posts payloads into a Profile.

    Profile data is mandatory (caller validated firstName presence). Posts
    data is optional — empty/missing falls back to summary + top position
    description(s) for recent_signals.
    """
    first = (profile_data.get("firstName") or "").strip()
    last = (profile_data.get("lastName") or "").strip()
    name = f"{first} {last}".strip() or identifier

    headline = (profile_data.get("headline") or "").strip()
    summary = (profile_data.get("summary") or "").strip()
    raw_positions = profile_data.get("position") or []
    positions = raw_positions if isinstance(raw_positions, list) else []

    role = (
        _role_from_positions(positions)
        or _role_from_headline(headline)
        or "professional"
    )
    domain = _domain_from_positions(positions)
    seniority = _seniority(role, headline, positions)
    recent_signals = (
        _signals_from_posts(posts_data)
        or _signals_from_profile(summary, positions)
    )
    archetype_summary = _archetype_summary(role, domain, headline)

    username = (profile_data.get("username") or "").strip()
    profile_id = f"li:{username}" if username else f"li:{_slugify(identifier)}"

    return Profile(
        id=profile_id,
        source_kind="linkedin_rapidapi",
        source_identifier=identifier,
        name=name,
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


def _role_from_positions(positions: list[Any]) -> str:
    if not positions:
        return ""
    first = positions[0]
    if not isinstance(first, dict):
        return ""
    return (first.get("title") or "").strip()


def _role_from_headline(headline: str) -> str:
    if not headline:
        return ""
    head = headline.split("|")[0].split("·")[0].split(" at ")[0]
    return head.strip()


def _domain_from_positions(positions: list[Any]) -> str:
    for pos in positions:
        if not isinstance(pos, dict):
            continue
        industry = (pos.get("companyIndustry") or "").strip()
        if industry:
            return industry
    return "unspecified"


def _seniority(role: str, headline: str, positions: list[Any]) -> str:
    """Title hints win over computed years (a 'Director with 4yrs' is senior)."""
    text = (role + " " + (headline or "")).lower()
    senior_markers = (
        "director", "vp", "vice president", "head of", "principal",
        "chief", "ceo", "cto", "cfo", "founder", "partner", "professor", "lead",
    )
    early_markers = ("intern", "junior", "associate", "phd student", "graduate")

    if any(m in text for m in senior_markers):
        return "senior"
    if any(m in text for m in early_markers):
        return "early"

    years = _years_from_positions(positions)
    if years is not None:
        if years >= 10:
            return "senior"
        if years <= 3:
            return "early"
    return "mid"


def _years_from_positions(positions: list[Any]) -> int | None:
    """Span between earliest start year and latest end year.

    end.year=0 with a known start is treated as "current position" → today.
    """
    starts: list[int] = []
    ends: list[int] = []
    for pos in positions:
        if not isinstance(pos, dict):
            continue
        s = (pos.get("start") or {}).get("year") or 0
        e = (pos.get("end") or {}).get("year") or 0
        if isinstance(s, int) and s > 0:
            starts.append(s)
        if isinstance(e, int) and e > 0:
            ends.append(e)
        elif isinstance(s, int) and s > 0:
            ends.append(datetime.utcnow().year)
    if starts and ends:
        return max(ends) - min(starts)
    return None


def _signals_from_posts(posts_data: dict[str, Any]) -> list[str]:
    """Top-3 original (non-reposted) posts, most recent first, truncated to 140.

    Reposts are skipped because the opener template wants to reference what
    the visitor *said*, not what they amplified.
    """
    items = posts_data.get("data") if isinstance(posts_data, dict) else None
    if not isinstance(items, list):
        return []
    originals = [p for p in items if isinstance(p, dict) and not p.get("reposted")]
    originals.sort(key=lambda p: p.get("postedDateTimestamp") or 0, reverse=True)
    out: list[str] = []
    for p in originals:
        text = (p.get("text") or "").strip()
        if text:
            out.append(_truncate(text, 140))
        if len(out) >= 3:
            break
    return out


def _signals_from_profile(summary: str, positions: list[Any]) -> list[str]:
    """Fallback when posts are missing or all reposted: bio + top descriptions."""
    out: list[str] = []
    if summary:
        out.append(_truncate(summary, 140))
    for pos in positions[:2]:
        if not isinstance(pos, dict):
            continue
        desc = (pos.get("description") or "").strip()
        if desc:
            out.append(_truncate(desc, 140))
        if len(out) >= 3:
            break
    return out


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
