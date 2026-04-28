"""Rules CRUD + induction trigger + revision trigger.

  GET  /rules                      list rules (optional status filter)
  POST /rules/induce?cluster_id    eligibility-checked manual induction
  GET  /rules/{id}/consistency     current CS for a rule
  POST /rules/{id}/revise          create a pending Revision (LLM stream runs
                                    when /reflections/stream/{id} opens)
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.db import get_session
from backend.induction import induce as induce_mod
from backend.memory import store
from backend.memory.ids import short_id
from backend.monitor import consistency as monitor_mod


router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=list[schemas.Rule])
async def list_rules(
    status: schemas.RULE_STATUS | None = None,
    session: AsyncSession = Depends(get_session),
):
    return await store.list_rules(session, status=status)


@router.post("/induce", response_model=schemas.Rule)
async def induce(
    cluster_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    cluster = await store.get_cluster(session, cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail=f"unknown cluster: {cluster_id}")
    try:
        induce_mod.check_eligibility(cluster)
    except induce_mod.NotEligible as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    cluster_eps = await store.episodes_for_cluster(session, cluster_id)
    existing_ids = await store.existing_rule_ids(session)
    try:
        rule = await induce_mod.induce_rule(
            cluster=cluster,
            cluster_episodes=cluster_eps,
            existing_rule_ids=existing_ids,
        )
    except Exception:  # noqa: BLE001
        # Fall back to deterministic mode-of-slots induction so a missing LLM
        # doesn't 500 the booth — same fallback the orchestrator uses.
        from backend.orchestrator import _fallback_induce

        rule = _fallback_induce(cluster, cluster_eps, existing_ids)
    await store.save_rule(session, rule)
    return rule


@router.get("/{rule_id}/consistency")
async def consistency_of(
    rule_id: str,
    session: AsyncSession = Depends(get_session),
):
    rule = await store.get_rule(session, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"unknown rule: {rule_id}")
    cluster_eps = await store.episodes_for_cluster(session, rule.cluster_id)
    cs = monitor_mod.compute_cs(rule, cluster_eps)
    return {
        "rule_id": rule_id,
        "consistency_score": cs,
        "should_revise": monitor_mod.should_revise(rule, cluster_eps),
        "post_induction_episodes": sum(
            1 for ep in cluster_eps if ep.timestamp > rule.induced_at
        ),
    }


@router.post("/{rule_id}/revise", response_model=schemas.Revision)
async def revise(
    rule_id: str,
    session: AsyncSession = Depends(get_session),
):
    rule = await store.get_rule(session, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"unknown rule: {rule_id}")

    existing = await store.pending_revision_for_rule(session, rule_id)
    if existing is not None:
        return existing

    cluster_eps = await store.episodes_for_cluster(session, rule.cluster_id)
    contradicting = [
        ep
        for ep in cluster_eps
        if ep.timestamp > rule.induced_at and ep.outcome != "accepted"
    ][-5:]

    rev = schemas.Revision(
        id=short_id("rev"),
        rule_id=rule_id,
        triggered_at=datetime.utcnow(),
        contradicting_episode_ids=[ep.id for ep in contradicting],
        llm_reasoning="",
        proposed_rule=rule.model_copy(),
        decision="pending",
        resolved_at=None,
    )
    await store.save_revision(session, rev)
    await store.update_rule(session, rule_id, status="under_revision")
    return rev
