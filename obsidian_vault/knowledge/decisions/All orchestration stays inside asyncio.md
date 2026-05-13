---
tags: [decision, architecture, asyncio, invariant]
date: 2026-05-13
---

# All orchestration stays inside asyncio

**Decision**: no external orchestrators (Celery, Airflow, n8n, background workers). All loops run as `asyncio.create_task` inside the FastAPI process.

**Why**: the booth is a single-machine demo. Adding a task queue would increase deployment complexity for zero benefit. The three loops (tick, consistency, factory) are lightweight and cooperative — they yield on every `asyncio.sleep` and on every async DB/HTTP call.

**Consequence**: everything dies together when the process stops. This is acceptable for a demo — there is no persistent job state to recover. `make reset` starts clean.

**TASK.md reference**: §§2, 6, 12.

See [[EDRA runs three asyncio loops inside FastAPI]] for implementation details.
