from __future__ import annotations

import types

from backend.clustering.summarize import summarize_profile_from_json, summarize_profile_from_archetype
from backend.clustering.knn import select_rule_by_knn
from backend.clustering.cluster import cluster_profiles, embed_single, match_cluster_to_existing


# ── helpers ──────────────────────────────────────────────────────────────────

def make_profile(id: str, embedding: list[float] | None, cluster_id: str | None):
    return types.SimpleNamespace(id=id, embedding=embedding, cluster_id=cluster_id)


def make_rule(cluster_id: str, rule_id: str):
    return types.SimpleNamespace(cluster_id=cluster_id, id=rule_id)


def make_cluster(id: str, centroid: list[float]):
    return types.SimpleNamespace(id=id, centroid_embedding=centroid)


# ── Group 1 — summarize.py ────────────────────────────────────────────────────

_PROFILE_JSON = {
    "headline": "AI Researcher",
    "location": {"city": "London"},
    "bio": None,
    "experiences": {
        "data": [
            {
                "title": "Researcher",
                "company": {"name": "DeepMind"},
                "description": "Built models.",
                "skills": ["Python", "PyTorch"],
            }
        ]
    },
}


def test_summarize_profile_from_json_deterministic():
    a = summarize_profile_from_json(_PROFILE_JSON, [])
    b = summarize_profile_from_json(_PROFILE_JSON, [])
    assert a == b
    assert "AI Researcher" in a
    assert "London" in a
    assert "Researcher" in a
    assert "DeepMind" in a
    assert "Python" in a


def test_summarize_profile_from_json_missing_fields():
    result = summarize_profile_from_json({}, [])
    assert isinstance(result, str)


def test_summarize_profile_from_json_truncates_description():
    long_desc = "x" * 400
    profile_json = {
        "experiences": {
            "data": [
                {
                    "title": "Engineer",
                    "company": {"name": "Acme"},
                    "description": long_desc,
                    "skills": [],
                }
            ]
        }
    }
    result = summarize_profile_from_json(profile_json, [])
    assert long_desc not in result


def test_summarize_profile_from_json_posts_included():
    result = summarize_profile_from_json({}, [{"text": "Hello world"}])
    assert "Post: Hello world" in result


def test_summarize_profile_from_archetype():
    mock = types.SimpleNamespace(
        role="PhD",
        domain="NLP",
        headline="Researcher",
        archetype_summary="Introvert",
        recent_signals=["published paper"],
    )
    result = summarize_profile_from_archetype(mock)
    assert "PhD" in result
    assert "NLP" in result
    assert "Researcher" in result
    assert "published paper" in result


# ── Group 2 — knn.py ─────────────────────────────────────────────────────────

import math
import numpy as np


def _unit_vec(vec: list[float]) -> list[float]:
    a = np.array(vec, dtype=np.float32)
    return (a / np.linalg.norm(a)).tolist()


_DIR_A_8 = _unit_vec([1, 0, 0, 0, 0, 0, 0, 0])
_DIR_B_8 = _unit_vec([0, 1, 0, 0, 0, 0, 0, 0])
_DIR_ORTHO_8 = _unit_vec([0, 0, 0, 0, 0, 0, 0, 1])


def _corpus_around(direction: list[float], cluster_id: str, n: int = 10, noise: float = 0.05):
    entries = []
    for i in range(n):
        perturbed = [d + (i * noise / n) * (0.5 - (j % 2)) for j, d in enumerate(direction)]
        entries.append((f"{cluster_id}_{i}", _unit_vec(perturbed), cluster_id))
    return entries


def test_knn_single_cluster_dominance():
    corpus = _corpus_around(_DIR_A_8, "A", n=10) + _corpus_around(_DIR_B_8, "B", n=10)
    rule_a = make_rule("A", "R.01")
    rule_b = make_rule("B", "R.02")
    query = make_profile("q", _unit_vec([0.95, 0.05, 0, 0, 0, 0, 0, 0]), None)

    result = select_rule_by_knn(query, corpus, {"A": rule_a, "B": rule_b})
    assert result is rule_a


def test_knn_split_vote():
    corpus = _corpus_around(_DIR_A_8, "A", n=10) + _corpus_around(_DIR_B_8, "B", n=10)
    rule_a = make_rule("A", "R.01")
    rule_b = make_rule("B", "R.02")
    query = make_profile("q", _unit_vec([0.707, 0.707, 0, 0, 0, 0, 0, 0]), None)

    result = select_rule_by_knn(query, corpus, {"A": rule_a, "B": rule_b})
    assert result is not None
    assert result in (rule_a, rule_b)


def test_knn_all_noise():
    corpus = _corpus_around(_DIR_A_8, "A", n=10)
    query = make_profile("q", _DIR_ORTHO_8, None)
    result = select_rule_by_knn(query, corpus, {"A": make_rule("A", "R.01")})
    assert result is None


def test_knn_empty_corpus():
    query = make_profile("q", _unit_vec([1, 0, 0, 0, 0, 0, 0, 0]), None)
    result = select_rule_by_knn(query, [], {})
    assert result is None


def test_knn_no_active_rules():
    corpus = _corpus_around(_DIR_A_8, "A", n=10)
    query = make_profile("q", _unit_vec([1, 0, 0, 0, 0, 0, 0, 0]), None)
    result = select_rule_by_knn(query, corpus, {})
    assert result is None


def test_knn_profile_no_embedding():
    corpus = _corpus_around(_DIR_A_8, "A", n=10)
    query = make_profile("q", None, None)
    result = select_rule_by_knn(query, corpus, {"A": make_rule("A", "R.01")})
    assert result is None


# ── Group 3 — cluster.py ──────────────────────────────────────────────────────

def test_cluster_profiles_uses_profile_embeddings():
    import sys
    import types as _types
    import unittest.mock as _mock
    import numpy as _np

    profiles = [
        make_profile(f"p{i}", [float(j == i) for j in range(5)], None)
        for i in range(5)
    ]

    fake_hdbscan_module = _types.ModuleType("hdbscan")

    class _FakeHDBSCAN:
        def __init__(self, **kwargs):
            pass

        def fit_predict(self, X):
            return _np.zeros(len(X), dtype=int)

    fake_hdbscan_module.HDBSCAN = _FakeHDBSCAN

    with _mock.patch.dict(sys.modules, {"hdbscan": fake_hdbscan_module}):
        result = cluster_profiles(profiles)

    assert isinstance(result, dict)


def test_embed_single_returns_list_of_floats():
    result = embed_single("hello world")
    assert isinstance(result, list)
    assert len(result) == 384
    assert all(isinstance(v, float) for v in result)


def test_match_cluster_to_existing_finds_match():
    centroid = [0.0] * 384
    centroid[0] = 1.0
    cluster = make_cluster("C1", centroid)
    result = match_cluster_to_existing(centroid, [cluster], threshold=0.85)
    assert result == "C1"


def test_match_cluster_to_existing_no_match():
    centroid_a = [0.0] * 384
    centroid_a[0] = 1.0
    centroid_b = [0.0] * 384
    centroid_b[1] = 1.0
    cluster = make_cluster("C1", centroid_a)
    result = match_cluster_to_existing(centroid_b, [cluster], threshold=0.85)
    assert result is None


def test_match_cluster_to_existing_empty():
    centroid = [0.0] * 384
    centroid[0] = 1.0
    result = match_cluster_to_existing(centroid, [], threshold=0.85)
    assert result is None
