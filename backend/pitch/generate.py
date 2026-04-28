"""Render the next DialogueStep for a pitch session.

Three paths share this entry point:
  - static-rule path: deterministic templates, no LLM call
  - hybrid-rule path: LLM fills dynamic slots (typically `opener_type`)
  - improvise path:    no rule applicable, LLM produces the opener with
                       a sensible default strategy

Every path produces a `DialogueStep` and the `PitchStrategy` actually used
(returned separately so the orchestrator can persist `Episode.pitch_strategy`).
"""

from __future__ import annotations

import logging

import httpx

from backend import schemas
from backend.llm import client as llm
from backend.pitch import strategy as strategy_mod
from backend.pitch import templates


log = logging.getLogger(__name__)

# Expected when Ollama is offline (booth running synthetic-only). We log a
# one-liner instead of a full traceback so the demo log stays readable;
# unexpected exceptions still get the full stack via log.exception below.
_LLM_OFFLINE_EXCEPTIONS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout)

OPENER_LLM_PATHS = ("hybrid", "improvise")  # surface for tests / introspection


async def generate_turn(
    profile: schemas.Profile,
    history: list[schemas.DialogueStep],
    applicable_rule: schemas.Rule | None,
    *,
    pitch_strategy: schemas.PitchStrategy | None = None,
) -> tuple[schemas.DialogueStep, schemas.PitchStrategy]:
    """Produce the next DialogueStep and the strategy used.

    Args:
      profile: the visitor's profile
      history: completed dialogue steps so far (turn 1..N-1, with their
               visitor_choice fields populated by /sessions/{id}/turn)
      applicable_rule: the rule that classification picked, or None
      pitch_strategy: previously-assembled strategy for this session; when
                      provided we reuse it (subsequent turns shouldn't pick
                      a new strategy mid-session). When None, we assemble.

    Returns:
      (DialogueStep, PitchStrategy) — the strategy is the same one across
      all calls within a session; we return it on every call so the
      caller doesn't need to track it separately.
    """
    strat = pitch_strategy or strategy_mod.assemble_strategy(applicable_rule)
    is_opener = len(history) == 0

    if is_opener:
        opener_text, path = await _produce_opener(profile, strat, applicable_rule)
        strat = strat.model_copy(update={"opener_text": opener_text})
        reply = opener_text
    else:
        path = "continuation"
        reply = templates.render_continuation(profile, strat, history)

    rule_id = applicable_rule.id if applicable_rule is not None else None
    thought = templates.render_thought(strat, rule_id, is_opener)
    log.debug(
        "pitch.generate_turn turn=%d path=%s rule=%s",
        len(history) + 1,
        path,
        rule_id,
    )

    step = schemas.DialogueStep(
        turn=len(history) + 1,
        agent_thought=thought,
        agent_reply=reply,
        visitor_choice=None,
        interest_delta=0,
        rule_applied=rule_id,
    )
    return step, strat


async def _produce_opener(
    profile: schemas.Profile,
    strat: schemas.PitchStrategy,
    applicable_rule: schemas.Rule | None,
) -> tuple[str, str]:
    """Returns (opener_text, path_label)."""
    if applicable_rule is None:
        return await _opener_via_llm(profile, strat), "improvise"

    if strategy_mod.has_dynamic_slot(applicable_rule, "opener_type"):
        return await _opener_via_llm(profile, strat), "hybrid"

    # All slots that affect the opener are static — render from templates.
    return templates.render_opener(profile, strat), "static"


async def _opener_via_llm(
    profile: schemas.Profile,
    strat: schemas.PitchStrategy,
) -> str:
    """Call the opener LLM prompt. On any failure, fall back to template."""
    try:
        prompt = llm.render(
            "opener",
            profile_name=profile.name,
            profile_role=profile.role,
            profile_domain=profile.domain,
            profile_seniority=profile.seniority,
            profile_headline=profile.headline,
            profile_recent_signals=" / ".join(profile.recent_signals)
            if profile.recent_signals
            else "(none)",
            framing=strat.framing,
            tone=strat.tone,
            opener_type=strat.opener_type,
            word_target=strat.word_target,
            ask_size=strat.ask_size,
        )
        text = await llm.complete(prompt, system="You are a research-liaison agent.")
        text = text.strip().strip('"').strip()
        if text:
            return text
    except _LLM_OFFLINE_EXCEPTIONS as e:
        log.warning("opener LLM unavailable (%s); using template fallback", e.__class__.__name__)
    except Exception:  # noqa: BLE001
        log.exception("opener LLM call failed; falling back to template")
    return templates.render_opener(profile, strat)
