---
tags: [home, priorities, status]
date: 2026-05-13
---

# Current Priorities

Pivot context → [[../sessions/2026-04-28 Re-pivot to VN Pitch Floor, vocabulary swap]]
Session 2026-04-28 (Phase 1B/2/3) → [[../sessions/2026-04-28 Phase 1B-2-3 shipped, live-mode booth wired]]
Session 2026-04-29 (Phase 4.1-4.4) → [[../sessions/2026-04-29 Phase 4.1-4.4 shipped, OpenAI live-mode validated]]
Session 2026-04-30 (Phase 5 prep) → [[../sessions/2026-04-30 Phase 5 prep — prompt audit + Defy fact research]]
Session 2026-05-13 (Phase 6 dataset) → [[../sessions/2026-05-13 Phase 6 — research profiles dataset 253 to 502]]
Session 2026-05-13 (vault + clustering) → [[../sessions/2026-05-13 Vault restructure and KNN clustering task]]

The 2026-04-21 skeleton was built for a café metaphor. After the 2026-04-28 pivot we drove through Phase 1B → 2 → 3 in a single session (booth ready in synthetic + live-mock). On 2026-04-29 we shipped Phase 4.1 → 4.4 in one session: new RapidAPI provider after two sunset events, OpenAI as a third LLM mode, rewritten prompts to match the 3-button UX, LLM-driven continuations with full history, visible logging, avatar plumbing. **Booth is fully functional with real LinkedIn fetch + OpenAI generation, 71/71 tests green, end-to-end session validated against the author's real profile.** On 2026-04-30 we ran an analytical session: prompt audit, research on the real Defy, discovered an architectural mismatch (EDRA vocab vs Defy ICP), drafted a founder questionnaire. On 2026-05-13 we expanded `research_profiles_master.csv` from 253 → 502 verified rows as the candidate pool for Phase 5 outreach testing.

## ✅ Phase 1A — Vocabulary swap (done, 2026-04-28)

See commit `fd5f4d6 Phase 1A — Vocabulary swap to VN Pitch Floor`.

## ✅ Phase 1B — Multi-turn dialogue + sessions API (done, 2026-04-28)

See commit `227e0d4 Phase 1B — Multi-turn pitch sessions, rule pipeline wired`.

## ✅ Phase 2 — VN frontend (done, 2026-04-28)

See commit `3773700 Phase 2 — Frontend port (Defy Brand V2.0)`.

## ✅ Phase 3 — Live mode + booth ready (done, 2026-04-28)

See commit `d6a9525 Phase 3 — Live LinkedIn mode + privacy purge + Wi-Fi fallback` + UI fixes (`bb77896` + `ffd978a`).

## ✅ Phase 4 — Real LinkedIn + OpenAI + production-grade dialog (done, 2026-04-29)

All four subphases plus diagnostic logging:
- `c533f84` Phase 4.1 — 2-endpoint flow + disk cache (linkedin-data-api)
- `fd238c7` Phase 4.2 — OpenAI provider + switch to fresh-linkedin-scraper-api (after two dead providers + parser hardening against real-world payload shape)
- `5eb9970` Phase 4.3 — Opener prompt fits visitor reaction buttons + LinkedIn avatar plumbing
- `d70aeda` Phase 4.4 — LLM-driven continuations + visible logging
- `3491146` + `5ff5ec4` — verbose diagnostic logging for follow-up iterations

End-to-end verification: real author URL → cache hit → OpenAI generates an opener about "competitive pricing" → 5 unique LLM responses → terminate at interest=+5 = `accepted`. Burned ~3 RapidAPI quota units across the entire session.

## 🟡 Phase 5 — Prompts and scenarios (in progress, BLOCKED on founders)

After the 2026-04-29 e2e run the priority shifted from "will it work" to "quality and robustness". On 2026-04-30 we audited the prompts — the root cause is not the diversity directive, it is **the absence of concrete Defy facts in the prompts**: the LLM hallucinates facts every turn ("we partnered with major retail brand", "cohort of 20 brands") because the system message contains a single line — "You are a research-liaison agent." — and nothing else. The diversity issue is a consequence: without facts, the LLM picks the single safe trajectory (enterprise sales credentials × N).

### 🚨 Architectural mismatch — Path A/B/C (decision deferred until founders reply)

The real Defy = **AI-SaaS for creative agencies** (3 products: Monitor / Automate / Report; founders Ian Cassidy + Alek Farseev), while the current EDRA vocabulary assumes **academic outreach** (PhD / postdoc / prof archetypes, ASK_SIZE=`co-author`/`intro`/`trial`).

