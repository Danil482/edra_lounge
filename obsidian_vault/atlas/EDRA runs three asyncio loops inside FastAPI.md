---
tags: [atlas, architecture, asyncio, orchestrator]
date: 2026-05-13
---

# EDRA runs three asyncio loops inside FastAPI

The backend has no external orchestrators — no Celery, no Airflow, no workers. All background work runs as three `asyncio.create_task` loops inside the FastAPI process, coordinated by `backend/orchestrator.py`.

## The three loops

| Loop | Interval | Purpose |
|---|---|---|
| **Tick** | 20s (configurable) | Spawns one synthetic visit per tick; no-op in live mode. Advances game clock, fires scheduled [[RapidAPI providers can sunset without notice\|drift events]] on day 3 @ 10:00 |
| **Consistency** | 10s | Computes CS per active rule via [[Preference function maps strategy to interest delta\|monitor formula]]. If `should_revise` → creates Revision row for [[SSE streams LLM reasoning tokens to the UI\|SSE streaming]] |
| **Factory** | 30s | Detects clusters without rules → spawns Agent stub. Also runs `purge_expired_live_profiles` — see [[Live profile PII expires after one hour]] |

Each loop wraps its body in `try/except` so a single-iteration failure does not kill the loop.

## Reactive hook

`on_new_episode(episode)` fires after every episode persist:
1. Re-clusters on every Nth episode (`recluster_every=3`)
2. Checks induction eligibility per cluster
3. Falls back to mode-of-slots induction when LLM is offline

This hook is the bridge between the session lifecycle and the background loops — see [[on_new_episode hook bridges the three async loops]].

## Key files

- `backend/orchestrator.py` — loop definitions + reactive hook
- `backend/app.py` — lifespan creates and starts the orchestrator
