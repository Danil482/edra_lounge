---
tags: [home, priorities, status]
date: 2026-05-20
---

# Current Priorities

Pivot context → [[../sessions/2026-04-28 Re-pivot to VN Pitch Floor, vocabulary swap]]
Session 2026-04-28 (Phase 1B/2/3) → [[../sessions/2026-04-28 Phase 1B-2-3 shipped, live-mode booth wired]]
Session 2026-04-29 (Phase 4.1-4.4) → [[../sessions/2026-04-29 Phase 4.1-4.4 shipped, OpenAI live-mode validated]]
Session 2026-04-30 (Phase 5 prep) → [[../sessions/2026-04-30 Phase 5 prep — prompt audit + Defy fact research]]
Session 2026-05-13 (Phase 6 dataset) → [[../sessions/2026-05-13 Phase 6 — research profiles dataset 253 to 502]]
Session 2026-05-13 (vault + clustering) → [[../sessions/2026-05-13 Vault restructure and KNN clustering task]]
Session 2026-05-14 (outreach module) → [[../sessions/2026-05-14 Outreach module and orchestrator workflow]]
Session 2026-05-14 (demo paper) → [[../sessions/2026-05-14 Demo paper rewrite and email enrichment]]
Session 2026-05-15 (frontend polish) → [[../sessions/2026-05-15 Frontend polish and evaluation discussion]]
Session 2026-05-18 (Phase 8 + Lemlist) → [[../sessions/2026-05-18 Phase 8 frontend overhaul and Lemlist decision]]
Session 2026-05-19 (Avatar regen + Phase 5 prompts) → [[../sessions/2026-05-19 Avatar regen Phase 5 prompts and clustering fix]]
Session 2026-05-20 (Demo paper + live clustering) → [[../sessions/2026-05-20 Demo paper rewrite and live clustering]]
Session 2026-05-20 (Evaluation methodology) → [[../sessions/2026-05-20 Evaluation methodology discussion with supervisor]]

The 2026-04-21 skeleton was built for a café metaphor. After the 2026-04-28 pivot we drove through Phase 1B → 2 → 3 in a single session (booth ready in synthetic + live-mock). On 2026-04-29 we shipped Phase 4.1 → 4.4 in one session: new RapidAPI provider after two sunset events, OpenAI as a third LLM mode, rewritten prompts to match the 3-button UX, LLM-driven continuations with full history, visible logging, avatar plumbing. **Booth is fully functional with real LinkedIn fetch + OpenAI generation, 71/71 tests green, end-to-end session validated against the author's real profile.** On 2026-04-30 we ran an analytical session: prompt audit, research on the real Defy, discovered an architectural mismatch (EDRA vocab vs Defy ICP), drafted a founder questionnaire. On 2026-05-13 we expanded `research_profiles_master.csv` from 253 → 502 verified rows as the candidate pool for Phase 5 outreach testing. On 2026-05-14 (AM) we built the outreach module through Phase O.2: CSV-to-Profile mapper, state machine, episode builder, message generation via GPT-4o-mini, Resend email integration, full CLI pipeline. **First real test emails sent and delivered via Resend. 139 tests green.** Also established an orchestrator workflow with 4 specialized agents, created Farseev academic writing skill, prepared presentation speech notes. On 2026-05-14 (PM) we rewrote `edra_demo.tex` for MM '26 demo track (2-page limit), fixed the clustering description (profiles not episodes), verified novelty claim against 25+ systems (narrowed to cluster-conditional adaptation), enriched 502-profile dataset with 64 public emails, and installed the humanizer anti-AI-slop skill. On 2026-05-15 we installed the UI/UX Pro Max skill suite (7 skills), audited the frontend against Defy brand guidelines, and shipped three visual polish items: editorial idle hero screen, gauge terminal-state animations, and smooth panel transitions. Also discussed evaluation methodology for the demo paper (decision deferred) and banked a cluster visualization idea. On 2026-05-18 we shipped Phase 8 — eight frontend overhaul commits (dynamic response buttons, cluster visualization, email auth gate, end-of-dialog popup, avatar integration, 12-state avatar emotion system with crossfade, speech bubble dialog mode), decided to switch outreach delivery from Resend to Lemlist, designed multi-batch EDRA outreach architecture with factorial seed + control groups. Full E2E verification: auth -> session -> 6 turns -> acceptance. **204 tests green, 0 regressions.** On 2026-05-19 we regenerated all 12 avatar PNGs via a chroma key pipeline (`scripts/chromakey_avatars.py`), overhauled avatar CSS (aspect ratio, positioning, removed blend mode), made speech bubble the default dialog mode, lowered clustering `n_min` from 5 to 3 so rules appear in early demos, and implemented Phase 5.1-5.3: lab fact sheet from 5 papers, ~450-word system prompt with anti-hallucination boundaries, 6-category response rotation, refusal rules, rewritten opener/continuation prompts and templates. Also extracted 10 Farseev publications from Google Scholar and started Lemlist warm-up on user's own account (ready ~2026-05-26). **206 tests green.** On 2026-05-20 we rewrote the demo paper Section 3 as dual-modality validation (booth primary + 502-profile longitudinal), ran humanizer pass, implemented KNN classification for live profiles (K=7 weighted cosine vote), created `seed_demo.py` for pre-populated demos with top-strategy rules, cached MiniLM locally, and polished the rulebook UI (slot-grid layout, archetype labels in legend/profile). Evaluated 4 HuggingFace datasets for validation — none suitable. **206 tests green.**
On 2026-05-20 (PM session) we had a methodology discussion with the PhD supervisor about evaluation. Key outcome: no existing dataset fits EDRA (expected for novel work), the correct evaluation protocol is prequential (test-then-train) from online learning, and EDRA maps to contextual bandit framework. User will request historical outreach data from colleague Philipp. Literature review confirms no published evaluation framework for adaptive closed-loop outreach — this is the gap.

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

