"""Hidden ground-truth preference function — TASK.md §5.2.

Each archetype has affinity tables over the 5 PitchStrategy slots plus a sparse
list of combo bonuses. The whole table lives in `archetypes.yaml` for editing;
this module loads it lazily and exposes a deterministic, no-LLM scoring path.

Score formula (TASK.md §5.2):

    base = 0.25 * framing_aff
         + 0.25 * tone_aff
         + 0.20 * opener_aff
         + 0.15 * word_target_aff
         + 0.15 * ask_size_aff
    base += sum(applicable combo_bonuses)
    base -= 0.10 * len(history)         # interest fatigue
    interest_delta = discretise(base)   # int in [-2, +2]

Drift functions in `drift.py` mutate the in-memory affinity tables; call
`reset()` to drop the cache and re-read the YAML.

Reproducibility: this module is the sole determinant of synthetic visitor
reactions. No randomness, no LLM, no I/O at evaluation time.
"""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Iterable

import yaml

from backend import schemas


DEFAULT_ARCHETYPES_PATH = Path(__file__).parent.parent / "data" / "archetypes.yaml"


# ── Slot vocabularies ─────────────────────────────────────────────────────

FRAMINGS: tuple[str, ...] = (
    "strategic-alignment",
    "peer-collaboration",
    "knowledge-share",
    "applied-curiosity",
    "skeptical-respect",
    "follow-up-comment",
)
TONES: tuple[str, ...] = ("formal", "warm", "socratic", "direct", "playful")
OPENER_TYPES: tuple[str, ...] = (
    "question",
    "reference-to-signal",
    "shared-context",
    "credential-anchor",
    "cold",
)
WORD_TARGETS: tuple[str, ...] = ("short", "medium", "long")
ASK_SIZES: tuple[str, ...] = ("chat", "co-author", "intro", "trial", "none")


# ── Lazy archetype-preferences cache ──────────────────────────────────────

# Shape: { archetype_id -> {
#     "framing_affinity":     {value: float, ...},
#     "tone_affinity":        {value: float, ...},
#     "opener_affinity":      {value: float, ...},
#     "word_target_affinity": {value: float, ...},
#     "ask_size_affinity":    {value: float, ...},
#     "combo_bonuses":        [{"if": {slot: value, ...}, "bonus": float}, ...],
# } }
_PREFERENCES: dict[str, dict] | None = None


def _load(path: Path | None = None) -> dict[str, dict]:
    global _PREFERENCES
    if _PREFERENCES is None:
        path = path or DEFAULT_ARCHETYPES_PATH
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        archetypes = data.get("archetypes") or {}
        out: dict[str, dict] = {}
        for aid, spec in archetypes.items():
            prefs = spec.get("preferences") or {}
            out[aid] = {
                "framing_affinity": dict(prefs.get("framing_affinity") or {}),
                "tone_affinity": dict(prefs.get("tone_affinity") or {}),
                "opener_affinity": dict(prefs.get("opener_affinity") or {}),
                "word_target_affinity": dict(prefs.get("word_target_affinity") or {}),
                "ask_size_affinity": dict(prefs.get("ask_size_affinity") or {}),
                "combo_bonuses": [
                    {"if": dict(rule.get("if") or {}), "bonus": float(rule.get("bonus", 0.0))}
                    for rule in (prefs.get("combo_bonuses") or [])
                ],
                "spawnable": bool(spec.get("spawnable", False)),
            }
        _PREFERENCES = out
    return _PREFERENCES


def reset() -> None:
    """Drop the cache so the next call reloads from disk.

    Drift handlers mutate the cached tables in place — call this only when you
    want to re-read the YAML from scratch.
    """
    global _PREFERENCES
    _PREFERENCES = None


def archetype_ids(*, include_spawnable: bool = True) -> list[str]:
    prefs = _load()
    return [
        aid for aid, spec in prefs.items()
        if include_spawnable or not spec.get("spawnable", False)
    ]


