"""Thin CRUD layer over SQLAlchemy rows. Returns Pydantic schemas, not ORM rows.

Kept intentionally narrow: add helpers as routers need them. Do not expose raw
ORM objects outside this module.
"""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.memory import models


# ── Profiles ──────────────────────────────────────────────────────────────

def _profile_from_row(row: models.ProfileRow) -> schemas.Profile:
    return schemas.Profile(
        id=row.id,
        source_kind=row.source_kind,
        source_identifier=row.source_identifier,
        name=row.name,
        role=row.role,
        domain=row.domain,
        seniority=row.seniority,  # type: ignore[arg-type]
        headline=row.headline,
        recent_signals=row.recent_signals or [],
        archetype_summary=row.archetype_summary,
        avatar_url=row.avatar_url,
        summary_text=row.summary_text,
        embedding=row.embedding,
        fetched_at=row.fetched_at,
        ttl_seconds=row.ttl_seconds,
        cluster_id=row.cluster_id,
    )


async def upsert_profile(session: AsyncSession, p: schemas.Profile) -> schemas.Profile:
    existing = await session.get(models.ProfileRow, p.id)
    if existing:
        existing.source_kind = p.source_kind
        existing.source_identifier = p.source_identifier
        existing.name = p.name
        existing.role = p.role
        existing.domain = p.domain
        existing.seniority = p.seniority
        existing.headline = p.headline
        existing.recent_signals = list(p.recent_signals)
        existing.archetype_summary = p.archetype_summary
        existing.avatar_url = p.avatar_url
        existing.summary_text = p.summary_text
        existing.embedding = p.embedding
        existing.fetched_at = p.fetched_at
        existing.ttl_seconds = p.ttl_seconds
        existing.cluster_id = p.cluster_id
    else:
        session.add(
            models.ProfileRow(
                id=p.id,
                source_kind=p.source_kind,
                source_identifier=p.source_identifier,
                name=p.name,
                role=p.role,
                domain=p.domain,
                seniority=p.seniority,
                headline=p.headline,
                recent_signals=list(p.recent_signals),
                archetype_summary=p.archetype_summary,
                avatar_url=p.avatar_url,
                summary_text=p.summary_text,
                embedding=p.embedding,
                fetched_at=p.fetched_at,
                ttl_seconds=p.ttl_seconds,
                cluster_id=p.cluster_id,
            )
        )
    await session.commit()
    return p


async def get_profile(session: AsyncSession, profile_id: str) -> schemas.Profile | None:
    row = await session.get(models.ProfileRow, profile_id)
    return _profile_from_row(row) if row else None


async def list_profiles(session: AsyncSession) -> list[schemas.Profile]:
    result = await session.execute(select(models.ProfileRow))
    return [_profile_from_row(r) for r in result.scalars()]


async def purge_expired_live_profiles(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    synthetic_kind: str = "synthetic",
) -> list[str]:
    """Delete non-synthetic ProfileRows older than their TTL window.

    Privacy task per TASK.md acceptance §14: PII fetched from external
    sources (e.g. LinkedIn) must not linger in SQLite. A row is purgeable iff
      - source_kind != 'synthetic'
      - ttl_seconds is set (default 3600 for live profiles)
      - (now - fetched_at) >= ttl_seconds

    Synthetic rows are left untouched — they carry no PII and are referenced
    by historical episodes for the demo run.

    Returns the list of purged profile_ids for logging.
    """
    cutoff_now = now or datetime.utcnow()
    stmt = select(models.ProfileRow).where(
        models.ProfileRow.source_kind != synthetic_kind,
        models.ProfileRow.ttl_seconds.is_not(None),
    )
    rows = (await session.execute(stmt)).scalars().all()

    expired_ids: list[str] = []
    for row in rows:
        ttl = row.ttl_seconds
        if ttl is None:
            continue
        age = (cutoff_now - row.fetched_at).total_seconds()
        if age >= ttl:
            expired_ids.append(row.id)

    if expired_ids:
        await session.execute(
            delete(models.ProfileRow).where(models.ProfileRow.id.in_(expired_ids))
        )
        await session.commit()
    return expired_ids


# ── Episodes ──────────────────────────────────────────────────────────────

