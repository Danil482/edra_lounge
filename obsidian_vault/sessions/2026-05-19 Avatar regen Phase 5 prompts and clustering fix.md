---
tags: [session, avatar, phase-5, prompts, clustering, frontend]
date: 2026-05-19
---

# 2026-05-19 Avatar regen, Phase 5 prompts, and clustering fix

Regenerated all 12 avatar PNGs with chroma key pipeline, overhauled avatar CSS for correct aspect ratio and positioning, implemented Phase 5.1-5.3 (lab fact sheet, system prompt rewrite, response category rotation, refusal rules), fixed clustering threshold so rules appear in early demos, and started Lemlist warm-up on user's own account.

## What was done

### Avatar idle fix and regeneration
1. **Avatar idle visibility** — `app.js`: avatar now renders in idle state (before session start), not only during dialogue.
2. **Avatar regeneration** — all 12 emotion PNGs regenerated with green screen (#00FF00) background, then chroma-keyed to transparent PNGs at 533x800 (2:3 ratio). Pipeline script: `scripts/chromakey_avatars.py`.
3. **Avatar CSS overhaul** — container `aspect-ratio: 0.667` (was 0.7), `object-fit: contain` (was `cover`), `bottom: 22%`, `height: 64%`, removed `mix-blend-mode: lighten`.

### Speech bubble and UI fixes
4. **Speech bubble as default** — `dialogMode: 'bubble'` is now the default mode, button label shows "PANEL".
5. **Speech bubble panel collision fix** — avatar and bubble shift left together when right panel opens (CSS transition, avatar 320px, bubble 420px).
6. **Avatar cache-busting** — added `?v=2` to all avatar image paths to force browser reload after green-screen regen.

### Clustering fix
6. **`n_min` lowered from 5 to 3** in `config.py` — rules now appear after ~8 episodes instead of never during early demos. Previous threshold was too high for booth-scale demonstrations.

### Phase 5.1-5.3 — Prompts and scenarios
7. **Phase 5.1 — Lab fact sheet**: `_lab_facts.txt` created from 5 analyzed papers (Farseev's lab publications). Contains concrete facts, proof points, and research context for prompt injection.
8. **Phase 5.2 — System prompt rewrite**: `_system.txt` expanded to ~450 words with anti-hallucination boundaries, brand voice, role definition, and "do not invent facts not listed in facts" rule.
9. **Phase 5.2 — Response category rotation**: 6 categories implemented (`specific-defy-fact` / `methodology-hook` / `profile-callback` / `concrete-next-step` / `soft-personal` / one more). `generate.py` loads new prompts, tracks used categories per session.
10. **Phase 5.2 — Prompt rewrite**: `opener.txt` and `continuation.txt` rewritten to consume fact sheet and system message.
11. **Phase 5.3 — Refusal rules**: system prompt includes refusal behavior for no-signal profiles, title-only profiles, over-credentialed sequences, and `ask_size=none`.
12. **Phase 5.5 — Templates updated**: `templates.py` rewritten to use real facts from the fact sheet (fallback must not diverge from LLM path).

### Google Scholar extraction
13. **10 publications** from Farseev's Google Scholar profile saved to `papers/farseev_google_scholar_top10.md`.

### Lemlist warm-up
14. **Lemlist warm-up started** on user's own account. Expected ready date: ~2026-05-26 (~1 week).

## What was NOT done

- **Demo paper compilation in Overleaf** — still pending
- **First outreach batch** — blocked on Lemlist warm-up (~May 26)
- **Phase 5.4 — Scenario test harness** — not started this session
- **Prompt humanizer pass** — completed (anti-AI-slop sweep on all templates)

## Key decisions

- **Clustering `n_min` = 3** (was 5) — booth demos rarely accumulate 5+ episodes in a single cluster, so rules were never induced. Lowering to 3 makes the rule pipeline visible after ~8 episodes.
- **Speech bubble is the default dialog mode** — panel mode is secondary, toggled via button.
- **Chroma key pipeline for avatars** — green screen generation + `chromakey_avatars.py` script produces cleaner transparent PNGs than direct transparent-background generation.
- **Phase 5.1 unblocked via papers** — instead of waiting for founder questionnaire, analyzed 5 lab papers to extract concrete facts. See [[../knowledge/decisions/Prompt improvement plan based on lab papers]].

## Open questions

- [ ] Lemlist warm-up completes ~2026-05-26 — first outreach batch can be sent after that
- [ ] IRB decision still pending
- [ ] HourglassNet paper still anonymous (cannot cite by name)
- [ ] Founder questionnaire still unanswered (but no longer blocking Phase 5.1-5.3)
- [ ] Phase 5.4 scenario test harness — needed to validate prompt quality before outreach

## Next session — entry points

1. **Phase 5.4 — Scenario test harness** — lock in prompt quality baseline with pytest scenarios
2. **Compile demo paper in Overleaf** — verify 2-page fit, insert booth screenshot
4. **Select first 20 profiles** for Batch 1 outreach (factorial design, segment-balanced)
5. **Phase O.3** — rewrite `sender.py` for Lemlist API (once warm-up completes ~May 26)
6. **Choice button disable on terminate** — frontend bug still open (409 in console)

See [[../00-home/current priorities]] for the full phase board.
