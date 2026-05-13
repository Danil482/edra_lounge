---
tags: [debugging, linkedin, scraping, dataset]
date: 2026-05-13
---

# LinkedIn blocks WebFetch with HTTP 999

**Problem**: during Phase 6 dataset collection (2026-05-13), direct `WebFetch` calls to LinkedIn profile URLs return HTTP 999 — LinkedIn's anti-scraping response.

**Impact**: ~10-15 rows in `research_profiles_master.csv` have LinkedIn slugs inferred from search snippets rather than directly verified. All flagged Medium or Low confidence.

**Workaround**: verify profiles via non-LinkedIn public sources (lab team pages, conference bios, GitHub org pages, arxiv papers) and infer the LinkedIn slug from search results. The slug is used as a candidate identifier, not as a verified URL.

**Recommendation**: before any outreach, manually eyeball-click the flagged Medium/Low slugs in a browser. Known suspects: Tom Moor, Wes Gurnee, Tan Zhi Xuan, Roger Grosse, Stephen Casper, Jacob Steinhardt, Trenton Bricken, Ohad Shamir, Ronen Eldan, Hannaneh Hajishirzi.
