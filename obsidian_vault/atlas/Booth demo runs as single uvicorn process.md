---
tags: [atlas, deploy, booth, uvicorn]
date: 2026-05-13
---

# Booth demo runs as single uvicorn process

There is no multi-service deployment. The entire application is one `uvicorn` process serving both the API and the static frontend.

## Run modes

| Command | What happens |
|---|---|
| `make demo` | `uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000` — dev mode with auto-reload |
| `make booth` | `make reset` + uvicorn + Chrome kiosk full-screen — deterministic demo, no devtools |
| `make reset` | Wipe SQLite DB + re-seed from `seeded_run.yaml` — acceptance: <5s |

## Env vars that change behaviour

- `LIVE_MODE=true` — switches from synthetic auto-play to operator-driven LinkedIn sessions
- `RAPIDAPI_KEY=<real>` — enables live LinkedIn fetch (see [[Mock API key enables offline booth demos]])
- `LLM_MODE=openai|local|remote` — selects LLM provider (see [[Three LLM providers share one httpx client]])

## What is NOT needed

- No Docker, no Kubernetes, no reverse proxy
- No external database (SQLite file, `edra_lounge.db`)
- No background workers (see [[EDRA runs three asyncio loops inside FastAPI]])
- No CDN or asset pipeline (static files served from FastAPI mount)

## Key files

- `Makefile` — all run targets
- `backend/config.py` — env var definitions
