---
tags: [session, pivot, vocabulary, vn, profile-source, mockup-v2]
date: 2026-04-28
---

# 2026-04-28 Re-pivot to VN Pitch Floor, vocabulary swap

The author rewrote TASK.md and replaced the mockup. The project stays EDRA (Experience-Driven Rule Adaptation) and keeps the full scientific spine (episodic memory → clustering → induction → consistency monitor → reflective revision → agent factory), but **the thematic wrapper and almost the entire vocabulary changed**. We move from the 2026-04-21 skeleton (café/lounge) onto VN Pitch Floor.

## What changed — the pivot itself

| Layer | Was (2026-04-21, café) | Now (2026-04-28, VN/research-outreach) |
|---|---|---|
| **Metaphor** | Bar manager, barista picks drinks | Visual novel: anime agent EDRA represents research-collaboration from DEFY.group, a visitor walks in with their own LinkedIn |
| **Main input object** | `Persona` (vibe, role, domain) | `Profile` (from `ProfileSource`, with `recent_signals`, `seniority`, `headline`, `embedding`) |
| **What the agent emits** | `Offer` = (topic, style, drink, opener) | `PitchStrategy` = (framing, tone, opener_type, word_target, ask_size) — 5 slots, not 4 |
| **Session type** | One-shot offer → outcome_score | **Multi-turn dialogue** (3-7 steps) with `DialogueStep`, visitor choice (positive/skeptical/negative), and an interest gauge from −5 to +5 |
| **Prompt vocabulary** | persona × tension → angle × expression (marketing vocab) | research-outreach: same field shape, but §4.3 terms directly — `framing/tone/opener_type/word_target/ask_size` |
| **Archetypes** | 6: persona_phd_nlp, _postdoc_cv, _tech_founder, _senior_prof, _industry_pm, _vc_investor | 6 default + 2 spawnable: arch_phd_nlp_introvert, arch_postdoc_cv_ambitious, arch_tech_founder_applied, arch_senior_prof_meta, arch_industry_pm_pragmatic, arch_research_engineer_skeptic, **+ arch_vc_investor + arch_journalist_curious** |
| **Drift A** | hype↔foundations + enthusiastic↔skeptical for tech-founder | applied-curiosity↔skeptical-respect (framing) + playful↔direct (tone) for tech-founder |
| **Drift B** | postdoc career affinity linear | postdoc strategic-alignment 0.9 → 0.4 across 15 episodes |
| **Profile source** | Synthetic only | **New abstraction `ProfileSource`** — protocol + Synthetic + LinkedIn-RapidAPI (Phase 3) |
| **Frontend** | Lounge mockup (author draft) | `frontend/edra_design_mockup.html` — final VN mockup (1465 lines, ready for verbatim port) |
| **Live mode** | Did not exist | Phase 3: visitor pastes a LinkedIn URL, RapidAPI fetch, profile purge after end-of-session |

## What in the science did NOT change

Architecture and the closed loop are the same. Concretely surviving as-is:
- 6 ORM tables (but `personas` → `profiles`, `offer` → `pitch_strategy` + new `dialogue` column)
- 3 orchestrator asyncio loops (tick / consistency / factory) + `on_new_episode`
- 5 LLM touchpoints (TASK.md §7) — prompt text changes, the inventory stays
- HDBSCAN on 384-dim MiniLM, n_min=5, θ_induce=0.6, CS window
- SSE split POST `/rules/{id}/revise` + GET `/reflections/stream/{id}`
- Hybrid rule with static + dynamic slots
- Acceptance checklist almost identical (new items — protocol-conformance test and privacy-purge test)

## What in the skeleton survives

From the 2026-04-21 artifacts, surviving the pivot:
- `backend/llm/client.py` — unchanged (httpx, local/remote, streaming)
- `backend/orchestrator.py` — class structure, loops, exception resilience (logic inside `_pick_rule_for_persona` becomes `_pick_rule_for_profile`, the implementation was a stub anyway)
- `backend/db.py` — engine/session, unchanged
- `backend/config.py` — `RAPIDAPI_KEY`, `LIVE_MODE` to be added
- `backend/clustering/cluster.py` — HDBSCAN stays
- `backend/induction/induce.py` — scaffold stays, the prompt and slot vocabulary change
- `backend/monitor/consistency.py` — CS formula stays
- `backend/reflection/revise.py` — scaffold stays
- `backend/factory/factory.py` — scaffold stays
- `seeded_run.yaml` — needs updating to the new archetypes and drift semantics
- Test scaffold (`tests/test_orchestrator.py`) — unchanged shape

## What we throw away wholesale