def _episode_from_row(row: models.EpisodeRow) -> schemas.Episode:
    return schemas.Episode(
        id=row.id,
        timestamp=row.timestamp,
        day=row.day,
        profile_id=row.profile_id,
        cluster_id=row.cluster_id,
        pitch_strategy=schemas.PitchStrategy(**row.pitch_strategy),
        dialogue=[schemas.DialogueStep(**s) for s in (row.dialogue or [])],
        final_interest=row.final_interest,
        outcome=row.outcome,  # type: ignore[arg-type]
        summary=row.summary,
        summary_embedding=row.summary_embedding or [],
        rule_applied_top=row.rule_applied_top,
    )


async def save_episode(session: AsyncSession, ep: schemas.Episode) -> schemas.Episode:
    row = models.EpisodeRow(
        id=ep.id,
        timestamp=ep.timestamp,
        day=ep.day,
        profile_id=ep.profile_id,
        cluster_id=ep.cluster_id,
        pitch_strategy=ep.pitch_strategy.model_dump(),
        dialogue=[s.model_dump() for s in ep.dialogue],
        final_interest=ep.final_interest,
        outcome=ep.outcome,
        summary=ep.summary,
        summary_embedding=ep.summary_embedding,
        rule_applied_top=ep.rule_applied_top,
    )
    session.add(row)
    await session.commit()
    return ep


async def list_episodes(
    session: AsyncSession, limit: int = 20, order: str = "desc"
) -> list[schemas.Episode]:
    stmt = select(models.EpisodeRow)
    stmt = stmt.order_by(
        models.EpisodeRow.timestamp.desc() if order == "desc" else models.EpisodeRow.timestamp
    )
    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return [_episode_from_row(r) for r in result.scalars()]


async def count_episodes(session: AsyncSession) -> int:
    from sqlalchemy import func
    result = await session.execute(select(func.count(models.EpisodeRow.id)))
    return result.scalar() or 0


async def episodes_for_cluster(
    session: AsyncSession, cluster_id: str
) -> list[schemas.Episode]:
    stmt = select(models.EpisodeRow).where(models.EpisodeRow.cluster_id == cluster_id)
    result = await session.execute(stmt)
    return [_episode_from_row(r) for r in result.scalars()]


async def delete_episodes(session: AsyncSession, episode_ids: list[str]) -> int:
    if not episode_ids:
        return 0
    result = await session.execute(
        delete(models.EpisodeRow).where(models.EpisodeRow.id.in_(episode_ids))
    )
    await session.commit()
    return result.rowcount or 0


# ── Rules ─────────────────────────────────────────────────────────────────

def _rule_from_row(row: models.RuleRow) -> schemas.Rule:
    return schemas.Rule(
        id=row.id,
        cluster_id=row.cluster_id,
        slots=[schemas.RuleSlot(**s) for s in row.slots],
        induced_at=row.induced_at,
        induced_from_episode_ids=row.induced_from_episode_ids or [],
        status=row.status,  # type: ignore[arg-type]
        deprecated_by=row.deprecated_by,
        cs_history=[(datetime.fromisoformat(t), s) for t, s in (row.cs_history or [])],
    )


async def save_rule(session: AsyncSession, rule: schemas.Rule) -> schemas.Rule:
    row = models.RuleRow(
        id=rule.id,
        cluster_id=rule.cluster_id,
        slots=[s.model_dump() for s in rule.slots],
        induced_at=rule.induced_at,
        induced_from_episode_ids=rule.induced_from_episode_ids,
        status=rule.status,
        deprecated_by=rule.deprecated_by,
        cs_history=[[t.isoformat(), s] for t, s in rule.cs_history],
    )
    session.add(row)
    await session.commit()
    return rule


async def list_rules(
    session: AsyncSession, status: str | None = None
) -> list[schemas.Rule]:
    stmt = select(models.RuleRow)
    if status:
        stmt = stmt.where(models.RuleRow.status == status)
    result = await session.execute(stmt)
    return [_rule_from_row(r) for r in result.scalars()]


async def get_rule(session: AsyncSession, rule_id: str) -> schemas.Rule | None:
    row = await session.get(models.RuleRow, rule_id)
    return _rule_from_row(row) if row else None


async def update_rule(
    session: AsyncSession,
    rule_id: str,
    *,
    status: str | None = None,
    deprecated_by: str | None = None,
    cs_history: list[tuple[datetime, float]] | None = None,
) -> schemas.Rule | None:
    row = await session.get(models.RuleRow, rule_id)
    if row is None:
        return None
    if status is not None:
        row.status = status
    if deprecated_by is not None:
        row.deprecated_by = deprecated_by
    if cs_history is not None:
        row.cs_history = [[t.isoformat(), s] for t, s in cs_history]
    await session.commit()
    return _rule_from_row(row)


