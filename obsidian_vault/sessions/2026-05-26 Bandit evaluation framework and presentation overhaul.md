---
tags: [session, evaluation, bandit, presentation, methodology, soinspire]
date: 2026-05-26
---

# 2026-05-26 Bandit evaluation framework and presentation overhaul

Session focused on deep understanding of the multi-armed bandit evaluation framework, correcting the three-level evaluation methodology, updating the presentation, and positioning EDRA against SOInspire.

## What was done

### Bandit evaluation explainer document

Created `papers/bandit_evaluation_explainer.html` — comprehensive educational document in Russian covering:
- Multi-armed bandit problem (casino analogy, formal definition, regret, exploration vs exploitation)
- Contextual bandit extension (context, policy, counterfactual problem)
- Why standard ML evaluation fails for bandits (no train/test split, non-i.i.d., counterfactual)
- Replay method (Li et al. WSDM 2011) — why it doesn't work for biased Pipedrive data
- Inverse Propensity Scoring — importance weighting as intermediate step
- Direct Method — reward model prediction, bias problem
- Doubly Robust estimator (Dudik et al. ICML 2011) — full formula with color-coded 3-part breakdown, worked numerical examples
- LinUCB (Li et al. WWW 2010) — algorithm, UCB score, why it's the baseline
- Prequential evaluation (Gama et al. 2013) — test-then-train, fading factor
- EDRA-to-bandit mapping table (cluster=context, rule=arm, reply=reward)
- Three-level evaluation plan

Every formula has per-symbol explanation tables. Dark theme matching the presentation style.

### Evaluation methodology corrections

Three major corrections applied to both the explainer and presentation:

1. **Level 1 target changed**: from 502 research profiles to 976 Pipedrive outreach recipients. The 502 profiles were never contacted — no reward signal. Clustering must be evaluated on people with actual outcomes.

2. **Level 2 reframed**: not "personalization beats templates" (trivial, already known) but "does optimal strategy differ between clusters?" (interaction effect). Key baseline renamed from pi_expel to pi_best_single — if EDRA can't beat "always use the best single strategy for everyone", clustering adds nothing.

3. **Level 3 uses same data**: prequential simulation on same 976 rows in chronological batches. Not blocked on real outreach — simulated learning curve is sufficient for paper. Added "why this is NOT obvious" subsection with 5 failure modes.

### Strategy set narrowed

Removed `follow_up` (30) and `re_engagement` (21) from evaluation data — they're funnel stages, not first-contact strategies. Final set: `cold_template` (826), `cold_personal` (113), `feature_announcement` (37) = 976 rows total.

### Reward model clarified

Added subsection in explainer: reward model r̂(x, a) is logistic regression on (profile_embedding_384d + action_onehot_3d) → P(reply). NOT text generation, NOT semantic similarity. Simple binary classifier to fill in counterfactual rewards for DR estimator.

### Presentation updates (12 slides now)

- **Slide 3**: Cluster cloud wrapped in frame (was floating disconnected dots)
- **Slide 3**: Rule Store text and equalizer centered
- **Slide 3**: Consistency Monitor mini-chart removed (was ugly red line), clean text-only box
- **Slide 7**: Booth demo screenshot updated to current UI (edra_booth_screenshot.png)
- **Slide 9**: All three evaluation levels updated — corrected data counts (976), badges show dependency chain (NEEDS ENRICHMENT → AFTER LEVEL 1 → AFTER LEVEL 2), Level 2 reframed as interaction effect
- **Slide 11 (NEW)**: "Different Problems, Different Layers" — landscape comparison of SOInspire, ExpeL, LinUCB, EDRA across 6 dimensions (layer, optimizes, personalizes for, clusters, feedback, output)
- **Slide 12**: Closing (renumbered from 11)

### SOInspire positioning

Analyzed SOInspire (Farseev et al., SIGIR '26) — NOT a competitor but complementary work from same group. SOInspire solves "what to say" (content quality, CTR, author-side), EDRA solves "whom to say what" (strategy selection, recipient-side, cluster-conditional). New landscape slide makes this distinction explicit.

### Agent mapping documented

Discovered custom agents at `~/.claude/agents/` use `name:` frontmatter as `subagent_type` value. Saved mapping to memory: developer → `Senior Python Developer`, tester → `QA Engineer`, designer → `Frontend Designer`, planner → `Planner`. ~150 agents total across 12 subdirectories.

## What was NOT done

- LinkedIn enrichment for 635 Pipedrive profiles with URLs (still needed for meaningful clustering)
- Actual Level 1 evaluation (blocked on enrichment)
- DR estimator implementation
- Prequential simulation implementation
- Demo paper tex update with corrected evaluation framing
- Visual QA of all 12 presentation slides in browser
- Presentation and explainer files not committed (user's choice)

## Key decisions

- **Evaluate on Pipedrive people, not 502 research profiles** — research profiles have no reward signal, useless for evaluation
- **3 strategies, not 5** — follow_up and re_engagement removed as non-first-contact
- **Level 2 tests interaction effect, not personalization** — the question is whether optimal strategy differs by cluster, not whether personalization beats templates
- **Level 3 on same data** — prequential simulation on chronological batches of 976 rows, no need for live outreach for paper
- **SOInspire is complementary, not competing** — cite as related work from same group, different layer (content vs strategy)
- **pi_best_single replaces pi_expel as key baseline** — the relevant comparison is "cluster-conditional vs best single strategy for everyone"

## Open questions

- [ ] Will LinkedIn enrichment produce meaningful clusters on Pipedrive profiles? (first attempt: silhouette 0.177)
- [ ] How to reconstruct propensity scores from Pipedrive campaign assignment for DR estimator?
- [ ] Should feature_announcement (37 rows) be kept or merged with cold_template? Small sample.
- [ ] CTO response on defygroup.ai deployment (questions sent 2026-05-26)
- [ ] IRB requirement at Kazan Federal University

## Next session — entry points

1. LinkedIn enrichment for 635 profiles → re-cluster → Level 1 evaluation (silhouette + chi-squared)
2. If Level 1 passes: build reward model (LogReg) + DR estimator → Level 2
3. If Level 2 passes: prequential simulation → Level 3 learning curve
4. Visual QA of all 12 presentation slides in browser
5. Update demo paper tex with corrected evaluation framing
6. Commit presentation + explainer when satisfied with visual QA

See [[../00-home/current priorities]] for the full phase board.