## 🟡 Phase 5 — Prompts and scenarios (in progress, 5.1-5.3 done)

After the 2026-04-29 e2e run the priority shifted from "will it work" to "quality and robustness". On 2026-04-30 we audited the prompts — the root cause is not the diversity directive, it is **the absence of concrete Defy facts in the prompts**: the LLM hallucinates facts every turn ("we partnered with major retail brand", "cohort of 20 brands") because the system message contains a single line — "You are a research-liaison agent." — and nothing else. The diversity issue is a consequence: without facts, the LLM picks the single safe trajectory (enterprise sales credentials × N).

### 🚨 Architectural mismatch — Path A/B/C (decision deferred until founders reply)

The real Defy = **AI-SaaS for creative agencies** (3 products: Monitor / Automate / Report; founders Ian Cassidy + Alek Farseev), while the current EDRA vocabulary assumes **academic outreach** (PhD / postdoc / prof archetypes, ASK_SIZE=`co-author`/`intro`/`trial`).

- **Path A**: rewrite archetypes around an agency ICP — breaks the preference matrix, drift events, and tests
- **Path B**: keep the research narrative as a booth-only wrapper — but at the booth, mismatch with the real DEFY.group on LinkedIn is uncomfortable; skeptical-defusing impossible without making things up
- **Path C (recommended)**: hybrid — research archetypes remain in synthetic mode, but prompts are rewritten on real Defy facts, refusal behaviour handles edge cases when a visitor is clearly out of ICP

### ✅ Phase 5.1 — Lab fact sheet (done, 2026-05-19)

Unblocked by analyzing 5 lab papers instead of waiting for founder questionnaire — see [[../knowledge/decisions/Prompt improvement plan based on lab papers]]. Created `_lab_facts.txt` with concrete facts extracted from publications. Loaded into prompts via `generate.py`.

### ✅ Phase 5.2 — Refactor opener/continuation prompts (done, 2026-05-19)

System prompt expanded to ~450 words (`_system.txt`) with brand voice, role, anti-hallucination boundaries, refusal rules. 6 response categories implemented with rotation tracking per session. `opener.txt` and `continuation.txt` rewritten to consume fact sheet and system message.

### ✅ Phase 5.3 — Refusal behaviour (done, 2026-05-19)