def affinity_table(archetype_id: str, slot: str) -> dict[str, float]:
    """Direct mutable handle to the affinity dict for the given slot.

    Drift functions call this to mutate values in place (and avoid silently
    creating new keys that the score formula would then ignore).
    """
    prefs = _load()
    if archetype_id not in prefs:
        raise KeyError(f"unknown archetype: {archetype_id}")
    key = f"{slot}_affinity"
    if key not in prefs[archetype_id]:
        raise KeyError(f"unknown slot for {archetype_id}: {slot}")
    return prefs[archetype_id][key]


# ── Score + discretisation ────────────────────────────────────────────────

def _combo_match(rule_if: dict[str, str], strategy_dict: dict[str, str]) -> bool:
    return all(strategy_dict.get(k) == v for k, v in rule_if.items())


def _strategy_to_dict(strategy: schemas.PitchStrategy) -> dict[str, str]:
    return {
        "framing": strategy.framing,
        "tone": strategy.tone,
        "opener_type": strategy.opener_type,
        "word_target": strategy.word_target,
        "ask_size": strategy.ask_size,
    }


def score(archetype_id: str, strategy: schemas.PitchStrategy) -> float:
    """Raw weighted affinity sum + combo bonuses. No fatigue, no discretisation."""
    prefs = _load()
    if archetype_id not in prefs:
        raise KeyError(f"unknown archetype: {archetype_id}")
    spec = prefs[archetype_id]

    base = (
        0.25 * spec["framing_affinity"].get(strategy.framing, 0.0)
        + 0.25 * spec["tone_affinity"].get(strategy.tone, 0.0)
        + 0.20 * spec["opener_affinity"].get(strategy.opener_type, 0.0)
        + 0.15 * spec["word_target_affinity"].get(strategy.word_target, 0.0)
        + 0.15 * spec["ask_size_affinity"].get(strategy.ask_size, 0.0)
    )
    sd = _strategy_to_dict(strategy)
    for rule in spec["combo_bonuses"]:
        if _combo_match(rule["if"], sd):
            base += rule["bonus"]
    return base


def discretise(score_value: float) -> int:
    """Map a continuous score in roughly [0, 1.5] to an interest_delta in [-2, +2].

    Bands chosen so that:
      - Top combo with bonus (~1.3-1.5) lands at +2.
      - Top affinity slot vector without bonus (~0.85-0.95) lands at +1.
      - Mediocre combos (0.40-0.70) sit at 0.
      - Anti-affinity combos (<0.40) drop to negative.
    """
    if score_value >= 0.95:
        return 2
    if score_value >= 0.70:
        return 1
    if score_value >= 0.40:
        return 0
    if score_value >= 0.15:
        return -1
    return -2


def preference(
    archetype_id: str,
    strategy: schemas.PitchStrategy,
    history: list[schemas.DialogueStep] | None = None,
) -> int:
    """Predicted interest_delta for the given (archetype, pitch, history) triple.

    Pure function. Same inputs always produce the same output.
    """
    base = score(archetype_id, strategy)
    h = history or []
    base -= 0.10 * len(h)
    return discretise(base)


# ── Visitor-choice prediction (synthetic mode only) ───────────────────────

def visitor_choice_from_delta(delta: int) -> schemas.VISITOR_CHOICE:
    """Map an interest_delta to the choice the synthetic visitor would click."""
    if delta >= 1:
        return "positive"
    if delta <= -1:
        return "negative"
    return "skeptical"


# ── Enumeration helper for the unique-top-K invariant test ────────────────

def all_strategies() -> Iterable[schemas.PitchStrategy]:
    """Generate every legal PitchStrategy. 6×5×5×3×5 = 2250 combos."""
    for f, t, o, w, a in itertools.product(
        FRAMINGS, TONES, OPENER_TYPES, WORD_TARGETS, ASK_SIZES
    ):
        yield schemas.PitchStrategy(
            framing=f,
            tone=t,
            opener_type=o,
            word_target=w,
            ask_size=a,
        )


def top_k_strategies(archetype_id: str, k: int = 3) -> list[schemas.PitchStrategy]:
    scored = [(score(archetype_id, s), s) for s in all_strategies()]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [s for _, s in scored[:k]]
