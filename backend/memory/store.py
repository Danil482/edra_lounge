"""Thin CRUD layer over SQLAlchemy rows. Returns Pydantic schemas, not ORM rows.

Kept intentionally narrow: add helpers as routers need them. Do not expose raw
ORM objects outside this module.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.memory import models


# ── Episodes ──────────────────────────────────────────────────────────────

def _episode_from_row(row: models.EpisodeRow) -> schemas.Episode:
    return schemas.Episode(
        id=row.id,
        timestamp=row.timestamp,
        day=row.day,
        visitor_persona_id=row.visitor_persona_id,
        context=row.context,
        offer=schemas.Offer(**row.offer),
        outcome=row.outcome,
        outcome_score=row.outcome_score,
        summary=row.summary,
        summary_embedding=row.summary_embedding,
        cluster_id=row.cluster_id,
        rule_applied=row.rule_applied,
    )


async def save_episode(session: AsyncSession, ep: schemas.Episode) -> schemas.Episode:
    row = models.EpisodeRow(
        id=ep.id,
        timestamp=ep.timestamp,
        day=ep.day,
        visitor_persona_id=ep.visitor_persona_id,
        context=ep.context,
        offer=ep.offer.model_dump(),
        outcome=ep.outcome,
        outcome_score=ep.outcome_score,
        summary=ep.summary,
        summary_embedding=ep.summary_embedding,
        cluster_id=ep.cluster_id,
        rule_applied=ep.rule_applied,
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


# ── Personas ──────────────────────────────────────────────────────────────

def _persona_from_row(row: models.PersonaRow) -> schemas.Persona:
    return schemas.Persona(
        id=row.id,
        display_name=row.display_name,
        role=row.role,
        domain=row.domain,
        vibe=row.vibe,
        archetype_summary=row.archetype_summary,
        is_seeded=row.is_seeded,
        created_at=row.created_at,
    )


async def upsert_persona(session: AsyncSession, p: schemas.Persona) -> schemas.Persona:
    existing = await session.get(models.PersonaRow, p.id)
    if existing:
        existing.display_name = p.display_name
        existing.role = p.role
        existing.domain = p.domain
        existing.vibe = p.vibe
        existing.archetype_summary = p.archetype_summary
        existing.is_seeded = p.is_seeded
    else:
        session.add(
            models.PersonaRow(
                id=p.id,
                display_name=p.display_name,
                role=p.role,
                domain=p.domain,
                vibe=p.vibe,
                archetype_summary=p.archetype_summary,
                is_seeded=p.is_seeded,
                created_at=p.created_at,
            )
        )
    await session.commit()
    return p


async def get_persona(session: AsyncSession, persona_id: str) -> schemas.Persona | None:
    row = await session.get(models.PersonaRow, persona_id)
    return _persona_from_row(row) if row else None


# ── Rules ─────────────────────────────────────────────────────────────────

def _rule_from_row(row: models.RuleRow) -> schemas.Rule:
    return schemas.Rule(
        id=row.id,
        cluster_id=row.cluster_id,
        slots=[schemas.RuleSlot(**s) for s in row.slots],
        induced_at=row.induced_at,
        induced_from_episode_ids=row.induced_from_episode_ids,
        status=row.status,
        deprecated_by=row.deprecated_by,
        cs_history=[(datetime.fromisoformat(t), s) for t, s in row.cs_history],
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


# ── Clusters, Revisions, Agents — add as routers need them ────────────────
