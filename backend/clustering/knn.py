"""K-nearest-neighbor rule selection with out-of-distribution rejection.

select_rule_by_knn finds the K=7 nearest neighbors of the incoming profile
in the corpus (cosine similarity), gates on mean similarity to reject
out-of-distribution visitors, then uses cosine-weighted voting across
clusters to pick the best rule.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import numpy as np

from backend.config import settings

if TYPE_CHECKING:
    from backend.schemas import Profile, Rule


def select_rule_by_knn(
    profile: "Profile",
    corpus: list[tuple[str, list[float], str | None]],
    rules: dict[str, "Rule"],
    k: int | None = None,
    min_avg_similarity: float | None = None,
) -> "Rule | None":
    k_val = settings.knn_k if k is None else k
    threshold = settings.knn_min_avg_similarity if min_avg_similarity is None else min_avg_similarity

    if not profile.embedding or not corpus or not rules:
        return None

    query = np.array(profile.embedding, dtype=np.float32)
    query_norm = np.linalg.norm(query)
    if query_norm == 0:
        return None

    sims: list[tuple[float, str | None]] = []
    for pid, emb, cid in corpus:
        if pid == profile.id:
            continue
        vec = np.array(emb, dtype=np.float32)
        vec_norm = np.linalg.norm(vec)
        if vec_norm == 0:
            continue
        sim = float(np.dot(query, vec) / (query_norm * vec_norm))
        sims.append((sim, cid))

    if not sims:
        return None

    sims.sort(key=lambda x: x[0], reverse=True)
    top_k = sims[:k_val]

    mean_sim = sum(s for s, _ in top_k) / len(top_k)
    if mean_sim < threshold:
        return None

    votes: dict[str, float] = defaultdict(float)
    for sim, cid in top_k:
        if cid is not None and cid in rules:
            votes[cid] += sim

    if not votes:
        return None

    best_cid = max(votes, key=votes.get)  # type: ignore[arg-type]
    return rules[best_cid]
