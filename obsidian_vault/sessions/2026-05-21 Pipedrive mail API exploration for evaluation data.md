---
tags: [session, evaluation, pipedrive, mail-api, data-extraction]
date: 2026-05-21
---

# 2026-05-21 Pipedrive mail API exploration for evaluation data

Exploration session — no code in edra-lounge. All scripts written in the EDRA project (`C:\Users\dania\PycharmProjects\EDRA`). Goal: determine whether Pipedrive mail API can provide historical outreach data for EDRA evaluation (Level 2 — off-policy evaluation via replay method).

## What was done

### Pipedrive mail API exploration

1. **Reviewed existing Pipedrive integration** in EDRA project — `ingestion/pipedrive_api.py` covers deals, stages, pipelines, deal flow. No mail endpoints implemented.

2. **Documented Pipedrive mail API** — 6 endpoints found:
   - `GET /v1/mailbox/mailThreads` — list threads by folder (sent/inbox/drafts/archive)
   - `GET /v1/mailbox/mailThreads/{id}/mailMessages` — messages in a thread
   - `GET /v1/mailbox/mailMessages/{id}?include_body=1` — single message with full HTML body
   - `GET /v1/deals/{id}/mailMessages` — deal-linked mail
   - `GET /v1/persons/{id}/mailMessages` — person-linked mail
   - Key fields: `sent_flag` (1=sent, 0=received), `snippet` (~220 chars), `body` (full HTML), `from`/`to` with `linked_person_id`

3. **Wrote `explore_pipedrive_mail.py`** — discovery script hitting 5 endpoint variants, printing raw JSON. Confirmed API returns usable data.

4. **Wrote `extract_outreach_mail.py`** — full extraction pipeline:
   - Paginates all sent threads, fetches messages per thread
   - Identifies outreach (first `sent_flag=1` from `@somin.ai`) and reply (first `sent_flag=0` from external)
   - Filters: lemwarmup warm-up emails, internal-only threads
   - Outputs CSV: person_name, person_email, linked_person_id, outreach_snippet, reply_snippet, outcome, timestamps
   - Resumable via `data/mail_extraction_state.json`
   - 60% daily budget cap via `--budget` CLI arg (Pipedrive rate limits: burst per 2s + daily token budget)
   - Fixed bug: `x-daily-requests-left` header not returned on GET requests — switched to explicit budget tracking

5. **Extracted 64 rows** from first partial run before manual stop (budget display was broken before fix).

6. **Analyzed deals CSV** (`deals-14356779-661.csv`) — 63 active enterprise deals. Lead sources: Conference outreach (18), Personal Referral (11), LinkedIn Automation (7), Conference Networking (7), Partner Intro (7), Email Outreach (5).

### Data quality assessment

Identified three problems with the extracted mail data for evaluation:
- **Selection bias**: active deals only — no negative examples (lost/archived)
- **WhatsApp black hole**: many conversations happen outside Pipedrive email
- **Low strategy variation**: most emails are credential-sharing and scheduling, not varied outreach pitches

## What was NOT done

- No code changes in edra-lounge
- No profile enrichment via `GET /persons/{id}` — deferred pending data quality decision
- Extraction not completed — stopped at 64 rows, needs re-run with fixed budget tracking
- No evaluation pipeline built yet

## Key decisions

- **Thread-based extraction** (not person-based) — more efficient, avoids N+1 API calls per contact
- **Explicit budget cap** (`--budget` CLI arg) because `x-daily-requests-left` header missing on GET
- **Stage progression as reward signal** may be better than email reply — captures WhatsApp interactions indirectly

## Open questions

- [ ] What Pipedrive plan and how many seats? Needed to set correct `--budget` value
- [ ] Is this Philipp's data or the whole company CRM?
- [ ] Should we also pull archived/lost deals for negative examples?
- [ ] Are the credential-sharing emails worth filtering out, or should we only extract first-contact pitches?
- [ ] WhatsApp gap — is it acceptable to acknowledge this limitation, or does it invalidate the email-based evaluation?
- [ ] Leaked passwords in CSV snippets — need to sanitize before any sharing

## Next session — entry points

1. Re-run `extract_outreach_mail.py` with correct `--budget` value and `--reset` to get clean data
2. Filter extraction to first-contact emails only (skip credential-sharing, scheduling)
3. Add archived/lost deals to build negative examples
4. Decide: email-reply outcome vs. stage-progression outcome for evaluation
5. If stage progression: use existing EDRA ingestion (`pipedrive_api.py`) which already has won/lost/stalled
6. Profile enrichment via `GET /persons/{id}` for context features
7. Welcome message + Accept/Decline buttons (frontend, carried over from previous session)

See [[../00-home/current priorities]] for the full phase board.
