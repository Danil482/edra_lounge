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
from pathlib import Path

import httpx

from backend import schemas
from backend.llm import client as llm
from backend.pitch import strategy as strategy_mod
from backend.pitch import templates


log = logging.getLogger(__name__)

_LLM_OFFLINE_EXCEPTIONS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout)

OPENER_LLM_PATHS = ("hybrid", "improvise")

_EXPECTED_SENTIMENTS = {"positive", "skeptical", "negative"}

RESPONSE_CATEGORIES = [
    "lab-paper-reference",
    "methodology-hook",
    "deployment-result",
    "profile-callback",
    "concrete-next-step",
    "honest-framing",
]

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "llm" / "prompts"
_LAB_FACTS = (_PROMPTS_DIR / "_lab_facts.txt").read_text(encoding="utf-8")
_SYSTEM_TEMPLATE = (_PROMPTS_DIR / "_system.txt").read_text(encoding="utf-8")
_SYSTEM_MESSAGE = _SYSTEM_TEMPLATE.format(lab_facts=_LAB_FACTS)


def _parse_llm_json(raw: str) -> tuple[str, str | None, list[schemas.ResponseOption] | None]:
    """Extract pitch text, inner thought, and response options from LLM JSON.

    Returns (pitch_text, thought_or_none, options_or_none).
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
        return raw.strip().strip('"').strip(), None, None

    if not isinstance(data, dict) or "pitch" not in data:
        return raw.strip().strip('"').strip(), None, None

    pitch = str(data["pitch"]).strip().strip('"').strip()
    thought = str(data["thought"]).strip() if data.get("thought") else None

    raw_options = data.get("options")
    if not isinstance(raw_options, list) or len(raw_options) != 3:
        return pitch, thought, None

    options: list[schemas.ResponseOption] = []
    seen_sentiments: set[str] = set()
    for opt in raw_options:
        if not isinstance(opt, dict):
            return pitch, thought, None
        opt_text = str(opt.get("text", "")).strip()
        sentiment = str(opt.get("sentiment", "")).strip().lower()
        if not opt_text or sentiment not in _EXPECTED_SENTIMENTS:
            return pitch, thought, None
        if sentiment in seen_sentiments:
            return pitch, thought, None
        seen_sentiments.add(sentiment)
        options.append(schemas.ResponseOption(text=opt_text, sentiment=sentiment))

    if seen_sentiments != _EXPECTED_SENTIMENTS:
        return pitch, thought, None

    return pitch, thought, options


async def generate_turn(
    profile: schemas.Profile,
    history: list[schemas.DialogueStep],
    applicable_rule: schemas.Rule | None,
    *,
    pitch_strategy: schemas.PitchStrategy | None = None,
    used_categories: list[str] | None = None,
    interest: int = 0,
) -> tuple[schemas.DialogueStep, schemas.PitchStrategy]:
    strat = pitch_strategy or strategy_mod.assemble_strategy(applicable_rule)
    is_opener = len(history) == 0

    if is_opener:
        opener_text, llm_thought, options, path = await _produce_opener(profile, strat, applicable_rule)
        strat = strat.model_copy(update={"opener_text": opener_text})
        reply = opener_text
    else:
        reply, llm_thought, options, path = await _produce_continuation(profile, strat, history, used_categories, interest=interest)

    rule_id = applicable_rule.id if applicable_rule is not None else None
    thought = llm_thought or templates.render_thought(strat, rule_id, is_opener)
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
) -> tuple[str, str | None, list[schemas.ResponseOption] | None, str]:
    path = "improvise"
    if applicable_rule is not None:
        path = "hybrid" if strategy_mod.has_dynamic_slot(applicable_rule, "opener_type") else "static"

    text, thought, options = await _opener_via_llm(profile, strat)
    return text, thought, options, path


async def _opener_via_llm(
    profile: schemas.Profile,
    strat: schemas.PitchStrategy,
) -> tuple[str, str | None, list[schemas.ResponseOption] | None]:
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
        raw = await llm.complete(prompt, system=_SYSTEM_MESSAGE)
        text, thought, options = _parse_llm_json(raw)
        if text:
            return text, thought, options
    except _LLM_OFFLINE_EXCEPTIONS as e:
        log.warning("opener LLM unavailable (%s); using template fallback", e.__class__.__name__)
    except Exception:  # noqa: BLE001
        log.exception("opener LLM call failed; falling back to template")
    return templates.render_opener(profile, strat), None, None


async def _produce_continuation(
    profile: schemas.Profile,
    strat: schemas.PitchStrategy,
    history: list[schemas.DialogueStep],
    used_categories: list[str] | None = None,
    *,
    interest: int = 0,
) -> tuple[str, str | None, list[schemas.ResponseOption] | None, str]:
    last = history[-1]
    remaining = _remaining_categories(used_categories)
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
            word_target=strat.word_target,
            history_block=_format_history_for_prompt(history),
            last_choice=last.visitor_choice or "neutral",
            used_categories=", ".join(used_categories) if used_categories else "(none)",
            remaining_categories=", ".join(remaining),
            interest=interest,
        )
        raw = await llm.complete(prompt, system=_SYSTEM_MESSAGE)
        text, thought, options = _parse_llm_json(raw)
        if text:
            return text, thought, options, "continuation-llm"
    except _LLM_OFFLINE_EXCEPTIONS as e:
        log.warning(
            "continuation LLM unavailable (%s); using template fallback",
            e.__class__.__name__,
        )
    except Exception:  # noqa: BLE001
        log.exception("continuation LLM call failed; falling back to template")
    return templates.render_continuation(profile, strat, history), None, None, "continuation-template"


def _remaining_categories(used: list[str] | None) -> list[str]:
    if not used:
        return list(RESPONSE_CATEGORIES)
    remaining = [c for c in RESPONSE_CATEGORIES if c not in used]
    return remaining if remaining else list(RESPONSE_CATEGORIES)


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
