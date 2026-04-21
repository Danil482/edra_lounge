---
tags: [home, index]
date: 2026-04-21
---

# EDRA Lounge — Vault Home

Booth demo of Experience-Driven Rule Adaptation (EDRA) as a café-manager game, for research-conference demo.

Spec: [`../../TASK.md`](../../TASK.md)

## Architecture (2 layers)

1. **Backend** (Python / FastAPI) — lives in [`../../backend/`](../../backend/)
   - `orchestrator.py` — asyncio loops (tick / consistency / factory) + `on_new_episode` reactive hook
   - Core modules: `memory`, `clustering`, `induction`, `monitor`, `reflection`, `factory`, `simulator`, `llm`
   - No external orchestrator. No n8n, no Celery. All coordination is in-process.
2. **Frontend** (vanilla HTML/JS) — [`../../frontend/`](../../frontend/)
   - Polls `/state` every 1s, subscribes to SSE `/reflections/stream/{id}` during revision
   - Ports the mockup `edra_lounge_mockup.html` (author still refining it)

## Where is the research track?

Doctoral-proposal work with real Pipedrive data lives in the **EDRA** repo (`../EDRA/`). That track is paused — Lounge is the focus until the booth is done.

## Status

- 2026-04-21: repo carved out of EDRA, Phase 1 skeleton in place. See [[current priorities]].

## Navigation

- [[current priorities]]
- [[sessions/2026-04-21 Pivot to Lounge demo, skeleton shipped]]
