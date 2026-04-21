"""SQLAlchemy ORM tables. Mirror the Pydantic schemas in backend/schemas.py.

Complex fields (embeddings, lists, nested models) are stored as JSON columns.
Rule.cs_history uses JSON to keep the timeline as one row per rule.
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PersonaRow(Base):
    __tablename__ = "personas"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    domain: Mapped[str] = mapped_column(String)
    vibe: Mapped[list] = mapped_column(JSON, default=list)
    archetype_summary: Mapped[str] = mapped_column(Text)
    is_seeded: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EpisodeRow(Base):
    __tablename__ = "episodes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    day: Mapped[int] = mapped_column(Integer)
    visitor_persona_id: Mapped[str] = mapped_column(String, ForeignKey("personas.id"))
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    offer: Mapped[dict] = mapped_column(JSON)  # {topic, style, drink, opener_text}
    outcome: Mapped[str] = mapped_column(String)  # satisfied|neutral|rejected
    outcome_score: Mapped[float] = mapped_column(Float)
    summary: Mapped[str] = mapped_column(Text)
    summary_embedding: Mapped[list] = mapped_column(JSON)  # 384-dim float list
    cluster_id: Mapped[str | None] = mapped_column(String, nullable=True)
    rule_applied: Mapped[str | None] = mapped_column(String, nullable=True)


class ClusterRow(Base):
    __tablename__ = "clusters"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str] = mapped_column(String, default="")
    episode_ids: Mapped[list] = mapped_column(JSON, default=list)
    centroid_embedding: Mapped[list] = mapped_column(JSON)
    size: Mapped[int] = mapped_column(Integer, default=0)
    success_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RuleRow(Base):
    __tablename__ = "rules"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # "R.07"
    cluster_id: Mapped[str] = mapped_column(String, ForeignKey("clusters.id"))
    slots: Mapped[list] = mapped_column(JSON)  # list of RuleSlot dicts
    induced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    induced_from_episode_ids: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String, default="active")
    deprecated_by: Mapped[str | None] = mapped_column(String, nullable=True)
    cs_history: Mapped[list] = mapped_column(JSON, default=list)  # [[iso_ts, cs], ...]


class RevisionRow(Base):
    __tablename__ = "revisions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    rule_id: Mapped[str] = mapped_column(String, ForeignKey("rules.id"))
    triggered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    contradicting_episode_ids: Mapped[list] = mapped_column(JSON, default=list)
    llm_reasoning: Mapped[str] = mapped_column(Text, default="")
    proposed_rule: Mapped[dict] = mapped_column(JSON)  # full Rule as dict
    decision: Mapped[str] = mapped_column(String, default="pending")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AgentRow(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    cluster_id: Mapped[str] = mapped_column(String, ForeignKey("clusters.id"))
    zone_description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