async def existing_rule_ids(session: AsyncSession) -> list[str]:
    result = await session.execute(select(models.RuleRow.id))
    return [rid for (rid,) in result.all()]


# ── Clusters ──────────────────────────────────────────────────────────────

def _cluster_from_row(row: models.ClusterRow) -> schemas.Cluster:
    return schemas.Cluster(
        id=row.id,
        label=row.label or "",
        profile_ids=row.profile_ids or [],
        episode_ids=row.episode_ids or [],
        centroid_embedding=row.centroid_embedding or [],
        size=row.size,
        success_ratio=row.success_ratio,
        created_at=row.created_at,
        last_updated=row.last_updated,
    )


async def upsert_cluster(session: AsyncSession, c: schemas.Cluster) -> schemas.Cluster:
    existing = await session.get(models.ClusterRow, c.id)
    if existing:
        existing.label = c.label
        existing.profile_ids = list(c.profile_ids)
        existing.episode_ids = list(c.episode_ids)
        existing.centroid_embedding = list(c.centroid_embedding)
        existing.size = c.size
        existing.success_ratio = c.success_ratio
        existing.last_updated = c.last_updated
    else:
        session.add(
            models.ClusterRow(
                id=c.id,
                label=c.label,
                profile_ids=list(c.profile_ids),
                episode_ids=list(c.episode_ids),
                centroid_embedding=list(c.centroid_embedding),
                size=c.size,
                success_ratio=c.success_ratio,
                created_at=c.created_at,
                last_updated=c.last_updated,
            )
        )
    await session.commit()
    return c


async def list_clusters(session: AsyncSession) -> list[schemas.Cluster]:
    result = await session.execute(select(models.ClusterRow))
    return [_cluster_from_row(r) for r in result.scalars()]


async def get_cluster(session: AsyncSession, cluster_id: str) -> schemas.Cluster | None:
    row = await session.get(models.ClusterRow, cluster_id)
    return _cluster_from_row(row) if row else None


# ── Revisions ─────────────────────────────────────────────────────────────

def _revision_from_row(row: models.RevisionRow) -> schemas.Revision:
    return schemas.Revision(
        id=row.id,
        rule_id=row.rule_id,
        triggered_at=row.triggered_at,
        contradicting_episode_ids=row.contradicting_episode_ids or [],
        llm_reasoning=row.llm_reasoning or "",
        proposed_rule=schemas.Rule(**row.proposed_rule),
        decision=row.decision,  # type: ignore[arg-type]
        resolved_at=row.resolved_at,
    )


async def save_revision(session: AsyncSession, r: schemas.Revision) -> schemas.Revision:
    row = models.RevisionRow(
        id=r.id,
        rule_id=r.rule_id,
        triggered_at=r.triggered_at,
        contradicting_episode_ids=list(r.contradicting_episode_ids),
        llm_reasoning=r.llm_reasoning,
        proposed_rule=r.proposed_rule.model_dump(mode="json"),
        decision=r.decision,
        resolved_at=r.resolved_at,
    )
    session.add(row)
    await session.commit()
    return r


async def get_revision(
    session: AsyncSession, revision_id: str
) -> schemas.Revision | None:
    row = await session.get(models.RevisionRow, revision_id)
    return _revision_from_row(row) if row else None


async def update_revision(
    session: AsyncSession,
    revision_id: str,
    *,
    decision: str | None = None,
    llm_reasoning: str | None = None,
    proposed_rule: schemas.Rule | None = None,
    resolved_at: datetime | None = None,
) -> schemas.Revision | None:
    row = await session.get(models.RevisionRow, revision_id)
    if row is None:
        return None
    if decision is not None:
        row.decision = decision
    if llm_reasoning is not None:
        row.llm_reasoning = llm_reasoning
    if proposed_rule is not None:
        row.proposed_rule = proposed_rule.model_dump(mode="json")
    if resolved_at is not None:
        row.resolved_at = resolved_at
    await session.commit()
    return _revision_from_row(row)


async def delete_revision(session: AsyncSession, revision_id: str) -> bool:
    result = await session.execute(
        delete(models.RevisionRow).where(models.RevisionRow.id == revision_id)
    )
    await session.commit()
    return bool(result.rowcount)


