"""ProfileSource conformance + import-graph isolation (TASK.md §14).

Two acceptance criteria are validated here:

  1. The two shipped implementations conform to the ProfileSource Protocol.
     Concretely: SyntheticProfileSource resolves every archetype id to a
     well-formed Profile; LinkedInRapidAPISource maps mocked RapidAPI
     responses to a Profile; missing API keys surface as
     ProfileSourceUnavailable so the booth UI can fall back.

  2. **No core module imports any concrete ProfileSource implementation.**
     The Protocol in `backend/profile_source/__init__.py` is the single
     coupling point — concrete implementations (`synthetic.py`,
     `linkedin_rapidapi.py`) must only be reachable from `backend/app.py`
     and the test suite. This is what makes EDRA source-agnostic.
"""

from __future__ import annotations

import ast
import re
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


def _ok_payload() -> dict:
    """Fresh-linkedin-profile-data success shape, abridged."""
    return {
        "data": {
            "full_name": "Maya Chen",
            "headline": "Director of ML Research at Defy.group",
            "job_title": "Director of ML Research",
            "industry": "Computer Software",
            "years_of_experience": 12,
            "company": {"name": "Defy.group", "industry": "Computer Software"},
            "experiences": [
                {
                    "title": "Director of ML Research",
                    "description": "Lead retrieval-augmented agents team",
                    "duration": {"years": 3},
                }
            ],
            "posts": [
                {"text": "Excited about open-source RAG benchmarks landing this Q2."},
                {"text": "Recruiting two staff researchers — DM me."},
                {"text": "Filler post that should be skipped because cap=3."},
            ],
        }
    }


def _mock_response(status_code: int, json_payload: dict | None = None):
    """Return a MagicMock that quacks like httpx.Response for our use."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_payload or {})
    return resp


def _patched_async_client(get_return=None, get_side_effect=None):
    """Patch backend.profile_source.linkedin_rapidapi.httpx.AsyncClient so the
    module under test uses a fully-mocked client."""
    instance = MagicMock()
    instance.get = AsyncMock(return_value=get_return, side_effect=get_side_effect)
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=None)
    factory = MagicMock(return_value=instance)
    return patch("backend.profile_source.linkedin_rapidapi.httpx.AsyncClient", factory)


@pytest.mark.asyncio
async def test_linkedin_maps_payload_to_profile():
    src = LinkedInRapidAPISource(api_key="test-key")
    response = _mock_response(200, _ok_payload())
    with _patched_async_client(get_return=response):
        profile = await src.fetch("https://www.linkedin.com/in/maya-chen/")

    assert profile.source_kind == "linkedin_rapidapi"
    assert profile.name == "Maya Chen"
    assert profile.role == "Director of ML Research"
    assert profile.domain == "Computer Software"
    assert profile.seniority == "senior"  # "Director" trips the senior marker
    assert profile.headline.startswith("Director of ML Research")
    assert profile.archetype_summary  # non-empty summary
    assert profile.id.startswith("li:")
    assert profile.ttl_seconds == 3600
    # We pull at most three signals — verify cap.
    assert 1 <= len(profile.recent_signals) <= 3
    assert any("RAG" in s for s in profile.recent_signals)


@pytest.mark.asyncio
async def test_linkedin_404_raises_not_found():
    src = LinkedInRapidAPISource(api_key="test-key")
    response = _mock_response(404, {})
    with _patched_async_client(get_return=response):
        with pytest.raises(ProfileNotFound):
            await src.fetch("https://www.linkedin.com/in/ghost/")


@pytest.mark.asyncio
async def test_linkedin_429_raises_unavailable():
    src = LinkedInRapidAPISource(api_key="test-key")
    response = _mock_response(429, {})
    with _patched_async_client(get_return=response):
        with pytest.raises(ProfileSourceUnavailable, match="rate-limited"):
            await src.fetch("https://www.linkedin.com/in/over-quota/")


@pytest.mark.asyncio
async def test_linkedin_5xx_raises_unavailable():
    src = LinkedInRapidAPISource(api_key="test-key")
    response = _mock_response(503, {})
    with _patched_async_client(get_return=response):
        with pytest.raises(ProfileSourceUnavailable, match="upstream"):
            await src.fetch("https://www.linkedin.com/in/upstream-down/")


@pytest.mark.asyncio
async def test_linkedin_network_error_raises_unavailable():
    """Booth Wi-Fi flaking should surface as ProfileSourceUnavailable, not 500.

    The frontend distinguishes 503 (try synthetic) from 404 (bad URL) — make
    sure transient network failures map to the former, not the latter.
    """
    src = LinkedInRapidAPISource(api_key="test-key")
    err = httpx.ConnectError("network unreachable")
    with _patched_async_client(get_side_effect=err):
        with pytest.raises(ProfileSourceUnavailable, match="ConnectError"):
            await src.fetch("https://www.linkedin.com/in/offline/")


@pytest.mark.asyncio
async def test_linkedin_malformed_payload_raises_unavailable():
    src = LinkedInRapidAPISource(api_key="test-key")
    response = _mock_response(200, {"unexpected": "shape"})
    with _patched_async_client(get_return=response):
        with pytest.raises(ProfileSourceUnavailable, match="missing"):
            await src.fetch("https://www.linkedin.com/in/weird/")


@pytest.mark.asyncio
async def test_linkedin_mock_key_returns_author_profile_without_http():
    """`RAPIDAPI_KEY=mock` short-circuits the HTTP path so the booth can be
    demoed without a real RapidAPI subscription. The mock returns the author's
    own LinkedIn profile so the live-mode UI can be exercised end-to-end."""
    src = LinkedInRapidAPISource(api_key="mock")
    # Patching the AsyncClient with a sentinel that *raises if called* —
    # mock mode must not perform any HTTP.
    sentinel_factory = MagicMock(side_effect=AssertionError("HTTP must not be called in mock mode"))
    with patch("backend.profile_source.linkedin_rapidapi.httpx.AsyncClient", sentinel_factory):
        profile = await src.fetch("any-identifier-here")

    assert profile.source_kind == "linkedin_rapidapi"
    assert profile.name == "Danil Onishchenko"
    assert profile.ttl_seconds == 3600
    # Identifier is rewritten to the author URL so Profile.id is stable.
    assert "danil-onishchenko" in profile.source_identifier


@pytest.mark.asyncio
async def test_linkedin_seniority_heuristic():
    """Title-based seniority overrides years; intern → early."""
    src = LinkedInRapidAPISource(api_key="test-key")
    payload = {
        "data": {
            "full_name": "Sam Intern",
            "headline": "Research Intern at Defy.group",
            "job_title": "Research Intern",
            "industry": "Research",
            "years_of_experience": 1,
        }
    }
    response = _mock_response(200, payload)
    with _patched_async_client(get_return=response):
        profile = await src.fetch("https://www.linkedin.com/in/intern/")
    assert profile.seniority == "early"


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
