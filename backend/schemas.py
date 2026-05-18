"""Pydantic data contracts — TASK.md §4. These shapes are consumed by multiple
layers (DB, routers, frontend, simulator). Do not deviate.

EDRA's internal vocabulary is defined here once, in §4.3, and lives nowhere else.
The 5-slot PitchStrategy is grounded in dialogue-act and persuasion theory; do
not introduce vendor-specific or product-flavoured terminology in its place.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── Pitch vocabulary (TASK.md §4.3) ──────────────────────────────────────

FRAMING = Literal[
    "strategic-alignment",
    "peer-collaboration",
    "knowledge-share",
    "applied-curiosity",
    "skeptical-respect",
    "follow-up-comment",
]
TONE = Literal["formal", "warm", "socratic", "direct", "playful"]
OPENER_TYPE = Literal[
    "question",
    "reference-to-signal",
    "shared-context",
    "credential-anchor",
    "cold",
]
WORD_TARGET = Literal["short", "medium", "long"]
ASK_SIZE = Literal["chat", "co-author", "intro", "trial", "none"]

SENIORITY = Literal["early", "mid", "senior"]
VISITOR_CHOICE = Literal["positive", "skeptical", "negative"]
OUTCOME = Literal["accepted", "exploring", "rejected", "abandoned"]
RULE_STATUS = Literal["active", "deprecated", "under_revision"]
REVISION_DECISION = Literal["pending", "accepted", "rejected", "edited"]
SLOT_NAME = Literal["framing", "tone", "opener_type", "word_target", "ask_size"]
SLOT_KIND = Literal["static", "dynamic"]


# ── Profile (TASK.md §4.2) ────────────────────────────────────────────────

class Profile(BaseModel):
    """Unified schema produced by any ProfileSource implementation."""

    id: str
    source_kind: str
    source_identifier: str
    name: str
    role: str
    domain: str
    seniority: SENIORITY
    headline: str
    recent_signals: list[str] = Field(default_factory=list)
    archetype_summary: str
    avatar_url: str | None = None  # remote URL when source provides one (LinkedIn)
    embedding: list[float] | None = None
    fetched_at: datetime
    ttl_seconds: int | None = None  # None = infinite (synthetic); 3600 = live


# ── PitchStrategy (TASK.md §4.3) ──────────────────────────────────────────

class PitchStrategy(BaseModel):
    framing: FRAMING
    tone: TONE
    opener_type: OPENER_TYPE
    word_target: WORD_TARGET
    ask_size: ASK_SIZE
    opener_text: str | None = None


# ── Episode + DialogueStep (TASK.md §4.4) ─────────────────────────────────

class ResponseOption(BaseModel):
    text: str
    sentiment: VISITOR_CHOICE


class DialogueStep(BaseModel):
    turn: int
    agent_thought: str
    agent_reply: str
    visitor_choice: VISITOR_CHOICE | None = None
    interest_delta: int = 0  # -2..+2 effect on the gauge
    rule_applied: str | None = None
    response_options: list[ResponseOption] | None = None


class Episode(BaseModel):
    id: str
    timestamp: datetime
    day: int
    profile_id: str
    cluster_id: str | None = None
    pitch_strategy: PitchStrategy
    dialogue: list[DialogueStep] = Field(default_factory=list)
    final_interest: int  # -5..+5
    outcome: OUTCOME
    summary: str
    summary_embedding: list[float] = Field(default_factory=list)
    rule_applied_top: str | None = None


# ── Cluster (TASK.md §4.5) ────────────────────────────────────────────────

class Cluster(BaseModel):
    id: str
    label: str = ""
    profile_ids: list[str] = Field(default_factory=list)
    episode_ids: list[str] = Field(default_factory=list)
    centroid_embedding: list[float] = Field(default_factory=list)
    size: int = 0
    success_ratio: float = 0.0  # accepted / (accepted + rejected); ignores 'exploring'
    created_at: datetime
    last_updated: datetime


# ── Rule (TASK.md §4.6) ───────────────────────────────────────────────────

class RuleSlot(BaseModel):
    name: SLOT_NAME
    kind: SLOT_KIND
    value: str | None = None  # static: literal value; dynamic: None
    prompt: str | None = None  # dynamic: LLM sub-prompt; static: None


class Rule(BaseModel):
    id: str  # "R.07" — human-friendly, monotonic
    cluster_id: str
    slots: list[RuleSlot]  # always 5 slots: framing, tone, opener_type, word_target, ask_size
    induced_at: datetime
    induced_from_episode_ids: list[str] = Field(default_factory=list)
    status: RULE_STATUS = "active"
    deprecated_by: str | None = None
    cs_history: list[tuple[datetime, float]] = Field(default_factory=list)

    def is_static(self) -> bool:
        return all(s.kind == "static" for s in self.slots)


# ── Revision (TASK.md §4.7) ───────────────────────────────────────────────

class Revision(BaseModel):
    id: str
    rule_id: str
    triggered_at: datetime
    contradicting_episode_ids: list[str] = Field(default_factory=list)
    llm_reasoning: str = ""
    proposed_rule: Rule
    decision: REVISION_DECISION = "pending"
    resolved_at: datetime | None = None


# ── Agent (Factory) ───────────────────────────────────────────────────────

class Agent(BaseModel):
    id: str
    cluster_id: str
    zone_description: str
    created_at: datetime
    is_active: bool = True


# ── /state snapshot (TASK.md §8) ──────────────────────────────────────────

class Clock(BaseModel):
    day: int
    time: str  # "HH:MM"


class ClusterViz(BaseModel):
    id: str
    label: str
    points: list[tuple[float, float]] = Field(default_factory=list)


class SessionSnapshot(BaseModel):
    """In-flight pitch session as exposed in /state.current_session.

    Phase 1B fully wires this when the multi-turn sessions API lands.
    """

    id: str
    profile: Profile
    cluster_id: str | None = None
    applicable_rule_id: str | None = None
    interest: int = 0
    dialogue: list[DialogueStep] = Field(default_factory=list)


class StateSnapshot(BaseModel):
    clock: Clock
    current_session: SessionSnapshot | None = None
    recent_episodes: list[Episode] = Field(default_factory=list)
    clusters_viz: list[ClusterViz] = Field(default_factory=list)
    rules: list[Rule] = Field(default_factory=list)
    active_revision: Revision | None = None
    agents: list[Agent] = Field(default_factory=list)
    interest_gauge: int | None = None
