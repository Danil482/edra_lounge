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
        # Synthetic archetype id is stable across the demo run — use it as
        # the cluster identifier so rules induced for an archetype apply
        # immediately to every visitor of that archetype, with no warmup.
        return profile.id

    if not profile.embedding:
        return None

    episodes = await store.all_episodes(session)
    profile_cluster: dict[str, str] = {}
    for ep in sorted(episodes, key=lambda e: e.timestamp):
        if ep.cluster_id is not None:
            profile_cluster[ep.profile_id] = ep.cluster_id

    if not profile_cluster:
        return None

    all_profiles = await store.list_profiles(session)
    candidates = [
        p for p in all_profiles
        if p.embedding and p.id in profile_cluster and p.id != profile.id
    ]
    if not candidates:
        return None

    query_vec = np.asarray(profile.embedding, dtype=np.float64)
    candidate_vecs = np.asarray([c.embedding for c in candidates], dtype=np.float64)
    similarities = candidate_vecs @ query_vec

    k = min(_KNN_K, len(candidates))
    top_indices = np.argpartition(similarities, -k)[-k:]

    cluster_scores: dict[str, float] = defaultdict(float)
    for idx in top_indices:
        cid = profile_cluster[candidates[idx].id]
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
