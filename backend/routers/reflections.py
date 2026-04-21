"""SSE endpoint for the Reflection Console.

Flow:
  1. POST /rules/{id}/revise → creates Revision row, status=pending, returns id.
  2. Frontend subscribes to GET /reflections/stream/{revision_id}.
  3. This endpoint runs reflection.stream_revision, emitting each chunk as an
     SSE `data:` event, then `event: done` with the parsed proposed_rule JSON.

Separating trigger from stream lets the client re-subscribe after a disconnect
without re-triggering the LLM.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from backend.db import get_session

router = APIRouter(prefix="/reflections", tags=["reflections"])


@router.get("/stream/{revision_id}")
async def stream(
    revision_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    # TODO(phase1): load Revision row by revision_id, load the underlying Rule
    # + contradicting episodes, iterate reflection.stream_revision and yield
    # SSE events. On completion, parse proposed_rule, persist, emit 'done' event.
    #
    # Sketch:
    #   revision = await _load_revision(session, revision_id)
    #   rule     = await _load_rule(session, revision.rule_id)
    #   contra   = await _load_episodes(session, revision.contradicting_episode_ids)
    #
    #   async def generator():
    #       accumulated = ""
    #       async for kind, chunk in reflection.stream_revision(rule, contra):
    #           if kind == "reasoning":
    #               accumulated += chunk
    #               yield {"event": "reasoning", "data": chunk}
    #           else:  # revision JSON
    #               proposed = reflection.parse_proposed_rule(rule, chunk)
    #               await _persist_proposal(session, revision_id, accumulated, proposed)
    #               yield {"event": "done", "data": proposed.model_dump_json()}
    #               return
    #
    #   return EventSourceResponse(generator())

    raise HTTPException(status_code=501, detail="phase1-stub: SSE wiring pending")


def _sse_event(event: str, data) -> dict:
    """sse-starlette expects dicts shaped like this."""
    if not isinstance(data, str):
        data = json.dumps(data)
    return {"event": event, "data": data}
