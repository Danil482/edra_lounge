---
tags: [integration, openai, llm, phase-4]
date: 2026-05-13
---

# OpenAI is the third LLM mode added in Phase 4

OpenAI Chat Completions was added in Phase 4.2 as `LLM_MODE=openai`. It is the production choice for live booth demos — [[Ollama serves local inference for offline demos|Ollama]] is for offline, Anthropic is a cloud fallback.

## Configuration

- `LLM_MODE=openai`
- `OPENAI_API_KEY=<key>` (in `.env`, never committed)
- `OPENAI_MODEL=gpt-4o-mini` (default)

## Implementation

Goes through the shared [[Three LLM providers share one httpx client|httpx client]] — `backend/llm/client.py`. No OpenAI SDK. The `complete()` and `stream()` methods format the request as OpenAI Chat Completions JSON and parse the response directly.

## Validated

End-to-end test on 2026-04-29: real author URL → cache hit → OpenAI generates opener about "competitive pricing" → 5 unique LLM responses → terminate at interest=+5 = `accepted`.
