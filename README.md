# EDRA Lounge

Booth demo of **Experience-Driven Rule Adaptation** (EDRA) wrapped as a
visual-novel "pitch floor" — an anime agent representing research
collaboration from [DEFY.group](https://defygroup.ai) takes a visitor
profile (synthetic archetype or live LinkedIn) and runs a multi-turn
pitch dialogue against it.

Spec: see [`TASK.md`](TASK.md). This repo is the implementation.
Project rules for AI assistants: see [`CLAUDE.md`](CLAUDE.md).
Status board: [`obsidian_vault/00-home/current priorities.md`](obsidian_vault/00-home/current%20priorities.md).

## Quickstart

```bash
pip install -e ".[dev]"
cp .env.example .env
make demo         # backend on :8000 (frontend mounted at /)
# open http://localhost:8000
```

Two-layer architecture: Python/FastAPI backend + vanilla HTML/JS frontend.
**No external orchestrator** — tick / consistency / factory loops run as
asyncio tasks inside the FastAPI process (see `backend/orchestrator.py`).

### Modes

- **Synthetic booth** — `make demo` (default). Self-playing 5-minute
  scenario unfolds on `seeded_run.yaml`, archetypes drawn from
  `backend/data/archetypes.yaml`. No network calls.
- **Live booth** — `LIVE_MODE=true RAPIDAPI_KEY=<key> LLM_MODE=openai make demo`.
  Visitor pastes a LinkedIn URL → RapidAPI fetch → real profile lands
  in the right panel → OpenAI generates a personalised opener.
- **Mock-live booth** — `LIVE_MODE=true RAPIDAPI_KEY=mock make demo`.
  No real RapidAPI call; the LinkedIn source short-circuits to a
  hand-crafted author profile. Useful for offline demos and CI.

## Layout

```
backend/
  app.py            FastAPI entry + lifespan (starts Orchestrator)
  orchestrator.py   asyncio loops + on_new_episode reactive hook
  memory/           SQLAlchemy ORM + Pydantic/DB bridge + seed
  clustering/       HDBSCAN over MiniLM embeddings + UMAP projection
  induction/        Cluster -> Rule (LLM, slot schema, mode-of-slots fallback)
  monitor/          Consistency score + revise trigger
  reflection/       Revision streaming over SSE
  factory/          Uncovered-cluster detection + agent spawning + privacy purge
  simulator/        Deterministic visitor + preference matrix + drift
  profile_source/   Protocol + SyntheticProfileSource + LinkedInRapidAPISource
  pitch/            Turn generation (static / hybrid / improvise) + templates fallback
  sessions/         start_session / take_turn / end_session lifecycle
  llm/              httpx-based Ollama/Anthropic/OpenAI client + 6 prompt templates
  routers/          FastAPI endpoint groups (one module per resource)
frontend/           index.html + styles.css + app.js (no build, polling + SSE)
seeded_run.yaml     Pre-recorded 3-day visit schedule
tests/              pytest (71 tests as of 2026-04-29)
obsidian_vault/     Per-session working notes + the live status board
```

## LLM modes

Switched via `LLM_MODE` env var. All three providers go through `httpx`
directly — no SDKs (`backend/llm/client.py`).

- `local` — Ollama at `localhost:11434`, model from `OLLAMA_MODEL`.
- `remote` — Anthropic API; needs `ANTHROPIC_API_KEY`.
- `openai` — OpenAI Chat Completions API; needs `OPENAI_API_KEY` and
  `OPENAI_MODEL` (default `gpt-4o-mini`).

## Profile sources

`ProfileSource` is a `typing.Protocol` (`backend/profile_source/__init__.py`)
with two implementations:

- `SyntheticProfileSource` — reads archetypes from
  `backend/data/archetypes.yaml`, instant fetch.
- `LinkedInRapidAPISource` — two-endpoint fetch against
  `fresh-linkedin-scraper-api.p.rapidapi.com`, on-disk cache at
  `data/linkedin_cache/<slug>.json`, raw-response dumps to
  `data/linkedin_raw/` for parser iteration (both gitignored).
- Mock-key path: `RAPIDAPI_KEY=mock` short-circuits before parsing
  and returns a hand-crafted author profile, no HTTP request.

Privacy purge: non-synthetic profile rows older than 1 hour are deleted
by `purge_expired_live_profiles` (called from the factory loop every
30s, enforced by `tests/test_privacy_purge.py`).

## Status

- **Phases 1A → 4.4 shipped** (2026-04-28 → 2026-04-29). Booth fully
  functional with real LinkedIn fetch + OpenAI generation, 71/71 tests
  green, end-to-end validated against a real profile.
- **Phase 5 — prompts and scenarios** (in progress, BLOCKED on founder
  answers to the questionnaire in
  [`current priorities.md`](obsidian_vault/00-home/current%20priorities.md)).
  Root cause of current hallucinations: the prompts contain no concrete
  Defy facts; rewriting them is gated on those answers.
- **Phase 6 — research profiles dataset** (done, 2026-05-13). Built a
  502-row balanced candidate pool of LinkedIn profiles as the prep
  substrate for Phase 5 outreach testing. Lives at
  `research_profiles_master.csv` (gitignored, local-only until cleared
  for publication).

For the full phase board, see
[`obsidian_vault/00-home/current priorities.md`](obsidian_vault/00-home/current%20priorities.md).

## Tests

```bash
pytest
```

71 tests across orchestrator resilience, preference invariants,
profile-source protocol conformance, import-graph isolation, LinkedIn
parser, and the privacy-purge contract.
