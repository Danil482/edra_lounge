"""Rule induction. Eligibility gate + LLM call + JSON parse → schemas.Rule.

A cluster qualifies for induction (TASK.md §2 / §6) when it reaches
`n_min` episodes with `success_ratio >= theta_induce`. The LLM is given the
cluster label, size, success ratio, and a few sample episodes; it returns a
5-slot Rule (framing, tone, opener_type, word_target, ask_size). Each slot
is either static (a literal vocabulary value) or dynamic (an LLM sub-prompt
that fills the slot at application time, e.g. for a per-visitor opener).
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from backend import schemas
from backend.config import settings
from backend.llm import client as llm
from backend.memory.ids import next_rule_id


class NotEligible(Exception):
    """Cluster does not meet n_min / theta_induce requirements."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def check_eligibility(cluster: schemas.Cluster) -> None:
    if cluster.size < settings.n_min:
        raise NotEligible(f"cluster size {cluster.size} < n_min={settings.n_min}")
    if cluster.success_ratio < settings.theta_induce:
        raise NotEligible(
            f"success_ratio {cluster.success_ratio:.2f} < theta_induce={settings.theta_induce}"
        )


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _format_episodes(episodes: list[schemas.Episode], limit: int = 5) -> str:
    lines = []
    for i, ep in enumerate(episodes[:limit], 1):
        ps = ep.pitch_strategy
        lines.append(
            f"  [{i}] profile={ep.profile_id}\n"
            f"      pitch=({ps.framing}/{ps.tone}/{ps.opener_type}/{ps.word_target}/{ps.ask_size})\n"
            f"      outcome={ep.outcome} final_interest={ep.final_interest:+d}\n"
            f"      summary: {ep.summary}"
        )
    return "\n".join(lines)


async def induce_rule(
    cluster: schemas.Cluster,
    cluster_episodes: list[schemas.Episode],
    existing_rule_ids: list[str],
) -> schemas.Rule:
    """Eligibility-checked induction. Raises NotEligible if the cluster doesn't qualify."""
    check_eligibility(cluster)

    prompt = llm.render(
        "induce",
        cluster_label=cluster.label or "(unlabelled)",
        cluster_size=cluster.size,
        success_ratio=f"{cluster.success_ratio:.2f}",
        episodes_formatted=_format_episodes(cluster_episodes),
    )
    raw = await llm.complete(
        prompt,
        system="You are a rule-induction engine. Output JSON only.",
    )
    data = json.loads(_strip_fences(raw))
    slots = [schemas.RuleSlot(**s) for s in data["slots"]]

    return schemas.Rule(
        id=next_rule_id(existing_rule_ids),
        cluster_id=cluster.id,
        slots=slots,
        induced_at=datetime.utcnow(),
        induced_from_episode_ids=[ep.id for ep in cluster_episodes],
        status="active",
        deprecated_by=None,
        cs_history=[],
    )
