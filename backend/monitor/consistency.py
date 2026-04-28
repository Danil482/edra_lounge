"""Consistency score — per-rule, over a rolling window of post-induction
episodes within the rule's cluster.

CS is the success_ratio over those post-induction episodes. The
`should_revise` predicate signals reflection when the last `cs_window`
episodes drop below `theta_revise` (TASK.md §6, §14).
"""

from datetime import datetime

from backend import schemas
from backend.config import settings


def _is_satisfied(ep: schemas.Episode) -> bool:
    return ep.outcome == "accepted"


def compute_cs(rule: schemas.Rule, cluster_episodes: list[schemas.Episode]) -> float:
    """success_ratio restricted to episodes emitted AFTER rule.induced_at.

    Returns 1.0 when there is no post-induction evidence yet — we don't trigger
    a revision against a rule we have no data for.
    """
    post = [ep for ep in cluster_episodes if ep.timestamp > rule.induced_at]
    if not post:
        return 1.0
    n_sat = sum(1 for ep in post if _is_satisfied(ep))
    return n_sat / len(post)


def should_revise(rule: schemas.Rule, cluster_episodes: list[schemas.Episode]) -> bool:
    """True when the last `cs_window` post-induction episodes yield CS < theta_revise."""
    post = [ep for ep in cluster_episodes if ep.timestamp > rule.induced_at]
    window = post[-settings.cs_window :]
    if len(window) < settings.cs_window:
        return False
    n_sat = sum(1 for ep in window if _is_satisfied(ep))
    return (n_sat / len(window)) < settings.theta_revise


def append_cs_history(rule: schemas.Rule, score: float) -> schemas.Rule:
    rule.cs_history = [*rule.cs_history, (datetime.utcnow(), score)]
    return rule
