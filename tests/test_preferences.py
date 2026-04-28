"""TASK.md §5.2 invariant — every archetype's top-K PitchStrategy must be
unique to that archetype.

If two archetypes share a top-K combo, cluster-specific rules will not emerge
cleanly in the demo: induction would pick the same pitch shape for two
clusters, and the demo arc loses its differentiating signal.

We test top-3 (the spec's lower-bound minimum). Top-1 is also unique by
construction, but we want headroom against accidental ties at rank 2 or 3
when affinity tables are tuned.
"""

from __future__ import annotations

from backend.simulator import preferences


def test_archetypes_loaded():
    prefs = preferences._load()
    assert len(prefs) == 8, f"expected 8 archetypes, got {len(prefs)}"
    expected = {
        "arch_phd_nlp_introvert",
        "arch_postdoc_cv_ambitious",
        "arch_tech_founder_applied",
        "arch_senior_prof_meta",
        "arch_industry_pm_pragmatic",
        "arch_research_engineer_skeptic",
        "arch_vc_investor",
        "arch_journalist_curious",
    }
    assert set(prefs.keys()) == expected


def test_spawnable_split():
    spawnable = {a for a in preferences.archetype_ids() if preferences._load()[a]["spawnable"]}
    assert spawnable == {"arch_vc_investor", "arch_journalist_curious"}, spawnable


def test_default_rotation_excludes_spawnable():
    rotation = preferences.archetype_ids(include_spawnable=False)
    assert len(rotation) == 6
    assert "arch_vc_investor" not in rotation
    assert "arch_journalist_curious" not in rotation


def test_top3_combos_are_unique_per_archetype():
    archetype_ids = preferences.archetype_ids()
    top3_per_archetype = {
        aid: frozenset(_strategy_key(s) for s in preferences.top_k_strategies(aid, k=3))
        for aid in archetype_ids
    }

    for i, a in enumerate(archetype_ids):
        for b in archetype_ids[i + 1 :]:
            overlap = top3_per_archetype[a] & top3_per_archetype[b]
            assert not overlap, (
                f"archetypes {a} and {b} share a top-3 combo: {sorted(overlap)}"
            )


def test_each_archetype_has_at_least_two_distinctive_combos():
    """TASK.md §5.2: 'every archetype has at least 2 distinct sweet-spot combos
    that no other archetype has' — verified across the top-5 ranks."""
    archetype_ids = preferences.archetype_ids()
    top5_per_archetype = {
        aid: [_strategy_key(s) for s in preferences.top_k_strategies(aid, k=5)]
        for aid in archetype_ids
    }

    for aid, top5 in top5_per_archetype.items():
        others = set()
        for other_aid, other_top5 in top5_per_archetype.items():
            if other_aid == aid:
                continue
            others.update(other_top5)
        distinctive = [s for s in top5 if s not in others]
        assert len(distinctive) >= 2, (
            f"{aid} has only {len(distinctive)} distinctive combo(s) in its top-5; "
            f"expected ≥ 2"
        )


def test_score_and_discretise_bands():
    # Build the canonical 'best combo' for the PhD archetype and verify it
    # scores +2; build a deliberately bad combo and verify it scores ≤ 0.
    from backend.schemas import PitchStrategy

    best = PitchStrategy(
        framing="knowledge-share",
        tone="socratic",
        opener_type="question",
        word_target="medium",
        ask_size="co-author",
    )
    bad = PitchStrategy(
        framing="strategic-alignment",
        tone="playful",
        opener_type="cold",
        word_target="long",
        ask_size="trial",
    )

    aid = "arch_phd_nlp_introvert"
    assert preferences.preference(aid, best, history=[]) == 2
    assert preferences.preference(aid, bad, history=[]) <= 0


def test_history_fatigue_lowers_delta():
    from backend.schemas import DialogueStep, PitchStrategy

    aid = "arch_phd_nlp_introvert"
    best = PitchStrategy(
        framing="knowledge-share",
        tone="socratic",
        opener_type="question",
        word_target="medium",
        ask_size="co-author",
    )

    fresh = preferences.preference(aid, best, history=[])
    fatigued = preferences.preference(
        aid,
        best,
        history=[
            DialogueStep(turn=i, agent_thought="", agent_reply="", interest_delta=0)
            for i in range(6)
        ],
    )
    assert fatigued <= fresh


def test_visitor_choice_mapping():
    assert preferences.visitor_choice_from_delta(2) == "positive"
    assert preferences.visitor_choice_from_delta(1) == "positive"
    assert preferences.visitor_choice_from_delta(0) == "skeptical"
    assert preferences.visitor_choice_from_delta(-1) == "negative"
    assert preferences.visitor_choice_from_delta(-2) == "negative"


# ── helpers ──────────────────────────────────────────────────────────────

def _strategy_key(s) -> tuple[str, str, str, str, str]:
    return (s.framing, s.tone, s.opener_type, s.word_target, s.ask_size)
