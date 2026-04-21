"""Drift events — mutate the preference matrix to simulate domain drift.

After any mutation, call `preferences.reset_matrix()` to invalidate the cache.
"""

from backend.simulator import preferences


def ai_bubble_pops() -> None:
    """Drift A (TASK.md §5.3): for tech-founder, swap topic hype↔foundations and
    style enthusiastic↔skeptical. Triggered by UI button or scheduled at day=3 10:00.
    """
    p = "persona_tech_founder"
    ta = preferences.topic_affinity[p]
    ta["hype"], ta["foundations"] = ta["foundations"], ta["hype"]

    sa = preferences.style_affinity[p]
    sa["enthusiastic"], sa["skeptical"] = sa["skeptical"], sa["enthusiastic"]

    preferences.reset_matrix()


class GradualPostdocShift:
    """Drift B: linearly interpolate postdoc topic affinities over 15 episodes
    starting at day=2 14:00.

      hype:    0.8 → 0.3
      applied: 0.7 → 0.9
    """

    TOTAL_STEPS = 15

    def __init__(self) -> None:
        self.step = 0
        self.start_hype = 0.80
        self.end_hype = 0.30
        self.start_applied = 0.70
        self.end_applied = 0.90

    def advance(self) -> bool:
        """Nudge one step. Returns True while drift is still advancing."""
        if self.step >= self.TOTAL_STEPS:
            return False
        t = (self.step + 1) / self.TOTAL_STEPS
        p = "persona_postdoc_cv"
        ta = preferences.topic_affinity[p]
        ta["hype"] = self.start_hype + t * (self.end_hype - self.start_hype)
        ta["applied"] = self.start_applied + t * (self.end_applied - self.start_applied)
        preferences.reset_matrix()
        self.step += 1
        return True


DRIFT_REGISTRY = {
    "ai_bubble_pops": ai_bubble_pops,
    "gradual_postdoc": GradualPostdocShift(),
}