Refusal rules integrated into `_system.txt`: no-signal profiles get general talk, title-only profiles use hints without attribution, 4+ proceed turns pivot to concrete next step, `ask_size=none` suppresses CTAs.

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

- [x] Templates: rewritten to use real facts from fact sheet (done 2026-05-19)
- [ ] **`*.log` → .gitignore** (uvicorn.log has been untracked since 2026-04-29)

## ✅ Phase 6 — Research profiles dataset (done, 2026-05-13)

See [[../sessions/2026-05-13 Phase 6 — research profiles dataset 253 to 502]].

Expanded `research_profiles_master.csv` from 253 → 502 verified rows across 10 batches. Strict schema (LinkedIn URL required), dedup at two levels, 376 High / 117 Medium / 9 Low confidence. Segment + geographic balance restored (Research share dropped from 56% to 45%, Bay Area from 24% to 21.5%, added Italy / Eastern Europe / LatAm / Turkey coverage that was missing before).

This dataset is the prep substrate for Phase 5 outreach testing — once prompts are rewritten with real Defy facts and category rotation, we have a ready candidate pool for hand-crafted test messages.

Known quality risk: ~10-15 rows have LinkedIn slugs inferred from search snippets (LinkedIn blocks WebFetch behind auth). All flagged Medium/Low confidence — manual eyeball verification recommended before any outreach.

Research profiles files moved to `data/research_profiles/` on 2026-05-13 (were cluttering repo root).

## ✅ Phase O.1 — Outreach foundation (done, 2026-05-14)

CSV-to-Profile mapper (`csv_source.py`), OutreachRow state machine (`state.py`), Episode builder (`episode_builder.py`). 68 tests in `tests/test_outreach.py`. Separate `outreach.db`.

## ✅ Phase O.2 — Message generation + email sending (done, 2026-05-14)

`outreach.txt` prompt (research framing, Farseev lab context), `classify_response.txt` prompt, `generate.py` (GPT-4o-mini), `sender.py` (Resend API), `cli.py` (8 commands). First 3 test emails generated and delivered via Resend to `daniel@defygroup.ai`.

**Blocked**: `defygroup.ai` domain not yet verified in Resend — can only send to account owner's email until DNS records are added.

## ✅ Phase 8 — Frontend overhaul (done, 2026-05-18)

See [[../sessions/2026-05-18 Phase 8 frontend overhaul and Lemlist decision]].

Eight commits shipped, 61 new tests (204 total), 0 regressions. Full E2E verification: auth -> session -> 6 turns -> acceptance.

### 8.1 — Dynamic response buttons
LLM generates 3 contextual response options per turn (ResponseOption schema, JSON prompts, robust parser with fallback to static options).

### 8.2 — Cluster visualization
`GET /api/cluster-viz` endpoint with t-SNE 2D projection, KNN neighbors, archetype labels. Canvas API scatter plot in frontend.

### 8.3 — Email auth gate
VisitorRow table, `POST /api/visitors` with email validation/upsert, frontend auth overlay before session start.

### 8.4 — End-of-dialog popup
Success ("Collaboration Initiated") / failure ("Until Next Time") variants with appropriate messaging.

### 8.5 — Avatar integration
`edra-idle.jpg` connected, fade-in animation, `data-emotion` attribute on avatar element, emotion state map designed (12 states). Full avatar set stored at `frontend/assets/avatar/`.

### 8.6 — Avatar emotion system
12 PNG emotion states generated and wired. Crossfade transitions between states. Background normalized to `#0A0A0A`. 3 images regenerated for visual consistency (hair length).

### 8.7 — Speech bubble dialog mode + fixes
Agent text renders in speech bubble anchored to avatar. Avatar `mix-blend-mode` fix for compositing. Cluster visualization UX fix.

## 🟡 Demo paper — edra_demo.tex (in progress, 2026-05-14)

Rewritten for MM '26 demo track (2-page limit, excluding references). Novelty narrowed to cluster-conditional rule adaptation after literature verification (ExpeL, EvolveR, ReasoningBank cited). Architecture diagram generated (`EDRA_workflow.png`). Humanizer pass applied.

