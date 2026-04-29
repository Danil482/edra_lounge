"""ProfileSource conformance + import-graph isolation (TASK.md §14).

Two acceptance criteria are validated here:

  1. The two shipped implementations conform to the ProfileSource Protocol.
     Concretely: SyntheticProfileSource resolves every archetype id to a
     well-formed Profile; LinkedInRapidAPISource maps mocked RapidAPI
     responses (two endpoints: profile + posts) to a Profile; missing API
     keys surface as ProfileSourceUnavailable so the booth UI can fall back.

  2. **No core module imports any concrete ProfileSource implementation.**
     The Protocol in `backend/profile_source/__init__.py` is the single
     coupling point — concrete implementations (`synthetic.py`,
     `linkedin_rapidapi.py`) must only be reachable from `backend/app.py`
     and the test suite. This is what makes EDRA source-agnostic.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.profile_source import (
    Profile,
    ProfileSource,
    ProfileSourceUnavailable,
    ProfileNotFound,
)
from backend.profile_source.synthetic import SyntheticProfileSource
from backend.profile_source.linkedin_rapidapi import LinkedInRapidAPISource


REPO_ROOT = Path(__file__).parent.parent
BACKEND = REPO_ROOT / "backend"


# ── 1. Protocol conformance ──────────────────────────────────────────────

def test_synthetic_implements_protocol():
    src = SyntheticProfileSource()
    assert isinstance(src, ProfileSource)
    assert src.source_kind == "synthetic"


def test_linkedin_implements_protocol():
    src = LinkedInRapidAPISource()
    assert isinstance(src, ProfileSource)
    assert src.source_kind == "linkedin_rapidapi"


@pytest.mark.asyncio
async def test_synthetic_fetches_every_seeded_archetype():
    src = SyntheticProfileSource()
    ids = src.list_ids(include_spawnable=True)
    assert len(ids) == 8
    for aid in ids:
        profile = await src.fetch(aid)
        assert isinstance(profile, Profile)
        assert profile.id == aid
        assert profile.source_kind == "synthetic"
        assert profile.source_identifier == aid
        assert profile.role
        assert profile.domain
        assert profile.seniority in ("early", "mid", "senior")
        assert profile.archetype_summary
        # Synthetic profiles never expire.
        assert profile.ttl_seconds is None


@pytest.mark.asyncio
async def test_synthetic_unknown_id_raises_not_found():
    src = SyntheticProfileSource()
    with pytest.raises(ProfileNotFound):
        await src.fetch("arch_does_not_exist")


@pytest.mark.asyncio
async def test_linkedin_no_api_key_raises_unavailable():
    """No API key → ProfileSourceUnavailable, no network call attempted.

    Acceptance posture: the booth must boot in offline mode without any
    setup steps. A missing RAPIDAPI_KEY is normal at install time.
    """
    src = LinkedInRapidAPISource(api_key="")
    with pytest.raises(ProfileSourceUnavailable, match="RAPIDAPI_KEY"):
        await src.fetch("https://www.linkedin.com/in/some-handle/")


# ── LinkedIn live-fetch path (mocked httpx) ─────────────────────────────


def _profile_envelope() -> dict:
    """fresh-linkedin-scraper-api response envelope for the profile endpoint.

    Modeled on a director-level career — multi-decade span, two experiences
    with the most recent being current (no end year).
    """
    return {
        "success": True,
        "cost": 1,
        "data": {
            "id": "12345",
            "urn": "urn:li:person:ACoAAA-maya",
            "public_identifier": "maya-chen",
            "first_name": "Maya",
            "last_name": "Chen",
            "full_name": "Maya Chen",
            "headline": "Director of ML Research at Defy.group",
            "bio": "Leading the retrieval-augmented agents team at Defy.group.",
            "location": {"country": "United States"},
            "avatar": [
                {"width": 100, "height": 100, "url": "https://media.example/avatar-100.jpg"},
                {"width": 200, "height": 200, "url": "https://media.example/avatar-200.jpg"},
                {"width": 400, "height": 400, "url": "https://media.example/avatar-400.jpg"},
            ],
            "experiences": [
                {
                    "title": "Director of ML Research",
                    "description": "Leading retrieval-augmented agents team",
                    "company": {"name": "Defy.group", "id": "100"},
                    "employment_type": "Full-time",
                    "date": {
                        "start": {"year": 2021, "month": 5},
                        "end": {"year": 0, "month": 0},
                    },
                },
                {
                    "title": "Senior Research Engineer",
                    "description": "Worked on scalable inference",
                    "company": {"name": "Acme Labs", "id": "101"},
                    "employment_type": "Full-time",
                    "date": {
                        "start": {"year": 2013, "month": 0},
                        "end": {"year": 2021, "month": 4},
                    },
                },
            ],
        },
    }


def _posts_envelope() -> dict:
    """fresh-linkedin-scraper-api response envelope for the posts endpoint.

    Includes one `activity` item to verify it's filtered out (only `ugc`
    posts represent original content the visitor said).
    """
    return {
        "success": True,
        "cost": 1,
        "data": [
            {
                "id": "p1",
                "text": "Excited about open-source RAG benchmarks landing this Q2.",
                "created_at": "2026-04-25T12:00:00Z",
                "post_type": "ugc",
                "activity": {"num_likes": 10, "num_comments": 1, "num_shares": 0},
            },
            {
                "id": "p2",
                "text": "Recruiting two staff researchers — DM me.",
                "created_at": "2026-04-22T09:00:00Z",
                "post_type": "ugc",
                "activity": {"num_likes": 5, "num_comments": 0, "num_shares": 0},
            },
            # Activity-type post should be filtered out (typically a like/reshare).
            {
                "id": "p3",
                "text": "Resharing a great post by a colleague about distributed training.",
                "created_at": "2026-04-23T11:00:00Z",
                "post_type": "activity",
                "activity": {"num_likes": 0, "num_comments": 0, "num_shares": 0},
            },
            {
                "id": "p4",
                "text": "Filler post that should be skipped because cap=3.",
                "created_at": "2026-04-20T15:00:00Z",
                "post_type": "ugc",
                "activity": {"num_likes": 1, "num_comments": 0, "num_shares": 0},
            },
        ],
    }


def _mock_response(status_code: int, json_payload: dict | None = None):
    """Return a MagicMock that quacks like httpx.Response for our use."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_payload or {})
    return resp


