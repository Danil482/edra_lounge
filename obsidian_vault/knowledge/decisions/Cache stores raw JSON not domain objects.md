---
tags: [decision, architecture, cache, linkedin]
date: 2026-05-13
---

# Cache stores raw JSON not domain objects

**Decision**: the LinkedIn disk cache (`data/linkedin_cache/<slug>.json`) stores the raw RapidAPI response, not parsed `Profile` objects.

**Why**: this lets the parser be iterated (fields added, extraction logic changed) without re-fetching from the API. RapidAPI quota is limited and expensive — each fetch burns quota units. Re-parsing is free.

**Consequence**: cache files are provider-specific JSON blobs. If the provider changes payload shape, old cache entries may fail to parse — but this is preferable to losing the raw data.

**Related**: [[LinkedIn fetch survived two provider sunsets]] — we went through three providers, and having raw responses let us debug parser issues against real data.
