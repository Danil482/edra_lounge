---
tags: [session, evaluation, clustering, umap, strategies, production-pipeline, paper]
date: 2026-05-28
---

# 2026-05-28 UMAP production pipeline and strategy reclassification

Validation session: discovered that production clustering pipeline (384d HDBSCAN) doesn't work on Pipedrive data (silhouette 0.179), traced root cause to curse of dimensionality, added UMAP-15d reduction to production, reclassified outreach strategies from 3 to 5 types.

## What was done

### Production vs evaluation pipeline mismatch

Ran production clustering (MiniLM-384d normalized + HDBSCAN, no UMAP) on 825 Pipedrive rows. Result: silhouette 0.179, 3 meaningless clusters (one mega-cluster at 73%). Root cause: 384 dimensions too high for density-based clustering on sparse text (job_title + org only). The surrogate pipeline (structured text extraction + UMAP-15d + HDBSCAN) got 0.739 on the same data — but was a different algorithm than production.

### UMAP added to production pipeline

Added `_reduce_for_clustering()` to `backend/clustering/cluster.py`: UMAP 15d (cosine metric, deterministic seed) before HDBSCAN in both `cluster_profiles` and `cluster_episodes`. This is standard practice (BERTopic does exactly this). `match_cluster_to_existing` and `embed()` unchanged — UMAP is only for clustering, not for embeddings or centroid matching.

Three-step validation:
1. Production without UMAP: silhouette 0.179, 3 clusters
2. Production with UMAP (raw text): silhouette 0.663, 3 clusters — still one mega-cluster
3. Production with UMAP + structured text: silhouette 0.726, 6 clusters — matches surrogate

### Strategy reclassification

Analyzed 638 cold_template emails — found event follow-ups, referral intros, and inbound responses incorrectly classified as cold_template. Reclassified:
- Extracted **warm_intro** from cold_template: event follow-up (54) + referral intro (16) + inbound (27) = 97 rows, 84.5% reply rate
- Removed **re_engagement** (21 rows, 38.1% reply rate) — not first-contact outreach
- Final: 5 strategies, 804 rows (was 825)

Updated `evaluation/filter_cold_outreach.py`: `classify_outreach_type` now takes full row (not just subject), matches on subject + snippet, filters re_engagement as excluded.

### Evaluation script

Created `evaluation/cluster_production.py`: standalone production-matching pipeline (MiniLM-384d normalized → UMAP-15d → HDBSCAN) with structured text extraction, text report, and interactive HTML visualization (canvas scatter, hover tooltips, strategy×cluster heatmap, dark theme).

Final result on 804 rows: silhouette 0.726, 6 clusters (Mixed 403, Managers 228, CEOs 85, Directors 43, Founders 23, Partners 20), 2 noise.

### Paper and presentation updates

- `edra_demo.tex`: 825→804, UMAP in pipeline description, 5 strategies, 5 policies, silhouette 0.726 and 6 clusters filled in (chi-squared still TBD)
- `edra_presentation.html`: 825→804, UMAP on slides 4 and 10, new slide 11 with iframe cluster visualization, 16 slides total
- `bandit_evaluation_explainer.html`: 825→804
- `papers/` added to `.gitignore`

### Pipedrive export enrichment check

Checked `evaluation/data/people-14356779-664.csv` (29K people export) for richer fields. Person summary exists for only 32/825 rows (3.9%), useful Notes for 39. Not enough to change the picture — structured text extraction + UMAP is the solution, not data enrichment.

## What was NOT done

- Chi-squared test on cluster reply rates (needs tier 2 no-reply data for realistic rates)
- Tier 2 data integration
- Level 2: reward model (LogReg) + DR estimator
- Level 3: prequential simulation
- Overleaf compilation check
- E2E test of demo with UMAP-enabled clustering
- Message to Alex about methodology (drafted but not sent)

## Key decisions

- **UMAP in production is an improvement, not a compromise** — HDBSCAN on raw 384d suffers from curse of dimensionality. Standard in NLP clustering (BERTopic pattern). Added to both `cluster_profiles` and `cluster_episodes`.
- **Structured text extraction is eval-only** — production uses full LinkedIn profiles via `summarize_profile_from_json`, which contains enough semantic signal. Keyword-based seniority/function parsing is a workaround for sparse CRM data.
- **5 strategies, not 3** — warm_intro is semantically distinct from cold_template (84% vs 77% reply rate). re_engagement removed (not first-contact).
- **papers/ gitignored** — managed outside git (Overleaf, local drafts).

## Open questions

- [ ] Chi-squared test: will it be significant on current data without tier 2? Reply rates 72-82% across clusters are close.
- [ ] Should the Mixed/unknown cluster (403 rows, 50%) be split further or excluded from evaluation?
- [ ] Does UMAP change the demo behavior? Need E2E test with real LinkedIn profile + seeded clusters.
- [ ] `umap-learn` not yet in requirements.txt — add it?
- [ ] Send methodology question to Alex or proceed with current approach?

## Next session — entry points

1. Chi-squared test on current 804 rows (or integrate tier 2 first)
2. Build reward model (LogReg) + DR estimator → Level 2
3. Prequential simulation → Level 3
4. E2E test of demo with UMAP-enabled clustering
5. Final paper compilation in Overleaf (deadline: 2026-06-11)

See [[../00-home/current priorities]] for the full phase board.