async def pending_revision_for_rule(
    session: AsyncSession, rule_id: str
) -> schemas.Revision | None:
    stmt = (
        select(models.RevisionRow)
        .where(models.RevisionRow.rule_id == rule_id)
        .where(models.RevisionRow.decision == "pending")
        .order_by(models.RevisionRow.triggered_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalars().first()
    return _revision_from_row(row) if row else None


async def latest_revision_for_rule(
    session: AsyncSession, rule_id: str
) -> schemas.Revision | None:
    stmt = (
        select(models.RevisionRow)
        .where(models.RevisionRow.rule_id == rule_id)
        .order_by(models.RevisionRow.triggered_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalars().first()
    return _revision_from_row(row) if row else None


async def latest_pending_revision(
    session: AsyncSession,
) -> schemas.Revision | None:
    stmt = (
        select(models.RevisionRow)
        .where(models.RevisionRow.decision == "pending")
        .order_by(models.RevisionRow.triggered_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalars().first()
    return _revision_from_row(row) if row else None


# ── Agents ────────────────────────────────────────────────────────────────

def _agent_from_row(row: models.AgentRow) -> schemas.Agent:
    return schemas.Agent(
        id=row.id,
        cluster_id=row.cluster_id,
        zone_description=row.zone_description,
        created_at=row.created_at,
        is_active=row.is_active,
    )


async def save_agent(session: AsyncSession, a: schemas.Agent) -> schemas.Agent:
    session.add(
        models.AgentRow(
            id=a.id,
            cluster_id=a.cluster_id,
            zone_description=a.zone_description,
            created_at=a.created_at,
            is_active=a.is_active,
        )
    )
    await session.commit()
    return a


async def list_agents(session: AsyncSession) -> list[schemas.Agent]:
    result = await session.execute(select(models.AgentRow))
    return [_agent_from_row(r) for r in result.scalars()]


async def cluster_has_agent(session: AsyncSession, cluster_id: str) -> bool:
    stmt = select(models.AgentRow.id).where(models.AgentRow.cluster_id == cluster_id)
    result = await session.execute(stmt)
    return result.first() is not None


# ── Episode helpers ───────────────────────────────────────────────────────

async def all_episodes(session: AsyncSession) -> list[schemas.Episode]:
    result = await session.execute(select(models.EpisodeRow))
    return [_episode_from_row(r) for r in result.scalars()]


async def profile_cluster_map(session: AsyncSession) -> dict[str, str]:
    """Return {profile_id: cluster_id} from episodes — lightweight KNN helper.

    Only fetches the two columns needed instead of full episode rows with
    dialogue JSON and embeddings.
    """
    stmt = (
        select(models.EpisodeRow.profile_id, models.EpisodeRow.cluster_id)
        .where(models.EpisodeRow.cluster_id.is_not(None))
        .order_by(models.EpisodeRow.timestamp)
    )
    result = await session.execute(stmt)
    mapping: dict[str, str] = {}
    for pid, cid in result.all():
        mapping[pid] = cid
    return mapping


async def set_profile_cluster(
    session: AsyncSession, profile_id: str, cluster_id: str
) -> None:
    row = await session.get(models.ProfileRow, profile_id)
    if row is not None:
        row.cluster_id = cluster_id
        await session.commit()


async def active_rules_by_cluster(session: AsyncSession) -> dict[str, "schemas.Rule"]:
    stmt = select(models.RuleRow).where(models.RuleRow.status == "active")
    result = await session.execute(stmt)
    return {_rule_from_row(r).cluster_id: _rule_from_row(r) for r in result.scalars()}


async def profiles_with_embeddings(session: AsyncSession) -> list[tuple[str, list[float]]]:
    """Return [(profile_id, embedding)] for profiles that have an embedding.

    Only fetches id + embedding columns — avoids deserialising headline,
    signals, and other text blobs that KNN classification does not need.
    """
    stmt = (
        select(models.ProfileRow.id, models.ProfileRow.embedding)
        .where(models.ProfileRow.embedding.is_not(None))
    )
    result = await session.execute(stmt)
    return [(pid, emb) for pid, emb in result.all()]


async def profiles_for_knn(session: AsyncSession) -> list[tuple[str, list[float], str | None]]:
    """Return (profile_id, embedding, cluster_id) for KNN rule selection."""
    stmt = (
        select(models.ProfileRow.id, models.ProfileRow.embedding, models.ProfileRow.cluster_id)
        .where(models.ProfileRow.embedding.is_not(None))
    )
    result = await session.execute(stmt)
    return [(pid, emb, cid) for pid, emb, cid in result.all()]
