"""KNN rule selection with out-of-distribution rejection.

select_rule_by_knn returns the nearest clustered+ruled rule only when the
strongest matching neighbor clears MIN_NEIGHBOR_SIMILARITY; otherwise it
returns None so the pitch path improvises. Embeddings here are synthetic and
deterministic (a near-duplicate of a corpus vector vs an orthogonal one) so the
test does not depend on the real MiniLM model.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import numpy as np

from backend import schemas
from backend.clustering.knn import MIN_NEIGHBOR_SIMILARITY, select_rule_by_knn


def _unit(vec: list[float]) -> list[float]:
    a = np.array(vec, dtype=np.float32)
    return (a / np.linalg.norm(a)).tolist()


# Two orthogonal directions in an 8-dim space; both unit-normalized so dot
# products are cosine similarities, mirroring the real L2-normalized corpus.
DIR_A = _unit([1, 0, 0, 0, 0, 0, 0, 0])
DIR_B = _unit([0, 1, 0, 0, 0, 0, 0, 0])
# A vector very close to DIR_A (cosine ~0.997) — a genuine cluster member.
NEAR_A = _unit([0.92, 0.08, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
# A vector midway between A and B (cosine ~0.71 to each) — borderline but still
# above threshold, used to assert a clearly-in-distribution match classifies.
MID_AB = _unit([1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])


def _corpus_member(pid: str, embedding: list[float], cluster_id: str):
    return SimpleNamespace(id=pid, embedding=embedding, cluster_id=cluster_id)


def _profile(embedding: list[float]) -> schemas.Profile:
    return schemas.Profile(
        id="visitor",
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


def test_returns_rule_when_neighbor_above_threshold():
    corpus = [
        _corpus_member("a1", DIR_A, "A"),
        _corpus_member("a2", NEAR_A, "A"),
        _corpus_member("b1", DIR_B, "B"),
    ]
    rules = {"A": _rule("A"), "B": _rule("B")}
    # Visitor sits essentially on top of cluster A.
    result = select_rule_by_knn(_profile(NEAR_A), corpus, rules, k=7)
    assert result is not None
    assert result.cluster_id == "A"


def test_returns_none_when_all_neighbors_below_threshold():
    # Corpus only has cluster A; visitor is orthogonal to it (cosine ~0.0),
    # far below MIN_NEIGHBOR_SIMILARITY — the out-of-distribution case.
    corpus = [
        _corpus_member("a1", DIR_A, "A"),
        _corpus_member("a2", NEAR_A, "A"),
    ]
    rules = {"A": _rule("A")}
    result = select_rule_by_knn(_profile(DIR_B), corpus, rules, k=7)
    assert result is None


def test_max_neighbor_similarity_gates_not_summed_votes():
    # Many moderate A-neighbors (cosine ~0.707 to the query) plus one strong
    # B-neighbor (cosine ~0.997). Summed votes would favor A by sheer count
    # (5 * 0.707 = 3.54 > 0.997); max-neighbor must pick B.
    corpus = [_corpus_member(f"a{i}", MID_AB, "A") for i in range(5)]
    corpus.append(_corpus_member("b1", NEAR_A, "B"))
    rules = {"A": _rule("A"), "B": _rule("B")}
    # Query aligned with DIR_A: each A member scores ~0.707, the lone B ~0.997.
    result = select_rule_by_knn(_profile(DIR_A), corpus, rules, k=7)
    assert result is not None
    assert result.cluster_id == "B"


def test_min_similarity_override_rejects_borderline_match():
    corpus = [_corpus_member("ab", MID_AB, "A")]
    rules = {"A": _rule("A")}
    prof = _profile(DIR_A)  # cosine to MID_AB ~0.707

    # Default threshold (0.55) accepts the borderline neighbor.
    assert select_rule_by_knn(prof, corpus, rules, k=7) is not None
    # A stricter override rejects it.
    assert select_rule_by_knn(prof, corpus, rules, k=7, min_similarity=0.9) is None


def test_default_threshold_constant():
    assert MIN_NEIGHBOR_SIMILARITY == 0.55
