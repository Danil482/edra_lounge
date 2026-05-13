---
tags: [atlas, stack, python, fastapi, dependencies]
date: 2026-05-13
---

# Stack is Python 3.13 FastAPI with vanilla JS

## Backend

- **Python 3.13** — `datetime.utcnow()` deprecation sweep pending (tech debt)
- **FastAPI ≥0.110** + **uvicorn** — async ASGI server
- **SQLAlchemy ≥2.0** + **aiosqlite** — async ORM over SQLite
- **sentence-transformers ≥2.7** — MiniLM embeddings
- **hdbscan** + **umap-learn** + **scikit-learn** + **numpy** — clustering pipeline
- **httpx** — all external HTTP (LLM providers + LinkedIn RapidAPI)
- **sse-starlette** — server-sent events for revision streaming
- **pydantic ≥2.6** + **pydantic-settings** — config + schemas
- **pyyaml** — archetypes.yaml + seeded_run.yaml

## Frontend

- Vanilla HTML / JS / CSS — zero build step, zero npm
- Served as static files mounted at `/` in FastAPI

## Dev tools

- **pytest ≥8.0** + **pytest-asyncio** — 71 tests
- **ruff** — linting
- **make** — `demo`, `reset`, `test`, `booth`, `seed`, `install`

## Key files

- `pyproject.toml` — all dependencies
- `Makefile` — build/run targets
