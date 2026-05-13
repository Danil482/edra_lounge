---
tags: [integration, linkedin, rapidapi, live-mode]
date: 2026-05-13
---

# LinkedIn fetch survived two provider sunsets

The booth fetches real visitor profiles from LinkedIn via RapidAPI. The current provider is the third one — two prior providers sunset during development.

## Provider history

1. **`fresh-linkedin-profile-data`** — Phase 4.1 original, died during implementation
2. **`linkedin-data-api.p.rapidapi.com`** — Phase 4.2 first replacement, sunset 2026-04-29
3. **`fresh-linkedin-scraper-api`** — current, working as of 2026-04-29

## How it works

1. Operator enters a LinkedIn URL or vanity handle
2. `_username_from_input()` normalises to canonical slug
3. Two RapidAPI calls: profile data + recent posts
4. Response cached to disk as raw JSON — see [[Cache stores raw JSON not domain objects]]
5. Parser extracts: name, role, domain, seniority, recent_signals, avatar_url
6. If `RAPIDAPI_KEY=mock` → short-circuits to hand-crafted author profile — see [[Mock API key enables offline booth demos]]

## Lessons learned

See [[RapidAPI providers can sunset without notice]] — the parser must be hardened against payload shape changes.

## Key files

- `backend/profile_source/linkedin_rapidapi.py` — fetch + parse + cache
- `backend/profile_source/__init__.py` — Protocol definition
