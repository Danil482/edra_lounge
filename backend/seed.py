"""CLI entry-point for seeding the DB with synthetic profiles.

Lives at the package root (not under `backend/memory/`) so that the
ProfileSource concrete implementation it instantiates does not violate the
core/profile_source isolation enforced by `tests/test_profile_source.py`.

Run via `python -m backend.seed` (also wired into `make reset`).
"""

from __future__ import annotations

import asyncio

from backend.db import async_session_factory, init_db
from backend.memory import store
from backend.profile_source.synthetic import SyntheticProfileSource


async def seed() -> int:
    await init_db()
    source = SyntheticProfileSource()
    archetype_ids = source.list_ids(include_spawnable=True)

    async with async_session_factory() as session:
        for aid in archetype_ids:
            profile = await source.fetch(aid)
            await store.upsert_profile(session, profile)

    return len(archetype_ids)


def main() -> None:
    n = asyncio.run(seed())
    print(f"Seeded {n} synthetic profiles")


if __name__ == "__main__":
    main()
