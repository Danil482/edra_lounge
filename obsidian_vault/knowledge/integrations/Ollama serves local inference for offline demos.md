---
tags: [integration, ollama, llm, offline]
date: 2026-05-13
---

# Ollama serves local inference for offline demos

`LLM_MODE=local` (the default) routes all LLM calls to a local Ollama instance at `localhost:11434`. This is the only mode that requires zero network access.

## Configuration

- `OLLAMA_BASE_URL=http://localhost:11434`
- `OLLAMA_MODEL=llama3.1:8b-instruct`

## Trade-offs

- **Pro**: booth works without internet, no API costs, no key management
- **Con**: requires Ollama installed locally (the user does not use this during dev — see [[Mock API key enables offline booth demos]])
- When Ollama is unreachable, the client logs an error and pitch generation falls back to [[LLM generates by default templates are fallback|templates]]

## Note

The dev environment does not run Ollama — the user is [[Mock API key enables offline booth demos|pragmatic about external deps]] and uses `RAPIDAPI_KEY=mock` + `LLM_MODE=openai` for development.
