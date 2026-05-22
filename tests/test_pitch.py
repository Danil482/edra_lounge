"""Pitch generation paths — TASK.md §2 / §7.

Three observable paths share `generate_turn` and we want to verify each one
hits the right code without booting the LLM:

  - static rule (all 5 slots static) → no LLM call, opener from templates
  - hybrid rule (≥ 1 dynamic slot)   → LLM called for the dynamic slot
  - no rule                          → LLM called with default strategy

The LLM client is monkeypatched per-test so unit tests stay offline and
deterministic. We assert both the strategy resolution AND that the right
code path fired (by counting LLM invocations).
"""

from __future__ import annotations

from datetime import datetime

import pytest

from backend import schemas
from backend.pitch import generate, strategy as strategy_mod
from backend.pitch import templates


# ── Fixtures ─────────────────────────────────────────────────────────────

def _phd_profile() -> schemas.Profile:
    return schemas.Profile(
        id="arch_phd_nlp_introvert",
        source_kind="synthetic",
        source_identifier="arch_phd_nlp_introvert",
        name="Anya Volkova",
        role="PhD student",
        domain="NLP",
        seniority="early",
        headline="PhD in compositional generalisation",
        recent_signals=["Wrote a thread on parsing benchmarks plateauing."],
        archetype_summary="depth-seeking PhD",
        embedding=None,
        fetched_at=datetime.utcnow(),
        ttl_seconds=None,
    )


def _static_rule() -> schemas.Rule:
    return schemas.Rule(
        id="R.07",
        cluster_id="arch_phd_nlp_introvert",
        slots=[
            schemas.RuleSlot(name="framing", kind="static", value="knowledge-share"),
            schemas.RuleSlot(name="tone", kind="static", value="socratic"),
            schemas.RuleSlot(name="opener_type", kind="static", value="question"),
            schemas.RuleSlot(name="word_target", kind="static", value="medium"),
            schemas.RuleSlot(name="ask_size", kind="static", value="co-author"),
        ],
        induced_at=datetime.utcnow(),
    )


def _hybrid_rule() -> schemas.Rule:
    return schemas.Rule(
        id="R.08",
        cluster_id="arch_phd_nlp_introvert",
        slots=[
            schemas.RuleSlot(name="framing", kind="static", value="knowledge-share"),
            schemas.RuleSlot(name="tone", kind="static", value="socratic"),
            schemas.RuleSlot(
                name="opener_type",
                kind="dynamic",
                value=None,
                prompt="open with a question that references the contact's most recent signal",
            ),
            schemas.RuleSlot(name="word_target", kind="static", value="medium"),
            schemas.RuleSlot(name="ask_size", kind="static", value="co-author"),
        ],
        induced_at=datetime.utcnow(),
    )


# ── Strategy assembly ────────────────────────────────────────────────────

def test_assemble_strategy_static_rule_uses_slot_values():
    s = strategy_mod.assemble_strategy(_static_rule())
    assert s.framing == "knowledge-share"
    assert s.tone == "socratic"
    assert s.opener_type == "question"
    assert s.word_target == "medium"
    assert s.ask_size == "co-author"


def test_assemble_strategy_hybrid_rule_falls_back_to_default_for_dynamic_slots():
    s = strategy_mod.assemble_strategy(_hybrid_rule())
    # static slots come through verbatim
    assert s.framing == "knowledge-share"
    assert s.tone == "socratic"
    # dynamic slot uses the per-slot default (so the strategy is still well-formed
    # and scorable against the preference function before LLM fills it).
    assert s.opener_type == strategy_mod._DYNAMIC_SLOT_DEFAULT["opener_type"]


def test_assemble_strategy_none_rule_returns_improvise_default():
    s = strategy_mod.assemble_strategy(None)
    assert s == strategy_mod.DEFAULT_IMPROVISED_STRATEGY


# ── Templates ────────────────────────────────────────────────────────────

def test_render_opener_uses_signal_when_opener_type_is_reference_to_signal():
    profile = _phd_profile()
    strat = strategy_mod.DEFAULT_IMPROVISED_STRATEGY  # opener_type=reference-to-signal
    text = templates.render_opener(profile, strat)
    # The first signal substring should appear (truncated).
    assert "parsing benchmarks plateauing" in text or "parsing benchmarks" in text


def test_render_opener_falls_back_when_signals_missing():
    profile = _phd_profile().model_copy(update={"recent_signals": []})
    strat = strategy_mod.DEFAULT_IMPROVISED_STRATEGY
    text = templates.render_opener(profile, strat)
    # No quoted signal — should still mention domain.
    assert "NLP" in text


