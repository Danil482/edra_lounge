"""Agent Factory — tracks which clusters have coverage by ≥1 active rule.
When a cluster forms that no active rule covers, signals spawn_needed.
"""

from datetime import datetime

from backend import schemas
from backend.memory.ids import short_id


def find_uncovered_cluster(
    clusters: list[schemas.Cluster],
    active_rules: list[schemas.Rule],
) -> schemas.Cluster | None:
    """Returns the first cluster with no active rule pointing at it, else None."""
    covered = {r.cluster_id for r in active_rules if r.status == "active"}
    for c in clusters:
        if c.id not in covered and c.size >= 1:
            return c
    return None


def spawn_agent(cluster: schemas.Cluster, description: str) -> schemas.Agent:
    """Create a new bartender specialist for the uncovered cluster."""
    return schemas.Agent(
        id=short_id("agent"),
        cluster_id=cluster.id,
        zone_description=description,
        created_at=datetime.utcnow(),
        is_active=True,
    )
