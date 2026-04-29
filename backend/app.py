"""EDRA FastAPI entry-point.

Run: `uvicorn backend.app:api --reload --port 8000`

All orchestration runs inside this process as asyncio tasks owned by
`Orchestrator` — no external scheduler (see TASK.md §6).

This module is the DI root: it picks the active ProfileSource implementation
(synthetic vs LinkedIn-RapidAPI, controlled by env vars), instantiates the
Orchestrator with it, and mounts the routers and the static frontend.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


# App-level logging so module loggers (LLM client, pitch generator, profile
# source) actually surface — without this, INFO/WARNING from our code is
# swallowed and only uvicorn's access log appears on stdout.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from backend.config import PROJECT_ROOT, settings
from backend.db import async_session_factory, init_db
from backend.orchestrator import Orchestrator
from backend.profile_source import ProfileSource
from backend.profile_source.linkedin_rapidapi import LinkedInRapidAPISource
from backend.profile_source.synthetic import SyntheticProfileSource
from backend.routers import (
    clusters,
    episodes,
    factory,
    reflections,
    revisions,
    rules,
    sessions,
    simulator,
    state,
)


def _build_profile_source() -> ProfileSource:
    """Pick the live or synthetic implementation based on env config.

    The orchestrator and the sessions router both read `app.state.profile_source`,
    which is set once here on startup so swapping the implementation only
    requires bouncing the process. Live mode also gets a disk cache so repeated
    fetches of the same URL during dev/prep don't burn the 50/mo RapidAPI quota.
    """
    if getattr(settings, "live_mode", False) and getattr(settings, "rapidapi_key", ""):
        return LinkedInRapidAPISource(
            api_key=settings.rapidapi_key,
            cache_dir=PROJECT_ROOT / "data" / "linkedin_cache",
        )
    return SyntheticProfileSource()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    profile_source = _build_profile_source()
    app.state.profile_source = profile_source

    orch = Orchestrator(
        session_factory=async_session_factory,
        profile_source=profile_source,
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

api.include_router(sessions.router)
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
