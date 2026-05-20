"""Seed DB with profiles, episodes, clusters, and rules for a ready-to-show demo.

Run via `python -m backend.seed_demo` (also wired into `make seed-demo`).
Works fully offline -- template fallback for LLM, structural fallback for summaries.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from backend import schemas
from backend.clustering.cluster import embed
from backend.db import async_session_factory, init_db
from backend.memory import store
from backend.memory.ids import next_rule_id
from backend.orchestrator import Orchestrator
from backend.profile_source.synthetic import SyntheticProfileSource
from backend.sessions.lifecycle import run_synthetic_session
from backend.simulator.preferences import top_k_strategies


DB_PATH = Path("edra_lounge.db")


async def seed_demo() -> None:
    for suffix in ("", "-shm", "-wal"):
        Path(f"{DB_PATH}{suffix}").unlink(missing_ok=True)

    await init_db()
    source = SyntheticProfileSource()

    all_ids = source.list_ids(include_spawnable=True)
    non_spawnable_ids = source.list_ids(include_spawnable=False)

    print(f"Seeding {len(all_ids)} profiles with embeddings...")
    async with async_session_factory() as session:
        for aid in all_ids:
            profile = await source.fetch(aid)
            profile.embedding = embed(
                [f"{profile.name}, {profile.role}. {profile.headline}. {profile.archetype_summary}"]
            )[0]
            await store.upsert_profile(session, profile)
            print(f"  {aid}")

    print(f"\nPre-creating rules from top strategies...")
    existing_rule_ids: list[str] = []
    async with async_session_factory() as session:
        for aid in non_spawnable_ids:
            best = top_k_strategies(aid, k=1)[0]
            rule = schemas.Rule(
                id=next_rule_id(existing_rule_ids),
                cluster_id=aid,
                slots=[
                    schemas.RuleSlot(name="framing", kind="static", value=best.framing),
                    schemas.RuleSlot(name="tone", kind="static", value=best.tone),
                    schemas.RuleSlot(name="opener_type", kind="static", value=best.opener_type),
                    schemas.RuleSlot(name="word_target", kind="static", value=best.word_target),
                    schemas.RuleSlot(name="ask_size", kind="static", value=best.ask_size),
                ],
                induced_at=datetime.utcnow(),
                induced_from_episode_ids=[],
                status="active",
                deprecated_by=None,
                cs_history=[],
            )
            await store.save_rule(session, rule)
            existing_rule_ids.append(rule.id)
            print(f"  {aid}: {best.framing}/{best.tone}/{best.opener_type}")

    print(f"\nRunning {len(non_spawnable_ids) * 3} synthetic sessions...")
    async with async_session_factory() as session:
        for day in (1, 2, 3):
            for aid in non_spawnable_ids:
                ep = await run_synthetic_session(
                    db=session,
                    profile_source=source,
                    archetype_id=aid,
                    day=day,
                    on_new_episode=None,
                )
                print(f"  {aid} day={day} -> {ep.outcome} ({ep.final_interest:+d})")

    print("\nClustering and inducing rules...")
    orch = Orchestrator(async_session_factory, source)
    async with async_session_factory() as session:
        await orch._recluster(session)
        await orch._try_induce_all(session)

    async with async_session_factory() as session:
        profiles = await store.list_profiles(session)
        episodes = await store.all_episodes(session)
        clusters = await store.list_clusters(session)
        rules = await store.list_rules(session)

    print(
        f"\nDone: {len(profiles)} profiles, {len(episodes)} episodes, "
        f"{len(clusters)} clusters, {len(rules)} rules"
    )


def main() -> None:
    asyncio.run(seed_demo())


if __name__ == "__main__":
    main()
