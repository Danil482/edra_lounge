---
tags: [pattern, protocol, dependency-injection, testing]
date: 2026-05-13
---

# ProfileSource protocol enables dependency injection

The `ProfileSource` Protocol (defined in `backend/profile_source/__init__.py`) decouples the session lifecycle from concrete data sources.

## The protocol

Two methods:
- `async fetch(identifier: str) -> Profile` — fetch a visitor profile by identifier
- `source_kind: str` — property returning "synthetic" or "linkedin"

## Implementations

- **SyntheticProfileSource** — reads from `archetypes.yaml`, returns profiles per archetype ID
- **LinkedInRapidAPISource** — fetches from RapidAPI, caches to disk, parses to Profile

## Injection point

`app.py` lifespan decides which source to build based on `LIVE_MODE` env var, then stores it in `app.state.profile_source`. Routers access it via `request.app.state`.

## Testing benefit

Core modules (sessions, clustering, induction) only depend on the Protocol. Tests use `SyntheticProfileSource` or simple stubs — no RapidAPI mocks needed. Import isolation is enforced by [[LinkedIn source is import-isolated from core|test_profile_source.py]].
