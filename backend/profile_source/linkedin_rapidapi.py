"""LinkedInRapidAPISource — Phase 4 implementation.

Provider: fresh-linkedin-scraper-api.p.rapidapi.com (saleleads.ai docs).

Two RapidAPI calls per fresh fetch:
  1. /api/v1/user/profile?username=<handle>&include_experiences=true&include_bio=true
       Wrapped {success, cost, data: {...}}; validates data.first_name presence.
       Returns the canonical urn used by the posts call.
  2. /api/v1/user/posts?urn=<urn>
       Wrapped {success, cost, data: [...]}.
       URN is preferred over username because the docs note that calling the
       posts endpoint with `username` consumes an additional request on top of
       the base cost.

Quota: free RapidAPI plan caps at 50 requests/month. Each successful full
  fetch burns 2 (profile + posts) at minimum; include_* flags may add cost
  per the provider's billing — surfaced via the `cost` field on each
  envelope (logged at INFO). The on-disk cache at data/linkedin_cache/
  re-uses raw responses for repeated lookups during dev — cache hits cost
  zero quota. Cache is opt-in via the `cache_dir` constructor arg; tests
  leave it None.

Input flexibility: identifier may be either a full LinkedIn URL
  (`https://www.linkedin.com/in/<handle>/`) or just the handle itself
  (`<handle>`). Both are normalized to the canonical URL form for
  source_identifier and cache-key consistency.

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
import re
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


DEFAULT_HOST = "fresh-linkedin-scraper-api.p.rapidapi.com"
DEFAULT_TIMEOUT = 15.0
LIVE_TTL_SECONDS = 3600  # SQLite Profile row TTL — see purge_expired_live_profiles

# Sentinel for booth without subscription. RAPIDAPI_KEY=mock → no HTTP, no cache,
# returns the hand-crafted author profile via the same mapper used for real data.
MOCK_KEY_SENTINEL = "mock"

_CANONICAL_URL_TEMPLATE = "https://www.linkedin.com/in/{handle}/"
_USERNAME_FROM_URL_RE = re.compile(r"/in/([^/?#]+)")
_VALID_HANDLE_RE = re.compile(r"^[A-Za-z0-9_-]+$")

_AUTHOR_HANDLE = "danil-onishchenko-30876037a"
_AUTHOR_LINKEDIN_URL = _CANONICAL_URL_TEMPLATE.format(handle=_AUTHOR_HANDLE)

_MOCK_AUTHOR_PROFILE_DATA: dict[str, Any] = {
    "id": "12345",
    "urn": "urn:li:person:ACoAAAxxxxxxxxxxx",
    "public_identifier": _AUTHOR_HANDLE,
    "first_name": "Danil",
    "last_name": "Onishchenko",
    "full_name": "Danil Onishchenko",
    "headline": "Software engineer · building research-liaison agents at Defy.group",
    "bio": (
        "Building EDRA at Defy.group — an agent framework that learns rules "
        "from booth visit episodes. Looking for collaborators on adaptive-rule "
        "research."
    ),
    "location": {"country": "Russia", "city": "Saint Petersburg"},
    "avatar": [
        {"width": 200, "height": 200, "url": "https://example.invalid/mock-avatar-200.jpg"},
        {"width": 400, "height": 400, "url": "https://example.invalid/mock-avatar-400.jpg"},
    ],
    "experiences": [
        {
            "title": "Software Engineer",
            "description": "EDRA — agent framework that learns rules from booth visit episodes.",
            "company": {"name": "Defy.group", "id": "111"},
            "employment_type": "Full-time",
            "date": {
                "start": {"year": 2024, "month": 1},
                "end": {"year": 0, "month": 0},
            },
        }
    ],
}

_MOCK_AUTHOR_POSTS_DATA: list[dict[str, Any]] = [
    {
        "id": "p1",
        "urn": "urn:li:activity:1",
        "text": "Shipped EDRA Phase 1B — multi-turn pitch sessions with hybrid static/dynamic rules.",
        "created_at": "2026-04-25T12:00:00Z",
        "activity": {"num_likes": 12, "num_comments": 2, "num_shares": 0, "reaction_counts": []},
        "post_type": "ugc",
        "url": "https://www.linkedin.com/feed/update/p1",
    },
    {
        "id": "p2",
        "urn": "urn:li:activity:2",
        "text": "Reading: Lin et al. on retrieval-augmented agents, and the latest MetaFlowLLM paper.",
        "created_at": "2026-04-22T09:00:00Z",
        "activity": {"num_likes": 5, "num_comments": 0, "num_shares": 0, "reaction_counts": []},
        "post_type": "ugc",
        "url": "https://www.linkedin.com/feed/update/p2",
    },
    {
        "id": "p3",
        "urn": "urn:li:activity:3",
        "text": "Looking for collaborators on adaptive-rule research — DM me on the Defy floor.",
        "created_at": "2026-04-20T15:00:00Z",
        "activity": {"num_likes": 18, "num_comments": 4, "num_shares": 1, "reaction_counts": []},
        "post_type": "ugc",
        "url": "https://www.linkedin.com/feed/update/p3",
    },
]


class LinkedInRapidAPISource:
    """Resolves a LinkedIn URL or handle to a Profile via two RapidAPI calls.

    Each successful real fetch costs at least two requests against the free
    50/mo quota — see module docstring. Pass `cache_dir` to enable on-disk
    cache; leaving it None (the default) disables the cache (used in tests).
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

        # Mock short-circuits before identifier parsing so the booth can demo
        # the live-mode UI without a real subscription, and the "profile" is
        # always the author's regardless of what the visitor typed in.
        if self._api_key == MOCK_KEY_SENTINEL:
            log.info("LinkedInRapidAPISource: returning mock author profile")
            return _map_to_profile(
                _AUTHOR_LINKEDIN_URL,
                _MOCK_AUTHOR_PROFILE_DATA,
                _MOCK_AUTHOR_POSTS_DATA,
            )

        username = _username_from_input(identifier)
        if not username:
            raise ProfileNotFound(
                f"could not parse LinkedIn handle from {identifier!r}"
            )
        canonical_url = _CANONICAL_URL_TEMPLATE.format(handle=username)

        cached = self._cache_load(canonical_url)
        if cached is not None:
            log.info("LinkedInRapidAPISource: cache hit for %s", canonical_url)
            return _map_to_profile(
                canonical_url,
                cached["profile_data"],
                cached.get("posts_data") or [],
            )

        # Profile is mandatory — failures propagate. Posts is best-effort —
        # if the posts call fails we still return a Profile, falling back
        # to bio + experience descriptions for recent_signals.
        profile_data = await self._fetch_profile_data(username)
        urn = (profile_data.get("urn") or "").strip()
        posts_data: list[dict[str, Any]] = []
        if urn:
            try:
                posts_data = await self._fetch_posts(urn)
            except (ProfileSourceUnavailable, ProfileNotFound) as e:
                log.warning(
                    "LinkedInRapidAPISource: posts fetch failed for %s — %s "
                    "(falling back to profile-only signals)",
                    urn, e,
                )

        self._cache_save(canonical_url, profile_data, posts_data)
        return _map_to_profile(canonical_url, profile_data, posts_data)

    async def _fetch_profile_data(self, username: str) -> dict[str, Any]:
        url = f"https://{self._host}/api/v1/user/profile"
        envelope = await self._http_get(
            url,
            params={
                "username": username,
                "include_experiences": "true",
                "include_bio": "true",
            },
        )
        if not isinstance(envelope, dict):
            raise ProfileSourceUnavailable(
                f"profile envelope not a dict: {repr(envelope)[:300]}"
            )
        if envelope.get("success") is False:
            raise ProfileSourceUnavailable(
                f"profile envelope success=false: {envelope.get('message') or envelope}"
            )
        data = envelope.get("data")
        if not isinstance(data, dict) or not data.get("first_name"):
            try:
                excerpt = json.dumps(envelope, ensure_ascii=False)[:400]
            except (TypeError, ValueError):
                excerpt = repr(envelope)[:400]
            raise ProfileSourceUnavailable(
                f"profile data missing first_name; got envelope: {excerpt}"
            )
        cost = envelope.get("cost")
        if cost is not None:
            log.info("RapidAPI profile cost=%s for username=%s", cost, username)
        return data

    async def _fetch_posts(self, urn: str) -> list[dict[str, Any]]:
        url = f"https://{self._host}/api/v1/user/posts"
        envelope = await self._http_get(url, params={"urn": urn})
        if not isinstance(envelope, dict):
            raise ProfileSourceUnavailable(
                f"posts envelope not a dict: {repr(envelope)[:300]}"
            )
        if envelope.get("success") is False:
            raise ProfileSourceUnavailable(
                f"posts envelope success=false: {envelope.get('message') or envelope}"
            )
        items = envelope.get("data")
        if items is None:
            return []
        if not isinstance(items, list):
            raise ProfileSourceUnavailable(
                f"posts data not a list: {repr(items)[:300]}"
            )
        cost = envelope.get("cost")
        if cost is not None:
            log.info("RapidAPI posts cost=%s for urn=%s", cost, urn)
        return items

    async def _http_get(self, url: str, params: dict[str, str]) -> Any:
        headers = {
            "x-rapidapi-key": self._api_key,
            "x-rapidapi-host": self._host,
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
        body_excerpt = (response.text or "")[:300].replace("\n", " ")
        if response.status_code == 429:
            raise ProfileSourceUnavailable(
                f"rate-limited by RapidAPI (HTTP 429): {body_excerpt}"
            )
        if response.status_code >= 500:
            raise ProfileSourceUnavailable(
                f"RapidAPI upstream error (HTTP {response.status_code}): {body_excerpt}"
            )
        if response.status_code != 200:
            raise ProfileSourceUnavailable(
                f"unexpected RapidAPI status: HTTP {response.status_code}: {body_excerpt}"
            )

        try:
            data = response.json()
        except ValueError as e:
            raise ProfileSourceUnavailable(f"malformed JSON from RapidAPI: {e}") from e

        self._dump_raw_response(url, params, data)
        return data

    def _dump_raw_response(
        self, endpoint_url: str, params: dict[str, str], payload: Any
    ) -> None:
        """Dev-aid: write each successful raw response to data/linkedin_raw/<slug>.json
        so the parser can be iterated on without re-burning RapidAPI quota.
        Silently no-op if cache_dir not configured (we reuse the same parent)."""
        if self._cache_dir is None:
            return
        try:
            raw_dir = self._cache_dir.parent / "linkedin_raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            endpoint_slug = endpoint_url.rsplit("/", 1)[-1]
            ident = (
                params.get("username")
                or params.get("urn")
                or params.get("url")
                or "noident"
            )
            file_slug = f"{endpoint_slug}__{_slugify(ident)}.json"
            (raw_dir / file_slug).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e:  # never let dev-aid fail a real fetch
            log.warning("raw response dump failed: %s", e)

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
        posts_data: list[dict[str, Any]],
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


# ── Input normalization ─────────────────────────────────────────────────


def _username_from_input(s: str) -> str:
    """Extract LinkedIn handle from either a profile URL or a bare handle.

    Accepts:
      - https://www.linkedin.com/in/<handle>/  (with or without trailing slash, scheme)
      - linkedin.com/in/<handle>
      - <handle>  (bare; validated against [A-Za-z0-9_-]+)

    Returns the handle (no leading/trailing slash). Empty string on failure.
    """
    s = (s or "").strip()
    if not s:
        return ""
    if "linkedin.com" in s.lower() or "/" in s:
        m = _USERNAME_FROM_URL_RE.search(s)
        if m and _VALID_HANDLE_RE.match(m.group(1)):
            return m.group(1)
        return ""
    if _VALID_HANDLE_RE.match(s):
        return s
    return ""


# ── Mapping helpers ──────────────────────────────────────────────────────


def _map_to_profile(
    identifier: str,
    profile_data: dict[str, Any],
    posts_data: list[dict[str, Any]],
) -> Profile:
    """Combine profile + posts data into a Profile.

    profile_data is the unwrapped envelope.data dict (caller validated
    first_name). posts_data is the unwrapped envelope.data list — empty
    list means "no posts" or "fetch failed", and triggers fallback to
    bio + experience descriptions for recent_signals.
    """
    first = (profile_data.get("first_name") or "").strip()
    last = (profile_data.get("last_name") or "").strip()
    full = (profile_data.get("full_name") or "").strip()
    name = full or f"{first} {last}".strip() or identifier

    headline = (profile_data.get("headline") or "").strip()
    bio = (profile_data.get("bio") or "").strip()

    experiences = _experiences_from_data(profile_data)

    role = (
        _role_from_experiences(experiences)
        or _role_from_headline(headline)
        or "professional"
    )
    domain = _domain_from_experiences(experiences) or _domain_from_headline(headline)
    seniority = _seniority(role, headline, experiences)
    recent_signals = (
        _signals_from_posts(posts_data)
        or _signals_from_profile(bio, experiences)
    )
    archetype_summary = _archetype_summary(role, domain, headline)

    handle = (profile_data.get("public_identifier") or "").strip()
    profile_id = f"li:{handle}" if handle else f"li:{_slugify(identifier)}"

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
        avatar_url=_avatar_url_from_data(profile_data),
        embedding=None,
        fetched_at=datetime.utcnow(),
        ttl_seconds=LIVE_TTL_SECONDS,
    )