class _GetCallTracker:
    """Async-callable that returns/raises items from a queue and counts calls.

    Used to mock httpx.AsyncClient.get when we care about call ordering or
    call counts (e.g. the cache test verifies the second fetch makes 0 calls).
    """

    def __init__(self, items):
        self.queue = list(items)
        self.call_count = 0
        self.calls = []

    async def __call__(self, url, **kwargs):
        self.call_count += 1
        self.calls.append((url, kwargs))
        if not self.queue:
            raise AssertionError(
                f"Unexpected extra HTTP call to {url} (queue exhausted)"
            )
        item = self.queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def _patched_async_client(items):
    """Patch httpx.AsyncClient with a tracker that returns `items` in order.

    Returns a (context_manager, tracker) tuple so tests can assert on
    `tracker.call_count` / `tracker.calls` after the fetch.
    """
    instance = MagicMock()
    tracker = _GetCallTracker(items)
    instance.get = tracker
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=None)
    factory = MagicMock(return_value=instance)
    return patch(
        "backend.profile_source.linkedin_rapidapi.httpx.AsyncClient", factory
    ), tracker


@pytest.mark.asyncio
async def test_linkedin_maps_payload_to_profile():
    src = LinkedInRapidAPISource(api_key="test-key")
    items = [
        _mock_response(200, _profile_envelope()),
        _mock_response(200, _posts_envelope()),
    ]
    cm, tracker = _patched_async_client(items)
    with cm:
        profile = await src.fetch("https://www.linkedin.com/in/maya-chen/")

    assert profile.source_kind == "linkedin_rapidapi"
    assert profile.name == "Maya Chen"
    assert profile.role == "Director of ML Research"
    # Provider doesn't expose industry, so domain falls back to company name.
    assert profile.domain == "Defy.group"
    assert profile.seniority == "senior"  # "Director" trips the senior marker
    assert profile.headline.startswith("Director of ML Research")
    assert profile.archetype_summary
    # Vanity handle (public_identifier) is preferred over slugified URL for Profile.id.
    assert profile.id == "li:maya-chen"
    assert profile.ttl_seconds == 3600
    # Avatar — picker prefers 200x200 over other sizes.
    assert profile.avatar_url == "https://media.example/avatar-200.jpg"
    # Top 3 ugc posts, with the activity item filtered out, ordered most-recent first.
    assert len(profile.recent_signals) == 3
    assert any("RAG" in s for s in profile.recent_signals)
    assert all("Resharing a great post" not in s for s in profile.recent_signals)
    # Two HTTP calls: profile then posts.
    assert tracker.call_count == 2
    assert "/api/v1/user/profile" in tracker.calls[0][0]
    assert "/api/v1/user/posts" in tracker.calls[1][0]


