---
tags: [session, frontend, phase-8, outreach, lemlist, avatar]
date: 2026-05-18
---

# 2026-05-18 Phase 8 frontend overhaul and Lemlist decision

Shipped eight frontend features (Phase 8.1-8.7), decided to switch outreach delivery from Resend to Lemlist, designed multi-batch EDRA outreach architecture, generated the Edra anime avatar with 12 emotion states. Full E2E verification: auth → session → 6 turns → acceptance.

## What was done

### Lemlist research and outreach decisions
1. Researched Lemlist as replacement for Resend: API, pricing ($69-79/mo Email Pro), credits (200 free = 40 email lookups), Lemwarm warm-up.
2. Decided to switch outreach delivery from Resend to Lemlist. See [[../knowledge/decisions/Lemlist replaces Resend for outreach delivery]].
3. Prepared enrichment batches: `lemlist_enrichment_priority.csv` (40 profiles) + `lemlist_enrichment_batch.csv` (437 profiles).
4. Open: investigating whether founders' warmed Lemlist account can be used (skips 3-4 week warm-up).

### Outreach architecture — multi-batch EDRA feedback loop
5. Identified core problem: sending k emails without feedback loop = just LLM outreach, not EDRA.
6. Designed multi-batch architecture: Batch 1 (factorial seed, no rules) -> collect responses -> cluster -> induce -> Batch 2+ (EDRA-guided + 20% control).
7. Minimum viable: 20 emails -> 14 days -> 20 episodes -> 2-3 clusters -> first rules.
8. Timeline: send by May 23, classify by June 6, write up by June 11 deadline.

### Phase 8 — Frontend overhaul (8 commits)
9. **Phase 8.1 — Dynamic response buttons**: LLM generates 3 contextual options per turn (ResponseOption schema, JSON prompts, robust parser with fallback).
10. **Phase 8.2 — Cluster visualization**: `GET /api/cluster-viz` with t-SNE 2D projection, KNN neighbors, archetype labels, Canvas API scatter plot.
11. **Phase 8.3 — Email auth gate**: VisitorRow table, `POST /api/visitors` with email validation/upsert, frontend auth overlay.
12. **Phase 8.4 — End-of-dialog popup**: success ("Collaboration Initiated") / failure ("Until Next Time") variants.
13. **Phase 8.5 — Avatar integration**: `edra-idle.jpg` connected, fade-in animation, `data-emotion` attribute, emotion state map designed (12 states).
14. **Phase 8.6 — Avatar emotion system**: 12 PNG emotion states generated and wired. Crossfade transitions between states. Background normalized to `#0A0A0A`. 3 images regenerated for visual consistency (hair length).
15. **Phase 8.7 — Speech bubble dialog mode + fixes**: Agent text renders in a speech bubble anchored to the avatar. Avatar `mix-blend-mode` fix for compositing. Cluster visualization UX fix.

### Testing
16. 204 tests total (143 existing + 61 new), 0 failures, 0 regressions.

### Avatar generation
17. Generated 2D anime character "Edra" matching Defy V2.0 brand (dark hair, red accent, black blazer, cream top, "Edra" badge). Stored at `frontend/assets/avatar/`.
18. All 12 emotion states generated as PNG. 3 regenerated for consistency (hair length mismatch).

### E2E verification
19. Full dialogue flow tested end-to-end: email auth -> session start -> 6 turns -> acceptance (interest +5).
20. Dynamic buttons confirmed working: 5 out of 6 turns returned contextual LLM-generated options.
21. All API endpoints verified operational.

## What was NOT done

- **ClickHouse migration** — rejected, using existing SQLAlchemy + SQLite instead
- **Lemlist account setup** — waiting on founders for warmed domain access
- **Demo paper compilation in Overleaf** — still pending
- **First outreach batch** — blocked on Lemlist setup and batch selection

## Key decisions

- **Lemlist replaces Resend** for outreach delivery. Lemlist offers warm-up (Lemwarm), email finder, campaign tracking, and better deliverability vs Resend's transactional focus.
- **Multi-batch outreach architecture** — Batch 1 is factorial seed (no rules), subsequent batches are EDRA-guided + 20% control group. This ensures the outreach IS the EDRA system, not just LLM-generated emails.
- **ClickHouse rejected** — SQLAlchemy + SQLite is sufficient for demo scale. No migration needed.
- **12-state emotion map** for avatar: idle, greeting, interested-low, interested-high, explaining, thinking, concerned, encouraging, celebrating, farewell-positive, farewell-negative, listening.

## Open questions

- [ ] Can founders share their warmed Lemlist account? (Critical for June 11 deadline — skips 3-4 week warm-up)
- [ ] Evaluation methodology for `edra_demo.tex` — which path (A/B/C)?
- [ ] Demo paper still not compiled in Overleaf — does it fit 2 pages?
- [ ] Phase 5.1 still blocked on founder questionnaire (no update since 2026-04-30)
- [ ] IRB decision for outreach campaign

## Next session — entry points

1. **Lemlist setup** — if founders confirm account sharing, configure campaigns; otherwise start warm-up on fresh domain
2. **Select first 20 profiles** for Batch 1 outreach (factorial design, segment-balanced)
3. **Compile demo paper in Overleaf** — verify 2-page fit
4. **Phase O.3 refinements** — rewrite `sender.py` for Lemlist API
5. **If founders reply** — Phase 5.1 Defy fact sheet
6. **Choice button disable on terminate** — frontend bug: buttons still clickable after session ends (409 in console)

See [[../00-home/current priorities]] for the full phase board.
