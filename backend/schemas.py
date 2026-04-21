"""Pydantic data contracts — TASK.md §4. These shapes are consumed by multiple
layers (DB, routers, frontend, simulator). Do not deviate."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


TOPIC = Literal["hype", "foundations", "applied", "meta-science", "career", "gossip"]
STYLE = Literal["enthusiastic", "skeptical", "socratic", "gossipy", "formal"]
DRINK = Literal["coffee", "beer", "tea", "water"]

OUTCOME = Literal["satisfied", "neutral", "rejected"]
RULE_STATUS = Literal["active", "deprecated", "under_revision"]
REVISION_DECISION = Literal["pending", "accepted", "rejected", "edited"]
SLOT_NAME = Literal["topic", "style", "drink", "opener"]
SLOT_KIND = Literal["static", "dynamic"]


# ── Personas ──────────────────────────────────────────────────────────────

class Persona(BaseModel):
    id: str
    display_name: str
    role: str
    domain: str
    vibe: list[str]
    archetype_summary: str
    is_seeded: bool
    created_at: datetime


# ── Offers ────────────────────────────────────────────────────────────────

class Offer(BaseModel):
    topic: TOPIC
    style: STYLE
    drink: DRINK
    opener_text: str | None = None


# ── Episodes ──────────────────────────────────────────────────────────────

class EpisodeCreate(BaseModel):
    persona_id: str
    offer: Offer
    outcome: OUTCOME
    outcome_score: float = Field(ge=0.0, le=1.0)
    day: int
    time: str  # "HH:MM" game-clock


class Episode(BaseModel):
    id: str  # "ep_<6char>"
    timestamp: datetime  # game time, not wall-clock
    day: int
    visitor_persona_id: str
    context: dict  # frozen snapshot of persona at visit time
    offer: Offer
    outcome: OUTCOME
    outcome_score: float
    summary: str
    summary_embedding: list[float]  # 384-dim MiniLM
    cluster_id: str | None = None
    rule_applied: str | None = None  # rule id, or None for "improvised"


# ── Clusters ──────────────────────────────────────────────────────────────

class Cluster(BaseModel):
    id: str  # "cluster_<6char>"
    label: str  # LLM-generated human-readable, e.g. "PhD-NLP researchers"
    episode_ids: list[str]
    centroid_embedding: list[float]
    size: int
    success_ratio: float  # satisfied / total
    created_at: datetime
    last_updated: datetime


# ── Rules ─────────────────────────────────────────────────────────────────

class RuleSlot(BaseModel):
    name: SLOT_NAME
    kind: SLOT_KIND
    value: str | None = None  # static: the literal tag
    prompt: str | None = None  # dynamic: LLM sub-prompt at apply-time


class Rule(BaseModel):
    id: str  # "R.07" — human-friendly, monotonic
    cluster_id: str
    slots: list[RuleSlot]  # always 4: topic, style, drink, opener
    induced_at: datetime
    induced_from_episode_ids: list[str]
    status: RULE_STATUS
    deprecated_by: str | None = None
    cs_history: list[tuple[datetime, float]] = Field(default_factory=list)

    def is_static(self) -> bool:
        return all(s.kind == "static" for s in self.slots)


# ── Revisions ─────────────────────────────────────────────────────────────

class Revision(BaseModel):
    id: str
    rule_id: str
    triggered_at: datetime
    contradicting_episode_ids: list[str]
    llm_reasoning: str  # streaming text accumulated
    proposed_rule: Rule
    decision: REVISION_DECISION
    resolved_at: datetime | None = None


# ── Agents (Factory) ──────────────────────────────────────────────────────

class Agent(BaseModel):
    id: str
    cluster_id: str
    zone_description: str
    created_at: datetime
    is_active: bool = True


# ── State snapshot ────────────────────────────────────────────────────────

class Clock(BaseModel):
    day: int
    time: str


class ClusterViz(BaseModel):
    id: str
    label: str
    points: list[tuple[float, float]]  # 2D UMAP coords


class StateSnapshot(BaseModel):
    clock: Clock
    current_visitor: Episode | None
    recent_episodes: list[Episode]
    clusters_viz: list[ClusterViz]
    rules: list[Rule]
    active_revision: Revision | None
    agents: list[Agent]
