"""SSE endpoint for the Reflection Console (TASK.md §7, §10.6).

Flow:
  1. POST /rules/{id}/revise (or auto from the consistency loop) creates a
     Revision row, status=pending, with proposed_rule starting as a copy of
     the rule under revision.
  2. Frontend opens GET /reflections/stream/{revision_id}.
  3. This endpoint runs `reflection.stream_revision`, emitting each token as
     `event: reasoning`, then `event: revision` carrying the parsed
     proposed_rule JSON, then a final `event: done`.
  4. The Revision row is updated with the accumulated reasoning + parsed rule
     so reconnecting clients see the final state in `/state.active_revision`.

If the LLM is unavailable or returns malformed JSON, we fall back to a
deterministic mode-of-slots induction over the succeeding (accepted)
post-induction episodes, so the proposed rule still reflects the strategy the
evidence supports and the booth UI never gets stuck on an empty diff.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from backend import schemas
from backend.config import settings
from backend.db import async_session_factory, get_session
from backend.memory import store
from backend.reflection import revise as reflect_mod


log = logging.getLogger(__name__)
router = APIRouter(prefix="/reflections", tags=["reflections"])

_SLOT_NAMES = ("framing", "tone", "opener_type", "word_target", "ask_size")


def _slots_match(a: schemas.Rule, b: schemas.Rule) -> bool:
    a_vals = {s.name: s.value for s in a.slots}
    b_vals = {s.name: s.value for s in b.slots}
    return all(a_vals.get(n) == b_vals.get(n) for n in _SLOT_NAMES)


@router.get("/stream/{revision_id}")
async def stream(revision_id: str):
    # We don't take a Depends-injected session here because SSE generators
    # outlive the request scope; we open our own session for the final commit.
    async with async_session_factory() as session:
        rev = await store.get_revision(session, revision_id)
        if rev is None:
            raise HTTPException(status_code=404, detail=f"unknown revision: {revision_id}")
        rule = await store.get_rule(session, rev.rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail=f"unknown rule: {rev.rule_id}")
        cluster_eps = await store.episodes_for_cluster(session, rule.cluster_id)
        contradicting = []
        if rev.contradicting_episode_ids:
            id_set = set(rev.contradicting_episode_ids)
            contradicting = [ep for ep in cluster_eps if ep.id in id_set]

        # Evidence for the revision is the recent post-induction history of the
        # cluster — both what is failing AND what is succeeding — so the LLM (and
        # the deterministic fallback) can induce toward the emerging winner.
        post = sorted(
            (ep for ep in cluster_eps if ep.timestamp > rule.induced_at),
            key=lambda ep: ep.timestamp,
        )[-(2 * settings.cs_window):]
        succeeding = [ep for ep in post if ep.outcome == "accepted"]

    fallback_rule = reflect_mod.mode_of_slots_rule(rule, succeeding)

    async def event_gen():
        accumulated_reasoning = ""
        proposed = fallback_rule
        try:
            async for kind, payload in reflect_mod.stream_revision(
                rule, contradicting, succeeding
            ):
                if kind == "reasoning":
                    accumulated_reasoning += payload
                    yield {"event": "reasoning", "data": payload}
                elif kind == "revision":
                    try:
                        proposed = reflect_mod.parse_proposed_rule(rule, payload)
                        if _slots_match(proposed, rule):
                            log.warning(
                                "LLM proposed rule identical to current for %s; "
                                "using mode-of-slots fallback",
                                rule.id,
                            )
                            proposed = fallback_rule
                    except Exception:  # noqa: BLE001
                        log.exception("parse_proposed_rule failed; using mode-of-slots")
                        proposed = fallback_rule
                        if _slots_match(proposed, rule):
                            log.error(
                                "mode-of-slots fallback also identical to current for %s; "
                                "succeeding evidence may be empty",
                                rule.id,
                            )
                    yield {
                        "event": "revision",
                        "data": json.dumps(proposed.model_dump(mode="json")),
                    }
        except Exception as e:  # noqa: BLE001
            log.exception("reflection stream errored: %s", e)
            fallback_msg = (
                "(LLM offline — proposed rule induced by mode-of-slots over the "
                "succeeding sessions in this cluster.)"
            )
            accumulated_reasoning = accumulated_reasoning or fallback_msg
            yield {"event": "reasoning", "data": fallback_msg}
            yield {
                "event": "revision",
                "data": json.dumps(fallback_rule.model_dump(mode="json")),
            }
            proposed = fallback_rule

        async with async_session_factory() as commit_session:
            await store.update_revision(
                commit_session,
                revision_id,
                llm_reasoning=accumulated_reasoning,
                proposed_rule=proposed,
            )
        yield {"event": "done", "data": "1"}

    return EventSourceResponse(event_gen())


def _sse_event(event: str, data) -> dict:
    if not isinstance(data, str):
        data = json.dumps(data)
    return {"event": event, "data": data}


# Re-export for tests
__all__ = ["router", "_sse_event"]


# Phase 2 will add a streaming-friendly polling fallback for the booth display
# in case browsers running the kiosk drop EventSource. Asyncio is referenced
# here purely so log captures land in time during shutdown.
_ = asyncio
_ = datetime
