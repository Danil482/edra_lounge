---
tags: [session, knn, centroid, ood, clustering, embeddings, revision, induction, demo-theater, cluster-viz, frontend]
date: 2026-06-01
---

# 2026-06-01 (PM) Centroid OOD gate, honest induced revision, viz palette

Second session on 2026-06-01, driven by four issues surfaced from screenshots of the seeded booth: (1) the "MOST SIMILAR PROFILES" panel showed "Professional" for everyone, (2) the rule-revision panel never showed a before→after diff, (3) the cluster-viz scatter looked like random noise, and (4) a deeper discussion of the KNN `0.55` cluster-membership threshold. All four addressed. All changes left UNCOMMITTED at session close, and the booth was NOT live-verified this session (user wrapped up before running it).

## What was done

### 1. Diagnosed and fixed the cluster-membership threshold ("0.55 problem")
The user asked whether the `MIN_NEIGHBOR_SIMILARITY = 0.55` OOD gate was mis-calibrated because "the rule wasn't applied at initial clustering, so seeded data differs from new." Confirmed — but the real mechanism is **two confounded defects**:

- **Problem A — clustering metric ≠ inference metric.** Seeded `cluster_id` comes from the eval pipeline (UMAP-15d + HDBSCAN — density / mutual-reachability geometry), but `select_rule_by_knn` gated on raw 384-d cosine to a single nearest neighbor. "In-cluster" and "cosine ≥ 0.55 to a member" are different predicates; core members can score low (the documented "cluster-4 weak members fall to improvise").
- **Problem B — seeded embeddings built from a different text template than live profiles.** `_build_profile_text` appended `({cluster_label} segment)` to every profile's embedding text → the cluster label was literally embedded into the vector and shared across all members, **artificially inflating intra-cluster cosine**. The 0.55 threshold was tuned on that inflated distribution (p1=0.58, p5=0.64). Live LinkedIn visitors (free text, no suffix) sit in a systematically different region → structurally capped below 0.55. So the threshold may have been rejecting nearly everyone, not just genuine outliers — calibration on the wrong reference set.

**Fixes applied** (`backend/seed_from_eval.py`, `backend/clustering/knn.py`, `backend/sessions/lifecycle.py`):
- Removed the `(segment)` suffix from `_build_profile_text` — seeded embeddings now reflect only real attributes (title + org), comparable to live free-text.
- Replaced single-NN gate with **`select_rule_by_centroid`** — cosine to each ruled cluster's stored `centroid_embedding` (the DB already stores them; mirrors `match_cluster_to_existing`). Norms divided out (centroid = mean of unit vectors, not unit-norm).
- Recalibrated the threshold on the corrected geometry: member→own-centroid cosine `min=0.14 p1=0.23 p5=0.45 p25=0.64 median=0.74`; OOD live-style profiles ("PhD researcher in NLP…" = 0.26, plumber = 0.28). New constant **`MIN_CENTROID_SIMILARITY = 0.45`** (genuine-member p5).
- Role-display fallback: `job_title → cluster_label → "Professional"` (only 398/744 rows have a real `job_title`; cluster_label values already read like roles, e.g. "Marketing Manager"). Fixes the "Professional"-everywhere panel.
- Reseeded `edra_lounge.db` anonymized (no `SEED_WITH_NAMES`).

### 2. Frontend rule-revision before→after diff
`frontend/app.js` + `frontend/styles.css`. Captures each `/state` poll's rules into a module-level `rulesById` (mirrors the `clusterLabelById` pattern). `renderProposed` looks up the baseline rule by `proposed.id` (the pending-only theater keeps the active rule's original slots until accept, so it IS the "before"), renders `before → after` per slot, highlights ONLY changed slots in Defy red, mutes unchanged. Graceful fallback to proposed-only render if no baseline. Handles static↔dynamic transitions as changes.

### 3. Cluster-viz color palette
`backend/routers/cluster_viz.py`. `CLUSTER_COLORS` had 6 entries for 7 clusters, several unreadable on `#0A0A0A` (near-black `#2D2D2D`, dim `#777777`, two indistinguishable creams, two reds). Replaced with **8 distinct dark-bg-readable colors** (Defy red kept first, + amber / teal / slate-blue / magenta / green / cream / grey). Frontend consumes `pt.color` directly — backend-only change. Explained that t-SNE 2D scatter being lossy is *expected* (high-D silhouette ~0.55 is the real measure); the palette was the actual defect making it read as noise.

### 4. Honest induced rule revision (demo theater)
The revision panel showed no diff because `proposed == current`: `inject_contradiction` injected only failing-current episodes (no winning alternative), so the reflection LLM had nothing to induce toward (and offline → copied the rule). User chose the **induced-honest** approach over a scripted flip.