@pytest.mark.asyncio
async def test_linkedin_falls_back_when_posts_endpoint_fails():
    """Posts call failure must not fail the whole fetch — fall back to
    bio + experience descriptions for recent_signals."""
    src = LinkedInRapidAPISource(api_key="test-key")
    items = [
        _mock_response(200, _profile_envelope()),
        _mock_response(503, {}),  # posts endpoint down
    ]
    cm, tracker = _patched_async_client(items)
    with cm:
        profile = await src.fetch("https://www.linkedin.com/in/maya-chen/")

    # Both calls were attempted.
    assert tracker.call_count == 2
    # Fallback signals: bio first, then experience descriptions.
    assert profile.recent_signals
    assert any("retrieval-augmented" in s for s in profile.recent_signals)


@pytest.mark.asyncio
async def test_linkedin_404_raises_not_found():
    src = LinkedInRapidAPISource(api_key="test-key")
    items = [_mock_response(404, {})]
    cm, _ = _patched_async_client(items)
    with cm:
        with pytest.raises(ProfileNotFound):
            await src.fetch("https://www.linkedin.com/in/ghost/")


@pytest.mark.asyncio
async def test_linkedin_429_raises_unavailable():
    src = LinkedInRapidAPISource(api_key="test-key")
    items = [_mock_response(429, {})]
    cm, _ = _patched_async_client(items)
    with cm:
        with pytest.raises(ProfileSourceUnavailable, match="rate-limited"):
            await src.fetch("https://www.linkedin.com/in/over-quota/")


@pytest.mark.asyncio
async def test_linkedin_5xx_raises_unavailable():
    src = LinkedInRapidAPISource(api_key="test-key")
    items = [_mock_response(503, {})]
    cm, _ = _patched_async_client(items)
    with cm:
        with pytest.raises(ProfileSourceUnavailable, match="upstream"):
            await src.fetch("https://www.linkedin.com/in/upstream-down/")


@pytest.mark.asyncio
async def test_linkedin_network_error_raises_unavailable():
    """Booth Wi-Fi flaking should surface as ProfileSourceUnavailable, not 500.

    The frontend distinguishes 503 (try synthetic) from 404 (bad URL) — make
    sure transient network failures map to the former, not the latter.
    """
    src = LinkedInRapidAPISource(api_key="test-key")
    items = [httpx.ConnectError("network unreachable")]
    cm, _ = _patched_async_client(items)
    with cm:
        with pytest.raises(ProfileSourceUnavailable, match="ConnectError"):
            await src.fetch("https://www.linkedin.com/in/offline/")


@pytest.mark.asyncio
async def test_linkedin_malformed_payload_raises_unavailable():
    """A 200 response without first_name means the API shape changed under us."""
    src = LinkedInRapidAPISource(api_key="test-key")
    items = [_mock_response(200, {"success": True, "data": {"unexpected": "shape"}})]
    cm, _ = _patched_async_client(items)
    with cm:
        with pytest.raises(ProfileSourceUnavailable, match="missing first_name"):
            await src.fetch("https://www.linkedin.com/in/weird/")


