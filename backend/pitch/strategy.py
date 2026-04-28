"""PitchStrategy assembly — turns a Rule (or its absence) into the concrete
5-slot strategy the agent will use for an episode.

A Rule has 5 slots, each `static` (literal value) or `dynamic` (LLM sub-prompt).
For a static rule the strategy is fully determined by slot values. For a hybrid
rule the dynamic slots default to a sensible fallback at strategy-assembly
time; the actual filled value (e.g. opener text) is produced by `generate.py`
when the turn is rendered. We keep the two concerns separate so the code path
that does NOT need an LLM can stay synchronous and deterministic.
"""

from __future__ import annotations

from backend import schemas


# Sensible cold-start strategy when no rule applies. Picks the broadly-warm
# peer-to-peer combination that matches "moderately curious researcher" defaults
# across most of the seeded archetypes. The point isn't to be optimal — the
# point is to be a stable starting baseline that won't crater interest below 0
# on the first turn before any rule has been induced.
DEFAULT_IMPROVISED_STRATEGY = schemas.PitchStrategy(
    framing="peer-collaboration",
    tone="warm",
    opener_type="reference-to-signal",
    word_target="medium",
    ask_size="chat",
)


# Per-slot defaults used when a Rule slot is dynamic and we need a placeholder
# value for scoring/templating purposes BEFORE the LLM has filled it. These
# match the "moderately curious researcher" baseline above.
_DYNAMIC_SLOT_DEFAULT: dict[str, str] = {
    "framing": "peer-collaboration",
    "tone": "warm",
    "opener_type": "reference-to-signal",
    "word_target": "medium",
    "ask_size": "chat",
}


def pitch_strategy_from_rule(rule: schemas.Rule) -> schemas.PitchStrategy:
    """Project a Rule's 5 slots into a PitchStrategy.

    Static slots map their literal value through directly. Dynamic slots
    receive the per-slot default — the LLM may overwrite this value later
    when the dynamic prompt is run, but the strategy is always well-formed
    for scoring against the preference function.
    """
    by_name: dict[str, schemas.RuleSlot] = {s.name: s for s in rule.slots}
    return schemas.PitchStrategy(
        framing=_resolve(by_name, "framing"),
        tone=_resolve(by_name, "tone"),
        opener_type=_resolve(by_name, "opener_type"),
        word_target=_resolve(by_name, "word_target"),
        ask_size=_resolve(by_name, "ask_size"),
        opener_text=None,
    )


def _resolve(by_name: dict[str, schemas.RuleSlot], slot: str) -> str:
    s = by_name.get(slot)
    if s is None:
        return _DYNAMIC_SLOT_DEFAULT[slot]
    if s.kind == "static" and s.value:
        return s.value
    return _DYNAMIC_SLOT_DEFAULT[slot]


def has_dynamic_slot(rule: schemas.Rule, name: str) -> bool:
    for s in rule.slots:
        if s.name == name and s.kind == "dynamic":
            return True
    return False


def dynamic_slot_prompt(rule: schemas.Rule, name: str) -> str | None:
    for s in rule.slots:
        if s.name == name and s.kind == "dynamic":
            return s.prompt
    return None


def assemble_strategy(rule: schemas.Rule | None) -> schemas.PitchStrategy:
    """Public entry point: project the active rule (or improvise default).

    Pure / synchronous. Does not call the LLM. Dynamic-slot fill happens at
    turn-render time in `generate.py`.
    """
    if rule is None:
        return DEFAULT_IMPROVISED_STRATEGY.model_copy()
    return pitch_strategy_from_rule(rule)
