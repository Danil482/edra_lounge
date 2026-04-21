---
tags: [home, priorities, status]
date: 2026-04-21
---

# Current Priorities

## Active (Phase 1 business logic)

- [ ] **Fill `# TODO(phase1)` markers** — the skeleton has frozen contracts; each module has stubs where the business logic lands. Hit the big ones first:
  - `orchestrator._recluster` / `_try_induce_all` / `_check_all_rule_cs` / `_evaluate_factory` / `_pick_rule_for_persona`
  - `routers/rules.py::induce` — load cluster + episodes, call `induction.induce_rule`, persist
  - `routers/rules.py::consistency_of` — compute CS + recent history
  - `routers/rules.py::revise` — find contradicting episodes via CS window, persist Revision row
  - `routers/reflections.py::stream` — wire `EventSourceResponse` over `reflection.stream_revision`
  - `routers/clusters.py::recompute_clusters` — clustering pipeline end-to-end (run HDBSCAN, upsert ClusterRows, label via LLM)
- [ ] **Finish mockup port** — author refining `edra_lounge_mockup.html`; when ready, copy CSS into `frontend/styles.css` verbatim and restructure `index.html` layout to match
- [ ] **Tune sim preferences** — `style_affinity`, `drink_affinity`, `combo_bonus` are placeholder numbers; run `pytest tests/test_preferences.py` (unique-top-3 invariant) after every tweak
- [ ] **Ollama model pre-download** — `ollama pull llama3.1:8b-instruct` before booth; verify `LLM_MODE=local` works offline
- [ ] **SSE wiring e2e** — POST revise → GET stream → frontend EventSource subscription; token-by-token render in reflection console

## Done 2026-04-21

- [x] Carved Lounge repo out of EDRA monorepo (sibling path, separate git)
- [x] Two-layer architecture skeleton per TASK.md §2
- [x] All 7 Pydantic data contracts + matching SQLAlchemy tables
- [x] LLM client (httpx, local/remote, streaming)
- [x] Simulator skeleton: preferences (topic_affinity verbatim from §5.2), drift handlers, schedule loader, deterministic tick
- [x] 5 prompts in marketing vocabulary (persona × tension → angle × expression)
- [x] Orchestrator with three resilient loops + `on_new_episode` hook, wired into FastAPI lifespan
- [x] SSE split — POST /rules/{id}/revise returns Revision, GET /reflections/stream/{id} streams
- [x] `seeded_run.yaml` — 3-day visit arc
- [x] Frontend stubs + tests (`test_preferences`, `test_orchestrator`)

## Known skeleton gaps (intentional — Phase 1 business logic)

- Most router handlers return 501 or placeholder values; contracts are there, wiring to modules is not
- `_pick_rule_for_persona` is hardcoded to None → bartender always improvises (fine until induction starts firing)
- No actual Cluster-row persistence yet; clustering stays in-memory
- Reflection SSE handler is a commented sketch — the machinery (`reflection.stream_revision`, `reflection.parse_proposed_rule`) exists and is unit-testable

## Upcoming (Phase 2–3)

- UMAP projection live-refreshed on clustering
- Pixel-art sprites for 6 personas
- Reflection console token animation
- `make booth` with health-wait + browser full-screen
- Docker-compose bundle with Ollama for offline booth
- Operator cheat-sheet PDF

## Open questions (TASK.md §15 — flag author on first PR)

1. Same model for all 5 LLM calls, or split (8B for summary, bigger for reflection)?
2. Hybrid-rule `opener` — regenerate per visit or cache per (rule, persona, day)?
3. On revision accept: delete old rule or deprecate with pointer? (ablation matters → recommend deprecate)
4. `make reset` — same seed (reproducible) or random (variety)?

Defaults: same model, regenerate, deprecate, same seed.