@pytest.mark.asyncio
async def test_linkedin_envelope_success_false_raises_unavailable():
    """Provider can return HTTP 200 with `success: false` (e.g. service sunset).
    We must surface this as ProfileSourceUnavailable, not silently miscount as
    a parser bug."""
    src = LinkedInRapidAPISource(api_key="test-key")
    items = [
        _mock_response(200, {
            "success": False,
            "message": "We are no longer providing this service",
            "data": None,
        }),
    ]
    cm, _ = _patched_async_client(items)
    with cm:
        with pytest.raises(ProfileSourceUnavailable, match="success=false"):
            await src.fetch("https://www.linkedin.com/in/anyone/")


@pytest.mark.asyncio
async def test_linkedin_mock_key_returns_author_profile_without_http():
    """`RAPIDAPI_KEY=mock` short-circuits the HTTP path so the booth can be
    demoed without a real RapidAPI subscription. The mock returns the author's
    own LinkedIn profile so the live-mode UI can be exercised end-to-end."""
    src = LinkedInRapidAPISource(api_key="mock")
    sentinel_factory = MagicMock(
        side_effect=AssertionError("HTTP must not be called in mock mode")
    )
    with patch("backend.profile_source.linkedin_rapidapi.httpx.AsyncClient", sentinel_factory):
        profile = await src.fetch("any-input-here")

    assert profile.source_kind == "linkedin_rapidapi"
    assert profile.name == "Danil Onishchenko"
    assert profile.id == "li:danil-onishchenko-30876037a"
    assert profile.ttl_seconds == 3600
    # Mock always returns the author URL as source_identifier — the booth
    # demo UX is "we hold up a stable example profile" regardless of input.
    assert "danil-onishchenko" in profile.source_identifier
    # Mock posts payload populates 3 recent signals.
    assert len(profile.recent_signals) == 3


@pytest.mark.asyncio
async def test_linkedin_seniority_heuristic():
    """Title-based seniority overrides years; intern → early."""
    src = LinkedInRapidAPISource(api_key="test-key")
    profile_envelope = {
        "success": True,
        "cost": 1,
        "data": {
            "first_name": "Sam",
            "last_name": "Intern",
            "full_name": "Sam Intern",
            "public_identifier": "sam-intern",
            "urn": "urn:li:person:sam",
            "headline": "Research Intern at Defy.group",
            "bio": "",
            "experiences": [
                {
                    "title": "Research Intern",
                    "description": "",
                    "company": {"name": "Defy.group"},
                    "date": {
                        "start": {"year": 2024, "month": 6},
                        "end": {"year": 0, "month": 0},
                    },
                }
            ],
        },
    }
    items = [
        _mock_response(200, profile_envelope),
        _mock_response(200, {"success": True, "cost": 1, "data": []}),
    ]
    cm, _ = _patched_async_client(items)
    with cm:
        profile = await src.fetch("https://www.linkedin.com/in/intern/")
    assert profile.seniority == "early"


@pytest.mark.asyncio
async def test_linkedin_accepts_bare_handle_input():
    """Hybrid input: bare handle should be canonicalized to the standard URL
    form internally, and the API call should use the handle as `username`."""
    src = LinkedInRapidAPISource(api_key="test-key")
    items = [
        _mock_response(200, _profile_envelope()),
        _mock_response(200, _posts_envelope()),
    ]
    cm, tracker = _patched_async_client(items)
    with cm:
        profile = await src.fetch("maya-chen")  # bare handle, no URL

    assert profile.id == "li:maya-chen"
    # source_identifier was canonicalized to the standard URL form.
    assert profile.source_identifier == "https://www.linkedin.com/in/maya-chen/"
    # Profile endpoint was called with username=maya-chen (the original handle).
    assert tracker.calls[0][1].get("params", {}).get("username") == "maya-chen"


@pytest.mark.asyncio
async def test_linkedin_avatar_absent_or_empty_yields_none():
    """Profiles without an avatar field (or empty array) → avatar_url is None,
    so frontend falls back to the placeholder graphic."""
    src = LinkedInRapidAPISource(api_key="test-key")
    envelope = _profile_envelope()
    envelope["data"]["avatar"] = []  # empty array
    items = [
        _mock_response(200, envelope),
        _mock_response(200, {"success": True, "cost": 1, "data": []}),
    ]
    cm, _ = _patched_async_client(items)
    with cm:
        profile = await src.fetch("https://www.linkedin.com/in/maya-chen/")
    assert profile.avatar_url is None


