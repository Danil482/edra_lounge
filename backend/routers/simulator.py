"""Simulator + drift control surface (TASK.md §8).

`POST /simulator/pause`                 — freeze / unfreeze the orchestrator tick loop
`POST /simulator/drift/{drift_id}`      — manually fire a scripted drift
`POST /simulator/inject_archetype`      — push a spawnable archetype to the queue
`POST /simulator/inject_contradiction`  — force a seeded rule below theta (demo theater)
`POST /simulator/reset_injection`       — undo the injected contradiction
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend import schemas
from backend.config import settings
from backend.memory import store
from backend.memory.ids import short_id


router = APIRouter(prefix="/simulator", tags=["simulator"])


class InjectIn(BaseModel):
    archetype_id: str


class PauseIn(BaseModel):
    paused: bool


class InjectContradictionIn(BaseModel):
    cluster_id: str | None = None
    n: int | None = None


@router.post("/pause")
async def pause(body: PauseIn, request: Request):
    request.app.state.orchestrator.paused = body.paused
    return {"paused": body.paused}


@router.post("/drift/{drift_id}")
async def fire_drift(drift_id: Literal["ai_bubble_pops", "postdoc_burnout"]):
    from backend.simulator import drift

    handler = drift.DRIFT_REGISTRY.get(drift_id)
    if handler is None:
        raise HTTPException(status_code=404, detail=f"unknown drift: {drift_id}")
    if callable(handler):
        handler()
    else:
        # GradualPostdocShift instance — advance one step.
        handler.advance()
    return {"ok": True, "drift": drift_id}


@router.post("/inject_archetype")
async def inject_archetype(body: InjectIn, request: Request):
    request.app.state.orchestrator.inject_archetype(body.archetype_id)
    return {"ok": True, "archetype_id": body.archetype_id}


@router.post("/inject_contradiction")
async def inject_contradiction(body: InjectContradictionIn, request: Request):
    orch = request.app.state.orchestrator
    n = body.n if body.n is not None else settings.cs_window

    async with orch.session_factory() as session:
        active_rules = await store.list_rules(session, status="active")

        if body.cluster_id is not None:
            target_cluster = body.cluster_id
            rule = next((r for r in active_rules if r.cluster_id == target_cluster), None)
            if rule is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"no active rule for cluster {target_cluster}",
                )
            cluster_eps = await store.episodes_for_cluster(session, target_cluster)
            if not cluster_eps:
                raise HTTPException(
                    status_code=404,
                    detail=f"cluster {target_cluster} has no episodes to seed from",
                )
        else:
            # No cluster supplied — pick the largest cluster that has both an
            # active rule and episodes to seed from (most episodes wins).
            best: tuple[int, schemas.Rule, list] | None = None
            for r in active_rules:
                eps = await store.episodes_for_cluster(session, r.cluster_id)
                if not eps:
                    continue
                if best is None or len(eps) > best[0]:
                    best = (len(eps), r, eps)
            if best is None:
                raise HTTPException(
                    status_code=404,
                    detail="no active rule with episodes to inject a contradiction into",
                )
            _, rule, cluster_eps = best
            target_cluster = rule.cluster_id

        donor = cluster_eps[0]

        slot_values = {s.name: s.value for s in rule.slots}
        failing_strategy = schemas.PitchStrategy(
            framing=slot_values["framing"],
            tone=slot_values["tone"],
            opener_type=slot_values["opener_type"],
            word_target=slot_values["word_target"],
            ask_size=slot_values["ask_size"],
        )

        injected_ids: list[str] = []
        now = datetime.utcnow()
        for _ in range(n):
            ep = schemas.Episode(
                id=short_id("eval_ep"),
                timestamp=now,
                day=donor.day,
                profile_id=donor.profile_id,
                cluster_id=target_cluster,
                pitch_strategy=failing_strategy,
                dialogue=[],
                final_interest=-3,
                outcome="rejected",
                summary="injected contradiction — current rule strategy now failing",
                summary_embedding=list(donor.summary_embedding),
                rule_applied_top=rule.id,
            )
            # Persist directly rather than via on_new_episode: that hook reclusters
            # and would reshuffle cluster_ids mid-demo, breaking the targeted rule.
            await store.save_episode(session, ep)
            injected_ids.append(ep.id)

    orch.injected_episode_ids.extend(injected_ids)
    orch.injected_rule_id = rule.id
    return {
        "ok": True,
        "cluster_id": target_cluster,
        "rule_id": rule.id,
        "injected_episode_ids": injected_ids,
        "n": n,
    }


@router.post("/reset_injection")
async def reset_injection(request: Request):
    orch = request.app.state.orchestrator

    deleted_episodes = 0
    deleted_revision: str | None = None
    restored_rule: str | None = None
    conflict_decision: str | None = None

    async with orch.session_factory() as session:
        deleted_episodes = await store.delete_episodes(session, orch.injected_episode_ids)

        if orch.injected_rule_id is not None:
            pending = await store.pending_revision_for_rule(session, orch.injected_rule_id)
            if pending is not None:
                await store.delete_revision(session, pending.id)
                await store.update_rule(session, orch.injected_rule_id, status="active")
                deleted_revision = pending.id
                restored_rule = orch.injected_rule_id
                if orch.active_revision_id == pending.id:
                    orch.active_revision_id = None
            else:
                resolved = await store.latest_revision_for_rule(session, orch.injected_rule_id)
                if resolved is not None and resolved.decision != "pending":
                    conflict_decision = resolved.decision

    orch.injected_episode_ids = []
    orch.injected_rule_id = None

    if conflict_decision is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"revision already resolved ({conflict_decision}); full accept-reversal "
                "is out of scope — run `make reset` to fully reseed."
            ),
        )

    return {
        "ok": True,
        "deleted_episodes": deleted_episodes,
        "deleted_revision": deleted_revision,
        "restored_rule": restored_rule,
    }
