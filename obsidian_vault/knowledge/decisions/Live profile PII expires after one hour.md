---
tags: [decision, privacy, purge, invariant]
date: 2026-05-13
---

# Live profile PII expires after one hour

**Decision**: non-synthetic profiles are purged from the database after `ttl_seconds` (default 3600 = 1 hour). Synthetic profiles are kept forever.

**Why**: the booth fetches real LinkedIn data from real visitors. Retaining PII indefinitely creates a compliance risk. The one-hour window covers the demo session; after that, the data is gone.

**Implementation**: `purge_expired_live_profiles()` runs in the factory loop every 30 seconds. It deletes `ProfileRow` entries where `source_kind != "synthetic"` and `fetched_at + ttl_seconds < now`.

**Enforcement**: `tests/test_privacy_purge.py` verifies that synthetic profiles survive and expired live profiles are deleted.

See [[EDRA runs three asyncio loops inside FastAPI]] for the factory loop.
