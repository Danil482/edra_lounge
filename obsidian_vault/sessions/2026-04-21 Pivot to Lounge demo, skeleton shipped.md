---
tags: [session, pivot, skeleton, architecture]
date: 2026-04-21
---

# 2026-04-21 Pivot to Lounge demo, skeleton shipped

Focus shifted from the doctoral proposal (EDRA repo, Pipedrive, 635 episodes, many data-quality problems) onto a **3-week demo for a research conference** — EDRA Lounge, a bar with synthetic visitors.

## Decisions this session

1. **Separate repository.** We started inside EDRA on a `lounge` branch, then decided to extract into a sibling repo at `C:\Users\dania\PycharmProjects\edra-lounge\` — to avoid double-reading code between the research track and the demo track. The `lounge` branch in EDRA was deleted.
2. **No n8n.** All orchestration lives inside the FastAPI process as asyncio tasks. TASK.md §§2, 6, 12 lock this down.
3. **Two-layer architecture:** Python backend + vanilla HTML/JS frontend. No workers, queues, or workflow engines.

## What was built (skeleton)

- `backend/` structure exactly per TASK.md §13: `app / orchestrator / memory / clustering / induction / monitor / reflection / factory / simulator / llm / routers`
- All 7 Pydantic models from §4 verbatim (Persona, Offer, Episode, Cluster, Rule+RuleSlot, Revision, Agent)
- SQLAlchemy ORM for 6 tables
- LLM client over httpx (no SDK) with two modes — `LLM_MODE=local` (Ollama) and `LLM_MODE=remote` (Anthropic)
- Simulator: preference matrix 6×6×5×4; `topic_affinity` taken verbatim from §5.2, other affinities marked with `TODO(author-tune)` notes
- Two drift functions: `ai_bubble_pops` (swap hype↔foundations + enthusiastic↔skeptical for tech-founder) and `GradualPostdocShift` (15-step linear interpolation)
- Orchestrator: a class with `start()/stop()`, three resilient loops (tick 20s / consistency 10s / factory 30s) and a reactive `on_new_episode` hook
- SSE split: `POST /rules/{id}/revise` returns `Revision{id, status=pending}` synchronously; `GET /reflections/stream/{id}` streams
- 5 prompts in marketing vocabulary (§7: persona × tension → angle × expression) with fixed-tag output
- `seeded_run.yaml` for 3 days, drift A/B triggers tied to game clock
- Frontend stubs (`index.html` + `styles.css` + `app.js`) — polling works, SSE subscription TODO
- Tests: `test_preferences.py` (unique top-3 invariant), `test_orchestrator.py` (§14 loop resilience)

## Prompts — important correction

§7 of TASK.md requires: **internally** prompts operate on marketing vocabulary (persona, tension/pain point, angle, insight), but **output** is a fixed tag vocabulary (hype/foundations/.../coffee/beer/...). I first wrote prompts in café terms, then rewrote all 5 — the scientific framing of the project is (persona, tension) → (angle, expression), the café vocabulary lives only on the UI.

## What is NOT in the skeleton (deliberately)

Business logic inside modules sits behind `# TODO(phase1)`:
- ClusterRows are not persisted — clusters are recomputed in memory every tick
- `_pick_rule_for_persona` returns None → the bartender always improvises (until the first rules appear)
- SSE handler — a commented-out sketch (the underlying `reflection.stream_revision` is written and unit-testable)
- UMAP projection in `/state.clusters_viz` is currently an empty list

This is an honest Phase 1 skeleton — contracts fixed, infrastructure works end-to-end (health check + polling + orchestrator loops), **business logic not yet plugged in**. The next session removes TODO(phase1) in the order `induce → CS monitor → reflect SSE → factory spawn`.

## Repo hygiene

- `N8N_GUIDE.md` deleted — contradicts §12 non-goals
- The Makefile no longer knows about a separate orchestrator process
- README rewritten around the 2-layer model (3 phases instead of 4, Phase 3 is now booth-ready, not n8n)

## Next session — entry points

1. Fill in the heaviest TODO(phase1) — `orchestrator._try_induce_all` (pull eligible clusters + persist Rule rows + generate `R.XX` IDs)
2. Implement `routers/clusters.py::recompute_clusters` — HDBSCAN + upsert ClusterRows + LLM label via the cluster_label prompt
3. Finish the SSE handler in `routers/reflections.py` — a working EventSourceResponse around `reflection.stream_revision`
4. Manually run `make seed && make demo`, confirm the frontend does not crash on an empty DB and polling spins

## Files

- Mockup `edra_lounge_mockup.html` — the author is still iterating, not in the repo yet
- TASK.md — in the repo but untracked (the author edits iteratively)