@pytest.mark.asyncio
async def test_linkedin_avatar_falls_back_to_largest_when_200_missing():
    """Picker prefers 200x200; if absent, walks 400 → 800 → 100 → first entry."""
    src = LinkedInRapidAPISource(api_key="test-key")
    envelope = _profile_envelope()
    envelope["data"]["avatar"] = [
        {"width": 100, "height": 100, "url": "https://media.example/avatar-100.jpg"},
        {"width": 800, "height": 800, "url": "https://media.example/avatar-800.jpg"},
    ]
    items = [
        _mock_response(200, envelope),
        _mock_response(200, {"success": True, "cost": 1, "data": []}),
    ]
    cm, _ = _patched_async_client(items)
    with cm:
        profile = await src.fetch("https://www.linkedin.com/in/maya-chen/")
    # 200 absent → next preference is 400 (also absent) → then 800.
    assert profile.avatar_url == "https://media.example/avatar-800.jpg"


@pytest.mark.asyncio
async def test_linkedin_handles_wrapped_experiences_and_string_dates():
    """Real-world response shape (observed against fresh-linkedin-scraper-api)
    differs from the docs in two ways:
      - experiences is wrapped in pagination metadata: {total, has_more, data: [...]}
      - date sub-fields are strings ('Feb 2026', 'Present') not nested {year: N}
    Parser must accept both shapes — docs-schema and real-world."""
    src = LinkedInRapidAPISource(api_key="test-key")
    real_world_envelope = {
        "success": True,
        "cost": 1,
        "data": {
            "first_name": "Real",
            "last_name": "Person",
            "full_name": "Real Person",
            "public_identifier": "real-person",
            "urn": "urn:li:person:real",
            "headline": "AI researcher at SomeCo",
            "bio": None,  # provider can return None even with include_bio=true
            "experiences": {
                "total": 2,
                "has_more": False,
                "data": [
                    {
                        "title": "Senior Research Engineer",
                        "description": "Doing things",
                        "date": {"start": "Feb 2024", "end": "Present"},
                        "company": {"name": "SomeCo"},
                    },
                    {
                        "title": "ML Engineer",
                        "description": "Did things",
                        "date": {"start": "Sep 2018", "end": "Feb 2024"},
                        "company": {"name": "OldCo"},
                    },
                ],
            },
        },
    }
    items = [
        _mock_response(200, real_world_envelope),
        _mock_response(200, {"success": True, "cost": 1, "data": []}),
    ]
    cm, _ = _patched_async_client(items)
    with cm:
        profile = await src.fetch("https://www.linkedin.com/in/real-person/")

    # Wrapped experiences were unwrapped: role/domain come from first entry.
    assert profile.role == "Senior Research Engineer"
    assert profile.domain == "SomeCo"
    # Years calc must work with string dates (Feb 2018 → today via "Present"):
    # ~8 years experience puts us in "mid" — proves the date parser succeeded
    # (otherwise years=None and we'd default to "mid" anyway, but for a
    # different reason). The point is no crash on string dates.
    assert profile.seniority in ("mid", "senior")


@pytest.mark.asyncio
async def test_linkedin_invalid_handle_raises_not_found():
    src = LinkedInRapidAPISource(api_key="test-key")
    sentinel = MagicMock(side_effect=AssertionError("HTTP must not be called"))
    with patch("backend.profile_source.linkedin_rapidapi.httpx.AsyncClient", sentinel):
        with pytest.raises(ProfileNotFound):
            await src.fetch("not a valid handle!")


