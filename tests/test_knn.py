"""K=7 cosine-weighted nearest-neighbor rule selection.

select_rule_by_knn finds the K nearest neighbors in the corpus, gates on
mean cosine similarity, and uses weighted voting to pick the best cluster rule.
Embeddings are synthetic 8-dim unit vectors so the test does not depend on the
real MiniLM model.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np

from backend import schemas
from backend.clustering.knn import select_rule_by_knn
from backend.config import settings


def _unit(vec: list[float]) -> list[float]:
    a = np.array(vec, dtype=np.float32)
    return (a / np.linalg.norm(a)).tolist()


DIR_A = _unit([1, 0, 0, 0, 0, 0, 0, 0])
DIR_B = _unit([0, 1, 0, 0, 0, 0, 0, 0])
DIR_ORTHO = _unit([0, 0, 0, 0, 0, 0, 0, 1])


def _corpus_around(direction: list[float], cluster_id: str, n: int = 10, noise: float = 0.05):
    entries = []
    for i in range(n):
        perturbed = [d + (i * noise / n) * (0.5 - (j % 2)) for j, d in enumerate(direction)]
        entries.append((f"{cluster_id}_{i}", _unit(perturbed), cluster_id))
    return entries


def _profile(embedding: list[float] | None, pid: str = "visitor") -> schemas.Profile:
    return schemas.Profile(
        id=pid,
        source_kind="synthetic",
        source_identifier="x",
        name="V",
        role="r",
        domain="d",
        seniority="senior",
        headline="h",
        archetype_summary="s",
        embedding=embedding,
        fetched_at=datetime.utcnow(),
    )


def _rule(cluster_id: str) -> schemas.Rule:
    return schemas.Rule(
        id=f"R.{cluster_id}",
        cluster_id=cluster_id,
        slots=[
            schemas.RuleSlot(name="framing", kind="static", value="knowledge-share"),
            schemas.RuleSlot(name="tone", kind="static", value="warm"),
            schemas.RuleSlot(name="opener_type", kind="static", value="cold"),
            schemas.RuleSlot(name="word_target", kind="static", value="medium"),
            schemas.RuleSlot(name="ask_size", kind="static", value="trial"),
        ],
        induced_at=datetime.utcnow(),
    )


def test_returns_rule_of_majority_cluster():
    corpus = _corpus_around(DIR_A, "A", n=10) + _corpus_around(DIR_B, "B", n=10)
    rules = {"A": _rule("A"), "B": _rule("B")}
    near_a = _unit([0.95, 0.05, 0, 0, 0, 0, 0, 0])
    result = select_rule_by_knn(_profile(near_a), corpus, rules)
    assert result is not None
    assert result.cluster_id == "A"


def test_returns_none_when_out_of_distribution():
    corpus = _corpus_around(DIR_A, "A", n=10) + _corpus_around(DIR_B, "B", n=10)
    rules = {"A": _rule("A"), "B": _rule("B")}
    result = select_rule_by_knn(_profile(DIR_ORTHO), corpus, rules)
    assert result is None


def test_weighted_voting_prefers_closer_cluster():
    corpus = _corpus_around(DIR_A, "A", n=10) + _corpus_around(DIR_B, "B", n=10)
    rules = {"A": _rule("A"), "B": _rule("B")}
    slightly_a = _unit([0.8, 0.2, 0, 0, 0, 0, 0, 0])
    result = select_rule_by_knn(_profile(slightly_a), corpus, rules)
    assert result is not None
    assert result.cluster_id == "A"


def test_unruled_cluster_is_ignored():
    corpus = _corpus_around(DIR_A, "A", n=10) + _corpus_around(DIR_B, "B", n=10)
    rules = {"B": _rule("B")}
    near_a = _unit([0.95, 0.05, 0, 0, 0, 0, 0, 0])
    result = select_rule_by_knn(_profile(near_a), corpus, rules)
    assert result is None


def test_no_corpus_or_rules_returns_none():
    assert select_rule_by_knn(_profile(DIR_A), [], {}) is None
    corpus = _corpus_around(DIR_A, "A", n=10)
    assert select_rule_by_knn(_profile(DIR_A), corpus, {}) is None


def test_profile_without_embedding_returns_none():
    corpus = _corpus_around(DIR_A, "A", n=10)
    rules = {"A": _rule("A")}
    assert select_rule_by_knn(_profile(None), corpus, rules) is None


def test_min_avg_similarity_override():
    corpus = _corpus_around(DIR_A, "A", n=10) + _corpus_around(DIR_B, "B", n=10)
    rules = {"A": _rule("A"), "B": _rule("B")}
    mid = _unit([1.0, 1.0, 0, 0, 0, 0, 0, 0])
    assert select_rule_by_knn(_profile(mid), corpus, rules) is not None
    assert select_rule_by_knn(_profile(mid), corpus, rules, min_avg_similarity=0.99) is None


def test_default_constants():
    assert settings.knn_k == 7
    assert settings.knn_min_avg_similarity == 0.40