- [x] Rewrite to 2 pages with 3 equations and 2 figures
- [x] Fix clustering description (profiles, not episodes)
- [x] Novelty verification: 25+ systems checked, claim narrowed
- [x] Add ExpeL, EvolveR, ReasoningBank to positioning
- [x] Architecture diagram generated and inserted
- [x] Figure cross-references added (Fig 1 architecture, Fig 2 booth UI)
- [x] Booth UI screenshot inserted (edra\_UI.png replaces placeholder)
- [x] Section 3 rewritten: dual-modality validation (booth primary + 502-profile longitudinal arm)
- [x] Abstract and conclusion updated for channel-agnostic framing
- [x] Humanizer pass: removed AI writing patterns (promotional qualifiers, passive clusters, em-dash parentheticals)
- [x] Removed unpublished doctoral citation
- [ ] Compile in Overleaf — verify 2-page fit
- [ ] Fill in real author names for EvolveR and ReasoningBank bib entries
- [ ] Create supplementary slides (10 max) or video (5 min max)

## 🟡 Evaluation methodology (in progress, 2026-05-20)

Three-level evaluation framework designed:

### Level 1 — Clustering quality (can start now)
- [ ] Silhouette score on 502-profile embeddings
- [ ] Human evaluation: 3 annotators label archetype coherence, inter-rater agreement

### Level 2 — Cluster-conditional rules vs. baselines (needs data)
- [ ] Off-policy evaluation using Philipp's historical outreach data (replay method, Li et al. WSDM 2011)
- [ ] Baselines: no-personalization, random strategy, static rules (no adaptation), ExpeL-style (no clustering)
- [ ] Metric: response rate (replied / not replied)

### Level 3 — Adaptive learning curve (needs own outreach data)
- [ ] Prequential evaluation over outreach batches (Gama et al. 2013)
- [ ] Learning curve: response rate per batch, EDRA-guided vs. control group
- [ ] Cumulative regret analysis (contextual bandit framing)

### Reading list
- [x] Compiled 6 key papers (2026-05-20)
- [ ] Read Li et al. WSDM 2011 — offline bandit evaluation (replay method)
- [ ] Read Gama et al. 2013 — prequential evaluation protocol
- [ ] Read ExpeL (Zhao et al. AAAI 2024) — Section 4 evaluation, competitor positioning
- [ ] Read LinUCB (Li et al. WWW 2010) — contextual bandit formalism
- [ ] Read Doubly Robust (Dudik et al. ICML 2011) — off-policy evaluation
- [ ] Read Karanam et al. 2025 — literature review, gap confirmation

### Depends on
- Philipp's historical outreach data (requested, pending)
- Own outreach campaign data (blocked on Lemlist warm-up ~2026-05-26)

## 🟡 Email enrichment (Lemlist integration, 2026-05-18)

65 existing emails from web-search (17% hit rate from 375 High-confidence profiles). Switching to Lemlist Email Finder for remaining profiles.

- [x] Web-search enrichment of High-confidence profiles (64 found, 311 not_found)
- [x] Prepared Lemlist enrichment batches: `lemlist_enrichment_priority.csv` (40 profiles, 200 credits) + `lemlist_enrichment_batch.csv` (437 profiles)
- [ ] Run Lemlist Email Finder on priority batch (40 academic profiles)
- [ ] Review found emails for accuracy
- [ ] ~~Investigate founders' warmed Lemlist account~~ — warm-up started on user's own account (2026-05-19), ready ~2026-05-26
- [ ] Select 20 profiles for first outreach batch (factorial design) — can proceed once warm-up completes

## 🟡 Phase O.3 — CLI workflow + ingest (next)

- [ ] `ingest.py` — batch ingestion into EDRA (recluster + induce with outreach-specific thresholds)
- [ ] CLI refinements: segment balancing in `prepare`, iteration reporting
- [ ] Rewrite `sender.py` for Lemlist API (decision: Lemlist replaces Resend — see [[../knowledge/decisions/Lemlist replaces Resend for outreach delivery]])
- [ ] First real outreach batch (20 High-confidence profiles with verified emails, factorial design)
- [ ] ~~Investigate founders' warmed Lemlist account~~ — warm-up started on user's own account (2026-05-19, ready ~2026-05-26)

