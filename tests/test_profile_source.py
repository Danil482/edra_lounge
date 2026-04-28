"""ProfileSource conformance + import-graph isolation (TASK.md §14).

Two acceptance criteria are validated here:

  1. The two shipped implementations conform to the ProfileSource Protocol.
     Concretely: SyntheticProfileSource resolves every archetype id to a
     well-formed Profile; LinkedInRapidAPISource raises
     ProfileSourceUnavailable in the Phase 1A stub state.

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
async def test_linkedin_stub_raises_unavailable():
    src = LinkedInRapidAPISource()
    with pytest.raises(ProfileSourceUnavailable):
        await src.fetch("https://www.linkedin.com/in/some-handle/")


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
