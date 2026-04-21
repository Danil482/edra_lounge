"""Consistency score — per-rule, over a rolling window of post-induction episodes
within the rule's cluster. CS = success_ratio over that window.

Emits `revision_needed` when CS < theta_revise for at least cs_window episodes.
"""

from datetime import datetime

from backend import schemas
from backend.config import settings


def compute_cs(rule: schemas.Rule, cluster_episodes: list[schemas.Episode]) -> float:
    """success_ratio restricted to episodes emitted AFTER rule.induced_at."""
    post = [ep for ep in cluster_episodes if ep.timestamp > rule.induced_at]
    if not post:
        return 1.0  # no evidence yet → don't trigger revision
    n_sat = sum(1 for ep in post if ep.outcome == "satisfied")
    return n_sat / len(post)


def should_revise(rule: schemas.Rule, cluster_episodes: list[schemas.Episode]) -> bool:
    """True when the last `cs_window` post-induction episodes yield CS < theta_revise."""
    post = [ep for ep in cluster_episodes if ep.timestamp > rule.induced_at]
    window = post[-settings.cs_window :]
    if len(window) < settings.cs_window:
        return False
    n_sat = sum(1 for ep in window if ep.outcome == "satisfied")
    return (n_sat / len(window)) < settings.theta_revise


def append_cs_history(rule: schemas.Rule, score: float) -> schemas.Rule:
    rule.cs_history = [*rule.cs_history, (datetime.utcnow(), score)]
    return rule
