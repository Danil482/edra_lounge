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

import json
import logging

import httpx

from backend import schemas
from backend.llm import client as llm
from backend.pitch import strategy as strategy_mod
from backend.pitch import templates


log = logging.getLogger(__name__)

_LLM_OFFLINE_EXCEPTIONS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout)

OPENER_LLM_PATHS = ("hybrid", "improvise")

_EXPECTED_SENTIMENTS = {"positive", "skeptical", "negative"}


def _parse_llm_json(raw: str) -> tuple[str, list[schemas.ResponseOption] | None]:
    """Extract pitch text and response options from LLM JSON output.

    Returns (pitch_text, options_or_none). On any parse issue, tries to
    salvage the pitch text and returns None for options.
    """
    text = raw.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return raw.strip().strip('"').strip(), None

    if not isinstance(data, dict) or "pitch" not in data:
        return raw.strip().strip('"').strip(), None

    pitch = str(data["pitch"]).strip().strip('"').strip()
    raw_options = data.get("options")
    if not isinstance(raw_options, list) or len(raw_options) != 3:
        return pitch, None

    options: list[schemas.ResponseOption] = []
    seen_sentiments: set[str] = set()
    for opt in raw_options:
        if not isinstance(opt, dict):
            return pitch, None
        opt_text = str(opt.get("text", "")).strip()
        sentiment = str(opt.get("sentiment", "")).strip().lower()
        if not opt_text or sentiment not in _EXPECTED_SENTIMENTS:
            return pitch, None
        if sentiment in seen_sentiments:
            return pitch, None
        seen_sentiments.add(sentiment)
        options.append(schemas.ResponseOption(text=opt_text, sentiment=sentiment))

    if seen_sentiments != _EXPECTED_SENTIMENTS:
        return pitch, None

    return pitch, options


async def generate_turn(
    profile: schemas.Profile,
    history: list[schemas.DialogueStep],
    applicable_rule: schemas.Rule | None,
    *,
    pitch_strategy: schemas.PitchStrategy | None = None,
) -> tuple[schemas.DialogueStep, schemas.PitchStrategy]:
    strat = pitch_strategy or strategy_mod.assemble_strategy(applicable_rule)
    is_opener = len(history) == 0

    if is_opener:
        opener_text, options, path = await _produce_opener(profile, strat, applicable_rule)
        strat = strat.model_copy(update={"opener_text": opener_text})
        reply = opener_text
    else:
        reply, options, path = await _produce_continuation(profile, strat, history)

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
        response_options=options,
    )
    return step, strat


async def _produce_opener(
    profile: schemas.Profile,
    strat: schemas.PitchStrategy,
    applicable_rule: schemas.Rule | None,
) -> tuple[str, list[schemas.ResponseOption] | None, str]:
    if applicable_rule is None:
        text, options = await _opener_via_llm(profile, strat)
        return text, options, "improvise"

    if strategy_mod.has_dynamic_slot(applicable_rule, "opener_type"):
        text, options = await _opener_via_llm(profile, strat)
        return text, options, "hybrid"

    return templates.render_opener(profile, strat), None, "static"


async def _opener_via_llm(
    profile: schemas.Profile,
    strat: schemas.PitchStrategy,
) -> tuple[str, list[schemas.ResponseOption] | None]:
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
        raw = await llm.complete(prompt, system="You are a research-liaison agent. Respond with valid JSON only.")
        text, options = _parse_llm_json(raw)
        if text:
            return text, options
    except _LLM_OFFLINE_EXCEPTIONS as e:
        log.warning("opener LLM unavailable (%s); using template fallback", e.__class__.__name__)
    except Exception:  # noqa: BLE001
        log.exception("opener LLM call failed; falling back to template")
    return templates.render_opener(profile, strat), None


async def _produce_continuation(
    profile: schemas.Profile,
    strat: schemas.PitchStrategy,
    history: list[schemas.DialogueStep],
) -> tuple[str, list[schemas.ResponseOption] | None, str]:
    last = history[-1]
    try:
        prompt = llm.render(
            "continuation",
            turn=len(history) + 1,
            profile_name=profile.name,
            profile_role=profile.role,
            profile_domain=profile.domain,
            profile_headline=profile.headline,
            profile_recent_signals=" / ".join(profile.recent_signals)
            if profile.recent_signals
            else "(none)",
            framing=strat.framing,
            tone=strat.tone,
            ask_size=strat.ask_size,
            history_block=_format_history_for_prompt(history),
            last_choice=last.visitor_choice or "neutral",
        )
        raw = await llm.complete(prompt, system="You are a research-liaison agent. Respond with valid JSON only.")
        text, options = _parse_llm_json(raw)
        if text:
            return text, options, "continuation-llm"
    except _LLM_OFFLINE_EXCEPTIONS as e:
        log.warning(
            "continuation LLM unavailable (%s); using template fallback",
            e.__class__.__name__,
        )
    except Exception:  # noqa: BLE001
        log.exception("continuation LLM call failed; falling back to template")
    return templates.render_continuation(profile, strat, history), None, "continuation-template"


def _format_history_for_prompt(history: list[schemas.DialogueStep]) -> str:
    button_label = {
        "positive": "[Tell me more.]",
        "skeptical": "[Skeptical, why Defy?]",
        "negative": "[Not interested.]",
    }
    lines: list[str] = []
    for step in history:
        lines.append(f"Agent (turn {step.turn}): {step.agent_reply}")
        if step.visitor_choice:
            lines.append(f"Visitor: {button_label.get(step.visitor_choice, step.visitor_choice)}")
    return "\n".join(lines) if lines else "(no prior turns)"
