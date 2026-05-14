---
tags: [session, outreach, agents, orchestrator, presentation, farseev]
date: 2026-05-14
---

# 2026-05-14 Outreach module and orchestrator workflow

Major session: established orchestrator workflow, built outreach module through Phase O.2, created Farseev academic writing skill, prepared presentation speech notes, and validated first real email send via Resend API.

## What was done

### Orchestrator workflow
1. **Created `/begin` slash command** (`~/.claude/commands/begin.md`) — reads CLAUDE.md, Obsidian home, latest session, agent files, and `.planning/` on startup; outputs a concise project briefing.
2. **Created 4 universal agent definitions** in `~/.claude/agents/`:
   - `developer.md` — senior Python developer, writes production code
   - `tester.md` — QA engineer, writes tests and reports bugs
   - `designer.md` — frontend designer, implements UI from mockups
   - `planner.md` — technical planner, discusses next steps without writing code
3. **Updated CLAUDE.md** with orchestrator model: main Claude delegates tasks to specialized agents, does not write code itself. Reviews results and discusses next steps with the user.

### Outreach module — Phase O.1 (foundation)
4. **`backend/outreach/csv_source.py`** — CSV-to-Profile mapper for 502-row dataset. Confidence filtering, seniority heuristic, `csv:{handle}` ID format, `ttl_seconds=None`.
5. **`backend/outreach/state.py`** — OutreachRow SQLAlchemy model in separate `outreach.db`. State machine: draft -> reviewed -> sent -> response_received/cutoff_expired -> classified -> ingested. Full CRUD operations.
6. **`backend/outreach/episode_builder.py`** — builds EDRA Episodes from outreach data. Maps 8 response classifications to EDRA outcomes.
7. **68 tests written** in `tests/test_outreach.py` — 139 total tests pass (68 new + 71 existing).

### Outreach module — Phase O.2 (message generation + sending)
8. **`backend/llm/prompts/outreach.txt`** — cold outreach prompt with research framing, Farseev lab context, subject line as first output line, 80-120 word body.
9. **`backend/llm/prompts/classify_response.txt`** — 5-category response classification prompt.
10. **`backend/outreach/generate.py`** — message generation + response classification via `llm.client`.
11. **`backend/outreach/sender.py`** — Resend API email sender (httpx, no SDK). From: `daniel@defygroup.ai`.
12. **`backend/outreach/cli.py`** — full CLI with 8 commands: prepare, review, mark-reviewed, send, record-response, classify, check-cutoffs, status.
13. **First real test send** — 3 personalized emails generated via GPT-4o-mini, sent via Resend to `daniel@defygroup.ai`. All 3 delivered successfully.

### Academic writing skill
14. **`.claude/skills/farseev-academic-voice.md`** — comprehensive skill for writing scientific text in Aleksandr Farseev's style. Built from Google Scholar analysis (774 citations, h-index 17), deep reading of "Against Opacity" (MM 2023) and SOMONITOR (2024). Covers argumentation patterns, vocabulary, section structure, anti-patterns, tone calibration.

### Presentation and paper
15. **`papers/speech_notes.md`** — speech notes for all 11 slides of `edra_presentation.html`. System explanation narrative + per-slide speaker notes, ~12-15 min total.
16. **`papers/edra_demo.tex`** — full style audit and rewrite to match Farseev's voice. Abstract, introduction (history-to-crisis escalation), section titles (provocative), related work (problem-oriented), conclusion ("We strongly believe...").

### CLAUDE.md updates
17. Added **orchestrator workflow** section (delegate to agents, don't write code)
18. Added **never read .env** rule (rule #2 in secrets section)
19. Added `RESEND_API_KEY` to secrets list

## What was NOT done

- **Domain verification** for `defygroup.ai` in Resend — required for sending to external recipients. Currently can only send to the account owner's email.
- **Phase O.3** (CLI workflow refinements, ingest.py) — planned, not started
- **Phase O.4-O.5** (email discovery, feedback loop automation) — planned, not started
- **Email collection** for the 502 LinkedIn profiles — deferred to a web search agent run

## Key decisions

- **Iteration 1 = pure improvisation** — no rules, no strategy planner. LLM writes freely-personalized messages. Data collection for future rule induction.
- **Research framing** for outreach (not Defy business) — affects IRB requirements
- **Resend over SendGrid** — simpler API, httpx-only, no SDK
- **Manual workflow** for now — manual cutoffs, manual classification review, manual ingestion
- **Separate `outreach.db`** — keeps booth demo DB clean

## Open questions

- [ ] Domain verification for `defygroup.ai` in Resend (DNS records needed)
- [ ] Email discovery for 502 profiles — web search agent or manual?
- [ ] IRB decision — is this a research study requiring review?
- [ ] Phase 5.1 still blocked on founder questionnaire (no update since 2026-04-30)

## Next session — entry points

1. **Verify `defygroup.ai` domain** in Resend, then test full send to `danial92335@mail.ru`
2. **Collect emails** for a batch of 20 High-confidence profiles via web search agent
3. **First real outreach batch** — prepare, review, send to actual researchers
4. **Phase O.3** — build ingest.py for feeding episodes back into EDRA
5. **If founders reply** → Phase 5.1 (fact sheet + prompt rewrite)

See [[../00-home/current priorities]] for the full phase board.
