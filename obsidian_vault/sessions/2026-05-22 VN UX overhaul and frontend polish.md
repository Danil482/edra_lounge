---
tags: [session, frontend, ux, prompts, performance, phase-11]
date: 2026-05-22
---

# 2026-05-22 VN UX overhaul and frontend polish

Major UX session — rebuilt the booth interaction flow to feel like a visual novel, with inner monologue mechanic, explicit accept/decline, and a clean welcome-to-session pipeline. Also fixed embedding preload performance and rewrote prompt behavior for negative/skeptical reactions.

## What was done

### Phase 11 — committed as single phase commit

**Backend performance:**
- MiniLM embedding model now preloads at app startup via `preload_embedder()` in lifespan handler — eliminates multi-second freeze on first profile insertion
- `classify_profile()` rewritten with lightweight SQL queries (`profile_cluster_map`, `profiles_with_embeddings`) instead of full-table deserialization

**Explicit session resolution:**
- New `POST /sessions/{id}/resolve` endpoint — accepts `{"decision": "accept"|"decline"}`, sets interest to ±5, terminates session, persists episode
- `resolve_session()` in lifecycle.py handles the full flow including `end_session()` call

**Prompt overhaul:**
- Opener always goes through LLM now (even static-rule path) — response options generated on first turn
- Added `thought` field to LLM JSON output — inner monologue before each reply
- Skeptical = clarifying question, honest about missing info, offer to email details later
- Negative = pivot to different angle, never surrender (Decline button is the explicit exit)

**Frontend — complete UX rebuild:**
- Welcome message with Edra greeting before session start
- Session-start dialog (live-dialog style) with LinkedIn URL input
- Removed: synthetic archetype selector, old live dialog, fallback dialog, Start Live button, panel/bubble toggle
- Bubble chat is now the sole dialog mode
- Accept (green, left) / Decline (red, right) buttons flanking the three choice buttons
- VN thought mechanic: italic thought in grey bubble → pulsing "Click to continue" → reply with typewriter
- Thinking avatar state during LLM wait (`awaitingLLM` flag blocks poll from overriding)
- Smoother avatar crossfade (0.45s CSS transition, matched JS timeout)
- Back to Lobby resets to welcome state (calls `showWelcome()`)
- Generation counter on `bubbleTransition` prevents typewriter race conditions

**Tests:** 204/206 pass (2 pre-existing cluster_viz failures)

## What was NOT done

- Pipedrive extraction not continued (waiting for CRM structure clarification)
- Demo paper Overleaf compile
- Phase 5.4 scenario test harness
- Welcome message for live-mode LinkedIn flow (currently works, but no special handling)

## Key decisions

- **Bubble chat only** — removed panel mode entirely, user preferred bubble
- **No synthetic archetype selector** — session-start dialog only offers LinkedIn URL + demo fallback removed
- **Opener always LLM** — even with static rule, LLM generates opener + response options. Template fallback only on LLM failure
- **Generation counter for typewriter** — solved race condition where two `bubbleTransition` calls would interleave characters via dual setInterval

## Open questions

- [ ] Visitor avatar URL expiry — LinkedIn signed URLs expire after ~3 months. Need cache invalidation strategy or proxy endpoint
- [ ] Pipedrive CRM structure — are deals about email outreach or mixed (calls, WhatsApp, conferences)?
- [ ] PhD dissertation title — preliminary options discussed, needs refinement after evaluation results

## Next session — entry points

1. Pipedrive data decision (pending colleague's answer on CRM structure)
2. Demo paper — compile in Overleaf, verify 2-page fit
3. Phase 5.4 — scenario test harness
4. Frontend: agent gives up too early on repeated negative (MAX_TURNS termination still fires)
5. Welcome message content refinement — current text is generic, could be more on-brand

See [[../00-home/current priorities]] for the full phase board.
