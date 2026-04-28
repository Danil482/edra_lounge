"""Pitch generation — produces the next DialogueStep given (Profile, history,
applicable rule | None) and the strategy that drives the whole episode.

Phase 1B paths (TASK.md §2 / §7):
  - static rule (all 5 slots static) → assemble pitch without an LLM call;
    the opener text is rendered from a slot-keyed template library.
  - hybrid rule (≥ 1 dynamic slot)   → fill dynamic slots via LLM (typically
    `opener_type` so the opener can reference the profile's signals).
  - no applicable rule               → improvise: pick a sensible default
    strategy and render the opener via LLM with cluster-recent few-shots.

Subsequent turns (turn ≥ 2) are continuations within the same strategy and,
in Phase 1B, use template-driven replies; the LLM is reserved for openers
and the five §7 touchpoints.
"""

from backend.pitch.classify import classify_profile, lookup_applicable_rule
from backend.pitch.generate import generate_turn
from backend.pitch.strategy import (
    DEFAULT_IMPROVISED_STRATEGY,
    assemble_strategy,
    pitch_strategy_from_rule,
)


__all__ = [
    "DEFAULT_IMPROVISED_STRATEGY",
    "assemble_strategy",
    "classify_profile",
    "generate_turn",
    "lookup_applicable_rule",
    "pitch_strategy_from_rule",
]
