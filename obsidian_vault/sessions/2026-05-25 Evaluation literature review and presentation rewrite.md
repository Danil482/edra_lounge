---
tags: [session, evaluation, literature-review, presentation, methodology]
date: 2026-05-25
---

# 2026-05-25 Evaluation literature review and presentation rewrite

Deep-dive session on 5 key evaluation papers for the EDRA demo paper, followed by a full rewrite of the HTML presentation deck. Goal: build a rigorous evaluation framework grounded in established methods and make the presentation understandable at a glance.

## What was done

### Literature review — 5 papers analyzed in depth

Each paper was read in full, explained in simple terms, and mapped to EDRA's evaluation needs:

1. **Li et al. WSDM 2011** — "Unbiased Offline Evaluation of Contextual-bandit-based News Article Recommendation". Replay method for offline evaluation. Key insight: works only with randomized logging policy. Pipedrive data is NOT random → pure replay not applicable.

2. **Li et al. WWW 2010** — "A Contextual-Bandit Approach to Personalized News Article Recommendation" (LinUCB). Formal bandit algorithm using ridge regression with confidence bounds. Provides a baseline for comparison: LinUCB = what if EDRA used linear models instead of LLM rules. Advantage grows with sparse data (+20.1% at 1% data).

3. **Gama et al. MLJ 2013** — "On evaluating stream learning algorithms". Prequential (test-then-train) evaluation protocol for models that evolve over time. Fading factors and sliding windows for error estimation. This is the protocol for Level 3 (own outreach batches).

4. **Zhao et al. AAAI 2024** — "ExpeL: LLM Agents Are Experiential Learners". Closest competitor to EDRA. Extracts text insights from experience without parameter updates. Key difference: ExpeL stores flat insights globally; EDRA uses cluster-conditional rules. ExpeL tested on 3 domains (HotpotQA 39%, ALFWorld 59%, WebShop 40%).

5. **Dudik et al. ICML 2011** — "Doubly Robust Policy Evaluation and Learning". Combines direct method (reward model) with inverse propensity scoring. Unbiased if EITHER model is correct. This is the answer for Level 2 evaluation on biased Pipedrive data. Reduces rmse by 10-20% vs IPS alone.

### Evaluation framework crystallized

Three-level evaluation strategy grounded in the papers:

| Level | Method | Paper | Data | Shows |
|---|---|---|---|---|
| 1 | Silhouette + human annotation | — | 502 profiles | Clusters are meaningful |
| 2 | Doubly robust estimator | Dudik et al. 2011 | 29K Pipedrive contacts | EDRA policy > baselines on historical data |
| 3 | Prequential test-then-train | Gama et al. 2013 | Own outreach batches | Learning curve improves over time |

LinUCB (Li et al. 2010) serves as a formal baseline at Levels 2-3.

### PDF organization

All 5 evaluation papers renamed with proper academic naming and moved to `papers/evaluation/`:
- `Dudik_et_al_2011_Doubly_Robust_Policy_Evaluation_ICML.pdf`
- `Gama_et_al_2013_Evaluating_Stream_Learning_Prequential_MLJ.pdf`
- `Li_et_al_2010_LinUCB_Contextual_Bandit_News_Recommendation_WWW.pdf`
- `Li_et_al_2011_Unbiased_Offline_Evaluation_Contextual_Bandits_WSDM.pdf`
- `Zhao_et_al_2024_ExpeL_LLM_Experiential_Learners_AAAI.pdf`

### Presentation rewrite

`papers/edra_presentation.html` completely rewritten — 11 slides:

1. Title (with Edra avatar image)
2. Problem: "One Strategy Does Not Fit All" (3 profiles → 1 template → 5% response)
3. Solution: full EDRA loop SVG diagram (adapted from fig.jpg to dark theme)
4. Clustering: Profile Text → MiniLM → HDBSCAN → KNN Vote
5. Rules: 5-slot equalizer visualization
6. Self-Repair: CS score chart with recovery jump after revision
7. Booth Demo: real UI screenshot (test1.jpg)
8. Pipeline: LinkedIn URL → Pitch horizontal flow
9. Evaluation: three-level framework with status badges
10. Positioning: ExpeL vs LinUCB vs EDRA comparison table
11. Closing: 3 contribution icons + summary

Fixed slide 3 SVG overflow (880x520 → 880x410, red arrow path kept inside viewBox).

## What was NOT done

- Reading list items not yet read: Karanam et al. 2025 (gap confirmation)
- Actual Level 1 evaluation (silhouette computation)
- Propensity score reconstruction from Pipedrive campaign labels
- Tier 1 extraction completion (API budget)
- Presentation not yet opened in browser for full visual QA beyond slide 3 fix

## Key decisions

- **Doubly robust for Pipedrive** — pure replay (Li et al.) requires random data collection. Pipedrive data is biased by campaign assignment. DR (Dudik et al.) tolerates this bias.
- **ExpeL as primary competitor** — closest architectural parallel. EDRA's novelty = cluster-conditional rules vs ExpeL's flat insights.
- **Prequential for own outreach** — Gama et al.'s test-then-train protocol maps directly to EDRA's batch-by-batch learning.
- **LinUCB as formal baseline** — provides a non-LLM comparison point at both Level 2 and Level 3.

## Open questions

- [ ] How to reconstruct propensity scores from Pipedrive campaign assignment logic for the DR estimator?
- [ ] Is LinUCB implementable on Pipedrive features (job title, industry, region) or does it need numerical encoding?
- [ ] Presentation visual QA — need to check all 11 slides in browser, especially slides 2, 9, 10
- [ ] `people-14356779-662.csv` still not in `.gitignore` — contains 29K people PII

## Next session — entry points

1. Complete tier 1 Pipedrive extraction (remaining API budget ~120K tokens)
2. Visual QA of all 11 presentation slides in browser
3. Begin Level 1 evaluation: silhouette score on 502-profile embeddings
4. Add `people-14356779-662.csv` to `.gitignore`
5. Lemlist warm-up should be complete (~2026-05-26) — first outreach batch unblocked

See [[../00-home/current priorities]] for the full phase board.
