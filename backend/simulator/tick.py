"""One simulator tick: pick a visitor, pick an offer, sample outcome, create
Episode. Called by orchestrator.py (Phase 1) or n8n workflow (Phase 3).
"""

import random
from datetime import datetime

from backend import schemas
from backend.clustering.cluster import embed
from backend.config import settings
from backend.llm import client as llm
from backend.memory import store
from backend.memory.ids import short_id
from backend.simulator import preferences
from backend.simulator.schedule import Visit


_rng = random.Random(settings.rng_seed)


def pick_offer(
    persona_id: str,
    active_rule: schemas.Rule | None,
) -> schemas.Offer:
    """If an active rule covers this persona's cluster, use its slots.
    Otherwise improvise: uniform-random offer (bartender has no prior).
    """
    if active_rule is not None and active_rule.is_static():
        return schemas.Offer(
            topic=_slot_value(active_rule, "topic"),
            style=_slot_value(active_rule, "style"),
            drink=_slot_value(active_rule, "drink"),
            opener_text=_slot_value(active_rule, "opener"),
        )

    # improvised
    return schemas.Offer(
        topic=_rng.choice(preferences.TOPICS),
        style=_rng.choice(preferences.STYLES),
        drink=_rng.choice(preferences.DRINKS),
        opener_text=None,
    )


def _slot_value(rule: schemas.Rule, name: str) -> str | None:
    for s in rule.slots:
        if s.name == name:
            return s.value
    return None


async def _summarise(
    persona: schemas.Persona,
    offer: schemas.Offer,
    outcome: schemas.OUTCOME,
) -> str:
    opener_line = f"\n  Opener: {offer.opener_text}" if offer.opener_text else ""
    prompt = llm.render(
        "summary",
        persona_display=persona.display_name,
        persona_role=persona.role,
        persona_vibe=", ".join(persona.vibe),
        topic=offer.topic,
        style=offer.style,
        drink=offer.drink,
        opener_line=opener_line,
        outcome=outcome,
    )
    return (await llm.complete(prompt)).strip()


async def tick_once(
    visit: Visit,
    persona: schemas.Persona,
    active_rule: schemas.Rule | None,
) -> schemas.Episode:
    """Build one Episode end-to-end (offer → outcome → summary → embedding)."""
    offer = pick_offer(persona.id, active_rule)
    score = preferences.score_offer(persona.id, offer)
    outcome = preferences.outcome_from_score(score)

    summary = await _summarise(persona, offer, outcome)
    embedding = embed([summary])[0]

    return schemas.Episode(
        id=short_id("ep", _rng),
        timestamp=datetime.utcnow(),
        day=visit.day,
        visitor_persona_id=persona.id,
        context={
            "role": persona.role,
            "domain": persona.domain,
            "vibe": persona.vibe,
        },
        offer=offer,
        outcome=outcome,
        outcome_score=score,
        summary=summary,
        summary_embedding=embedding,
        cluster_id=None,
        rule_applied=active_rule.id if active_rule else None,
    )
