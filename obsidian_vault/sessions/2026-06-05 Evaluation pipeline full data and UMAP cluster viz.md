---
tags: [session, evaluation, clustering, visualization, umap, workflow]
date: 2026-06-05
---

# 2026-06-05 Evaluation pipeline on full data and UMAP cluster viz

Major session: ran evaluation on full tier1+tier2 (30K rows), diagnosed strategy clustering degradation, implemented name masking, validated on original 744-row dataset, rewrote cluster visualization from t-SNE individual points to UMAP pre-computed centroids.

## What was done

### 1. CLAUDE.md workflow overhaul
- Sub-agents fully banned (Agent/Workflow tools prohibited)
- 15 token-economy rules added (narrow reads, batch calls, terse responses, grep-before-read)

### 2. Evaluation pipeline on full data (tier1=4536 + tier2=25144)
- Full pipeline run: 7734 clean rows, 44 strategy clusters, 106 recipient clusters
- Strategy clustering produced garbage labels (person names from emails, not archetypes)
- HDBSCAN `min_cluster_size` tuned: 30→300→150→30 across multiple iterations
- **Name masking** implemented in `clean_snippet`: `RECIPIENT`/`SENDER` tokens replace person names before embedding. `GREETING_RE` + `SENDER_NAMES` set + per-row recipient name from CSV
- `--tier1-only` and `--target-n` flags added to prepare.py for controlled dataset sizing
- All evaluation modules updated to read `dataset_final.csv`

### 3. Evaluation results validated on original 744 rows
- Chi-squared: all three tests significant (Cluster×Outcome V=0.346, Strategy×Outcome V=0.381, Cluster×Strategy V=0.536)
- DR estimator: **V_DR(EDRA)=0.672 > best_single=0.661 > uniform=0.540 > random=0.377**
- Reward model AUC: 0.555
- HDBSCAN strategy aliases: 8 raw labels → 7 normalized strategies (two mass_newsletter merged)
- Paper numbers confirmed: close to published 0.654/0.588/0.510

### 4. Cluster visualization rewrite (demo booth)
- Backend: t-SNE replaced with UMAP (384d → UMAP-15d → UMAP-2d)
- Pre-computed 2D coordinates saved at seed time (`data/viz_coords_2d.json`)
- Endpoint loads pre-computed coords instantly (was 45s UMAP on every restart)
- New visitors interpolated via K=7 cosine-weighted average of known positions
- Percentile-based normalization (p2-p98) to handle outliers
- **Centroid-only scatter**: 7 cluster centroids as labeled rings + visitor marker (was 744 individual dots)

### 5. Frontend fixes
- Inject Contradiction button disabled until session active
- Poll timers cleared on session end (fixes second-conversation-won't-start bug)
- Episodes counter reads `total_episodes` from backend (was capped at 20)
- Neighbor lines and individual profile dots removed from scatter plot

### 6. Backend fixes
- `total_episodes` count added to StateSnapshot (count query, not list length)
- Reflection parsing: handles missing `slots` key (tries `rule.slots`, `proposed_slots`)
- `seed_from_eval`: generates `viz_coords_2d.json`, `_DEFAULT_RULE` fallback for unknown strategies
- Cluster C0 renamed from "Mixed" to "Unresolved Contacts"

## What was NOT done
- Evaluation numbers in paper not updated (close enough to published, within CI)
- Level 3 prequential still shows DOWN trend (distribution shift)
- Name masking in evaluation viz labels still ugly (TF-IDF picks up RECIPIENT/SENDER tokens)
- PCA 2D explored for paper figure per supervisor suggestion — worse visual separation, reverted to UMAP
- `data/viz_coords_2d.json` not in .gitignore (regenerable from seed)

## Key decisions
- **Sub-agents banned** — token waste from context duplication outweighs parallelism benefit
- **Keep original 744-row dataset and paper numbers** — full 30K data dilutes signal (95% no-reply), tier1-only too homogeneous (76% reply). Original balanced sample is the sweet spot
- **UMAP over t-SNE** for booth viz — deterministic (fixed seed), pre-computable, consistent with evaluation viz
- **Centroid-only scatter** — 744 dots unreadable in small booth canvas; 7 centroids + visitor clear and fast
- **8 HDBSCAN labels → 7 strategies** via aliases: `dear_thrilled_james` + `mater_block7_block71_dear` → `mass_newsletter`

## Open questions
- Should `data/viz_coords_2d.json` be gitignored? It's regenerable but saves 45s on cold start
- Paper says "Seven message archetypes" — technically 8 raw HDBSCAN clusters merged to 7. Wording OK?
- Reflection `KeyError: 'slots'` — gpt-5.4 returns different JSON structure. Fallback works but prompt may need update
- Level 3 learning curve still shows DOWN — worth investigating distribution shift fix or just acknowledge in paper?

## Next session — entry points
1. **Live quality check** with gpt-4.1/5.4: run 2-3 conversations, verify no repetition
2. **Resume Lemlist campaign** in UI → test full booth flow end-to-end
3. **Paper finalization**: update table if needed, screenshot new cluster viz for figure
4. **Dockerfile for HuggingFace Spaces** — if deployment decision is made
5. **Fix 2 pre-existing `test_cluster_viz` failures**

See [[../00-home/current priorities]] for the full phase board. Prior session: [[2026-06-03 Lemlist all-outcome follow-up and dialogue quality fixes]].
