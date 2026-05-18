"""Feature 1: Dynamic response buttons — ResponseOption schema + DialogueStep serialization.

Validates the ResponseOption model, DialogueStep.response_options field,
and edge cases around serialization/deserialization.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.schemas import DialogueStep, ResponseOption


# ── ResponseOption schema validation ─────────────────────────────────────

def test_response_option_valid_positive():
    opt = ResponseOption(text="Sounds interesting!", sentiment="positive")
    assert opt.text == "Sounds interesting!"
    assert opt.sentiment == "positive"


def test_response_option_valid_skeptical():
    opt = ResponseOption(text="Why should I trust you?", sentiment="skeptical")
    assert opt.sentiment == "skeptical"


def test_response_option_valid_negative():
    opt = ResponseOption(text="No thanks.", sentiment="negative")
    assert opt.sentiment == "negative"


def test_response_option_rejects_invalid_sentiment():
    with pytest.raises(ValidationError):
        ResponseOption(text="Some text", sentiment="neutral")


def test_response_option_rejects_empty_sentiment():
    with pytest.raises(ValidationError):
        ResponseOption(text="Some text", sentiment="")


# ── DialogueStep.response_options serialization ─────────────────────────

def _three_options() -> list[ResponseOption]:
    return [
        ResponseOption(text="Go on.", sentiment="positive"),
        ResponseOption(text="Prove it.", sentiment="skeptical"),
        ResponseOption(text="No thanks.", sentiment="negative"),
    ]


def test_dialogue_step_with_response_options_serializes():
    step = DialogueStep(
        turn=1,
        agent_thought="thinking",
        agent_reply="Hello.",
        response_options=_three_options(),
    )
    data = step.model_dump()
    assert len(data["response_options"]) == 3
    assert data["response_options"][0]["text"] == "Go on."
    assert data["response_options"][0]["sentiment"] == "positive"


def test_dialogue_step_response_options_roundtrip():
    step = DialogueStep(
        turn=2,
        agent_thought="analysis",
        agent_reply="Nice point.",
        response_options=_three_options(),
    )
    json_str = step.model_dump_json()
    restored = DialogueStep.model_validate_json(json_str)
    assert len(restored.response_options) == 3
    assert restored.response_options[1].sentiment == "skeptical"


def test_dialogue_step_response_options_default_is_none():
    step = DialogueStep(
        turn=1,
        agent_thought="t",
        agent_reply="r",
    )
    assert step.response_options is None


def test_dialogue_step_response_options_explicit_none():
    step = DialogueStep(
        turn=1,
        agent_thought="t",
        agent_reply="r",
        response_options=None,
    )
    data = step.model_dump()
    assert data["response_options"] is None


def test_dialogue_step_response_options_empty_list():
    step = DialogueStep(
        turn=1,
        agent_thought="t",
        agent_reply="r",
        response_options=[],
    )
    assert step.response_options == []
    data = step.model_dump()
    assert data["response_options"] == []


def test_dialogue_step_response_options_preserves_order():
    opts = [
        ResponseOption(text="C", sentiment="negative"),
        ResponseOption(text="A", sentiment="positive"),
        ResponseOption(text="B", sentiment="skeptical"),
    ]
    step = DialogueStep(
        turn=1,
        agent_thought="t",
        agent_reply="r",
        response_options=opts,
    )
    assert step.response_options[0].text == "C"
    assert step.response_options[1].text == "A"
    assert step.response_options[2].text == "B"
