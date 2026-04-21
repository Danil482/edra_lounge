"""Seed the 6 personas from TASK.md §5.1 into the DB.

Run via: `python -m backend.memory.seed` (also wired into `make reset`).
"""

import asyncio
from datetime import datetime

from backend import schemas
from backend.db import async_session_factory, init_db
from backend.memory import store


SEEDED_PERSONAS: list[schemas.Persona] = [
    schemas.Persona(
        id="persona_phd_nlp",
        display_name="PhD-NLP · introverted",
        role="PhD student",
        domain="NLP",
        vibe=["introverted", "depth-seeking", "budget-conscious"],
        archetype_summary=(
            "Quiet doctoral student in natural language processing. Cares about "
            "formal foundations and reproducibility; wary of hype. Low budget, "
            "prefers deep conversation over small talk."
        ),
        is_seeded=True,
        created_at=datetime.utcnow(),
    ),
    schemas.Persona(
        id="persona_postdoc_cv",
        display_name="postdoc-CV · ambitious",
        role="Postdoc",
        domain="CV",
        vibe=["ambitious", "trend-aware", "networking"],
        archetype_summary=(
            "Computer-vision postdoc hunting for faculty jobs or industry leads. "
            "Reads every arXiv trending list; optimises visibility; enjoys a "
            "fast-paced exchange and will name-drop."
        ),
        is_seeded=True,
        created_at=datetime.utcnow(),
    ),
    schemas.Persona(
        id="persona_tech_founder",
        display_name="tech-founder · energetic",
        role="Startup founder",
        domain="applied-AI",
        vibe=["energetic", "applied-first", "splurge"],
        archetype_summary=(
            "Early-stage founder building an applied-AI product. Hype-tolerant, "
            "wants shipping advice, happy to order the expensive drink. Impatient "
            "with meta-science tangents."
        ),
        is_seeded=True,
        created_at=datetime.utcnow(),
    ),
    schemas.Persona(
        id="persona_senior_prof",
        display_name="senior-prof · reserved",
        role="Full professor",
        domain="any",
        vibe=["reserved", "meta-oriented", "formal"],
        archetype_summary=(
            "Senior academic who has seen several hype cycles. Enjoys meta-science "
            "and history, distrusts enthusiastic sales pitches, drinks tea."
        ),
        is_seeded=True,
        created_at=datetime.utcnow(),
    ),
    schemas.Persona(
        id="persona_industry_pm",
        display_name="industry-PM · pragmatic",
        role="Product manager",
        domain="MLOps",
        vibe=["pragmatic", "business-minded", "concise"],
        archetype_summary=(
            "Product manager from a mid-sized AI company. Wants the business "
            "angle, no philosophy. Short attention span, rewards concise answers "
            "with applied value."
        ),
        is_seeded=True,
        created_at=datetime.utcnow(),
    ),
    # Not in rotation until New-Segment button is pressed:
    schemas.Persona(
        id="persona_vc_investor",
        display_name="VC-investor · hype-tolerant",
        role="Venture capitalist",
        domain="applied-AI",
        vibe=["hype-tolerant", "status-seeking", "gossipy"],
        archetype_summary=(
            "Early-stage VC scanning the conference for deal flow. Loves hype and "
            "gossip, reads the room for rising stars, happy with coffee or beer."
        ),
        is_seeded=True,
        created_at=datetime.utcnow(),
    ),
]


async def seed() -> None:
    await init_db()
    async with async_session_factory() as session:
        for p in SEEDED_PERSONAS:
            await store.upsert_persona(session, p)
    print(f"Seeded {len(SEEDED_PERSONAS)} personas")


if __name__ == "__main__":
    asyncio.run(seed())
