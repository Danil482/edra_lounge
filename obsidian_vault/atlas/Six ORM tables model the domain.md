---
tags: [atlas, database, orm, sqlalchemy]
date: 2026-05-13
---

# Six ORM tables model the domain

SQLAlchemy async ORM over SQLite (aiosqlite). All tables defined in `backend/memory/models.py`.

| Table | Key columns | Role |
|---|---|---|
| **ProfileRow** | id, source_kind, source_identifier, name, role, domain, seniority, headline, recent_signals[], avatar_url, embedding, fetched_at, ttl_seconds | Root entity — visitor identity |
| **EpisodeRow** | id, profile_id (FK), cluster_id, pitch_strategy (JSON), dialogue (JSON), final_interest, outcome, summary, summary_embedding | One completed conversation |
| **ClusterRow** | id, label, profile_ids, episode_ids, centroid_embedding, size, success_ratio | Grouping of similar episodes |
| **RuleRow** | id, cluster_id (FK), slots (JSON — 5 RuleSlot), status (active/under_revision/deprecated), cs_history | Induced pitch strategy for a cluster |
| **RevisionRow** | id, rule_id (FK), contradicting_episode_ids, llm_reasoning, proposed_rule (JSON), decision (pending/approved/rejected) | Rule revision record |
| **AgentRow** | id, cluster_id (FK), zone_description, is_active | Stub for uncovered clusters |

## Design choices

- Complex fields (embeddings, lists, nested models) stored as JSON — no separate join tables.
- No explicit indexes except `source_kind` on ProfileRow and `cluster_id` on EpisodeRow.
- `init_db()` runs idempotent migration for `avatar_url` column added in Phase 4.
- Live profiles have `ttl_seconds=3600` — see [[Live profile PII expires after one hour]].

## Key files

- `backend/memory/models.py` — all six models
- `backend/db.py` — async engine + session factory + init
