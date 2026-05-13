---
tags: [session, phase-1b, phase-2, phase-3, live-mode, linkedin, privacy-purge, ui-fixes]
date: 2026-04-28
---

# 2026-04-28 Phase 1B → 2 → 3 shipped, live-mode booth wired

After the pivot to VN Pitch Floor (see [[2026-04-28 Re-pivot to VN Pitch Floor, vocabulary swap]]) we drove through all three remaining phases in one session. The booth is now fully functional in both synthetic and live modes; the LLM (Ollama) is not installed yet — fallback paths catch `httpx.ConnectError/ConnectTimeout/ReadTimeout` in a single line and continue the demo.

## What was done

### Phase 1B — Multi-turn pitch sessions
- `backend/pitch/` — `generate.py` (3 paths: static / hybrid / improvise), `templates.py` (deterministic openers + continuations keyed by tone × visitor_choice), `strategy.py` (DEFAULT_IMPROVISED_STRATEGY = peer-collaboration/warm/reference-to-signal/medium/chat), `classify.py` (synthetic = archetype_id, `lookup_applicable_rule` by latest active)
- `backend/sessions/lifecycle.py` — `start_session` / `take_turn` / `end_session`, ±5 termination, MAX_TURNS=7, `_summarise` with offline fallback
- `backend/sessions/store.py` — process-local Session dict + active-session pointer
- `backend/routers/sessions.py` — `POST /sessions/start | /turn | /end`, sets `orch.live_session_active`
- Orchestrator wiring — `_try_induce_all` (LLM or mode-of-slots fallback), `_check_all_rule_cs` creates a pending Revision (LLM stream lazy via SSE endpoint), `_evaluate_factory` spawns an Agent for an uncovered cluster, `on_new_episode` hook re-clusters and tries induction
- Cluster.size = `len(episodes)`, **not** distinct profile_ids — synthetic mode runs one archetype many times, distinct would stay at 1 and induction would never trigger
- Fallback induction: mode-of-slots across accepted episodes (or all of them if accepted=0) — bootstraps a static rule without LLM
- Tests: 48 → 62

### Phase 2 — Frontend port (Defy Brand V2.0)
- Copied the v3 mockup `edra_pitch_mockup.html` verbatim into `styles.css` (1217 lines CSS) + `index.html` (data-binding skeleton)
- `frontend/app.js` ≈ 340 LOC: poll every 1000ms, typewriter ~30 cps, gauge with `.cell-on/-warm/-hot` by sign and magnitude, hover-out edge panels, choice buttons, operator buttons, reflection console via `EventSource`
- Brand: Playfair Display + DM Sans, palette `#0A0A0A` / `#F9F9F7` / `#F3F1EC` / `#CC0000`, 50/40/10 ratio, no rounded corners / shadows / decorative gradients

### Phase 3 — Live LinkedIn mode + privacy purge + fallback
- `LinkedInRapidAPISource` — real httpx fetch against `fresh-linkedin-profile-data.p.rapidapi.com` with status-aware error mapping: 404 → `ProfileNotFound`, 429/5xx/network → `ProfileSourceUnavailable`. JSON → Profile mapping (full_name, role, domain, seniority heuristic from title + years, recent_signals from posts capped at 3 strings)
- `RAPIDAPI_KEY=mock` sentinel — without a real key (no HTTP request) returns a hand-crafted profile for the author (Danil Onishchenko, headline + 3 posts). Used for booth demo without a RapidAPI subscription
- `purge_expired_live_profiles` in `backend/memory/store.py` — non-synthetic ProfileRow rows are deleted after `now - fetched_at >= ttl_seconds` (default 3600 for live). Runs from the factory loop every 30s. Synthetic rows untouchable
- Wi-Fi fallback — `GET /sessions/sources` returns the active source kind + full list of synthetic archetypes. On 503 from `/sessions/start`, the frontend opens a dialog with an archetype dropdown
- The orchestrator tick loop is now a no-op in live mode (the booth waits for real visitors via HTTP, not auto-playing synthetic). In synthetic mode the self-playing demo continues as before
- Makefile: `make reset` (rm db + reseed <5s), `make booth` (reset → uvicorn → poll /health → kiosk Chrome)
- Tests: 14 new ones (LinkedIn mocked-httpx success/404/429/5xx/network/malformed + mock-key bypass + seniority heuristic + 6 privacy-purge cases)

### UI iteration after the first run
- **Live form was originally** a persistent bar `top:0` — it intersected with the hover top panel and looked noisy even when no one was starting a live session
- **Textbox / choices overlap** — `.textbox bottom:110px` + `min-height:184` intersected with `.choices bottom:60px height:~80`; the textbox frame ran on top of the button text
- **Fix**: the live form became a modal opened by clicking the operator button `Start Live` (visible only in live mode). Esc closes, Enter confirms. Choices raised to `bottom:110px`, textbox to `bottom:220px` — clean stack: gauge [0,92] → choices [110,~190] → textbox [220,…]

## Final state

- 62/62 tests green
- `make demo` starts in synthetic mode without errors (only LLM-offline warnings in one line)
- `LIVE_MODE=true RAPIDAPI_KEY=mock make demo` starts in live mode, the `Start Live` button is visible, the modal opens, `https://www.linkedin.com/in/danil-onishchenko-30876037a/` → the author's mock profile lands in the right panel, opener with a reference to a post lands in the textbox
- 8 commits from Phase 1A to UI fix

## Open questions / next steps

See `current priorities.md`. Short form:
1. **Real LinkedIn parsing** — needs a `RAPIDAPI_KEY` and a check that `_map_payload_to_profile` works against a real RapidAPI response. Everything so far runs against the mock payload, no real request has been made yet
2. **Live mode by default** — set `LIVE_MODE=true` as the default in `backend/config.py` (or via `.env.example`), synthetic stays available via `LIVE_MODE=false`
3. **Profile in the right panel** — visually check how mock and real profiles render in the hover-right panel, whether long headlines / signals overflow the frame, and whether `source_kind: linkedin_rapidapi` is shown correctly

## Tech debt

- ~50 places with `datetime.utcnow()` — Python 3.13 removes it, needs a sweep to `datetime.now(UTC)`
- Profile.id for live: `li:https--wwwlinkedincom-in-danil-onishchenko-30876037a` — functionally fine but visually ugly in logs, can be reduced to `li:<vanity-handle>` via regex
- `classify_profile` for live mode returns `None` (cluster_id) because there is no embedding plumbed in; until Phase 4 a live profile lands in the "uncovered" pile and the factory spawns an agent after 30s. Not a blocker for the demo, but the UI shows `cluster_id: —`
- `LIVE_MODE=true` is not yet the default — boots into synthetic, which is the wrong default for booth
