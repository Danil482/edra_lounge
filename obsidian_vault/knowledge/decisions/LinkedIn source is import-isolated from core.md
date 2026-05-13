---
tags: [decision, architecture, isolation, testing, invariant]
date: 2026-05-13
---

# LinkedIn source is import-isolated from core

**Decision**: no core module imports `profile_source/linkedin_rapidapi`. The LinkedIn source is injected via dependency injection at startup (`app.py` lifespan), not imported directly.

**Why**: the LinkedIn integration is a volatile, external-API-dependent module. Isolating it means core logic (clustering, induction, sessions) can be tested without RapidAPI mocks and without risking accidental API calls.

**Enforcement**: `tests/test_profile_source.py` scans the import graph and fails if any core module references the concrete LinkedIn source.

**Pattern**: the `ProfileSource` Protocol defines the interface — see [[ProfileSource protocol enables dependency injection]].
