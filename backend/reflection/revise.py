"""Rule revision — streams LLM reasoning for the UI reflection console, then
parses a proposed rule. Does NOT auto-apply in Phase 1; returns a pending
Revision for the operator to accept / reject / edit (TASK.md §10.6).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import AsyncIterator

from backend import schemas
from backend.llm import client as llm


REVISION_MARKER = "---REVISION---"


def _format_rule_slots(rule: schemas.Rule) -> str:
    return "\n".join(
        f"  {s.name}: kind={s.kind} value={s.value!r} prompt={s.prompt!r}"
        for s in rule.slots
    )


def _format_contradicting(episodes: list[schemas.Episode]) -> str:
    lines = []
    for i, ep in enumerate(episodes, 1):
        ps = ep.pitch_strategy
        lines.append(
            f"  [{i}] profile={ep.profile_id} "
            f"pitch=({ps.framing}/{ps.tone}/{ps.opener_type}/{ps.word_target}/{ps.ask_size}) "
            f"outcome={ep.outcome} final_interest={ep.final_interest:+d}"
        )
    return "\n".join(lines)


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def stream_revision(
    rule: schemas.Rule,
    contradicting: list[schemas.Episode],
) -> AsyncIterator[tuple[str, str]]:
    """Yields ('reasoning', chunk) while reasoning flows, then ('revision', json).

    The router converts these into SSE events: `event: reasoning` / `event: revision`.
    """
    prompt = llm.render(
        "reflect",
        rule_id=rule.id,
        rule_slots_formatted=_format_rule_slots(rule),
        contradicting_episodes_formatted=_format_contradicting(contradicting),
    )

    buffer = ""
    reasoning_done = False
    async for chunk in llm.stream(prompt, system="You are a rule-revision engine."):
        buffer += chunk
        if not reasoning_done and REVISION_MARKER in buffer:
            head, _, tail = buffer.partition(REVISION_MARKER)
            # Yield only the portion of head we haven't already yielded as reasoning.
            already_yielded_len = len(buffer) - len(chunk)
            new_reasoning = head[max(0, already_yielded_len) :]
            if new_reasoning:
                yield ("reasoning", new_reasoning)
            reasoning_done = True
            buffer = tail
        elif not reasoning_done:
            yield ("reasoning", chunk)
        # after marker we accumulate the JSON body into buffer

    yield ("revision", buffer.strip())


def parse_proposed_rule(
    original: schemas.Rule,
    revision_json: str,
) -> schemas.Rule:
    data = json.loads(_strip_fences(revision_json))
    slots = [schemas.RuleSlot(**s) for s in data["slots"]]
    return schemas.Rule(
        id=original.id,  # caller decides whether to issue a new id on accept
        cluster_id=original.cluster_id,
        slots=slots,
        induced_at=datetime.utcnow(),
        induced_from_episode_ids=original.induced_from_episode_ids,
        status="under_revision",
        deprecated_by=None,
        cs_history=original.cs_history,
    )
