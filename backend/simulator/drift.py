"""Drift events — mutate the preference matrix to simulate domain drift.

Two scripted drifts (TASK.md §5.3):

  - `ai_bubble_pops`  (instantaneous, fires day-3 10:00 or via button):
        For arch_tech_founder_applied:
            framing[applied-curiosity]  ↔  framing[skeptical-respect]
            tone[playful]               ↔  tone[direct]
        Effect: rules induced for tech-founders flip in CS, triggering revision.

  - `GradualPostdocShift` (over 15 episodes from day-2 14:00):
        For arch_postdoc_cv_ambitious:
            framing[strategic-alignment]  linearly interp 0.90 → 0.40
        Effect: rule for postdocs degrades slowly — illustrates θ_revise sensitivity.

After any mutation the caller should NOT call preferences.reset() — that would
reload the YAML from disk and undo the drift. The mutation lives in the cache.
"""

from __future__ import annotations

from backend.simulator import preferences


# ── Drift A — AI Bubble Pops ─────────────────────────────────────────────

FOUNDER_ARCHETYPE = "arch_tech_founder_applied"


def ai_bubble_pops() -> None:
    """Swap two pairs of affinity values for the tech-founder archetype.

    Idempotent if applied an even number of times; intended to fire once per
    demo run.
    """
    framing = preferences.affinity_table(FOUNDER_ARCHETYPE, "framing")
    framing["applied-curiosity"], framing["skeptical-respect"] = (
        framing["skeptical-respect"],
        framing["applied-curiosity"],
    )

    tone = preferences.affinity_table(FOUNDER_ARCHETYPE, "tone")
    tone["playful"], tone["direct"] = tone["direct"], tone["playful"]


# ── Drift B — Postdoc burnout creep ──────────────────────────────────────

POSTDOC_ARCHETYPE = "arch_postdoc_cv_ambitious"


class GradualPostdocShift:
    """Linearly interpolate one framing affinity over a fixed number of steps.

    Step 0 leaves the baseline value alone; step TOTAL_STEPS lands on `END`.
    `advance()` is idempotent past the final step (returns False once exhausted).
    """

    TOTAL_STEPS = 15
    SLOT_NAME = "framing"
    SLOT_VALUE = "strategic-alignment"
    START = 0.90
    END = 0.40

    def __init__(self) -> None:
        self.step = 0

    def advance(self) -> bool:
        if self.step >= self.TOTAL_STEPS:
            return False
        self.step += 1
        t = self.step / self.TOTAL_STEPS
        new_value = self.START + t * (self.END - self.START)
        table = preferences.affinity_table(POSTDOC_ARCHETYPE, self.SLOT_NAME)
        table[self.SLOT_VALUE] = new_value
        return True


# ── Public registry — used by /simulator/drift/{drift_id} ─────────────────

DRIFT_REGISTRY: dict[str, object] = {
    "ai_bubble_pops": ai_bubble_pops,
    "postdoc_burnout": GradualPostdocShift(),
}
