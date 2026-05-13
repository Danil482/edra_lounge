---
tags: [decision, architecture, llm, httpx, invariant]
date: 2026-05-13
---

# No LLM SDKs only httpx

**Decision**: all three LLM providers (Ollama, Anthropic, OpenAI) are called via `httpx.AsyncClient` directly. No `openai` SDK, no `anthropic` SDK.

**Why**: a shared interface (`complete` / `stream` / `render`) across three providers is simpler to maintain than three SDK wrappers with different error models, retry logic, and async patterns. The request/response format for each provider is ~20 lines of JSON formatting.

**Consequence**: when a provider changes their API shape, we fix one file (`backend/llm/client.py`). No SDK version pinning surprises.

**Trade-off**: no automatic retries, no token counting, no built-in rate limiting from SDKs. Acceptable for a demo with low request volume.

See [[Three LLM providers share one httpx client]] for the implementation.
