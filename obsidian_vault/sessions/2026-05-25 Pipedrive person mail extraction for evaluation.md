---
tags: [session, evaluation, pipedrive, data-extraction, tooling]
date: 2026-05-25
---

# 2026-05-25 Pipedrive person mail extraction for evaluation

Data engineering session — analyzed 29K-person Pipedrive export, built person-targeted mail extraction pipeline, ran first test extraction. Goal: build evaluation dataset from historical outreach data.

## What was done

### Pipedrive people export analysis

1. **Analyzed `people-14356779-662.csv`** — 29,310 people from Pipedrive CRM. After excluding 151 somin.ai internal contacts:
   - Tier 1 (sent + reply): 4,556 people (2,065 with LinkedIn URL, 2,188 with job title)
   - Tier 2 (sent, no reply): 24,415 people (14,253 with LinkedIn URL)
   - Overall response rate: 16.3%

2. **Response rate analysis by campaign label** — significant variation:
   - AIGen_SG_Companies: 34.1%, AIGen_SG_Agency: 27.9%, UK_AGENCY: 14.0%
   - LEADS_VentFund: 11.4%, Outreach: 7.2%, PERSOCBEXP: 1.9%, Influencer: 0.6%
   - This variation supports the EDRA hypothesis: personalization by cluster has signal

3. **Assessed evaluation potential** — this data validates Level 1 (clustering quality) but not Level 2 (adaptive rules vs baselines) without strategy annotation from email content

### Tier CSV generation

Generated two lean CSV files in EDRA project `data/`:
- `eval_tier1_replied.csv` — 4,556 people sorted by last_email_sent descending
- `eval_tier2_no_reply.csv` — 24,415 people

Script: `edra-lounge/scripts/build_eval_tiers.py`

### Person-targeted extraction script

Wrote `EDRA/extract_person_mail.py` — new extraction approach:
- Input: CSV of people with email addresses
- Per person: search Pipedrive by email → get person_id → fetch `/persons/{id}/mailMessages`
- Output: CSV with outreach snippet, reply snippet, outcome, timestamps, thread count
- Reuses `BudgetTracker` and `MailExtractorClient` from existing `extract_outreach_mail.py`
- Resumable via `person_extraction_state.json`, `--limit` flag for test runs

### Bug found and fixed

`/persons/{id}/mailMessages` endpoint wraps each message in `{"object": "mailMessage", "data": {actual fields}}` — different structure from `/mailThreads/{id}/mailMessages`. First test run returned all `no_reply` outcomes with empty fields. Diagnosed with `debug_person_mail.py`, fixed unwrapping in `_fetch_person_mail`.

### API budget discovery

Pipedrive Premium (3 seats) actual daily budget: **270K tokens** (not 450K from formula). First extraction run: 150K tokens today, remainder 2026-05-26.

### Test extraction results (10 people)

8/10 successfully extracted with outreach + reply data. Three types of "first outreach" observed:
- Cold outreach ("Let's Connect", "Nice to meet you")
- Post-meeting follow-up ("Thank you for the call")
- Credential sharing ("Platform Access Credentials")
Post-extraction filtering needed to isolate true cold outreach.

### Global config.py read ban

Added three-level protection against reading config.py (contains hardcoded API keys):
- PreToolUse hook: `~/.claude/hooks/block-config-read.js`
- Global CLAUDE.md: `~/.claude/CLAUDE.md`
- Memory: feedback_no_read_config.md

## What was NOT done

- Full tier 1 extraction (running 150K tonight, remainder 2026-05-26)
- Tier 2 extraction (deferred — do after tier 1 complete)
- Strategy annotation from snippets
- Clustering quality evaluation (needs full extraction first)
- Full body text retrieval (would need extra `GET /mailMessages/{id}?include_body=1` calls)

## Key decisions

- **Person-targeted over thread-based extraction** — more efficient for known target list, costs ~60 tokens/person vs bulk thread crawl
- **Snippet sufficient for initial analysis** — full body stored on S3, not inline. Snippet gives ~220 chars which covers subject + opening line. Full body fetch deferred.
- **270K daily budget, not 450K** — empirically discovered, adjusts extraction timeline to 2 days for tier 1

## Open questions

- [ ] `people-14356779-662.csv` should go in `.gitignore` — contains PII for 29K people
- [ ] Post-extraction filtering criteria — what subject patterns identify cold outreach vs follow-ups vs credential-sharing?
- [ ] Whether to fetch full body text for strategy annotation (adds ~2 tokens/message, but needs separate API call per message)
- [ ] Tier 2 extraction scope — all 24K or sampled subset matched to tier 1 size?

## Next session — entry points

1. Complete tier 1 extraction (remaining ~120K tokens budget)
2. Analyze full tier 1 results — distribution of outcomes, subject patterns, snippet quality
3. Filter cold outreach vs follow-ups for evaluation dataset
4. Begin clustering quality evaluation (Level 1): embed profiles → HDBSCAN → reply rate by cluster
5. Lemlist warm-up should be complete (~2026-05-26) — first outreach batch unblocked

See [[../00-home/current priorities]] for the full phase board.
