"""Preference matrix — the hidden ground-truth the simulator samples from.

TASK.md §5.2: do NOT make these random. Each persona has a distinct sweet spot
so cluster-specific rules emerge cleanly. Invariant enforced by
tests/test_preferences.py: every persona's top-3 preferred offer is unique.

Outcome mapping:
    score ≥ 0.7            → "satisfied"
    0.3 ≤ score < 0.7      → "neutral"
    score < 0.3            → "rejected"

Score composition (§5.2):
    score = 0.25 * topic_affinity[p][t]
          + 0.25 * style_affinity[p][s]
          + 0.15 * drink_affinity[p][d]
          + 0.35 * combo_bonus[p][(t, s, d)]   # sparse, hand-crafted peaks
"""

from __future__ import annotations

import numpy as np

from backend import schemas


PERSONA_IDS: list[str] = [
    "persona_phd_nlp",
    "persona_postdoc_cv",
    "persona_tech_founder",
    "persona_senior_prof",
    "persona_industry_pm",
    "persona_vc_investor",
]

TOPICS: list[str] = ["hype", "foundations", "applied", "meta-science", "career", "gossip"]
STYLES: list[str] = ["enthusiastic", "skeptical", "socratic", "gossipy", "formal"]
DRINKS: list[str] = ["coffee", "beer", "tea", "water"]


# ── Topic affinity (TASK.md §5.2 verbatim) ────────────────────────────────

topic_affinity: dict[str, dict[str, float]] = {
    "persona_phd_nlp":      {"foundations": 0.95, "applied": 0.40, "hype": 0.10, "meta-science": 0.70, "career": 0.50, "gossip": 0.20},
    "persona_tech_founder": {"foundations": 0.50, "applied": 0.95, "hype": 0.85, "meta-science": 0.30, "career": 0.60, "gossip": 0.40},
    "persona_postdoc_cv":   {"foundations": 0.60, "applied": 0.70, "hype": 0.80, "meta-science": 0.50, "career": 0.90, "gossip": 0.30},
    "persona_senior_prof":  {"foundations": 0.70, "applied": 0.40, "hype": 0.20, "meta-science": 0.95, "career": 0.30, "gossip": 0.10},
    "persona_industry_pm":  {"foundations": 0.30, "applied": 0.90, "hype": 0.60, "meta-science": 0.40, "career": 0.50, "gossip": 0.30},
    "persona_vc_investor":  {"foundations": 0.20, "applied": 0.85, "hype": 0.95, "meta-science": 0.20, "career": 0.40, "gossip": 0.60},
}


# ── Style / drink affinity (TODO(author-tune) — keep unique top-3 invariant) ─

style_affinity: dict[str, dict[str, float]] = {
    "persona_phd_nlp":      {"socratic": 0.90, "formal": 0.70, "skeptical": 0.75, "enthusiastic": 0.30, "gossipy": 0.10},
    "persona_tech_founder": {"enthusiastic": 0.95, "socratic": 0.40, "formal": 0.30, "skeptical": 0.35, "gossipy": 0.55},
    "persona_postdoc_cv":   {"enthusiastic": 0.70, "socratic": 0.65, "gossipy": 0.75, "formal": 0.50, "skeptical": 0.40},
    "persona_senior_prof":  {"formal": 0.95, "socratic": 0.80, "skeptical": 0.70, "enthusiastic": 0.20, "gossipy": 0.15},
    "persona_industry_pm":  {"formal": 0.70, "skeptical": 0.75, "socratic": 0.60, "enthusiastic": 0.50, "gossipy": 0.40},
    "persona_vc_investor":  {"gossipy": 0.90, "enthusiastic": 0.85, "formal": 0.50, "skeptical": 0.35, "socratic": 0.30},
}

drink_affinity: dict[str, dict[str, float]] = {
    "persona_phd_nlp":      {"coffee": 0.85, "tea": 0.70, "water": 0.60, "beer": 0.20},
    "persona_tech_founder": {"coffee": 0.80, "beer": 0.75, "water": 0.40, "tea": 0.30},
    "persona_postdoc_cv":   {"coffee": 0.90, "tea": 0.50, "beer": 0.55, "water": 0.40},
    "persona_senior_prof":  {"tea": 0.95, "water": 0.60, "coffee": 0.50, "beer": 0.15},
    "persona_industry_pm":  {"coffee": 0.75, "water": 0.70, "tea": 0.45, "beer": 0.50},
    "persona_vc_investor":  {"beer": 0.85, "coffee": 0.70, "water": 0.30, "tea": 0.25},
}


# ── Combo bonus (sparse hand-crafted sweet spots; one unique peak per persona) ─
# Keys are (topic, style, drink). All unlisted combos → bonus=0.
# TODO(author-tune): verify each persona's peak is unique and gives score ≥ 0.85.

combo_bonus: dict[str, dict[tuple[str, str, str], float]] = {
    "persona_phd_nlp": {
        ("foundations", "socratic", "coffee"): 1.00,
        ("foundations", "skeptical", "tea"): 0.70,
    },
    "persona_tech_founder": {
        ("applied", "enthusiastic", "coffee"): 1.00,
        ("hype", "enthusiastic", "beer"): 0.75,
    },
    "persona_postdoc_cv": {
        ("career", "gossipy", "coffee"): 1.00,
        ("hype", "enthusiastic", "coffee"): 0.70,
    },
    "persona_senior_prof": {
        ("meta-science", "formal", "tea"): 1.00,
        ("foundations", "socratic", "tea"): 0.70,
    },
    "persona_industry_pm": {
        ("applied", "skeptical", "coffee"): 1.00,
        ("applied", "formal", "water"): 0.70,
    },
    "persona_vc_investor": {
        ("hype", "gossipy", "beer"): 1.00,
        ("applied", "enthusiastic", "beer"): 0.70,
    },
}


# ── Matrix construction ───────────────────────────────────────────────────

def build_matrix() -> np.ndarray:
    """Returns shape (6, 6, 5, 4) — personas × topics × styles × drinks."""
    M = np.zeros((len(PERSONA_IDS), len(TOPICS), len(STYLES), len(DRINKS)))
    for pi, p in enumerate(PERSONA_IDS):
        for ti, t in enumerate(TOPICS):
            for si, s in enumerate(STYLES):
                for di, d in enumerate(DRINKS):
                    score = (
                        0.25 * topic_affinity[p][t]
                        + 0.25 * style_affinity[p][s]
                        + 0.15 * drink_affinity[p][d]
                        + 0.35 * combo_bonus.get(p, {}).get((t, s, d), 0.0)
                    )
                    M[pi, ti, si, di] = score
    return M


_MATRIX: np.ndarray | None = None


def matrix() -> np.ndarray:
    global _MATRIX
    if _MATRIX is None:
        _MATRIX = build_matrix()
    return _MATRIX


def reset_matrix() -> None:
    """Called after a drift event mutates the affinity tables."""
    global _MATRIX
    _MATRIX = None


# ── Sampling ──────────────────────────────────────────────────────────────

def score_offer(persona_id: str, offer: schemas.Offer) -> float:
    M = matrix()
    pi = PERSONA_IDS.index(persona_id)
    ti = TOPICS.index(offer.topic)
    si = STYLES.index(offer.style)
    di = DRINKS.index(offer.drink)
    return float(M[pi, ti, si, di])


def outcome_from_score(score: float) -> schemas.OUTCOME:
    if score >= 0.7:
        return "satisfied"
    if score >= 0.3:
        return "neutral"
    return "rejected"
