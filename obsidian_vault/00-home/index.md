---
tags: [home, index]
date: 2026-05-13
---

# EDRA — Vault Home

Booth demo + research artifact for **EDRA** (Experience-Driven Rule Adaptation). Thematic wrapper — a visual-novel scene with an anime agent representing research collaboration from **DEFY.group**. The earlier working title "Lounge / Café Manager" was retired on 2026-04-28 — see [[../sessions/2026-04-28 Re-pivot to VN Pitch Floor, vocabulary swap]].

Spec: [`../../TASK.md`](../../TASK.md) (living document, rewritten 2026-04-28)
Mockup: [`../../frontend/edra_pitch_mockup.html`](../../frontend/edra_pitch_mockup.html) (final, ported verbatim)

## Architecture (2 layers)

1. **Backend** (Python / FastAPI) — [`../../backend/`](../../backend/)
   - `orchestrator.py` — three asyncio loops (tick / consistency / factory) + `on_new_episode` reactive hook
   - Core modules: `memory`, `clustering`, `induction`, `monitor`, `reflection`, `factory`, `simulator`, `pitch`, `llm`
   - **New**: `profile_source/` — Protocol + Synthetic + LinkedIn-RapidAPI (load-bearing for the scientific framing, TASK.md §4.1)
   - No external orchestrators. Everything in-process inside FastAPI / asyncio.
2. **Frontend** (vanilla HTML/JS) — [`../../frontend/`](../../frontend/)
   - VN scene: anime portrait centred, VN textbox bottom, interest gauge from −5 to +5, three hover-out panels (top/left/right)
   - Polling `GET /state` every second + SSE on `/reflections/stream/{id}` during revision

## Vocabulary cheat-sheet (post-pivot 2026-04-28)

| Concept | Kind | Values / shape |
|---|---|---|
| `Profile` | object | `id, source_kind, source_identifier, name, role, domain, seniority, headline, recent_signals[], archetype_summary, embedding, fetched_at, ttl_seconds` |
| `PitchStrategy` | object | 5 slots: `framing, tone, opener_type, word_target, ask_size` (TASK.md §4.3) |
| `FRAMING` | literal | `strategic-alignment, peer-collaboration, knowledge-share, applied-curiosity, skeptical-respect, follow-up-comment` |
| `TONE` | literal | `formal, warm, socratic, direct, playful` |
| `OPENER_TYPE` | literal | `question, reference-to-signal, shared-context, credential-anchor, cold` |
| `WORD_TARGET` | literal | `short ~30, medium ~80, long ~120` |
| `ASK_SIZE` | literal | `chat, co-author, intro, trial, none` |
| `Episode.dialogue` | list | `[DialogueStep]` 3-7 steps, each with `agent_thought, agent_reply, visitor_choice, interest_delta` |
| `Episode.outcome` | literal | `accepted, exploring, rejected, abandoned` |
| Interest gauge | int | `−5..+5`; ±5 terminates the session |

## Where is the scientific track?

The doctoral proposal with real Pipedrive data lives in the **EDRA repo** (`../EDRA/`). That track is on pause — Lounge/PitchFloor (this repo) is the focus until the booth demo lands.

## Status

- 2026-04-21: repo split off from EDRA, Phase 1 skeleton (café vocab) done
- 2026-04-28 (morning): the author rewrote TASK.md → pivot to VN Pitch Floor + research-outreach vocab; final mockup `edra_pitch_mockup.html` in the repo. See [[../sessions/2026-04-28 Re-pivot to VN Pitch Floor, vocabulary swap]]
- 2026-04-28 (day): **Phase 1B → 2 → 3 done in one session**. Booth works in synthetic and live(mock); 62/62 tests green. See [[../sessions/2026-04-28 Phase 1B-2-3 shipped, live-mode booth wired]]. Open items for Phase 4 → [[current priorities]]
- 2026-04-29: **Phase 4.1 → 4.4 done in one session**. Real LinkedIn fetch (after two sunset RapidAPI providers → `fresh-linkedin-scraper-api`) + OpenAI as the third LLM mode + LLM-driven continuations with history + visible logging + avatar plumbing. End-to-end validated against the author's real profile, 71/71 tests green. See [[../sessions/2026-04-29 Phase 4.1-4.4 shipped, OpenAI live-mode validated]]. Open items for Phase 5 → [[current priorities]]
- 2026-04-30: **Phase 5 prep — analytical session, no code changes**. Audited all 6 prompts, identified the root cause — no Defy specifics in the system message → hallucinations. Public research on the real DEFY.group (defygroup.ai + WebSearch): **Defy = AI-SaaS for creative agencies** (3 products Monitor/Automate/Report, founders Ian Cassidy + Alek Farseev) — mismatch with the EDRA vocabulary (academic outreach). Drafted a 6-question founder questionnaire (in English). Phase 5 split into 5 sub-stages, 5.1 BLOCKED on founders. See [[../sessions/2026-04-30 Phase 5 prep — prompt audit + Defy fact research]]
- 2026-05-13: **Phase 6 — research profiles dataset expanded 253 → 502**. Built a balanced candidate pool of verified LinkedIn profiles across 10 batches (OSS infra, applied engineers, APAC, Germany, France, Canada, industry research scientists, AI safety, AI4Science, under-represented regions). 0 schema violations, 0 duplicates. Segment + geographic balance restored. See [[../sessions/2026-05-13 Phase 6 — research profiles dataset 253 to 502]]

## Navigation

- [[current priorities]] — phase status + Phase 5 backlog + founder questionnaire + tech debt
- [[../sessions/2026-05-13 Phase 6 — research profiles dataset 253 to 502]] — Phase 6 dataset session: 10 batches, schema discipline, distribution audit
- [[../sessions/2026-04-30 Phase 5 prep — prompt audit + Defy fact research]] — analytical session: prompt audit + Defy research + founder questionnaire + Path A/B/C
- [[../sessions/2026-04-29 Phase 4.1-4.4 shipped, OpenAI live-mode validated]] — implementation session Phase 4.1/4.2/4.3/4.4 + e2e against real LinkedIn
- [[../sessions/2026-04-28 Phase 1B-2-3 shipped, live-mode booth wired]] — implementation session Phase 1B/2/3 + UI iteration
- [[../sessions/2026-04-28 Re-pivot to VN Pitch Floor, vocabulary swap]] — pivot session: what we drop / what we keep
- [[../sessions/2026-04-21 Pivot to Lounge demo, skeleton shipped]] — historical session with the café skeleton (vocab retired, infra survived)

## Project conventions

- All Obsidian notes are written in **English** (project-wide rule, see `CLAUDE.md` at repo root)
- Phase commits use the format `Phase N.M — <short title>` for code, `Obsidian — <session summary>` for Obsidian-only changes
- Secrets (RapidAPI key, OpenAI key, `.env`) are never committed; mock fallbacks must keep the booth working without real keys
