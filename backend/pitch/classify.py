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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.memory import models
from backend.memory import store


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

    # Live mode (Phase 3): nearest-centroid lookup against ClusterRows.
    # Until embeddings + clustering fully wire, return None — this lets the
    # session take the improvise path rather than mis-applying a rule.
    return None


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
