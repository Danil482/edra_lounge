"""Seed the EDRA demo DB from the evaluation dataset (real CRM outreach data).

Replaces synthetic archetypes with real-world clusters and rules derived from
744 outreach episodes across 7 cluster types and 8 strategies.

Run via: python -m backend.seed_from_eval
"""

from __future__ import annotations

import asyncio
import csv
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.memory.models import (
    AgentRow,
    Base,
    ClusterRow,
    EpisodeRow,
    ProfileRow,
    RuleRow,
)

DATASET_PATH = Path("evaluation/data/dataset_final.csv")
DB_PATH = Path("edra_lounge.db")
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"

HDBSCAN_STRATEGY_ALIASES = {
    "dear_thrilled_james": "mass_newsletter",
    "mater_block7_block71_dear": "mass_newsletter",
    "vc_backed_startups_singapore_grown": "vc_fundraising",
    "somin_ai_brands_like_improve": "company_pitch",
    "performance_new_swiftly_automate_ai_brings": "tech_demo",
}

STRATEGY_TO_RULE = {
    "personalized_opener": {
        "framing": "applied-curiosity",
        "tone": "direct",
        "opener_type": "reference-to-signal",
        "word_target": "medium",
        "ask_size": "trial",
    },
    "tech_demo": {
        "framing": "applied-curiosity",
        "tone": "formal",
        "opener_type": "cold",
        "word_target": "long",
        "ask_size": "trial",
    },
    "company_pitch": {
        "framing": "knowledge-share",
        "tone": "warm",
        "opener_type": "cold",
        "word_target": "medium",
        "ask_size": "trial",
    },
    "general_intro": {
        "framing": "knowledge-share",
        "tone": "warm",
        "opener_type": "reference-to-signal",
        "word_target": "medium",
        "ask_size": "trial",
    },
    "event_followup": {
        "framing": "follow-up-comment",
        "tone": "warm",
        "opener_type": "shared-context",
        "word_target": "medium",
        "ask_size": "intro",
    },
    "vc_fundraising": {
        "framing": "strategic-alignment",
        "tone": "formal",
        "opener_type": "credential-anchor",
        "word_target": "long",
        "ask_size": "intro",
    },
    "mass_newsletter": {
        "framing": "peer-collaboration",
        "tone": "playful",
        "opener_type": "credential-anchor",
        "word_target": "long",
        "ask_size": "chat",
    },
}

_DEFAULT_RULE = {
    "framing": "knowledge-share",
    "tone": "warm",
    "opener_type": "cold",
    "word_target": "medium",
    "ask_size": "trial",
}

SLOT_NAMES = ["framing", "tone", "opener_type", "word_target", "ask_size"]

MIN_SAMPLES_FOR_BEST = 5

log = logging.getLogger(__name__)


def _names_enabled() -> bool:
    """LOCAL-ONLY toggle. When SEED_WITH_NAMES is truthy, the seeded DB stores
    real CRM person names instead of anonymized cluster labels. The resulting
    DB contains PII and must NEVER be deployed to the booth/public — it is for
    manually verifying clustering quality on the dev machine only."""
    return os.environ.get("SEED_WITH_NAMES", "").strip().lower() in ("1", "true", "yes")


def _choose_profile_name(real_name: str | None, cluster_label: str, idx: int, *, with_names: bool) -> str:
    """Anonymized label by default; real name only when explicitly opted in.
    Falls back to the anonymized form if a row has no usable name."""
    anonymized = f"{cluster_label} #{idx}"
    if with_names and real_name and real_name.strip():
        return real_name.strip()
    return anonymized


def _normalize_strategy(raw: str) -> str:
    return HDBSCAN_STRATEGY_ALIASES.get(raw, raw)