def _avatar_url_from_data(profile_data: dict[str, Any]) -> str | None:
    """Pick a portrait avatar URL from the provider's avatar array.

    Provider returns up to 4 sizes (100/200/400/800) per `avatar[N]` with
    `{width, height, url, expires_at}`. We prefer 200x200 (sharp enough for
    the booth's right-panel portrait while staying small over the wire);
    fall back to whatever's available in 400 → 800 → 100 → first.

    URLs are signed and expire (`expires_at` is a few months out for this
    provider) — fine for the booth demo session, would need refresh for
    long-lived pages. We don't store expires_at; the avatar is purely
    cosmetic and a 404 just shows the placeholder.
    """
    raw = profile_data.get("avatar")
    if not isinstance(raw, list) or not raw:
        return None
    candidates: list[dict[str, Any]] = [a for a in raw if isinstance(a, dict) and a.get("url")]
    if not candidates:
        return None
    for preferred in (200, 400, 800, 100):
        for entry in candidates:
            if entry.get("width") == preferred:
                return str(entry["url"])
    return str(candidates[0]["url"])


def _role_from_experiences(experiences: list[Any]) -> str:
    if not experiences:
        return ""
    first = experiences[0]
    if not isinstance(first, dict):
        return ""
    return (first.get("title") or "").strip()