def test_render_thought_carries_rule_id_when_present():
    s = strategy_mod.DEFAULT_IMPROVISED_STRATEGY
    assert "rule R.07" in templates.render_thought(s, "R.07", is_opener=True)
    assert "improvising" in templates.render_thought(s, None, is_opener=True)


# ── generate_turn — three paths ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_turn_static_rule_calls_llm_for_response_options(monkeypatch):
    """Static rule path now uses LLM to generate opener with response options."""
    _LLM_JSON = '{"pitch": "Your parsing work is exactly what our benchmark needs.", "options": [{"text": "Tell me more about those benchmarks.", "sentiment": "positive"}, {"text": "What makes your lab different?", "sentiment": "skeptical"}, {"text": "Not really my area, thanks.", "sentiment": "negative"}]}'
    calls: dict[str, int] = {"complete": 0}

    async def _fake_llm(*args, **kwargs):
        calls["complete"] += 1
        return _LLM_JSON

    monkeypatch.setattr("backend.pitch.generate.llm.complete", _fake_llm)

    profile = _phd_profile()
    rule = _static_rule()
    step, used_strategy = await generate.generate_turn(
        profile=profile,
        history=[],
        applicable_rule=rule,
    )
    assert calls["complete"] == 1
    assert step.turn == 1
    assert step.rule_applied == "R.07"
    assert used_strategy.framing == "knowledge-share"
    assert step.response_options is not None
    assert len(step.response_options) == 3


@pytest.mark.asyncio
async def test_generate_turn_hybrid_rule_calls_llm_for_dynamic_slot(monkeypatch):
    """Hybrid rule with dynamic opener_type triggers exactly one LLM call."""
    calls: dict[str, int] = {"complete": 0}
    _LLM_JSON = '{"pitch": "Saw your work on parsing — keen to compare notes.", "options": [{"text": "That sounds interesting, tell me more.", "sentiment": "positive"}, {"text": "Why should I trust Defy on this?", "sentiment": "skeptical"}, {"text": "Thanks, but not for me.", "sentiment": "negative"}]}'

    async def _stub_complete(prompt, *, system=None):
        calls["complete"] += 1
        return _LLM_JSON

    monkeypatch.setattr("backend.pitch.generate.llm.complete", _stub_complete)

    step, used = await generate.generate_turn(
        profile=_phd_profile(),
        history=[],
        applicable_rule=_hybrid_rule(),
    )
    assert calls["complete"] == 1
    assert step.agent_reply == "Saw your work on parsing — keen to compare notes."
    assert used.opener_text == "Saw your work on parsing — keen to compare notes."
    assert step.response_options is not None
    assert len(step.response_options) == 3
    sentiments = {o.sentiment for o in step.response_options}
    assert sentiments == {"positive", "skeptical", "negative"}


@pytest.mark.asyncio
async def test_generate_turn_no_rule_calls_llm_with_default_strategy(monkeypatch):
    calls: dict[str, int] = {"complete": 0}
    _LLM_JSON = '{"pitch": "Improvised opener.", "options": [{"text": "Interesting, go on.", "sentiment": "positive"}, {"text": "What makes you credible?", "sentiment": "skeptical"}, {"text": "No thanks.", "sentiment": "negative"}]}'

    async def _stub_complete(prompt, *, system=None):
        calls["complete"] += 1
        return _LLM_JSON

    monkeypatch.setattr("backend.pitch.generate.llm.complete", _stub_complete)

    step, used = await generate.generate_turn(
        profile=_phd_profile(),
        history=[],
        applicable_rule=None,
    )
    assert calls["complete"] == 1
    assert used == strategy_mod.DEFAULT_IMPROVISED_STRATEGY.model_copy(
        update={"opener_text": "Improvised opener."}
    )
    assert step.rule_applied is None
    assert step.response_options is not None
    assert len(step.response_options) == 3


@pytest.mark.asyncio
async def test_generate_turn_llm_failure_falls_back_to_template(monkeypatch):
    """A broken LLM must not break the booth — template path takes over."""

    async def _broken_complete(*args, **kwargs):
        raise RuntimeError("ollama down")

    monkeypatch.setattr("backend.pitch.generate.llm.complete", _broken_complete)

    step, used = await generate.generate_turn(
        profile=_phd_profile(),
        history=[],
        applicable_rule=None,
    )
    assert step.agent_reply
    assert used.opener_text
    assert step.response_options is None


