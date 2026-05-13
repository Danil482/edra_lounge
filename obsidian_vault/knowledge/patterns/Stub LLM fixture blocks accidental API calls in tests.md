---
tags: [pattern, testing, fixtures, llm]
date: 2026-05-13
---

# Stub LLM fixture blocks accidental API calls in tests

The test suite uses an autouse `stub_llm` fixture that monkeypatches `backend.pitch.generate.llm.complete` and `backend.sessions.lifecycle.llm.complete` to raise an error if called.

## Why

Tests must never hit real LLM APIs — this would be slow, flaky, and costly. The stub ensures that any test accidentally reaching the LLM path fails loudly rather than silently burning OpenAI credits.

## Other test patterns

- **`db_factory`** (async) — in-memory SQLite + `Base.metadata.create_all` for isolation per test
- **`reset_store`** (autouse) — clears `session_store` between tests
- **`monkeypatch`** — used to speed up `tick_seconds`, inject failures, replace methods

## Test coverage (71 tests as of 2026-04-29)

| File | Focus |
|---|---|
| `test_orchestrator.py` | Loop resilience, task cancellation |
| `test_pitch.py` | Strategy assembly (static/hybrid/improvise) |
| `test_sessions.py` | Session lifecycle, interest termination |
| `test_profile_source.py` | Protocol conformance, import-graph isolation |
| `test_privacy_purge.py` | TTL-based PII deletion |
| `test_preferences.py` | Preference/tone functions |
