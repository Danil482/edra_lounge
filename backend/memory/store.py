"""Thin CRUD layer over SQLAlchemy rows. Returns Pydantic schemas, not ORM rows.

Kept intentionally narrow: add helpers as routers need them. Do not expose raw
ORM objects outside this module.
"""

from datetime import datetime

from sqlalchemy import select
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
        embedding=row.embedding,
        fetched_at=row.fetched_at,
        ttl_seconds=row.ttl_seconds,
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
        existing.embedding = p.embedding
        existing.fetched_at = p.fetched_at
        existing.ttl_seconds = p.ttl_seconds
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
                embedding=p.embedding,
                fetched_at=p.fetched_at,
                ttl_seconds=p.ttl_seconds,
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


async def episodes_for_cluster(
    session: AsyncSession, cluster_id: str
) -> list[schemas.Episode]:
    stmt = select(models.EpisodeRow).where(models.EpisodeRow.cluster_id == cluster_id)
    result = await session.execute(stmt)
    return [_episode_from_row(r) for r in result.scalars()]


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


# ── Clusters, Revisions, Agents — added as routers / orchestrator need them ─
