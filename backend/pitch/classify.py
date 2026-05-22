"""Profile → cluster classification + active-rule lookup.

Phase 1B keeps classification deliberately simple:

  - synthetic profile:  the archetype id IS the cluster id (stable identifier
    per archetype). When real ClusterRows exist with that id, they take over;
    otherwise we treat the archetype as a one-of-one pseudo-cluster.
  - live profile (Phase 3): nearest-centroid lookup against active ClusterRows
    using the profile embedding. Until live mode lands we just return None
    when no synthetic-archetype mapping fires.

The active-rule lookup picks the most recently induced active rule for the
classified cluster — there can be at most one in normal flow because the
revision pipeline deprecates old rules when accepting new ones.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.memory import models
from backend.memory import store

_KNN_K = 7


async def classify_profile(
    session: AsyncSession,
    profile: schemas.Profile,
) -> str | None:
    """Return the cluster_id this profile belongs to, or None if uncovered."""
    if profile.source_kind == "synthetic":
        return profile.id

    if not profile.embedding:
        return None

    profile_cluster = await store.profile_cluster_map(session)
    if not profile_cluster:
        return None

    all_embeddings = await store.profiles_with_embeddings(session)
    candidate_ids: list[str] = []
    candidate_vecs: list[list[float]] = []
    for pid, emb in all_embeddings:
        if pid in profile_cluster and pid != profile.id:
            candidate_ids.append(pid)
            candidate_vecs.append(emb)

    if not candidate_ids:
        return None

    query_vec = np.asarray(profile.embedding, dtype=np.float64)
    mat = np.asarray(candidate_vecs, dtype=np.float64)
    similarities = mat @ query_vec

    k = min(_KNN_K, len(candidate_ids))
    top_indices = np.argpartition(similarities, -k)[-k:]

    cluster_scores: dict[str, float] = defaultdict(float)
    for idx in top_indices:
        cid = profile_cluster[candidate_ids[idx]]
        cluster_scores[cid] += float(similarities[idx])

    return max(cluster_scores, key=cluster_scores.get)


async def lookup_applicable_rule(
    session: AsyncSession,
    cluster_id: str | None,
) -> schemas.Rule | None:
    """Most-recently-induced active rule for the cluster, or None."""
    if cluster_id is None:
        return None

    stmt = (
        select(models.RuleRow)
        .where(models.RuleRow.cluster_id == cluster_id)
        .where(models.RuleRow.status == "active")
        .order_by(models.RuleRow.induced_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalars().first()
    if row is None:
        return None
    return store._rule_from_row(row)
