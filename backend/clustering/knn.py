from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from backend.memory.models import ProfileRow
    from backend.schemas import Profile, Rule


# Embeddings are L2-normalized, so matrix @ query is cosine similarity in [-1, 1].
# A profile whose strongest clustered+ruled neighbor falls below this is treated
# as out-of-distribution: select_rule_by_knn returns None and the pitch path
# improvises instead of being force-bucketed into the nearest seeded cluster.
# Tuned empirically against the seeded eval DB (744 profiles): the in-cluster
# nearest-neighbor similarity distribution has p1=0.58, p5=0.64, while an
# out-of-domain AI-researcher outlier scored ~0.46-0.53 against the marketing
# clusters. 0.55 sits below the genuine-member low end (false-reject ~0.13%)
# while rejecting that outlier.
MIN_NEIGHBOR_SIMILARITY = 0.55


def select_rule_by_knn(profile: Profile,
                       corpus: list[ProfileRow],
                       rules: dict[str, Rule],
                       k: int = 7,
                       min_similarity: float | None = None,) -> object | None:

    threshold = MIN_NEIGHBOR_SIMILARITY if min_similarity is None else min_similarity

    if not corpus:
        return None
    if not profile.embedding:
        return None

    eligible = [p for p in corpus if p.embedding]
    if not eligible:
        return None

    query = np.array(profile.embedding, dtype=np.float32)
    matrix = np.array([p.embedding for p in eligible], dtype=np.float32)
    similarities = matrix @ query

    top_k_count = min(k, len(eligible))
    top_indices = np.argpartition(similarities, -top_k_count)[-top_k_count:]

    # Confidence = max cosine similarity among the top-k neighbors that belong to
    # a clustered+ruled profile (matches the "% similar" the UI shows). Summed
    # votes would let many lukewarm neighbors outweigh a single close match.
    cluster_best: dict[str, float] = {}
    for idx in top_indices:
        neighbor = eligible[idx]
        cid = getattr(neighbor, "cluster_id", None)
        if cid is not None and cid in rules:
            sim = float(similarities[idx])
            if sim > cluster_best.get(cid, float("-inf")):
                cluster_best[cid] = sim

    if not cluster_best:
        return None

    best_cluster = max(cluster_best, key=lambda c: cluster_best[c])
    if cluster_best[best_cluster] < threshold:
        return None
    return rules[best_cluster]
