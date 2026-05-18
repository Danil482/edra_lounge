"""SQLAlchemy ORM tables. Mirror the Pydantic schemas in backend/schemas.py.

Complex fields (embeddings, lists, nested models) are stored as JSON columns.
Rule.cs_history is JSON to keep one row per rule (history is small enough).

Six tables per TASK.md §2: profiles, episodes, clusters, rules, revisions, agents.
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProfileRow(Base):
    """Profiles arrive from any ProfileSource (synthetic, LinkedIn, ...).

    Live (non-synthetic) profiles must be purged after session end — a Phase 3
    privacy task verifies that source_kind != 'synthetic' rows older than 1h
    are gone. The schema itself does not enforce that; the cleaner does.
    """

    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_kind: Mapped[str] = mapped_column(String, index=True)
    source_identifier: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    domain: Mapped[str] = mapped_column(String)
    seniority: Mapped[str] = mapped_column(String)  # early|mid|senior
    headline: Mapped[str] = mapped_column(Text)
    recent_signals: Mapped[list] = mapped_column(JSON, default=list)
    archetype_summary: Mapped[str] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ttl_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)


class EpisodeRow(Base):
    __tablename__ = "episodes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    day: Mapped[int] = mapped_column(Integer)
    profile_id: Mapped[str] = mapped_column(String, ForeignKey("profiles.id"))
    cluster_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    pitch_strategy: Mapped[dict] = mapped_column(JSON)
    dialogue: Mapped[list] = mapped_column(JSON, default=list)
    final_interest: Mapped[int] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String)
    summary: Mapped[str] = mapped_column(Text)
    summary_embedding: Mapped[list] = mapped_column(JSON, default=list)
    rule_applied_top: Mapped[str | None] = mapped_column(String, nullable=True)


class ClusterRow(Base):
    __tablename__ = "clusters"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str] = mapped_column(String, default="")
    profile_ids: Mapped[list] = mapped_column(JSON, default=list)
    episode_ids: Mapped[list] = mapped_column(JSON, default=list)
    centroid_embedding: Mapped[list] = mapped_column(JSON, default=list)
    size: Mapped[int] = mapped_column(Integer, default=0)
    success_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RuleRow(Base):
    __tablename__ = "rules"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # "R.07"
    cluster_id: Mapped[str] = mapped_column(String, ForeignKey("clusters.id"))
    slots: Mapped[list] = mapped_column(JSON)  # list of RuleSlot dicts (5 slots)
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


class VisitorRow(Base):
    __tablename__ = "visitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    session_id: Mapped[str | None] = mapped_column(String, nullable=True)