def _infer_seniority(job_title: str) -> str:
    t = job_title.lower()
    if any(kw in t for kw in ("ceo", "coo", "cfo", "cto", "chief", "director",
                               "vp", "vice president", "founder", "co-founder",
                               "partner", "head of", "president", "owner")):
        return "senior"
    if any(kw in t for kw in ("manager", "lead", "supervisor", "senior")):
        return "mid"
    return "early"


def _role_display(job_title: str | None, cluster_label: str) -> str:
    """User-visible role for a seeded profile. Only 398/744 rows carry a real
    job_title; the cluster_label values already read like roles ("Marketing
    Manager", "Marketing Investor"), so they are a better fallback than the
    bare literal "Professional"."""
    if job_title and job_title.strip():
        return job_title.strip()
    if cluster_label and cluster_label.strip():
        return cluster_label.strip()
    return "Professional"


def _build_profile_text(job_title: str, organization: str) -> str:
    parts = []
    if job_title:
        parts.append(job_title)
    if organization:
        parts.append(f"at {organization}")
    return " ".join(parts)


def _parse_timestamp(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    cleaned = raw.replace("Z", "+00:00")
    return datetime.fromisoformat(cleaned)


def _make_slots_json(strategy_name: str) -> list[dict]:
    rule_def = STRATEGY_TO_RULE.get(strategy_name, _DEFAULT_RULE)
    return [
        {"name": name, "kind": "static", "value": rule_def[name], "prompt": None}
        for name in SLOT_NAMES
    ]


def _best_strategy_for_cluster(rows: list[dict]) -> str:
    strategy_stats: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
    for row in rows:
        strategy = _normalize_strategy(row["strategy"])
        replies, total = strategy_stats[strategy]
        is_reply = 1 if row["outcome"] == "reply" else 0
        strategy_stats[strategy] = (replies + is_reply, total + 1)

    best_strategy = "general_intro"
    best_rate = -1.0
    for strategy, (replies, total) in strategy_stats.items():
        if total < MIN_SAMPLES_FOR_BEST:
            continue
        rate = replies / total
        if rate > best_rate:
            best_rate = rate
            best_strategy = strategy

    return best_strategy


def _assign_day_buckets(timestamps: list[datetime], n_buckets: int = 10) -> list[int]:
    if not timestamps:
        return []
    epoch = [t.timestamp() for t in timestamps]
    mn, mx = min(epoch), max(epoch)
    span = mx - mn if mx > mn else 1.0
    return [min(n_buckets, max(1, int((e - mn) / span * n_buckets) + 1)) for e in epoch]


async def seed_from_eval() -> None:
    from backend.clustering.cluster import embed

    for suffix in ("", "-shm", "-wal"):
        Path(f"{DB_PATH}{suffix}").unlink(missing_ok=True)

    engine = create_async_engine(DB_URL, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    with open(DATASET_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)

    print(f"Loaded {len(all_rows)} rows from {DATASET_PATH}")

    with_names = _names_enabled()
    if with_names:
        # LOCAL-ONLY: the DB will hold real CRM person names (PII).
        log.warning(
            "SEED_WITH_NAMES is ON — seeding edra_lounge.db with REAL person names (PII). "
            "This DB is for local clustering verification only and must NEVER be deployed."
        )
        print("WARNING: seeding with REAL names (PII) — local verification only, do NOT deploy this DB")

    clusters: dict[str, list[dict]] = defaultdict(list)
    for row in all_rows:
        clusters[row["cluster_label"]].append(row)

    print(f"Found {len(clusters)} clusters: {', '.join(sorted(clusters.keys()))}")

    print("\nComputing embeddings for all profiles...")
    profile_texts = []
    for i, row in enumerate(all_rows):
        cluster_label = row.get("cluster_label", "")
        role = _role_display(row.get("job_title"), cluster_label)
        organization = row.get("organization") or "Unknown"
        profile_texts.append(_build_profile_text(role, organization))

    BATCH_SIZE = 128
    all_profile_embeddings: list[list[float]] = []
    for start in range(0, len(profile_texts), BATCH_SIZE):
        batch = profile_texts[start:start + BATCH_SIZE]
        all_profile_embeddings.extend(embed(batch))
        print(f"  Embedded {min(start + BATCH_SIZE, len(profile_texts))}/{len(profile_texts)}")

    print("\nComputing embeddings for episode summaries...")
    summary_texts = []
    for row in all_rows:
        snippet = (row.get("clean_snippet") or "")[:200]
        summary_texts.append(snippet if snippet else "outreach episode")

    all_summary_embeddings: list[list[float]] = []
    for start in range(0, len(summary_texts), BATCH_SIZE):
        batch = summary_texts[start:start + BATCH_SIZE]
        all_summary_embeddings.extend(embed(batch))
        print(f"  Embedded {min(start + BATCH_SIZE, len(summary_texts))}/{len(summary_texts)}")

    now = datetime.now(timezone.utc)
    all_timestamps = [_parse_timestamp(row.get("outreach_timestamp")) for row in all_rows]
    day_buckets = _assign_day_buckets(all_timestamps)

    cluster_id_map: dict[str, str] = {}
    cluster_profile_ids: dict[str, list[str]] = defaultdict(list)
    cluster_episode_ids: dict[str, list[str]] = defaultdict(list)
    cluster_embeddings: dict[str, list[list[float]]] = defaultdict(list)
    cluster_reply_counts: dict[str, tuple[int, int]] = {}

    for label, rows in clusters.items():
        cid_num = int(rows[0]["cluster_id"])
        cid = str(cid_num)
        cluster_id_map[label] = cid

        replies = sum(1 for r in rows if r["outcome"] == "reply")
        cluster_reply_counts[cid] = (replies, len(rows))

    print("\nInserting profiles and episodes...")
    async with session_factory() as session:
        for i, row in enumerate(all_rows):
            cluster_label = row["cluster_label"]
            role = _role_display(row.get("job_title"), cluster_label)
            organization = row.get("organization") or "Unknown"
            cid = cluster_id_map[cluster_label]

            profile_id = f"eval:{i}"
            episode_id = f"eval_ep:{i}"

            cluster_profile_ids[cid].append(profile_id)
            cluster_episode_ids[cid].append(episode_id)
            cluster_embeddings[cid].append(all_profile_embeddings[i])

            strategy = _normalize_strategy(row["strategy"])
            slots_json = _make_slots_json(strategy)
            is_reply = row["outcome"] == "reply"

            session.add(ProfileRow(
                id=profile_id,
                source_kind="synthetic",
                source_identifier=f"eval_dataset:{i}",
                name=_choose_profile_name(row.get("name"), cluster_label, i, with_names=with_names),
                role=role,
                domain=organization,
                seniority=_infer_seniority(role),
                headline=f"{role} at {organization}",
                recent_signals=[],
                archetype_summary=_build_profile_text(role, organization),
                avatar_url=None,
                summary_text=profile_texts[i],
                embedding=all_profile_embeddings[i],
                fetched_at=now,
                ttl_seconds=None,
                cluster_id=cid,
            ))

            session.add(EpisodeRow(
                id=episode_id,
                timestamp=all_timestamps[i],
                day=day_buckets[i],
                profile_id=profile_id,
                cluster_id=cid,
                pitch_strategy=dict(zip(SLOT_NAMES, [slots_json[j]["value"] for j in range(5)])),
                dialogue=[],
                final_interest=4 if is_reply else -2,
                outcome="accepted" if is_reply else "rejected",
                summary=(row.get("clean_snippet") or "")[:200],
                summary_embedding=all_summary_embeddings[i],
                rule_applied_top=f"R.{int(row['cluster_id']):02d}",
            ))

        await session.commit()
        print(f"  Inserted {len(all_rows)} profiles and {len(all_rows)} episodes")

    print("\nCreating clusters and rules...")
    async with session_factory() as session:
        for label in sorted(clusters.keys()):
            cid = cluster_id_map[label]
            rows = clusters[label]
            replies, total = cluster_reply_counts[cid]
            success = replies / total if total > 0 else 0.0

            embs = cluster_embeddings[cid]
            centroid = np.mean(np.array(embs), axis=0).tolist() if embs else []

            best_strategy = _best_strategy_for_cluster(rows)

            session.add(ClusterRow(
                id=cid,
                label=label,
                profile_ids=cluster_profile_ids[cid],
                episode_ids=cluster_episode_ids[cid],
                centroid_embedding=centroid,
                size=len(rows),
                success_ratio=success,
                created_at=now,
                last_updated=now,
            ))

            rule_id = f"R.{int(cid):02d}"
            session.add(RuleRow(
                id=rule_id,
                cluster_id=cid,
                slots=_make_slots_json(best_strategy),
                induced_at=now,
                induced_from_episode_ids=cluster_episode_ids[cid][:10],
                status="active",
                deprecated_by=None,
                cs_history=[[now.isoformat(), success]],
            ))

            print(f"  Cluster {cid} ({label}): {len(rows)} rows, "
                  f"{replies}/{total} replies ({success:.1%}), "
                  f"best strategy: {best_strategy}")

        await session.commit()

    print("\nCreating agents...")
    async with session_factory() as session:
        for label in sorted(clusters.keys()):
            cid = cluster_id_map[label]
            agent_id = f"agent_{cid}"
            session.add(AgentRow(
                id=agent_id,
                cluster_id=cid,
                zone_description=f"Outreach agent for {label} segment",
                created_at=now,
                is_active=True,
            ))
        await session.commit()
        print(f"  Created {len(clusters)} agents")

    async with session_factory() as session:
        from sqlalchemy import func, select
        p_count = (await session.execute(select(func.count(ProfileRow.id)))).scalar()
        e_count = (await session.execute(select(func.count(EpisodeRow.id)))).scalar()
        c_count = (await session.execute(select(func.count(ClusterRow.id)))).scalar()
        r_count = (await session.execute(select(func.count(RuleRow.id)))).scalar()
        a_count = (await session.execute(select(func.count(AgentRow.id)))).scalar()

    print(f"\nDone: {p_count} profiles, {e_count} episodes, "
          f"{c_count} clusters, {r_count} rules, {a_count} agents")

    import json as _json
    umap_profiles_path = Path("evaluation/data/umap_profiles.npy")
    if umap_profiles_path.exists():
        from umap import UMAP as _UMAP
        umap_15d = np.load(umap_profiles_path)
        coords_2d = _UMAP(n_components=2, random_state=42, metric="euclidean", min_dist=0.5, spread=2.0).fit_transform(umap_15d)
        x_min, x_max = coords_2d[:, 0].min(), coords_2d[:, 0].max()
        y_min, y_max = coords_2d[:, 1].min(), coords_2d[:, 1].max()
        x_range = x_max - x_min if x_max > x_min else 1.0
        y_range = y_max - y_min if y_max > y_min else 1.0
        margin = 0.08
        coords_map = {}
        for i, row in enumerate(all_rows):
            pid = f"eval:{i}"
            nx = margin + (1 - 2 * margin) * (coords_2d[i, 0] - x_min) / x_range
            ny = margin + (1 - 2 * margin) * (coords_2d[i, 1] - y_min) / y_range
            coords_map[pid] = [round(float(nx), 5), round(float(ny), 5)]
        coords_path = Path("data/viz_coords_2d.json")
        coords_path.parent.mkdir(parents=True, exist_ok=True)
        coords_path.write_text(_json.dumps(coords_map), encoding="utf-8")
        print(f"Saved {len(coords_map)} pre-computed 2D coords to {coords_path}")

    await engine.dispose()


def main() -> None:
    asyncio.run(seed_from_eval())


if __name__ == "__main__":
    main()
