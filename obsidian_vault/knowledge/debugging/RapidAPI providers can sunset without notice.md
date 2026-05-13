---
tags: [debugging, rapidapi, linkedin, resilience]
date: 2026-05-13
---

# RapidAPI providers can sunset without notice

**Problem**: during Phase 4 (2026-04-29), two LinkedIn data providers sunset within a single development session. `fresh-linkedin-profile-data` stopped responding mid-implementation; `linkedin-data-api` was dead by the time we switched to it.

**Symptoms**: HTTP 5xx or empty responses from previously-working endpoints. No deprecation notice in the RapidAPI dashboard.

**Resolution**: switched to `fresh-linkedin-scraper-api` (third provider). Hardened the parser against payload shape differences between providers — field names, nesting, and missing fields all vary.

**Lessons**:
1. Always cache raw API responses to disk — see [[Cache stores raw JSON not domain objects]]. This lets you iterate the parser without burning quota.
2. Parser must handle missing fields gracefully — any field can be absent or null.
3. Keep the mock path working — see [[Mock API key enables offline booth demos]]. When the API is down, the demo must still work.
4. Budget ~3 RapidAPI quota units for a dev session — don't test against live API more than necessary.