`backend/routers/simulator.py`, `backend/monitor/consistency.py`, `backend/reflection/revise.py`, `backend/routers/reflections.py`, `backend/llm/prompts/reflect.txt`:
- `inject_contradiction` now injects **two groups**: `cs_window` `accepted` episodes carrying a different "winning" strategy (back-dated −2s) + `cs_window` `rejected` episodes carrying the current strategy (at `now`). Winner selected data-grounded (highest accept-rate cluster strategy differing in ≥2 slots), else fixed `STRATEGY_TO_RULE` fallback differing in ≥2 slots.
- **Trigger preserved**: `should_revise` now sorts post-induction episodes by timestamp before taking the trailing `cs_window` window, so the back-dated winners stay OUT of the trigger window (only failures count → CS=0 < theta_revise → fires). Also `now = max(utcnow(), induced_at + 10s)` fixes a real bug where a freshly-seeded rule has `induced_at == now` and injected episodes wouldn't count as post-induction.
- Reflection now fetches recent post-induction episodes of BOTH outcomes and shows the LLM failing-current + winning-alternative → it induces the winner. `reflect.txt` updated with a "Succeeding sessions" section.
- **Deterministic fallback**: `mode_of_slots_rule` over the accepted evidence (LLM offline / parse fail) → proposed differs from current in ≥2 slots by construction. Never an empty diff.
- Example: R.03 `knowledge-share/warm/…` → `applied-curiosity/direct/…` (framing + tone changed).

**Tests: 252 passed, 2 pre-existing `test_cluster_viz` failures** (archetype-label mismatches, unrelated). Updated `test_knn.py`, `test_clustering_refactor.py`, `test_sessions.py`, `test_inject_contradiction.py`, `test_consistency_loop_integration.py`; added an offline-fallback test.

## What was NOT done
- **No live verification** — user invoked `/end` before running the booth. The whole batch (centroid admission side, induced diff in-browser, palette) is verified only by tests + reasoning, not a real run.
- **Nothing committed** — all code in the working tree pending the user's commit decision.
- **Admission side of the threshold unverified** — only OOD *rejection* (0.26/0.28 ≪ 0.45) is proven. No real in-domain marketing LinkedIn profile was tested against 0.45. Residual Problem B (live free-text vs short-CRM-string centroids) is mitigated, not eliminated — a genuine marketing visitor *might* not clear 0.45.
- **2 pre-existing `test_cluster_viz` failures** still not fixed.
- `papers/edra_demo.tex` left to the user (pre-existing M).

## Key decisions
- **Role fallback = `cluster_label`** (over `organization` or cascade) — cluster labels here already read like roles.
- **Fix the threshold/metric now (suffix removal + centroid gate)**, not as tech debt.
- **Threshold 0.45 = genuine-member p5** on corrected geometry — a single named constant, trivial to retune; flagged as a hypothesis verified on the rejection side only.
- **Revision = induced-honest, not scripted** — induced from injected evidence with a deterministic mode-of-slots fallback for offline. Scripted-flip rejected.
- **Palette: distinguishability > strict monochrome branding** — kept Defy red as cluster 0, added jewel-tone hues.
- **`should_revise` sorts by timestamp** — a genuine improvement to the real revision path, not demo-only.
- **Neighbor-panel "% similar" (raw NN) now diverges from assignment (centroid)** — accepted as a deliberate, known divergence.

## Open questions
- Does a real in-domain marketing LinkedIn profile clear the 0.45 centroid gate (admission side)? Only a live run answers this.
- Keep 0.45, or retune once we have live in-domain data? (p25=0.64 stricter, lower for more coverage.)
- Pursue Problem B to the end — option 3 (run live visitors through the same fitted UMAP+HDBSCAN, `approximate_predict`) or option 4 (calibrate the threshold on real live-style profiles, e.g. the 502 research set)?
- The demo "winner" is currently the fixed `STRATEGY_TO_RULE` fallback (seeded clusters are strategy-homogeneous, so data-grounded 2nd-best rarely qualifies) — induced from *injected* evidence, not discovered in real cluster data. Acceptable for reversible theater, but worth noting it doesn't demonstrate "learning from the cluster's own history."
- Fix or delete the 2 `test_cluster_viz` tests?

## Next session — entry points
1. **Live-verify the whole batch**: restart backend + hard-refresh (Ctrl+Shift+R). Check: (a) palette — 7 clusters visually distinct; (b) a real marketing LinkedIn URL clears 0.45 and gets a rule (admission side); (c) neighbor panel shows real titles/segments, not "Professional"; (d) Inject Contradiction → streams reasoning → before→after diff with only changed slots highlighted → OK rolls back.
2. **Commit the accumulated code** in atomic groups (if not committed this session): (a) seed + centroid geometry + role fallback, (b) cluster-viz palette, (c) honest induced revision, (d) frontend revision diff — then obsidian separately. Leave `papers/edra_demo.tex` to the user.
3. **Decide threshold 0.45** final after live admission test.
4. Fix the 2 `test_cluster_viz` failures.
5. (Optional) Pursue Problem B (option 3/4) if live admission shows genuine visitors falling below 0.45.

See [[../00-home/current priorities]] for the full phase board. Prior session: [[2026-06-01 Live rule-revision demo theater and live-run fixes]].
