"""§14 acceptance: orchestrator loops must survive individual exceptions.

We verify by monkeypatching `advance_one_visit` to raise once, then return,
and asserting that the tick loop keeps running past the failure.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from backend.orchestrator import Orchestrator


@pytest.mark.asyncio
async def test_tick_loop_survives_exception(monkeypatch):
    orch = Orchestrator(session_factory=MagicMock())

    calls = {"n": 0}

    async def flaky_advance():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated tick failure")
        return None

    monkeypatch.setattr(orch, "advance_one_visit", flaky_advance)
    # Speed up the loop for the test
    monkeypatch.setattr("backend.orchestrator.settings.tick_seconds", 0.01)

    task = asyncio.create_task(orch._tick_loop())
    await asyncio.sleep(0.05)  # enough ticks for 2+ iterations
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert calls["n"] >= 2, "loop should have continued past the first exception"


@pytest.mark.asyncio
async def test_stop_cancels_all_tasks(monkeypatch):
    orch = Orchestrator(session_factory=MagicMock())
    monkeypatch.setattr("backend.orchestrator.settings.tick_seconds", 1.0)

    # Avoid loading seeded_run.yaml in unit test
    monkeypatch.setattr(orch, "_visits", __import__("collections").deque())

    await orch.start()
    assert len(orch._tasks) == 3
    await orch.stop()
    assert all(t.cancelled() or t.done() for t in orch._tasks)
