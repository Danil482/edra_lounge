---
tags: [session, evaluation, pipeline, dr-estimator, chi-squared, strategies, prequential, presentation, demo-paper]
date: 2026-05-29
---

# 2026-05-29 Evaluation pipeline refactor and 3-level validation

Major evaluation overhaul: integrated tier 2 data, replaced coarse strategy labels with text-level archetypes via MiniLM+HDBSCAN, rebuilt the entire pipeline as 6 sequential steps, ran all 3 evaluation levels, updated presentation and demo paper with real numbers.

## What was done

### Tier 2 data integration

Loaded partial tier 2 data (6,757 rows from `EDRA/data/eval_tier2_no_reply_mail.csv`). After filtering: 589 cold outreach rows (539 no_reply, 50 reply). Combined with 804 tier 1 rows, deduplicated by email: 1,386 total. Reply rate dropped from 78% (tier 1 only) to 51% — realistic.

Chi-squared on combined data: **Cluster x Outcome became significant** (p < 0.001, V=0.202) — was p=0.208 on tier 1 alone. The tier 2 no-reply data disentangled the cluster effect from strategy confounding.

### Text-level strategy archetypes

Identified fundamental flaw: coarse strategy labels (cold_template, cold_personal, etc.) were trivially dominated by warm contacts (relationship). Removed warm contacts and reclassified cold outreach by MESSAGE CONTENT via MiniLM embedding + HDBSCAN clustering of outreach snippets.

7 strategy archetypes discovered: personalized_opener (68% reply), tech_demo (64%), company_pitch (62%), general_intro (60%), event_followup (43%), vc_fundraising (23%), mass_newsletter (9%). These map to EDRA's 5-slot rule structure (framing, tone, opener_type, word_target, ask_size).

### Complete pipeline refactor

Deleted old scripts (filter_cold_outreach.py, filter_autoreplies.py, cluster_production.py, dr_estimator_archetypes.py, message_archetypes.py). Created clean 6-step pipeline:

1. `level0_data/prepare.py` — filter tier1+tier2: 11,176 raw -> 720 clean
2. `level1_clustering/classify_strategies.py` — embed snippets, HDBSCAN -> 7 strategies, 632 rows
3. `level1_clustering/cluster_recipients.py` — embed profiles, HDBSCAN -> 7 clusters, silhouette 0.551
4. `level1_clustering/chi_squared_test.py` — statistical tests (all significant)
5. `level2_policy/dr_estimator.py` — doubly robust policy comparison
6. `level3_learning/prequential_simulation.py` — prequential learning curve

Single entry point: `python -m evaluation.run_pipeline [--recompute]` (2m 48s full run).

### 3-level evaluation results

**Level 1 — Chi-squared** (all significant at alpha=0.05):
- Cluster x Outcome: chi2=33.16, p<0.001, V=0.229 (small)
- Strategy x Outcome: chi2=77.32, p approx 0, V=0.350 (medium)
- Cluster x Strategy: chi2=542.5, p approx 0, V=0.378 (confounded)

**Level 2 — DR estimator**:
- pi_uniform (always general_intro): V_DR = 0.571
- pi_best_single (always personalized_opener): V_DR = 0.569
- pi_edra (cluster-conditional): V_DR = 0.670
- **Delta pi_edra vs pi_best_single: +0.102**
- Each cluster picks a different strategy: Marketing Sales -> personalized_opener, Investor Angel -> company_pitch, Founder -> general_intro, Director CEO -> vc_fundraising

**Level 3 — Prequential** (30 sliding windows, size=60, step=20):
- Both EDRA and uniform show DOWN trend due to distribution shift (early=inbound, late=cold)
- EDRA avg 0.556, uniform avg 0.611
- Learning Dynamics section left as placeholder in demo paper pending more data

### Strategy-to-rule mapping

Created `evaluation/strategy_rules.py` with mapping of 7 archetypes to EDRA's 5-slot rules. Key pattern: applied-curiosity framing + reference-to-signal opener + medium length works best (68%); credential-anchor + long + mass = worst (9%).

### Presentation and demo paper updates

- Slides 9-13 updated with final numbers (632 rows, 7 clusters, 0.551 silhouette)
- Slide 11: chi-squared results cards
- Slide 12: DR estimator table with per-cluster picks and policy bars
- New slide 12a: strategy-to-rule mapping table
- Slide 13: learning curve iframe (pi_uniform + pi_edra only)
- `edra_demo.tex`: all placeholders filled, Section 3 rewritten with DR table, Learning Dynamics = placeholder

### Custom agent debugging

Investigated why `subagent_type: "developer"` fails — the Agent tool matches on the `name:` frontmatter field, not the filename. `developer.md` has `name: Senior Python Developer` so must use that as subagent_type. Documented in conversation.

## What was NOT done

- Tier 2 full extraction (only partial — 6,757 of 24,415)
- Level 3 prequential with enough data for conclusive learning curve
- Overleaf compilation check
- CTO deployment message
- Dockerization
- Short custom agent aliases (name: field rename in 4 agent files)

## Key decisions

- **Text-level strategies replace coarse labels** — MiniLM+HDBSCAN on message snippets produces 7 archetypes that map to EDRA's 5-slot rules
- **Warm contacts excluded from evaluation** — they trivially dominate reply rates and don't represent EDRA's action space
- **Pipeline as 6 sequential steps** — single entry point `run_pipeline.py`, each step produces a CSV consumed by the next
- **Learning Dynamics = placeholder in paper** — current 632-row dataset too sparse for 7x7 prequential; will revisit after more data
- **Sliding windows for prequential** — window=60, step=20 gives 30 points instead of 8 fixed batches
- **Only pi_uniform + pi_edra on learning curve chart** — cleaner visualization

## Open questions

- [ ] Will tier 2 full extraction (24K rows) change the learning dynamics picture?
- [ ] Should strategy archetypes be manually refined or kept as auto-discovered?
- [ ] How to handle distribution shift in EDRA's greedy policy? Epsilon-greedy? Decay?
- [ ] Paper: can Learning Dynamics section be filled with current data, or wait for more?
- [ ] Agent aliases: rename `name:` field in 4 custom agent files for convenience?

## Next session — entry points

1. Consider collecting more tier 2 data to strengthen prequential evaluation
2. Fill in Learning Dynamics section in demo paper when data is sufficient
3. Compile paper in Overleaf — verify 2-page fit
4. Production deployment: send CTO message, Dockerize
5. Level 2/3 re-evaluation if more data collected

See [[../00-home/current priorities]] for the full phase board.
