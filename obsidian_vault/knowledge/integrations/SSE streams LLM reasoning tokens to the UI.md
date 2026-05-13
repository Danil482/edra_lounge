---
tags: [integration, sse, reflection, streaming]
date: 2026-05-13
---

# SSE streams LLM reasoning tokens to the UI

When a rule revision is triggered, the LLM's reasoning is streamed to the frontend in real time via Server-Sent Events (SSE).

## Flow

1. Consistency loop detects `should_revise` → creates `RevisionRow` (status=pending)
2. Frontend detects active revision via `/state` polling → opens SSE at `/reflections/stream/{revision_id}`
3. `reflection/revise.py → stream_revision()` renders the "reflect" prompt and calls `llm.stream()`
4. Tokens arrive as `event: reasoning` until a `---REVISION---` marker
5. After the marker, JSON accumulates and is emitted as `event: revision` (proposed rule slots)
6. Final `event: done` closes the stream

## Frontend handling

`app.js` displays reasoning tokens in a reflection console panel. The proposed rule change appears as a diff-style display. Operator can approve/reject via API.

## Dependencies

- `sse-starlette` — FastAPI-compatible SSE responses
- `backend/llm/client.py → stream()` — async token iterator

## Key files

- `backend/reflection/revise.py` — stream_revision async generator
- `backend/routers/reflections.py` — SSE endpoint
