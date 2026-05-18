---
tags: [decision, outreach, email, lemlist]
date: 2026-05-18
---

# Lemlist replaces Resend for outreach delivery

Decided 2026-05-18 to switch from Resend API to Lemlist for outreach email delivery.

## Why Lemlist

- **Lemwarm** — built-in domain warm-up (peer-to-peer network, 3-4 weeks to full warm-up)
- **Email Finder** — waterfall enrichment, 60-80% hit rate for LinkedIn profiles (vs 17% from web-search)
- **Webhooks** — real-time callbacks when recipients reply, enabling automated response classification
- **Unsubscribe management** — out of the box, important for research ethics / IRB compliance
- **REST API** — full programmatic control: create campaigns, add leads, trigger sends, track activities
- Partners (Defy founders) already use Lemlist — may share a warmed domain/account

## Pricing

Free trial: 200 credits (= 40 email lookups at 5 credits each). Sending is free (no credits). Email Pro plan: $69-79/user/month for API access + Lemwarm.

## Credit budget (200 free)

- 40 priority profiles prepared in `data/research_profiles/lemlist_enrichment_priority.csv`
- All High confidence, Research segment, academic roles (highest discovery probability)
- Combined with 65 existing emails = enough for 4-5 batches of 20

## Open: warmed domain

Investigating whether Defy founders' existing Lemlist account has a warmed domain we can use. This would skip the 3-4 week warm-up period — critical given the June 11 demo paper deadline.

## What this replaces

- `backend/outreach/sender.py` (Resend API) — will be rewritten for Lemlist API
- Resend domain verification blocker — no longer relevant if using Lemlist with founders' account

See also: [[Automated email for outreach not LinkedIn DM]], [[../business/Founder answers are needed to fix prompt hallucinations]]