## 🟡 Phase 7 — Outreach data collection module (planned, 2026-05-13)

Design document: `papers/OUTREACH_MODULE_DESIGN.md`

CLI-driven module (`backend/outreach/`) that automates real first-contact outreach to researchers from the 502-row dataset, collects responses, and feeds single-stage episodes into EDRA to induce and iteratively revise rules from real-world evidence.

### Key decisions (2026-05-13)
- **Automated sending** via email (SendGrid/Mailgun API). LinkedIn DM automation violates ToS and conflicts with IRB requirements for a research study.
- **Research study framing** — may need IRB approval. Email with proper disclosure is the clean path.
- **One attempt per person** — no re-contact with different strategy.
- **Separate DB** — outreach episodes go to `outreach.db`, not `edra_lounge.db`. Rule transfer to booth DB is a later manual step.
- **No paid RapidAPI yet** — CSV-only profiles initially, LinkedIn enrichment is optional upgrade.

### Pipeline
```
CSV row → thin Profile (source_kind="csv_research")
  → batch selector (15-20 per iteration, segment-balanced, High confidence)
  → [optional LinkedIn enrichment]
  → strategy assignment (iteration 1: fractional factorial; iteration 2+: EDRA-guided + 20% control)
  → LLM generates outreach message via new outreach.txt template
  → automated email send via API
  → wait 14-21 days for responses
  → classify responses (rule-based auto + LLM-assisted for text replies)
  → create Episode (fits existing schema: 1-2 DialogueSteps, day=iteration number)
  → batch ingest into EDRA (recluster + induce once per batch)
```

### Outreach-specific thresholds
- `theta_induce=0.25` (not 0.6) — cold outreach response rates are 5-30%
- `exploring` counts as success (connection accepted / clarifying questions)
- `n_min=8` for outreach clusters

### Response classification mapping
| Signal | EDRA outcome | final_interest |
|---|---|---|
| Reply with interest | `accepted` | +4 |
| Clarifying questions | `exploring` | +2 |
| Connection accepted, no reply (14d) | `exploring` | +1 |
| Polite decline | `rejected` | -3 |
| Ignored (21d) | `abandoned` | -1 |

### Timeline estimate
- 3-4 batches (60-80 episodes) before meaningful clusters and first rules
- 6-8 batches over 6-8 weeks = 90-160 total outreach attempts
- Iteration 1-2: pure data collection (factorial design)
- Iteration 3+: EDRA feedback guides strategy selection

### Implementation phases
- [ ] **O.1** — CSV-to-Profile mapper, OutreachRow state table, Episode builder
- [ ] **O.2** — `outreach.txt` + `classify_response.txt` templates, message generation, strategy planner
- [ ] **O.3** — CLI workflow (prepare, review, send, record-response, classify, ingest)
- [ ] **O.4** — Email sending integration (SendGrid/Mailgun), LinkedIn enrichment, iteration metrics + reporting
- [ ] **O.5** — First real batch (20 profiles, High confidence, segment-balanced)

### Open questions (still need answers)
- [x] ~~Email discovery service~~ — web search yielded 64 emails (17% hit rate). Hunter.io/Apollo.io still an option for remaining ~440 profiles.
- [x] ~~Which email sending service?~~ — Resend (decided 2026-05-14)
- [ ] IRB — does Kazan Federal University require IRB review for this type of study?
- [ ] Should outreach results be visible in the booth demo frontend, or strictly separate?

### Depends on
- Phase 6 dataset (done)
- Email discovery solution (partial — 64 emails found 2026-05-14)
- IRB decision (not started)
- Paid RapidAPI plan decision (deferred)

## 🔒 Open questions for founders (questionnaire 2026-04-30, in English)