- **Path A**: rewrite archetypes around an agency ICP — breaks the preference matrix, drift events, and tests
- **Path B**: keep the research narrative as a booth-only wrapper — but at the booth, mismatch with the real DEFY.group on LinkedIn is uncomfortable; skeptical-defusing impossible without making things up
- **Path C (recommended)**: hybrid — research archetypes remain in synthetic mode, but prompts are rewritten on real Defy facts, refusal behaviour handles edge cases when a visitor is clearly out of ICP

### Phase 5.1 — Defy fact sheet 🔒 BLOCKED (highest priority)

Waiting for founders to answer the questionnaire (see below). When the answers arrive:
- [ ] Create `backend/llm/prompts/_defy_brand.txt` with all the facts (positioning, 3 products, founders, proof points, out-of-scope, engagement)
- [ ] Load via `llm.client.render()` as `{defy_facts}`, inject into `opener.txt` + `continuation.txt`
- [ ] Unify casing (`Defy` without `.group`? Or `Defy.group` everywhere?)

### Phase 5.2 — Refactor opener/continuation prompts

- [ ] Expand `system` message to 200-300 words: brand voice + role + boundaries + "do not invent facts not listed in `{defy_facts}`"
- [ ] Remove duplicated button rules from opener/continuation (move into system)
- [ ] Add **response categories** to continuation: `specific-defy-fact` / `methodology-hook` / `profile-callback` / `concrete-next-step` / `soft-personal`
- [ ] Pass `used_categories: list[str]` from Session → LLM is required to pick an unused one (solves diversity via state, not via directive)
- [ ] Return `category` in the continuation result → update Session
- [ ] Pass `word_target` into the continuation prompt (currently lost)

### Phase 5.3 — Refusal behaviour

- [ ] "If the profile has no signals relevant to Defy work — do not force fit. Speak generally."
- [ ] "If the only signal is a job title (not a post) — use as a hint, but do not attribute beliefs/publications to the person."
- [ ] "If visitor has proceeded × 4 — do not offer more credentials. Pivot to a narrow concrete next step."
- [ ] "If ask_size=`none` — no CTAs at all, only a soft door-open."

### Phase 5.4 — Scenario test harness

- [ ] Pytest harness mocking the LLM (or hitting real OpenAI) for:
  - positive×5 (baseline)
  - skeptical → positive → positive (defusing → advance)
  - positive → skeptical → positive (mid-dialog skepticism)
  - negative first turn (immediate close)
  - positive → negative (late close after progress)
  - empty headline / no signals (graceful)
  - mismatched-domain profile
- [ ] Asserts: ≤35 words, no `?` at the end (except rhetorical), mentions Defy ≥1×, no CTA verbs on `negative`, on `skeptical` includes a quote from `{defy_facts}`
- [ ] **Can be started BEFORE 5.1 unblocks** to lock in a baseline and catch regressions from the 5.2 refactor

### Phase 5.5 — Minor cleanup

- [ ] Templates: rewrite to also consume `_defy_brand.txt` (the fallback must not diverge from the LLM)
- [ ] **`*.log` → .gitignore** (uvicorn.log has been untracked since 2026-04-29)

## ✅ Phase 6 — Research profiles dataset (done, 2026-05-13)

See [[../sessions/2026-05-13 Phase 6 — research profiles dataset 253 to 502]].

Expanded `research_profiles_master.csv` from 253 → 502 verified rows across 10 batches. Strict schema (LinkedIn URL required), dedup at two levels, 376 High / 117 Medium / 9 Low confidence. Segment + geographic balance restored (Research share dropped from 56% to 45%, Bay Area from 24% to 21.5%, added Italy / Eastern Europe / LatAm / Turkey coverage that was missing before).

This dataset is the prep substrate for Phase 5 outreach testing — once prompts are rewritten with real Defy facts and category rotation, we have a ready candidate pool for hand-crafted test messages.

Known quality risk: ~10-15 rows have LinkedIn slugs inferred from search snippets (LinkedIn blocks WebFetch behind auth). All flagged Medium/Low confidence — manual eyeball verification recommended before any outreach.

Research profiles files moved to `data/research_profiles/` on 2026-05-13 (were cluttering repo root).

## 🔒 Open questions for founders (questionnaire 2026-04-30, in English)

