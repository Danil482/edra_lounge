"""EDRA FastAPI entry-point.

Run: `uvicorn backend.app:api --reload --port 8000`

All orchestration runs inside this process as asyncio tasks owned by
`Orchestrator` — no external scheduler (see TASK.md §6).

This module is the DI root: it picks the active ProfileSource implementation
(synthetic vs LinkedIn-RapidAPI, controlled by env vars), instantiates the
Orchestrator with it, and mounts the routers and the static frontend.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import PROJECT_ROOT
from backend.db import async_session_factory, init_db
from backend.orchestrator import Orchestrator
from backend.profile_source import ProfileSource
from backend.profile_source.synthetic import SyntheticProfileSource
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


def _build_profile_source() -> ProfileSource:
    """Phase 1A: synthetic only. Phase 3 will branch on LIVE_MODE / RAPIDAPI_KEY
    and return LinkedInRapidAPISource when live mode is enabled.
    """
    return SyntheticProfileSource()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    orch = Orchestrator(
        session_factory=async_session_factory,
        profile_source=_build_profile_source(),
    )
    await orch.start()
    app.state.orchestrator = orch
    try:
        yield
    finally:
        await orch.stop()


api = FastAPI(title="EDRA", version="0.1.0", lifespan=lifespan)

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
