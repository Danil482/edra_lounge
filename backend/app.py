"""EDRA Lounge FastAPI entry-point.

Run: `uvicorn backend.app:api --reload --port 8000`

All orchestration runs inside this process as asyncio tasks owned by
`Orchestrator` — no external scheduler (see TASK.md §6).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import PROJECT_ROOT
from backend.db import async_session_factory, init_db
from backend.orchestrator import Orchestrator
from backend.routers import (
    clusters,
    episodes,
    factory,
    reflections,
    revisions,
    rules,
    simulator,
    state,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    orch = Orchestrator(async_session_factory)
    await orch.start()
    app.state.orchestrator = orch
    try:
        yield
    finally:
        await orch.stop()


api = FastAPI(title="EDRA Lounge", version="0.1.0", lifespan=lifespan)

api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

api.include_router(episodes.router)
api.include_router(clusters.router)
api.include_router(rules.router)
api.include_router(revisions.router)
api.include_router(reflections.router)
api.include_router(factory.router)
api.include_router(simulator.router)
api.include_router(state.router)


@api.get("/health")
async def health():
    return {"status": "ok"}


# Serve the frontend at / — mounted last so it doesn't shadow API routes.
frontend_dir = PROJECT_ROOT / "frontend"
if frontend_dir.exists():
    api.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