def _role_from_headline(headline: str) -> str:
    if not headline:
        return ""
    head = headline.split("|")[0].split("·")[0].split(" at ")[0]
    return head.strip()


def _domain_from_experiences(experiences: list[Any]) -> str:
    """Provider doesn't expose company industry directly. Fall back to the
    company name in the most recent experience as a coarse proxy.
    """
    for exp in experiences:
        if not isinstance(exp, dict):
            continue
        company = exp.get("company")
        if isinstance(company, dict):
            name = (company.get("name") or "").strip()
            if name:
                return name
    return ""


def _domain_from_headline(headline: str) -> str:
    if " at " in headline:
        return headline.split(" at ", 1)[1].split("·")[0].split("|")[0].strip() or "unspecified"
    return "unspecified"


def _seniority(role: str, headline: str, experiences: list[Any]) -> str:
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

    years = _years_from_experiences(experiences)
    if years is not None:
        if years >= 10:
            return "senior"
        if years <= 3:
            return "early"
    return "mid"


def _experiences_from_data(profile_data: dict[str, Any]) -> list[Any]:
    """Extract experience entries from profile_data.

    The provider's docs show `experiences: [{...}]` but real responses wrap
    the array in pagination metadata: `experiences: {total, has_more, data: [...]}`.
    Accept either shape.
    """
    raw = profile_data.get("experiences")
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        items = raw.get("data")
        return items if isinstance(items, list) else []
    return []