- `backend/schemas.py` — 80% rewrite (Persona→Profile, Offer→PitchStrategy, new TONE/FRAMING/OPENER_TYPE/WORD_TARGET/ASK_SIZE literals, DialogueStep, updated Episode)
- `backend/memory/models.py` — same tables, but columns and semantics change (PersonaRow→ProfileRow, new fields `source_kind`, `source_identifier`, `recent_signals`, `ttl_seconds`, `dialogue` JSON in episodes, etc.)
- `backend/simulator/preferences.py` — entirely new matrix: 6 personas × 6 framings × 5 tones × 5 opener_types × 3 word_targets × 5 ask_sizes (= 11250 cells in theory, but the affinities are factorised and stored as 5 dicts + combo_bonuses, not as a dense tensor)
- `backend/simulator/drift.py` — both functions rewritten against the new fields
- `backend/llm/prompts/*.txt` — all 5 prompts rewritten in research-outreach vocabulary with §4.3 tags
- `backend/data/archetypes.yaml` — NEW file, did not exist; will hold 6+2 archetypes with full Profile + preferences
- `frontend/index.html`, `frontend/styles.css`, `frontend/app.js` — drop, port `edra_design_mockup.html` wholesale
- `tests/test_preferences.py` — invariant stays (unique top combos), implementation against the new slots

## What we build fresh

- `backend/profile_source/__init__.py` — `ProfileSource` Protocol + `ProfileNotFound`, `ProfileSourceUnavailable` exceptions
- `backend/profile_source/synthetic.py` — `SyntheticProfileSource` reads `archetypes.yaml`, instant-fetch by archetype id
- `backend/profile_source/linkedin_rapidapi.py` — Phase 3, `LinkedInRapidAPISource` via RapidAPI, retry+timeout, profile purge hook
- `backend/pitch/` — new module: `generate_turn(profile, dialogue_history, applicable_rule | None) -> DialogueStep`. Static rules without LLM, hybrid rules → `fill_dynamic_slot()`, no rule → improvise via LLM with a few-shot from cluster episodes
- `backend/routers/sessions.py` — `POST /sessions/start`, `POST /sessions/{id}/turn`, `POST /sessions/{id}/end`. Stateful session store in-memory + persist on end
- `tests/test_profile_source.py` — protocol conformance + import-graph test (no core module imports linkedin_rapidapi)

## Archived mockup filenames

`TASK.md` references `edra_pitch_mockup.html` in §1.3, §1.4, §10. The actual file in the repo is `frontend/edra_design_mockup.html`. This is a rename by the author — **we use the one in the repo**. The version from the `2026-04-21 session note` (`edra_lounge_mockup.html`) is no longer current.

## Risk areas / what to watch

1. **5-slot PitchStrategy → 11250 theoretical combos**. Do not build a dense numpy tensor. Store the affinities as 5 dicts (one per slot) + sparse combo_bonuses. See the §5.2 formula — strictly factorised sum.
2. **TASK.md §14 import-graph test** — this is a new acceptance check that isolates `profile_source/linkedin_rapidapi.py` from core. Do not skip it.
3. **Live-mode privacy purge** — `tests/test_privacy_purge.py` checks that no PII for `source_kind != "synthetic"` older than 1 hour is left in SQLite.
4. **The VN mockup has hover-out edge handles on three sides**. This is not a small thing — three hidden panels (top/left/right) — extensive markup plus CSS `transform: translateX(...)` with triggers. Copy styles from `edra_design_mockup.html` verbatim, do not rewrite.
5. **Multi-turn dialogue** — an episode used to be 1 step (offer→outcome), now it is 3-7 steps. SSE streaming of the dialogue **is not** in TASK.md §7 — the dialogue uses ordinary HTTP calls `/sessions/{id}/turn`. SSE is only for reflection (§7).
6. **Anime PNG agent** — production asset, not a blocker for Phase 1. The mockup has a `.agent-slot-placeholder` fallback — keep it, plug in images in Phase 3.

## Next session — entry points

1. Rewrite `backend/schemas.py` against §4.1-4.7 → new literals and DialogueStep, multi-turn Episode
2. Replace `memory/models.py` ORM columns (Persona→Profile, Offer→PitchStrategy)
3. Create `backend/profile_source/` with Protocol + SyntheticProfileSource
4. Create `backend/data/archetypes.yaml` — 6 default + 2 spawnable
5. Rewrite `backend/simulator/preferences.py` — 5 affinity dicts + combo_bonuses
6. Rewrite the 5 prompts in `backend/llm/prompts/` — research-outreach vocab
7. Create `backend/pitch/` module for turn generation
8. Create `backend/routers/sessions.py` for the multi-turn API
9. Port `frontend/edra_design_mockup.html` → `index.html` + `styles.css` + `app.js` with polling and SSE
10. Run `make demo` — the 5-minute scenario (TASK.md §9) unfolds on the new vocab

See [[../00-home/current priorities]] for the phase breakdown.