1. **Anonymized case examples** — 2-3 short anonymized client examples ("top-20 UK agency used Monitor for 6 weeks before a pitch...") for booth use
2. **Permission to cite founder credentials** — public OK to mention Ian's SHARE Creative / Samy / 50+ relationships and Alek's Singapore AI prof background?
3. **Out-of-scope** — 3-5 explicit boundaries (not recruiting? not consulting hours? not data licensing? not for in-house brand teams?)
4. **Engagement format & next-step shape** — demo → trial → paid pilot? Pilot length, cadence, deliverables? When the agent says "let's talk pilot", what is the literal next step?
5. **Booth ICP & lead product** — agency founders/MDs/planners/CDs/mixed? Which of Monitor/Automate/Report is the lead product to open with?
6. **Conferences / shared-context anchors** — which events does Defy attend/sponsor (Cannes, SXSW, agency circle)?

## 🟢 UI polish (not blocked, can run in parallel with Phase 5.x)

- [ ] **Avatar caching strategy** — signed URLs from LinkedIn live ~3 months and then 404. Cache currently keeps URL forever. Parse the `e=` query param and invalidate cache at expiry, or proxy avatars via a `/avatar/<profile_id>` endpoint
- [ ] **`cluster_id: —` for live** — live profiles are not classified, so the right panel always shows `—`. Either hide the field in live mode, or implement live classification
- [ ] **Idle screen** — what is shown when there is no active session? Current fallback is functional but boring. Maybe a small carousel of synthetic archetypes: "next visitor could be..."
- [ ] **Choice buttons after terminate** — currently still enabled, user can click → 409. Disable when `current_session.dialogue.last.visitor_choice` is non-null AND terminated

### Frontend bugfix
- [ ] **`session ended` → 409 stub** — after terminate the frontend clicks Tell me more → 409 in console. Does not break UX but is noisy. Fix in `applyChoices`: if the last step has visitor_choice and interest is at the limit — disable buttons

### Clustering refactor — KNN-based profile clustering
- [ ] **TASK_refactor_clustering.md rewritten 2026-05-13** — new approach: cluster LinkedIn profile summaries (not episode summaries) with HDBSCAN, apply rules via KNN vote (K=7 nearest profiles, weighted by similarity). Pipeline: LinkedIn JSON → text summary → MiniLM embedding → HDBSCAN → KNN rule lookup. Ready for implementation — not blocked on founders.

## Tech debt

- [ ] **`datetime.utcnow()` deprecation** — ~50 places in code. Sweep to `datetime.now(UTC)`
- [ ] **SQLAlchemy DateTime UTC migration** — coupled with the previous item
- [x] **`Profile.id` for live = `li:<vanity-handle>`** — done in Phase 4.2 (`_username_from_input` normalises, slug-fallback only if the handle does not parse)
- [ ] **`*.log` → .gitignore** — `uvicorn.log` from the tee experiment has been untracked since 2026-04-29

## Acceptance gates (TASK.md §14, status)

- [x] `make demo` <30s
- [x] UI === mockup (Defy Brand V2.0)
- [x] 5-minute scenario §9 unfolds on seed=42
- [x] AI Bubble Pops → CS drop → revision <60s
- [x] +Segment → factory spawn ≤3 episodes
- [x] Expert View toggle works
- [x] LLM_MODE=local + LIVE_MODE=false → no network calls
- [x] `make reset` reproduces the same trajectory
- [x] 5+ prompts documented (`opener.txt`, `continuation.txt`, `induce.txt`, `cluster_label.txt`, `reflect.txt`, `summary.txt`)
- [x] Loops survive in-loop exceptions
- [x] **import-graph test**
- [x] **live LinkedIn URL → 5-turn dialogue** ✅ end-to-end validated 2026-04-29 against a real profile
- [x] **privacy-purge test**
- [x] pytest passes (71/71)

## What we are dropping — final archive list

From 2026-04-21:
- ~~7 Pydantic models under café vocabulary~~
- ~~Preference matrix 6×6×5×4 (dense tensor)~~
- ~~Frontend stubs~~
- ~~Lounge mockup~~

From 2026-04-28:
- ~~Single-endpoint RapidAPI provider (`fresh-linkedin-profile-data`)~~ — replaced in Phase 4.1, then again in 4.2
- ~~`linkedin-data-api.p.rapidapi.com`~~ — sunset by the provider 2026-04-29

From 2026-04-29:
- ~~Static template-based continuations~~ — replaced with LLM-driven with history (Phase 4.4); templates remain only as offline fallback
- ~~`LLM_MODE` limited to two values (`local`/`remote`)~~ — extended to `local`/`remote`/`openai`

What survived: `llm/client.py` (extended to a third provider), `db.py` (+migration), `config.py` (+OpenAI fields), the entire test scaffold, the CS formula, the HDBSCAN pipeline, the 3-loop orchestrator, the 6 ORM tables.