def _year_from_date_field(field: Any) -> int | None:
    """Extract a 4-digit year from a date sub-field that may be either:
      - a nested dict like `{"year": 2024, "month": 5}` (docs schema)
      - a string like `"Feb 2026"` or `"2024"` (observed real responses)
      - the sentinel `"Present"` / `"Current"` → today's year
      - empty / missing / 0 → None
    """
    if field is None or field == "" or field == 0:
        return None
    if isinstance(field, dict):
        y = field.get("year")
        return y if isinstance(y, int) and y > 0 else None
    if isinstance(field, str):
        s = field.strip()
        if not s:
            return None
        if s.lower() in ("present", "current", "ongoing"):
            return datetime.utcnow().year
        m = re.search(r"\b((?:19|20|21)\d{2})\b", s)
        return int(m.group(1)) if m else None
    if isinstance(field, int) and field > 0:
        return field
    return None


def _years_from_experiences(experiences: list[Any]) -> int | None:
    """Span between earliest experience start year and latest end year.

    Missing/empty end with a known start is treated as "current" → today.
    """
    starts: list[int] = []
    ends: list[int] = []
    for exp in experiences:
        if not isinstance(exp, dict):
            continue
        date = exp.get("date")
        if not isinstance(date, dict):
            continue
        start = _year_from_date_field(date.get("start"))
        end = _year_from_date_field(date.get("end"))
        if start is not None:
            starts.append(start)
            if end is None:
                ends.append(datetime.utcnow().year)
        if end is not None:
            ends.append(end)
    if starts and ends:
        return max(ends) - min(starts)
    return None


