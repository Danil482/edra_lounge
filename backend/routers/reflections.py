"""SSE endpoint for the Reflection Console (TASK.md §7, §10.6).

Flow (Phase 1B will fully wire it):
  1. POST /rules/{id}/revise  →  creates a Revision row, status=pending, returns id
  2. Frontend subscribes to GET /reflections/stream/{revision_id}
  3. This endpoint runs reflection.stream_revision, emitting each chunk as an
     SSE `event: reasoning` line, then a final `event: done` with the parsed
     proposed_rule JSON.

Splitting the trigger from the stream lets the client re-subscribe after a
disconnect without re-triggering the LLM.
"""

import json

from fastapi import APIRouter, HTTPException


router = APIRouter(prefix="/reflections", tags=["reflections"])


@router.get("/stream/{revision_id}")
async def stream(revision_id: str):
    raise HTTPException(status_code=501, detail="phase1B-stub: SSE wiring pending")


def _sse_event(event: str, data) -> dict:
    """sse-starlette expects dicts shaped like this; kept here for Phase 1B reuse."""
    if not isinstance(data, str):
        data = json.dumps(data)
    return {"event": event, "data": data}
