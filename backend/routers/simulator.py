"""Simulator + drift control surface (TASK.md §8).

`POST /simulator/pause`                 — freeze / unfreeze the orchestrator tick loop
`POST /simulator/drift/{drift_id}`      — manually fire a scripted drift
`POST /simulator/inject_archetype`      — push a spawnable archetype to the queue
`POST /simulator/inject_contradiction`  — force a seeded rule below theta (demo theater)
`POST /simulator/reset_injection`       — undo the injected contradiction
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend import schemas
from backend.config import settings
from backend.memory import store
from backend.memory.ids import short_id
from backend.seed_from_eval import STRATEGY_TO_RULE


router = APIRouter(prefix="/simulator", tags=["simulator"])

SLOT_NAMES = ["framing", "tone", "opener_type", "word_target", "ask_size"]


def _slot_diff_count(a: dict[str, str], b: schemas.PitchStrategy) -> int:
    return sum(1 for name in SLOT_NAMES if a[name] != getattr(b, name))


def _strategy_from_slots(slots: dict[str, str]) -> schemas.PitchStrategy:
    return schemas.PitchStrategy(**{name: slots[name] for name in SLOT_NAMES})


def _pick_alternative_strategy(
    cluster_eps: list[schemas.Episode],
    current: schemas.PitchStrategy,
) -> schemas.PitchStrategy:
    """The honest 'emerging winner'. Rank strategies present in the cluster's
    real episodes by accept rate and take the highest-rate one that differs from
    the current rule in >=2 slots. If the cluster's data offers no such strategy,
    fall back to the highest-rate STRATEGY_TO_RULE entry differing in >=2 slots.
    Guarantees a proposed rule that visibly differs from the current one."""
    stats: dict[tuple[str, ...], list[int]] = defaultdict(lambda: [0, 0])
    for ep in cluster_eps:
        ps = ep.pitch_strategy
        key = tuple(getattr(ps, name) for name in SLOT_NAMES)
        stats[key][1] += 1
        if ep.outcome == "accepted":
            stats[key][0] += 1

    ranked = sorted(
        stats.items(),
        key=lambda kv: (kv[1][0] / kv[1][1] if kv[1][1] else 0.0, kv[1][1]),
        reverse=True,
    )
    for key, _counts in ranked:
        slots = dict(zip(SLOT_NAMES, key))
        if _slot_diff_count(slots, current) >= 2:
            return _strategy_from_slots(slots)

    for slots in STRATEGY_TO_RULE.values():
        if _slot_diff_count(slots, current) >= 2:
            return _strategy_from_slots(slots)

    # Theoretically unreachable: the 7 seeded strategies span enough variation
    # that at least one differs in >=2 slots from any single current rule.
    raise HTTPException(
        status_code=409,
        detail="no alternative strategy differs from the current rule in >=2 slots",
    )


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
        failing_strategy = _strategy_from_slots(slot_values)
        winning_strategy = _pick_alternative_strategy(cluster_eps, failing_strategy)

        injected_ids: list[str] = []
        # Anchor both groups strictly AFTER rule.induced_at so they count as
        # post-induction evidence even when the operator injects right after a
        # fresh seed (where induced_at == now). Winners land STRICTLY EARLIER
        # than the failures so the trailing cs_window window `should_revise`
        # inspects contains only the failing episodes — the accepted winners
        # must not lift the success ratio back above theta.
        now = max(datetime.utcnow(), rule.induced_at + timedelta(seconds=10))
        winner_ts = now - timedelta(seconds=2)
        for _ in range(n):
            ep = schemas.Episode(
                id=short_id("eval_ep"),
                timestamp=winner_ts,
                day=donor.day,
                profile_id=donor.profile_id,
                cluster_id=target_cluster,
                pitch_strategy=winning_strategy,
                dialogue=[],
                final_interest=4,
                outcome="accepted",
                summary="injected contradiction — emerging alternative strategy winning",
                summary_embedding=list(donor.summary_embedding),
                rule_applied_top=rule.id,
            )
            await store.save_episode(session, ep)
            injected_ids.append(ep.id)

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
        "winning_strategy": winning_strategy.model_dump(exclude={"opener_text"}),
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