def _signals_from_posts(posts: list[dict[str, Any]]) -> list[str]:
    """Top-3 original (UGC) posts, most recent first, truncated to 140.

    Activity-type posts (likes, reshares without commentary) are skipped
    because the opener wants to reference what the visitor *said*, not
    what they amplified. If filtering UGC leaves us with nothing, we
    fall back to any post that has non-empty text — better signal than none.
    """
    if not isinstance(posts, list):
        return []
    originals = [
        p for p in posts
        if isinstance(p, dict) and (p.get("post_type") or "").lower() == "ugc"
    ]
    if not originals:
        originals = [
            p for p in posts
            if isinstance(p, dict) and (p.get("text") or "").strip()
        ]
    # ISO 8601 timestamps sort lexicographically as chronologically.
    originals.sort(key=lambda p: p.get("created_at") or "", reverse=True)
    out: list[str] = []
    for p in originals:
        text = (p.get("text") or "").strip()
        if text:
            out.append(_truncate(text, 140))
        if len(out) >= 3:
            break
    return out


def _signals_from_profile(bio: str, experiences: list[Any]) -> list[str]:
    """Fallback when posts are missing/empty: bio + top experience descriptions."""
    out: list[str] = []
    if bio:
        out.append(_truncate(bio, 140))
    for exp in experiences[:2]:
        if not isinstance(exp, dict):
            continue
        desc = (exp.get("description") or "").strip()
        if desc:
            out.append(_truncate(desc, 140))
        if len(out) >= 3:
            break
    return out


def _archetype_summary(role: str, domain: str, headline: str) -> str:
    parts = [role]
    if domain and domain != "unspecified":
        parts.append(f"at {domain}")
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
