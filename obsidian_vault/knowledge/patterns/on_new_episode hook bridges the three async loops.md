---
tags: [pattern, architecture, reactive, orchestrator]
date: 2026-05-13
---

# on_new_episode hook bridges the three async loops

The `on_new_episode(episode)` method on the Orchestrator is a reactive hook that fires after every episode is persisted. It is the bridge between the request-driven session lifecycle and the background async loops.

## What it does (in order)

1. **Re-cluster** — if episode count hits the `recluster_every` threshold (default 3), runs full HDBSCAN; otherwise assigns to nearest centroid
2. **Check induction** — per cluster, checks eligibility (`size >= n_min` and `success_ratio >= theta_induce`); if eligible and no active rule exists, induces via LLM
3. **Fallback induction** — if LLM call fails, uses mode-of-slots (most common slot value per cluster) as a rule

## Why a hook and not a loop

Sessions are driven by HTTP requests (operator clicks), not by a timer. The hook ensures that the EDRA learning cycle (cluster → induce → monitor → revise) advances immediately after each conversation, not on the next tick.

## Connections

- Called from `end_session()` in `backend/sessions/lifecycle.py`
- Triggers work that the consistency loop and factory loop consume downstream
- See [[EDRA runs three asyncio loops inside FastAPI]] for the full loop architecture
