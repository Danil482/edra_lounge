"""Rule revision — streams LLM reasoning for the UI reflection console, then
parses a proposed rule. Does NOT auto-apply in Phase 1; returns a pending
Revision for the operator to accept / reject / edit (TASK.md §10.6).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from typing import AsyncIterator

from backend import schemas
from backend.llm import client as llm


_REVISION_RE = re.compile(r'-{3}\s*REVISION\s*-{3}')

SLOT_NAMES = ["framing", "tone", "opener_type", "word_target", "ask_size"]


def _format_rule_slots(rule: schemas.Rule) -> str:
    return "\n".join(
        f"  {s.name}: kind={s.kind} value={s.value!r} prompt={s.prompt!r}"
        for s in rule.slots
    )


def _format_episodes(episodes: list[schemas.Episode]) -> str:
    if not episodes:
        return "  (none)"
    lines = []
    for i, ep in enumerate(episodes, 1):
        ps = ep.pitch_strategy
        lines.append(
            f"  [{i}] profile={ep.profile_id} "
            f"pitch={{framing={ps.framing}, tone={ps.tone}, opener_type={ps.opener_type}, "
            f"word_target={ps.word_target}, ask_size={ps.ask_size}}} "
            f"outcome={ep.outcome} final_interest={ep.final_interest:+d}"
        )
    return "\n".join(lines)


def mode_of_slots_rule(
    original: schemas.Rule,
    accepted: list[schemas.Episode],
) -> schemas.Rule:
    """Deterministic induction: most-frequent slot value over the accepted
    (succeeding) episodes → a revised static rule sharing the original's id and
    cluster. Used when the LLM is offline or returns malformed JSON, so the
    reflection console still proposes the strategy the evidence supports."""
    def _mode(field: str) -> str | None:
        counter: Counter[str] = Counter(getattr(ep.pitch_strategy, field) for ep in accepted)
        if not counter:
            slot = next((s for s in original.slots if s.name == field), None)
            return slot.value if slot else None
        return counter.most_common(1)[0][0]

    slots = [
        schemas.RuleSlot(name=name, kind="static", value=_mode(name))
        for name in SLOT_NAMES
    ]
    return schemas.Rule(
        id=original.id,
        cluster_id=original.cluster_id,
        slots=slots,
        induced_at=datetime.utcnow(),
        induced_from_episode_ids=original.induced_from_episode_ids,
        status="under_revision",
        deprecated_by=None,
        cs_history=original.cs_history,
    )


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def stream_revision(
    rule: schemas.Rule,
    contradicting: list[schemas.Episode],
    succeeding: list[schemas.Episode] | None = None,
) -> AsyncIterator[tuple[str, str]]:
    """Yields ('reasoning', chunk) while reasoning flows, then ('revision', json).

    `contradicting` are post-induction episodes where the current rule's strategy
    failed; `succeeding` are post-induction episodes (a different strategy) that
    are now winning. The LLM is shown both so it can induce the revised rule the
    evidence supports rather than echoing the failing rule.

    The router converts these into SSE events: `event: reasoning` / `event: revision`.
    """
    prompt = llm.render(
        "reflect",
        rule_id=rule.id,
        rule_slots_formatted=_format_rule_slots(rule),
        contradicting_episodes_formatted=_format_episodes(contradicting),
        succeeding_episodes_formatted=_format_episodes(succeeding or []),
    )

    buffer = ""
    reasoning_done = False
    async for chunk in llm.stream(prompt, system="You are a rule-revision engine."):
        buffer += chunk
        m = _REVISION_RE.search(buffer)
        if not reasoning_done and m:
            head = buffer[:m.start()]
            tail = buffer[m.end():]
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
    raw_slots = data.get("slots") or data.get("rule", {}).get("slots") or data.get("proposed_slots")
    if not raw_slots:
        raise KeyError("slots")
    slots = [schemas.RuleSlot(**s) for s in raw_slots]
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
