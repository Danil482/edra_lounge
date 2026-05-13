---
tags: [atlas, llm, httpx, openai, ollama, anthropic]
date: 2026-05-13
---

# Three LLM providers share one httpx client

All LLM calls go through `backend/llm/client.py` — no SDKs, only `httpx.AsyncClient`. This is an [[All orchestration stays inside asyncio|architectural invariant]].

## Three modes (via `LLM_MODE` env var)

| Mode | Endpoint | Default model | Use case |
|---|---|---|---|
| `local` | Ollama localhost:11434 | llama3.1:8b-instruct | Offline booth, no network |
| `remote` | Anthropic Messages API | claude-opus-4-7 | Cloud fallback |
| `openai` | OpenAI Chat Completions | gpt-4o-mini | Production live mode |

## Public API

- `complete(prompt, *, system)` — non-streaming, returns `str`
- `stream(prompt, *, system)` — async iterator of token chunks (used by [[SSE streams LLM reasoning tokens to the UI|revision streaming]])
- `render(template_name, **fields)` — loads `prompts/{name}.txt`, substitutes `{field}` placeholders

## Prompt templates (6 files in `backend/llm/prompts/`)

`induce.txt`, `opener.txt`, `continuation.txt`, `summary.txt`, `reflect.txt`, `cluster_label.txt`

On network errors the client logs a one-liner and the caller falls back to [[LLM generates by default templates are fallback|template-based generation]].

## Key files

- `backend/llm/client.py` — three-mode client
- `backend/llm/prompts/` — 6 prompt templates
