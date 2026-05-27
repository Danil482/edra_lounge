from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from backend.memory.models import ProfileRow
    from backend.schemas import Profile, Rule


def select_rule_by_knn(profile: Profile,
                       corpus: list[ProfileRow],
                       rules: dict[str, Rule],
                       k: int = 7,) -> object | None:
    
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

    cluster_votes: dict[str, float] = {}
    for idx in top_indices:
        neighbor = eligible[idx]
        cid = getattr(neighbor, "cluster_id", None)
        if cid is not None and cid in rules:
            cluster_votes[cid] = cluster_votes.get(cid, 0.0) + float(similarities[idx])

    if not cluster_votes:
        return None

    best_cluster = max(cluster_votes, key=lambda c: cluster_votes[c])
    return rules[best_cluster]
