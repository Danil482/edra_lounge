---
tags: [session, evaluation, chi-squared, statistics, reorganization, tier2, deployment]
date: 2026-05-28
---

# 2026-05-28 Chi-squared test and evaluation reorganization

Statistical validation session: ran chi-squared independence tests on 804 tier-1 rows, reorganized evaluation module by levels, fixed tier 2 extraction script, drafted CTO deployment request.

## What was done

### Chi-squared independence tests on tier-1 data

Created `evaluation/level1_clustering/chi_squared_test.py`. Three tests on 804 rows (excluding noise):

1. **Cluster × Outcome**: χ²=7.18, p=0.208, V=0.095 — NOT significant. Reply rates across clusters (72-83%) too close within tier-1 cohort.
2. **Strategy × Outcome**: χ²=81.31, p≈0, V=0.318 (medium effect) — SIGNIFICANT. cold_personal 97%, warm_intro 93%, cold_template 77%, follow_up 57%, feature_announcement 31%.
3. **Cluster × Strategy**: χ²=58.76, p=0.00001, V=0.135 — SIGNIFICANT. Strategy distribution is confounded with cluster assignment (some clusters got more personal outreach).

Key insight: cluster effect is either absent or masked by uneven strategy allocation. Tier-2 data (24K no-reply contacts) is essential to disentangle.

### Evaluation module reorganized by levels

Moved scripts into level-based subdirectories:
- `level0_data/` — filter_cold_outreach, filter_autoreplies (data preparation)
- `level1_clustering/` — cluster_outreach, cluster_production, chi_squared_test (clustering quality)
- `level2_policy/` — placeholder (reward model + DR estimator)
- `level3_learning/` — placeholder (prequential simulation)

All data paths updated. `evaluation/data/` stays shared at root level. Git history preserved via `git mv`.

### Tier 2 extraction script fixed

Fixed `EDRA/extract_person_mail.py`:
1. State file now derived from input filename (`person_extraction_state_{stem}.json`) — tier 1 and tier 2 states don't mix.
2. Added `--state` CLI parameter for explicit override.
3. Added `_retry_get()` with 3 retries + exponential backoff (1s, 2s, 4s) for transient httpx errors (RemoteProtocolError, ConnectError, ReadTimeout, ConnectTimeout). Previously crashed on Pipedrive connection drops.

Tier 2 extraction started: 762/24,415 processed before crash (now fixed). Budget: 200K tokens/run ≈ 3,300 people.

### Deployment — CTO message drafted

Drafted concise message for CTO requesting:
- Small server (1 vCPU, 512MB) or billing account for fly.io/Railway
- Subdomain `edra.defygroup.ai`
- Write access to `defygroup-cloud/website` repo

Defy website analysis: pure HTML/CSS/JS on Vercel, single `index.html` with base64 assets. Variant B (embed their landing into our demo) is simpler than iframe integration.

User decided to postpone sending the message.

## What was NOT done

- Tier 2 data integration into evaluation (extraction in progress, ~5 days at 270K/day)
- Level 2: reward model (LogReg) + DR estimator
- Level 3: prequential simulation
- Overleaf compilation check
- CTO message not sent yet
- Dockerization

## Key decisions

- **Chi-squared on tier-1 alone is inconclusive for cluster effect** — strategy effect is real and strong, but cluster effect needs tier 2 to surface
- **Evaluation module organized by level** — matches the three-level framework from literature review
- **Tier 2 extraction state isolated per input file** — prevents cross-contamination between extraction runs
- **Deployment variant B** — embed Defy landing into our demo, deploy as single service on fly.io/Railway

## Open questions

- [ ] Will chi-squared cluster×outcome become significant after tier 2 integration? Current p=0.208 might flip with 24K no-reply rows diluting the inflated rates
- [ ] CTO response on server resources — when to send the message?
- [ ] Tier 2 extraction budget: run full 24K (5.4 days) or sample subset?
- [ ] 13 cells with expected frequency <5 in cluster×strategy test — merge small clusters/strategies for cleaner test?

## Next session — entry points

1. Continue tier 2 extraction (762/24,415 done, retry fix applied)
2. After tier 2: rerun chi-squared with combined data
3. Build reward model (LogReg) + DR estimator → Level 2
4. Prequential simulation → Level 3
5. Dockerize for deployment (Dockerfile + docker-compose.yml)
6. Send CTO deployment request when ready

See [[../00-home/current priorities]] for the full phase board.
