---
tags: [session, live-revision, demo-theater, knn, improvise, frontend, email-gate, privacy, simulator]
date: 2026-06-01
---

# 2026-06-01 Live rule-revision demo theater and live-run fixes

Built a reversible "demo theater" for live rule revision (the revision button existed in the UI but was never triggered on the seeded real-data DB), then drove the booth live and fixed a wave of issues the run surfaced. All changes left uncommitted at session close pending the user's commit decision.

## What was done

### Live rule-revision demo theater (reversible)
The whole revision pipeline already worked (consistency loop → pending `Revision` → SSE-streamed reasoning → decision), but on the seeded DB it never fired: the seeded clusters are real CRM clusters, all seeded episodes are PRE-induction (`timestamp < induced_at`), and the old `ai_bubble_pops` drift only mutates the synthetic-archetype preference matrix. New surface:

- **`POST /simulator/inject_contradiction`** `{cluster_id?, n?}` — inserts `n=settings.cs_window` `rejected` POST-induction episodes into a cluster (reusing a donor episode's `profile_id` + `summary_embedding`, no new profiles/PII), with `pitch_strategy` = the rule's own slots so the contradiction reads as "this rule's strategy is now failing". Persists DIRECTLY, **bypassing `on_new_episode`** so reclustering can't reshuffle `cluster_id` mid-demo. `cluster_id` optional → defaults to the **largest ruled cluster**. Consistency loop (every 10s) then raises a pending revision and the existing `/state`→SSE wiring streams live OpenAI reasoning + the proposed rule.
- **`POST /simulator/reset_injection`** — deletes the tracked injected episodes + the pending revision and restores the rule to `active`. Idempotent; 409 guard if the revision was already resolved (episodes still cleaned).
- **Frontend "OK" preview** — replaced Accept/Edit/Keep with a single `#refl-ok` that calls `reset_injection`; copy reads "Preview — how this rule would change if these signals were real. Not applied." **Real rules are never mutated by artificial injection** (the chosen pending-only design).
- **Latent bug fixed**: `save_revision`/`update_revision` now dump `proposed_rule` with `model_dump(mode="json")`. The `Rule` schema carries `datetime` (`induced_at`, `cs_history`) which a JSON column can't serialize — the consistency loop would have crashed on the first persisted revision. The test suite never exercised this path before.
- Orchestrator tracks `injected_episode_ids` + `injected_rule_id`; store gained `delete_episodes`, `delete_revision`, `latest_revision_for_rule`.
- Integration test proves the full in-process path: real `inject_contradiction` route → `_check_all_rule_cs()` → `save_revision` → `latest_pending_revision` returns it, rule `under_revision`, `active_revision_id` set; reset reverses it.

### Six fixes from the live booth run
1. **Rulebook cluster names** — `renderRule` now resolves labels from the live `/api/cluster-viz` `clusters` (new `clusterLabelById` map, same data as the legend), falling back to `ARCHETYPE_LABELS` then id. Seeded clusters showed bare numbers because their ids aren't in the hardcoded map.
2. **Out-of-distribution → no cluster → improvise** — added `MIN_NEIGHBOR_SIMILARITY = 0.55` to `select_rule_by_knn` (gate on MAX cosine among top-k ruled neighbors; below → return `None`). `lifecycle.start_session` already derives `cluster_id=None` and `pitch/generate.py` already improvises on a null rule. Threshold tuned empirically against the seeded corpus (in-cluster nearest-neighbor cosine: p1=0.576, p5=0.639; per-cluster mins 0.49–0.65). The AI-researcher test profile (max ~0.53) is now correctly unclustered.
3. **Top panel declutter** — kept Episodes/Rules/Revising counters, removed Day + Specialists; operator controls collapsed to a single **Inject Contradiction** (removed the cluster select, Reset Demo, + Segment, Expert toggle). Expert panels are now permanently visible.
4. **"Unclustered — improvising"** — the visitor panel's CLASSIFIED ARCHETYPE was leaking `profile.id` when `cluster_id` was null; now shows "Unclustered — improvising" and resolves via `clusterLabelById` otherwise. Backend `cluster_viz` also stopped fabricating `"The Visitor"`: `archetype_label` now gates on the authoritative `active_session.cluster_id` (None → null → frontend keeps the improvising label).
5. **Dynamic edge-handle bars** — the three collapsed hover strips were hardcoded CSS `content` (incl. fake name "MAYA LIANG", "DAY 03 · 47 EPISODES · 5 RULES", "R.07/R.12"). Switched to `content: attr(data-label)` set from live `/state` each poll (top: Episodes/Rules/Revising; right: subject name or NO ACTIVE SESSION; left: active/revising rule counts).
6. **Second conversation wouldn't start** — root cause: `showSessionStartDialog` clones the "Fetch & Start" button via `cloneNode(true)`, which copies the `disabled` attribute set during the first submit, so the cloned button is born disabled and never fires. Fix: explicitly clear `disabled` on dialog open. Also guarded `startPolling` against stacking a new `setInterval` pair per session.

### Local-only real names
`SEED_WITH_NAMES` env (default OFF → anonymized `"{cluster_label} #{i}"` as before; ON → real CRM `name` from `evaluation/data/dataset.csv`). `log.warning` on seed when enabled. Re-seeded locally with names ON for clustering-quality eyeballing. `edra_lounge.db` + `evaluation/data/*.csv` already gitignored. Name flows to the UI via `cluster_viz` `points[].name`/`neighbors[].name`.

### Email gate per-visitor reset
Kept the boot-time email gate but `hideEndDialog` ("Back to Lobby") now clears `visitorId`/`visitorEmail` and re-shows the gate blank, so each walk-up visitor enters their own email (was: first visitor's email stuck for everyone until reload). `bootAfterAuth` avatar preloading made idempotent so it doesn't re-run per visitor.

### Docs
`edra_pitch_mockup.html` marked **DEPRECATED / stale** in `CLAUDE.md` and `obsidian/index.md` — the live `index.html`/`app.js`/`styles.css` are now the source of truth (the frontend has diverged from the mockup this session).

**Tests: 248 passed, 2 failed** (the 2 are pre-existing `test_cluster_viz` archetype-label mismatches, unrelated). New: `test_inject_contradiction.py`, `test_knn.py`, `test_consistency_loop_integration.py`, `test_seed_with_names.py`; additions to `test_sessions.py`, `test_end_dialog_frontend.py`.

## What was NOT done

- **Nothing committed** — code + docs left in the working tree pending the user's commit decision at session close.
- **Re-seed anonymized before deploy** — `edra_lounge.db` currently holds real names (PII). Run `python -m backend.seed_from_eval` (no `SEED_WITH_NAMES`) before any deployment.
- **2 pre-existing `test_cluster_viz` failures** not fixed (archetype-label string expectations from an earlier uncommitted refactor).
- **User live-verification** of the latest batch (second-conversation fix, email reset, Unclustered label, dynamic bars).
- **Email → episode backend link** — captured email is still standalone lead capture, not tied to the session/outcome.
- Mockup file itself NOT re-synced (deprecated instead, per decision).

## Key decisions

- **Demo theater is pending-only** — OK previews the revision and rolls back; artificial injection never mutates real rules. Full accept-reversal explicitly out of scope (use `make reset` to fully reseed).
- **Inject targets the largest ruled cluster** automatically — no operator cluster picker.
- **KNN OOD threshold = 0.55** — pragmatic compromise: catches the AI-researcher outlier (~0.53) at the cost of ~0.13% genuine-member false-rejects (cluster-4 weak members fall to improvise). One constant in `knn.py` to retune.
- **Real names LOCAL-ONLY** via opt-in env; anonymized stays the default for booth/deploy (CRM PII / GDPR). User wanted names only to verify clustering quality, not on the public booth.
- **Email: boot-gate retained but reset between visitors** (not moved to a post-result form, which was the alternative considered).
- **Mockup deprecated, not re-synced** — live frontend leads.

## Open questions

- Fix or delete the 2 pre-existing `test_cluster_viz` tests?
- KNN threshold 0.55 — keep, or adjust given cluster-4's weak members?
- Link the captured email to the session/episode backend-side for lead attribution?
- Wording: "Unclustered — improvising" vs "New archetype"?

## Next session — entry points

1. **User live-verify** the latest fixes (second conversation, email reset per visitor, "Unclustered — improvising", dynamic edge bars, inject → live reasoning → OK rollback).
2. **Commit the accumulated work** in atomic groups: (a) demo-theater feature (backend + frontend + tests), (b) live-run fixes + `CLAUDE.md` mockup note, (c) obsidian separately. Leave `papers/edra_demo.tex` (pre-existing) to the user.
3. **Re-seed anonymized** before any deploy (`SEED_WITH_NAMES` currently ON locally).
4. Fix the 2 `test_cluster_viz` failures.
5. (Optional) link email → episode for lead attribution.

See [[../00-home/current priorities]] for the full phase board.