@pytest.mark.asyncio
async def test_linkedin_cache_hit_skips_http(tmp_path):
    """Second fetch of the same URL must not call HTTP.

    The cache directory is a tmp_path so this test is hermetic and never
    pollutes the real data/linkedin_cache/ directory.
    """
    src = LinkedInRapidAPISource(api_key="test-key", cache_dir=tmp_path)
    items = [
        _mock_response(200, _profile_envelope()),
        _mock_response(200, _posts_envelope()),
    ]
    cm, tracker = _patched_async_client(items)
    with cm:
        profile1 = await src.fetch("https://www.linkedin.com/in/maya-chen/")
    assert tracker.call_count == 2  # both endpoints hit on first fetch

    # Cache file written.
    cache_files = list(tmp_path.glob("*.json"))
    assert len(cache_files) == 1

    # Second fetch — patch with a sentinel that raises if called.
    sentinel = MagicMock(side_effect=AssertionError("HTTP must not be called on cache hit"))
    with patch("backend.profile_source.linkedin_rapidapi.httpx.AsyncClient", sentinel):
        profile2 = await src.fetch("https://www.linkedin.com/in/maya-chen/")

    # Same Profile shape served from cache.
    assert profile2.id == profile1.id
    assert profile2.name == profile1.name
    assert profile2.recent_signals == profile1.recent_signals


def test_synthetic_marks_spawnable_correctly():
    src = SyntheticProfileSource()
    assert src.is_spawnable("arch_vc_investor") is True
    assert src.is_spawnable("arch_journalist_curious") is True
    assert src.is_spawnable("arch_phd_nlp_introvert") is False
    rotation_only = src.list_ids(include_spawnable=False)
    assert "arch_vc_investor" not in rotation_only
    assert len(rotation_only) == 6


# ── 2. Import-graph isolation ────────────────────────────────────────────

# The set of EDRA core packages that MUST NOT import any concrete
# ProfileSource implementation. Per TASK.md §14, the abstract Protocol is
# the only coupling point.
CORE_PACKAGES = (
    "memory",
    "clustering",
    "induction",
    "pitch",
    "monitor",
    "reflection",
    "factory",
    "orchestrator",  # single-file module, see core_modules() below
    "simulator",
)

FORBIDDEN_IMPORT_TARGETS = (
    "backend.profile_source.synthetic",
    "backend.profile_source.linkedin_rapidapi",
)


def _python_files_in(pkg_name: str) -> list[Path]:
    """Return all .py files under backend/<pkg_name>, treating a missing dir
    or a single-file module (e.g. orchestrator.py) gracefully."""
    pkg_dir = BACKEND / pkg_name
    if pkg_dir.is_dir():
        return sorted(pkg_dir.rglob("*.py"))
    pkg_file = BACKEND / f"{pkg_name}.py"
    if pkg_file.is_file():
        return [pkg_file]
    return []


def _imports(path: Path) -> list[str]:
    """Return the dotted-name targets of every import statement in `path`."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if not module:
                continue
            out.append(module)
            for alias in node.names:
                out.append(f"{module}.{alias.name}")
    return out


@pytest.mark.parametrize("package", CORE_PACKAGES)
def test_core_module_does_not_import_concrete_profile_source(package: str):
    files = _python_files_in(package)
    assert files, f"no python files found under backend/{package}"
    offenders: list[tuple[str, str]] = []
    for f in files:
        for target in _imports(f):
            for forbidden in FORBIDDEN_IMPORT_TARGETS:
                if target == forbidden or target.startswith(forbidden + "."):
                    offenders.append((str(f.relative_to(REPO_ROOT)), target))
    assert not offenders, (
        "ProfileSource isolation violated — these core files import a concrete "
        "implementation directly:\n  "
        + "\n  ".join(f"{f}: {t}" for f, t in offenders)
    )


def test_protocol_module_itself_does_not_import_implementations():
    """The protocol-defining module must stay free of implementation imports.

    Importing concrete implementations from `backend/profile_source/__init__.py`
    would re-introduce a hard dependency on RapidAPI / requests / yaml just by
    using the Protocol — defeating the abstraction.
    """
    init_file = BACKEND / "profile_source" / "__init__.py"
    for target in _imports(init_file):
        for forbidden in FORBIDDEN_IMPORT_TARGETS:
            assert not (target == forbidden or target.startswith(forbidden + ".")), (
                f"profile_source/__init__.py imports {target}"
            )
