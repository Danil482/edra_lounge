---
tags: [session, evaluation, clustering, autoreply-filter, pitch-escalation, presentation]
date: 2026-05-27
---

# 2026-05-27 Evaluation cleanup and pitch escalation

Second session of the day. Three tracks: cleaning evaluation data (autoreply filter + reclustering), reframing presentation evaluation slides, and fixing the pitch agent's escalation behavior.

## What was done

### Evaluation data cleanup

Created `evaluation/filter_autoreplies.py` — second step in the pipeline after `filter_cold_outreach.py`. Classifies replies as `genuine`, `expired`, or `auto` (OOO, bounces, gone-from-company, unsubscribe). Engagement signals override auto-reply classification (e.g. "I'm OOO but let's connect when I return" → genuine). Conscious declines kept as genuine (negative reward signal).

Results: 1027 → 825 rows (202 auto-replies removed, 20%). Breakdown: 607 genuine, 188 no_reply, 30 expired.

Updated row count 976 → 825 across `edra_demo.tex`, `edra_presentation.html`, `bandit_evaluation_explainer.html`.

### Clustering breakthrough: silhouette 0.18 → 0.74

Previous clustering on `job_title + org + labels` produced silhouette 0.177 (one mega-cluster). Root cause: MiniLM embeddings collapse "Marketing Manager at X" and "Marketing Manager at Y" into the same point.

Solution: structured text extraction + UMAP dimensionality reduction.

1. **Structured text builder (v3)**: extracts seniority level (C-level/Founder/Partner/Director/Manager/Specialist) and functional area (marketing/digital/sales/growth/media/product/strategy) from job title, combines with org name and campaign labels
2. **UMAP 15-dim reduction** before HDBSCAN (cosine metric, random_state=42)
3. Parameter sweep across 3 text strategies × 2 embedding approaches × 12 HDBSCAN configs

Best config: v3_umap, min_cluster_size=8, min_samples=5 → **6 clusters, silhouette 0.739, 4 noise (99.5% clustered)**.

Clusters: Mixed/unknown (417), Marketing Directors (43), CEOs/C-level (86), Marketing Managers (231), Founders (24), Partners/VCs (20). Reply rates 72-83% — close but with sharp strategy×cluster interaction effects (feature_announcement: 30% for Mixed vs 0% for Partners).

Note: reply rates are inflated because data is tier 1 (people with at least one reply thread). Next session will incorporate tier 2 no-reply data.

### Presentation overhaul (3 new evaluation slides)

Added slides 10-12 to `edra_presentation.html` (now 15 total):
- **Slide 10 (08a PREREQUISITE 1)**: "Do Natural Groups Exist?" — pipeline SVG, silhouette + chi-squared metrics, outcome cards
- **Slide 11 (08b PREREQUISITE 2)**: "Does Optimal Strategy Differ by Cluster?" — strategy×cluster matrix, 4 policy bars, DR estimator
- **Slide 12 (08c THE TEST)**: "Can EDRA Learn What Works?" — learning curve chart (EDRA vs LinUCB), shaded advantage area

Reframed evaluation narrative: Levels 1-2 are explicitly labeled PREREQUISITE ("tests the data/problem, not the model"), Level 3 is THE TEST ("tests the actual contribution"). Fixed SVG `<sub>` rendering bug (invalid HTML inside SVG → `<tspan>`). Fixed "by segment" → "by campaign" on slide 2 (data sourced from Pipedrive campaign labels, not EDRA clusters).

### Pitch agent escalation fix

Agent was dumping random facts on repeated positive responses instead of escalating toward a concrete offer. Root cause: continuation prompt had no visibility into interest level.

Fix: pass `sess.interest` through `generate_turn()` → continuation prompt. Added ESCALATION ladder:
- interest ≤ 0 → RECOVER (reframe, find genuine connection)
- interest 1-2 → BUILD (establish credibility with facts)
- interest 3 → PERSONALIZE (reference their specific profile)
- interest 4+ → CLOSE (propose concrete next step, override category rotation)

220 tests green, 0 regressions.

## What was NOT done

- LinkedIn enrichment for Pipedrive profiles (decided: not worth scraping, try structured features first — and it worked)
- Chi-squared test on cluster reply rates (reply rates too close, need tier 2 data)
- Tier 2 no-reply data integration (next session)
- Actual evaluation results (Level 1-3 placeholders remain)
- Overleaf compilation check

## Key decisions

- **No LinkedIn scraper** — ToS violation, detection risk, multi-day effort, 43% profiles have no URL anyway. Structured text extraction + UMAP achieved silhouette 0.74 without external data.
- **Autoreply filter as separate pipeline step** — `filter_cold_outreach.py` (is this first contact?) vs `filter_autoreplies.py` (is the reply genuine?). Different concerns, separate scripts.
- **Bounce always beats engagement** — "no longer with company" + engagement signals = still auto (unrealistic combo). OOO + engagement = genuine (real person planning to follow up).
- **Evaluation narrative: prerequisites vs actual test** — Levels 1-2 validate the problem exists, Level 3 validates EDRA's contribution. Prevents the "isn't personalization obviously better?" objection.
- **Next session: add tier 2 data** — current reply rates too high (72-83%) because data is tier 1 only. Need no-reply rows to make chi-squared meaningful and reply rates realistic.

## Open questions

- [ ] How to incorporate tier 2 (no-reply) data? Match by campaign/outreach_type or by profile features?
- [ ] Should the "Mixed/unknown" cluster (417 rows, 51% of data) be excluded from evaluation as noise?
- [ ] `umap-learn` added as dependency — add to requirements.txt?
- [ ] Does the pitch escalation feel natural in live demo? Need E2E test with real profile

## Next session — entry points

1. Incorporate tier 2 no-reply data → realistic reply rates → chi-squared test (Level 1 completion)
2. Build reward model (LogReg) + DR estimator → fill Level 2 placeholders
3. Prequential simulation → fill Level 3 placeholder
4. E2E test of pitch escalation with real LinkedIn profile
5. Final paper compilation in Overleaf (deadline: 2026-06-11)

See [[../00-home/current priorities]] for the full phase board.