1. **Anonymized case examples** — 2-3 short anonymized client examples ("top-20 UK agency used Monitor for 6 weeks before a pitch...") for booth use
2. **Permission to cite founder credentials** — public OK to mention Ian's SHARE Creative / Samy / 50+ relationships and Alek's Singapore AI prof background?
3. **Out-of-scope** — 3-5 explicit boundaries (not recruiting? not consulting hours? not data licensing? not for in-house brand teams?)
4. **Engagement format & next-step shape** — demo → trial → paid pilot? Pilot length, cadence, deliverables? When the agent says "let's talk pilot", what is the literal next step?
5. **Booth ICP & lead product** — agency founders/MDs/planners/CDs/mixed? Which of Monitor/Automate/Report is the lead product to open with?
6. **Conferences / shared-context anchors** — which events does Defy attend/sponsor (Cannes, SXSW, agency circle)?
7. **Lemlist account sharing** — can we use your warmed Lemlist domain/account for the first outreach batch? This skips 3-4 weeks of domain warm-up (critical for June 11 deadline)

## 🟢 UI polish (not blocked, can run in parallel with Phase 5.x)

- [ ] **Avatar caching strategy** — signed URLs from LinkedIn live ~3 months and then 404. Cache currently keeps URL forever. Parse the `e=` query param and invalidate cache at expiry, or proxy avatars via a `/avatar/<profile_id>` endpoint
- [x] **`cluster_id: —` for live** — KNN classification for live profiles implemented (2026-05-20): K=7 weighted cosine vote over seeded profiles
- [x] **Idle screen** — editorial hero with Defy Research eyebrow, 44px headline, rotating archetype descriptions (done 2026-05-15)
- [x] **Dynamic response buttons** — LLM generates 3 contextual options per turn (done 2026-05-18, Phase 8.1)
- [x] **Cluster visualization** — t-SNE 2D scatter plot with KNN neighbors and archetype labels (done 2026-05-18, Phase 8.2)
- [x] **Email auth gate** — visitor email collection before session start (done 2026-05-18, Phase 8.3)
- [x] **End-of-dialog popup** — success/failure variants (done 2026-05-18, Phase 8.4)
- [x] **Avatar integration** — Edra character connected with fade-in animation and emotion state map (done 2026-05-18, Phase 8.5)
- [ ] **Choice buttons after terminate** — currently still enabled, user can click → 409. Disable when `current_session.dialogue.last.visitor_choice` is non-null AND terminated
- [ ] **Welcome message before pitch** — agent introduces itself and explains who it is before diving into personalized pitch. First turn should be a greeting, not a sales opener.
- [ ] **Accept / Decline buttons** — two explicit buttons: "Accept" (instantly sets interest=+5, triggers success popup) and "Decline" (sets interest=-5, triggers failure popup). Gives the user agency to end the conversation at any point with a clear decision.
- [ ] **Agent gives up too early** — after a few negative turns the agent terminates instead of trying a different approach. The agent should persist with alternative proposals rather than surrendering. Only terminate via the explicit Decline button or after MAX_TURNS.
- [x] **Speech bubble dialog mode** — agent text in speech bubble, avatar mix-blend-mode fix (done 2026-05-18, Phase 8.7)
- [x] **Emotion avatar variants** — all 12 states generated as PNG, crossfade transitions, BG normalized (done 2026-05-18, Phase 8.6)

### Frontend bugfix
- [ ] **`session ended` → 409 stub** — after terminate the frontend clicks Tell me more → 409 in console. Does not break UX but is noisy. Fix in `applyChoices`: if the last step has visitor_choice and interest is at the limit — disable buttons

### Clustering refactor — KNN-based profile clustering
- [ ] **TASK_refactor_clustering.md rewritten 2026-05-13** — new approach: cluster LinkedIn profile summaries (not episode summaries) with HDBSCAN, apply rules via KNN vote (K=7 nearest profiles, weighted by similarity). Pipeline: LinkedIn JSON → text summary → MiniLM embedding → HDBSCAN → KNN rule lookup. Ready for implementation — not blocked on founders.

## 💡 Ideas bank

- [x] **Cluster visualization + visitor feedback** — implemented in Phase 8.2 (2026-05-18): `GET /api/cluster-viz` with t-SNE 2D projection, KNN neighbors, archetype labels, Canvas API scatter plot. Remaining: standalone shareable page, outreach follow-up use case.

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
- [x] pytest passes (206/206, updated 2026-05-19)

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
