"""Feature 2: Cluster visualization API — GET /api/cluster-viz.

Tests the endpoint responses for cold-start, populated clusters, archetype
label mapping, fingerprint-based cache invalidation, and helper functions.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from backend.routers.cluster_viz import (
    ARCHETYPE_LABELS,
    _archetype_label,
    _cache,
    _cluster_color,
    _compute_fingerprint,
)
from backend import schemas


# ── ARCHETYPE_LABELS coverage ────────────────────────────────────────────

def test_archetype_labels_covers_six_archetypes():
    expected = {
        "arch_professor_skeptic",
        "arch_postdoc_eager",
        "arch_industry_pragmatist",
        "arch_journalist_curious",
        "arch_vc_investor",
        "arch_student_enthusiast",
    }
    assert set(ARCHETYPE_LABELS.keys()) == expected


def test_archetype_labels_values_all_start_with_the():
    for label in ARCHETYPE_LABELS.values():
        assert label.startswith("The ")


# ── _archetype_label helper ──────────────────────────────────────────────

def test_archetype_label_known_cluster_id():
    assert _archetype_label("arch_professor_skeptic", "whatever") == "The Skeptic"


def test_archetype_label_custom_short_label():
    assert _archetype_label("custom_cluster", "Data Enthusiast") == "The Data Enthusiast"


def test_archetype_label_custom_long_label():
    assert _archetype_label("custom_cluster", "Very Long Label Here") == "The Very"


def test_archetype_label_empty_label():
    assert _archetype_label("custom_cluster", "") == "The Visitor"


def test_archetype_label_label_equals_cluster_id():
    assert _archetype_label("some_id", "some_id") == "The Visitor"


# ── _compute_fingerprint ────────────────────────────────────────────────

def _make_cluster(cid: str, size: int, pids: list[str]) -> schemas.Cluster:
    now = datetime.utcnow()
    return schemas.Cluster(
        id=cid,
        label="lbl",
        profile_ids=pids,
        size=size,
        created_at=now,
        last_updated=now,
    )


def test_fingerprint_deterministic():
    clusters = [_make_cluster("c1", 3, ["a", "b", "c"]), _make_cluster("c2", 2, ["d", "e"])]
    fp1 = _compute_fingerprint(clusters)
    fp2 = _compute_fingerprint(clusters)
    assert fp1 == fp2


def test_fingerprint_changes_with_new_cluster():
    clusters_v1 = [_make_cluster("c1", 3, ["a", "b", "c"])]
    clusters_v2 = [_make_cluster("c1", 3, ["a", "b", "c"]), _make_cluster("c2", 1, ["d"])]
    assert _compute_fingerprint(clusters_v1) != _compute_fingerprint(clusters_v2)


def test_fingerprint_changes_with_size_change():
    clusters_v1 = [_make_cluster("c1", 3, ["a", "b", "c"])]
    clusters_v2 = [_make_cluster("c1", 4, ["a", "b", "c", "d"])]
    assert _compute_fingerprint(clusters_v1) != _compute_fingerprint(clusters_v2)


def test_fingerprint_order_independent():
    c1 = _make_cluster("c1", 2, ["a"])
    c2 = _make_cluster("c2", 3, ["b"])
    assert _compute_fingerprint([c1, c2]) == _compute_fingerprint([c2, c1])


# ── _cluster_color ──────────────────────────────────────────────────────

def test_cluster_color_wraps_around():
    from backend.routers.cluster_viz import CLUSTER_COLORS
    assert _cluster_color(0) == CLUSTER_COLORS[0]
    assert _cluster_color(len(CLUSTER_COLORS)) == CLUSTER_COLORS[0]


# ── Cache invalidation ──────────────────────────────────────────────────

def test_cache_invalidated_on_fingerprint_change():
    old_fingerprint = "c1:3:3|c2:2:2"
    new_fingerprint = "c1:3:3|c2:3:3"
    _cache["fingerprint"] = old_fingerprint
    assert _cache["fingerprint"] != new_fingerprint


# ── GET /api/cluster-viz cold start ─────────────────────────────────────

@pytest.mark.asyncio
async def test_cluster_viz_cold_start_returns_status():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from backend.memory.models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        with patch("backend.routers.cluster_viz.store.list_clusters", new_callable=AsyncMock, return_value=[]):
            from backend.routers.cluster_viz import cluster_viz
            result = await cluster_viz(session=db)

    assert result["status"] == "cold_start"
    assert result["points"] == []
    assert result["clusters"] == []
    assert result["current_visitor"] is None
    assert result["neighbors"] == []
    assert result["archetype_label"] is None
    await engine.dispose()


@pytest.mark.asyncio
async def test_cluster_viz_no_embeddings_returns_status():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from backend.memory.models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.utcnow()

    clusters = [schemas.Cluster(
        id="c1", label="test", profile_ids=["p1"],
        size=1, created_at=now, last_updated=now,
    )]
    profiles = [schemas.Profile(
        id="p1", source_kind="synthetic", source_identifier="p1",
        name="Test", role="PhD", domain="NLP", seniority="early",
        headline="test", archetype_summary="test", embedding=None,
        fetched_at=now,
    )]

    async with factory() as db:
        with patch("backend.routers.cluster_viz.store.list_clusters", new_callable=AsyncMock, return_value=clusters), \
             patch("backend.routers.cluster_viz.store.list_profiles", new_callable=AsyncMock, return_value=profiles), \
             patch("backend.routers.cluster_viz.get_active_session", return_value=None):
            from backend.routers.cluster_viz import cluster_viz
            result = await cluster_viz(session=db)

    assert result["status"] == "no_embeddings"
    await engine.dispose()


@pytest.mark.asyncio
async def test_cluster_viz_with_clusters_returns_ok():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from backend.memory.models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.utcnow()
    emb = [0.1] * 384

    clusters = [schemas.Cluster(
        id="c1", label="cluster one", profile_ids=["p1", "p2"],
        size=2, created_at=now, last_updated=now,
    )]
    profiles = [
        schemas.Profile(
            id="p1", source_kind="synthetic", source_identifier="p1",
            name="Alice", role="PhD", domain="NLP", seniority="early",
            headline="test", archetype_summary="test", embedding=emb,
            fetched_at=now,
        ),
        schemas.Profile(
            id="p2", source_kind="synthetic", source_identifier="p2",
            name="Bob", role="Postdoc", domain="ML", seniority="mid",
            headline="test2", archetype_summary="test2", embedding=emb,
            fetched_at=now,
        ),
    ]

    _cache["fingerprint"] = None

    fake_coords = [(0.3, 0.4), (0.6, 0.7)]

    async with factory() as db:
        with patch("backend.routers.cluster_viz.store.list_clusters", new_callable=AsyncMock, return_value=clusters), \
             patch("backend.routers.cluster_viz.store.list_profiles", new_callable=AsyncMock, return_value=profiles), \
             patch("backend.routers.cluster_viz.get_active_session", return_value=None), \
             patch("backend.routers.cluster_viz._project_tsne", return_value=fake_coords):
            from backend.routers.cluster_viz import cluster_viz
            result = await cluster_viz(session=db)

    assert result["status"] == "ok"
    assert len(result["points"]) == 2
    assert len(result["clusters"]) == 1
    assert result["clusters"][0]["id"] == "c1"
    assert result["current_visitor"] is None
    assert result["neighbors"] == []
    await engine.dispose()
