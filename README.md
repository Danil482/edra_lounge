# EDRA Lounge

Booth demo of Experience-Driven Rule Adaptation as a café-manager game.

Spec: see [`TASK.md`](./TASK.md). This repo is the implementation.

## Quickstart

```bash
pip install -e ".[dev]"
cp .env.example .env
make seed         # populate SQLite with seeded personas
make demo         # backend on :8000 (frontend mounted at /)
# open http://localhost:8000
```

Two-layer architecture: Python/FastAPI backend + vanilla HTML/JS frontend.
**No external orchestrator** — tick / consistency / factory loops run as
asyncio tasks inside the FastAPI process (see `backend/orchestrator.py`).

## Layout

```
backend/
  app.py           FastAPI entry + lifespan (starts Orchestrator)
  orchestrator.py  asyncio loops + on_new_episode reactive hook
  memory/          SQLAlchemy ORM + Pydantic/DB bridge + seed
  clustering/      HDBSCAN over MiniLM embeddings + UMAP projection
  induction/       Cluster → Rule (LLM, slot schema)
  monitor/         Consistency score + revise trigger
  reflection/      Revision streaming
  factory/         Uncovered-cluster detection + agent spawning
  simulator/       Deterministic visitor + preference matrix + drift
  llm/             httpx-based Ollama/Anthropic client + 5 prompt templates
  routers/         FastAPI endpoint groups (one module per resource)
frontend/          index.html + styles.css + app.js (no build)
seeded_run.yaml    Pre-recorded 3-day visit schedule
tests/             pytest (preferences, orchestrator resilience, ...)
```

## LLM modes

Switched via `LLM_MODE` env var.

- `local` (default, booth) — Ollama at `localhost:11434`, model from `OLLAMA_MODEL`.
- `remote` (dev only) — Anthropic API; needs `ANTHROPIC_API_KEY`.

## Status

Phase 1 skeleton — data contracts frozen, orchestrator + routers wired,
business logic inside modules is marked `# TODO(phase1)` and lands next.
