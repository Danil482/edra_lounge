---
tags: [session, evaluation, clustering, pipedrive, data-filtering, production-planning]
date: 2026-05-26
---

# 2026-05-26 Evaluation module and cold outreach clustering

Session focused on three areas: fixing Claude Code hook infrastructure, filtering Pipedrive outreach data for evaluation, and first clustering attempt on cold outreach profiles.

## What was done

### Claude Code hook fix

The `PreToolUse:Read` hook at `~/.claude/hooks/block-config-read.js` was missing (causing `node:internal/modules/cjs/loader` errors on every Read/Bash call). Created the script with correct protocol: exit 0 for allow (no stdout), exit 2 + `{"reason": "..."}` JSON for block. Blocks reads of `config.py` and `.env` files.

### Pipedrive budget tracker fix

Removed the 60% daily budget cap from `BudgetTracker` in EDRA project (`extract_outreach_mail.py` + `extract_person_mail.py`). `--budget N` now means exactly N tokens, not N*0.6. Default budget lowered from 450K to 270K to match real API daily limit. Changes are in the EDRA project, not this repo.

### Cold outreach filtering

Created `evaluation/filter_cold_outreach.py` — filters 4,536 Pipedrive tier 1 rows down to 1,027 cold outreach rows. Five outreach types classified: `cold_template` (826), `cold_personal` (113), `feature_announcement` (37), `follow_up` (30), `re_engagement` (21).

Exclusion rules remove: Re:/Fw: threads, platform credentials, meeting follow-ups, Marketing Mondays invitations, invoices, onboarding, internal communications. Empty-subject rows (1,543) examined — only 6 had snippets (all Marketing Mondays), rest were empty shells.

### Evaluation module created as standalone

Moved `evaluation/` out of `backend/` to project root — separate module, not part of the FastAPI app. Structure:
- `evaluation/__init__.py`
- `evaluation/filter_cold_outreach.py` — Pipedrive data filtering
- `evaluation/cluster_outreach.py` — MiniLM embeddings + HDBSCAN + silhouette + strategy analysis
- `evaluation/data/` — generated CSVs and embeddings (gitignored)

### First clustering attempt

Ran HDBSCAN on `job_title + organization + labels` embeddings (MiniLM 384-dim). Results: 3 clusters, silhouette 0.177 — essentially no meaningful structure found. One mega-cluster (788 samples) and two clusters of empty-feature rows. Root cause: features too sparse without LinkedIn profile enrichment.

### Production deployment discussion

Discussed deploying EDRA demo on defygroup.ai (3rd button). Key conclusions:
- Blocker zero: need access to site code and founder approval (CTO questions sent)
- Realistic path: iframe/popup with microservice on own domain
- SQLite OK for demo-level traffic; Postgres when real load appears
- Prompt injection defence needed before public exposure
- GDPR consent required for email storage
- Rate limiter on RapidAPI calls essential

### Evaluation methodology explained

Detailed walkthrough of how to evaluate EDRA using Pipedrive data:
1. Build context embeddings from person features
2. Cluster with HDBSCAN
3. Compute strategy effectiveness per cluster (reply rates)
4. Compare policies: uniform vs random vs ExpeL-flat vs EDRA cluster-conditional
5. Off-policy evaluation via doubly robust estimator (Dudik et al.)

Key insight: tier 2 (24K no-reply) not needed — tier 1 already contains both outcomes (841 reply, 186 no_reply within 1,027 cold outreach rows). Biased sample, but relative policy comparison is valid.

## What was NOT done

- LinkedIn enrichment of 635 profiles with URLs (deferred to future session)
- Re-clustering with enriched features
- Level 1 silhouette score on good clusters (blocked on better features)
- Strategy x Cluster chi-squared significance tests
- Off-policy evaluation implementation (doubly robust estimator)
- Presentation visual QA (11 slides)
- `people-14356779-662.csv` still not in `.gitignore` (PII file)

## Key decisions

- **Evaluation module is standalone** — `evaluation/` at project root, not inside `backend/`. Clean separation between demo app and research evaluation.
- **Tier 2 extraction not needed** — the 1,027 tier 1 rows contain both reply and no_reply outcomes. Biased sample acknowledged but sufficient for relative comparison.
- **LinkedIn enrichment next** — current features (job_title/org/labels) too sparse for meaningful clustering. 635/1027 rows have LinkedIn URLs.
- **Production deployment blocked** — questions sent to CTO, awaiting response before planning further.
- **Generated data gitignored** — CSVs and .npy embeddings are regenerable from scripts, not committed.

## Open questions

- [ ] CTO response on defygroup.ai integration (questions sent 2026-05-26)
- [ ] Will LinkedIn enrichment produce better clusters, or is the data fundamentally too homogeneous?
- [ ] Should `outreach_subject` be included in embedding features? It adds strategy signal but mixes action into context.
- [ ] IRB requirement at Kazan Federal University — still undecided

## Next session — entry points

1. LinkedIn enrichment for 635 profiles with URLs → re-cluster
2. If clusters improve: strategy x cluster significance tests + policy comparison
3. Visual QA of presentation (11 slides in browser)
4. Add `people-14356779-662.csv` to `.gitignore`
5. CTO response → production deployment planning
6. Lemlist warm-up should be complete — first outreach batch preparation

See [[../00-home/current priorities]] for the full phase board.