@pytest.mark.asyncio
async def test_generate_turn_continuation_calls_llm_with_history(monkeypatch):
    """Phase 4.3: turns 2+ go through the LLM (with full history) so replies
    vary per turn instead of cycling through 5 hardcoded templates."""
    calls: dict[str, int] = {"complete": 0}
    captured_prompts: list[str] = []
    _LLM_JSON = '{"pitch": "Continuation reply from LLM.", "options": [{"text": "That cohort sounds promising.", "sentiment": "positive"}, {"text": "How do I know this is legit?", "sentiment": "skeptical"}, {"text": "I will pass, thanks.", "sentiment": "negative"}]}'

    async def _stub_complete(prompt, *, system=None):
        calls["complete"] += 1
        captured_prompts.append(prompt)
        return _LLM_JSON

    monkeypatch.setattr("backend.pitch.generate.llm.complete", _stub_complete)

    profile = _phd_profile()
    rule = _static_rule()
    history = [
        schemas.DialogueStep(
            turn=1,
            agent_thought="(rule R.07: knowledge-share/socratic/question)",
            agent_reply="Opener line.",
            visitor_choice="positive",
            interest_delta=2,
            rule_applied="R.07",
        )
    ]
    step, _ = await generate.generate_turn(
        profile=profile,
        history=history,
        applicable_rule=rule,
        pitch_strategy=strategy_mod.assemble_strategy(rule),
    )
    assert step.turn == 2
    assert calls["complete"] == 1, "continuation must call the LLM"
    assert step.agent_reply == "Continuation reply from LLM."
    assert step.rule_applied == "R.07"
    assert "Opener line." in captured_prompts[0]
    assert "[Tell me more.]" in captured_prompts[0]
    assert step.response_options is not None
    assert len(step.response_options) == 3
    sentiments = {o.sentiment for o in step.response_options}
    assert sentiments == {"positive", "skeptical", "negative"}


@pytest.mark.asyncio
async def test_generate_turn_continuation_falls_back_to_template_on_llm_failure(monkeypatch):
    """If the LLM is offline mid-session, continuation must still produce
    a non-empty reply via the template fallback (no booth crash)."""

    async def _broken(*args, **kwargs):
        raise RuntimeError("openai down")

    monkeypatch.setattr("backend.pitch.generate.llm.complete", _broken)

    history = [
        schemas.DialogueStep(
            turn=1,
            agent_thought="(rule R.07: knowledge-share/socratic/question)",
            agent_reply="Opener line.",
            visitor_choice="skeptical",
            interest_delta=-1,
            rule_applied="R.07",
        )
    ]
    step, _ = await generate.generate_turn(
        profile=_phd_profile(),
        history=history,
        applicable_rule=_static_rule(),
        pitch_strategy=strategy_mod.assemble_strategy(_static_rule()),
    )
    assert step.turn == 2
    assert step.agent_reply  # template fallback fired
    assert step.response_options is None


# ── _parse_llm_json edge cases ──────────────────────────────────────────

def test_parse_llm_json_valid():
    raw = '{"pitch": "Hello world.", "options": [{"text": "Go on.", "sentiment": "positive"}, {"text": "Prove it.", "sentiment": "skeptical"}, {"text": "No thanks.", "sentiment": "negative"}]}'
    text, _thought, options = generate._parse_llm_json(raw)
    assert text == "Hello world."
    assert options is not None
    assert len(options) == 3
    assert {o.sentiment for o in options} == {"positive", "skeptical", "negative"}


def test_parse_llm_json_plain_text_fallback():
    raw = "Just a plain text response."
    text, _thought, options = generate._parse_llm_json(raw)
    assert text == "Just a plain text response."
    assert options is None


def test_parse_llm_json_markdown_fences():
    raw = '```json\n{"pitch": "Fenced.", "options": [{"text": "Yes.", "sentiment": "positive"}, {"text": "Why?", "sentiment": "skeptical"}, {"text": "No.", "sentiment": "negative"}]}\n```'
    text, _thought, options = generate._parse_llm_json(raw)
    assert text == "Fenced."
    assert options is not None


def test_parse_llm_json_duplicate_sentiment():
    raw = '{"pitch": "Dup.", "options": [{"text": "A.", "sentiment": "positive"}, {"text": "B.", "sentiment": "positive"}, {"text": "C.", "sentiment": "negative"}]}'
    text, _thought, options = generate._parse_llm_json(raw)
    assert text == "Dup."
    assert options is None


def test_parse_llm_json_missing_options():
    raw = '{"pitch": "No opts."}'
    text, _thought, options = generate._parse_llm_json(raw)
    assert text == "No opts."
    assert options is None


def test_parse_llm_json_wrong_option_count():
    raw = '{"pitch": "Two.", "options": [{"text": "A.", "sentiment": "positive"}, {"text": "B.", "sentiment": "skeptical"}]}'
    text, _thought, options = generate._parse_llm_json(raw)
    assert text == "Two."
    assert options is None
