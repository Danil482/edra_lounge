---
tags: [home, index]
date: 2026-06-08
---

# EDRA — Vault Home

Booth demo + research artifact for **EDRA** (Experience-Driven Rule Adaptation). Thematic wrapper — a visual-novel scene with an anime agent representing research collaboration from **DEFY.group**. The earlier working title "Lounge / Cafe Manager" was retired on 2026-04-28 — see [[../sessions/2026-04-28 Re-pivot to VN Pitch Floor, vocabulary swap]].

Spec: [`../../TASK.md`](../../TASK.md) (living document, rewritten 2026-04-28)
Mockup: [`../../frontend/edra_pitch_mockup.html`](../../frontend/edra_pitch_mockup.html) (**DEPRECATED / stale** — the live `frontend/index.html` + `app.js` + `styles.css` are now the source of truth; the mockup predates the operator-panel/revision-preview/email-gate changes and should not be ported from)

## Vault structure

| Folder | What lives here |
|---|---|
| **00-home/** | This index + [[current priorities]] |
| **atlas/** | Architecture, stack, DB, deploy, data flow |
| **knowledge/integrations/** | Each external integration (LinkedIn, OpenAI, Ollama, MiniLM, SSE) |
| **knowledge/decisions/** | Architectural and process decisions with rationale |
| **knowledge/debugging/** | Bugs encountered and how they were resolved |
| **knowledge/patterns/** | Recurring code patterns worth documenting |
| **knowledge/business/** | Product, audience, Defy context |
| **sessions/** | One note per working session, dated |
| **inbox/** | Unprocessed ideas and raw notes |

## Atlas — architecture at a glance

- [[../atlas/EDRA runs three asyncio loops inside FastAPI]]
- [[../atlas/Six ORM tables model the domain]]
- [[../atlas/Three LLM providers share one httpx client]]
- [[../atlas/HDBSCAN clusters episodes by summary embeddings]]
- [[../atlas/Frontend polls state and streams revisions via SSE]]
- [[../atlas/Stack is Python 3.13 FastAPI with vanilla JS]]
- [[../atlas/Booth demo runs as single uvicorn process]]

## Key decisions

- [[../knowledge/decisions/All orchestration stays inside asyncio]]
- [[../knowledge/decisions/No LLM SDKs only httpx]]
- [[../knowledge/decisions/LLM generates by default templates are fallback]]
- [[../knowledge/decisions/Mock API key enables offline booth demos]]
- [[../knowledge/decisions/Live profile PII expires after one hour]]
- [[../knowledge/decisions/LinkedIn source is import-isolated from core]]
- [[../knowledge/decisions/Hybrid path C balances Defy facts with research vocab]]
- [[../knowledge/decisions/Lemlist replaces Resend for outreach delivery]]
- [[../knowledge/decisions/Prompt improvement plan based on lab papers]]

## Business context

- [[../knowledge/business/Defy sells Monitor Automate Report to creative agencies]]
- [[../knowledge/business/Booth demo presents EDRA research as visual novel]]
- [[../knowledge/business/Current archetypes model academic researchers not agencies]]
- [[../knowledge/business/Founder answers are needed to fix prompt hallucinations]]

## Status

- 2026-04-21: repo split off from EDRA, Phase 1 skeleton (cafe vocab) done
- 2026-04-28 (morning): pivot to VN Pitch Floor — see [[../sessions/2026-04-28 Re-pivot to VN Pitch Floor, vocabulary swap]]
- 2026-04-28 (day): **Phase 1B-2-3 shipped** — see [[../sessions/2026-04-28 Phase 1B-2-3 shipped, live-mode booth wired]]
- 2026-04-29: **Phase 4.1-4.4 shipped** — see [[../sessions/2026-04-29 Phase 4.1-4.4 shipped, OpenAI live-mode validated]]
- 2026-04-30: **Phase 5 prep** — see [[../sessions/2026-04-30 Phase 5 prep — prompt audit + Defy fact research]]
- 2026-05-13 (AM): **Phase 6 dataset** — see [[../sessions/2026-05-13 Phase 6 — research profiles dataset 253 to 502]]
- 2026-05-13 (PM): **Vault restructure + KNN clustering task** — see [[../sessions/2026-05-13 Vault restructure and KNN clustering task]]
- 2026-05-14 (AM): **Outreach module O.1-O.2 + orchestrator workflow** — see [[../sessions/2026-05-14 Outreach module and orchestrator workflow]]
- 2026-05-14 (PM): **Demo paper rewrite + email enrichment** — see [[../sessions/2026-05-14 Demo paper rewrite and email enrichment]]
- 2026-05-15: **Frontend polish + evaluation discussion** — see [[../sessions/2026-05-15 Frontend polish and evaluation discussion]]
- 2026-05-18: **Phase 8 shipped (8 commits) + Lemlist decision + E2E verified** — see [[../sessions/2026-05-18 Phase 8 frontend overhaul and Lemlist decision]]
- 2026-05-19: **Avatar regen + Phase 5.1-5.3 prompts + clustering fix** — see [[../sessions/2026-05-19 Avatar regen Phase 5 prompts and clustering fix]]
- 2026-05-20: **Phase 10 — demo paper rewrite, KNN classify, seed_demo, rulebook UI** — see [[../sessions/2026-05-20 Demo paper rewrite and live clustering]]
- 2026-05-20 (PM): **Evaluation methodology discussion** — see [[../sessions/2026-05-20 Evaluation methodology discussion with supervisor]]
- 2026-05-21: **Pipedrive mail API exploration for evaluation data** — see [[../sessions/2026-05-21 Pipedrive mail API exploration for evaluation data]]
- 2026-05-22: **Phase 11 — VN UX overhaul** — see [[../sessions/2026-05-22 VN UX overhaul and frontend polish]]
- 2026-05-25: **Pipedrive person mail extraction for evaluation** — see [[../sessions/2026-05-25 Pipedrive person mail extraction for evaluation]]
- 2026-05-25 (PM): **Evaluation literature review + presentation rewrite** — see [[../sessions/2026-05-25 Evaluation literature review and presentation rewrite]]
- 2026-05-26: **Evaluation module + cold outreach clustering** — see [[../sessions/2026-05-26 Evaluation module and cold outreach clustering]]
- 2026-05-26 (PM): **Bandit evaluation framework + presentation overhaul** — see [[../sessions/2026-05-26 Bandit evaluation framework and presentation overhaul]]
- 2026-05-27: **Clustering integration + demo paper rewrite** — see [[../sessions/2026-05-27 Clustering integration and demo paper rewrite]]
- 2026-05-27 (PM): **Eval cleanup + pitch escalation** — see [[../sessions/2026-05-27 Evaluation cleanup and pitch escalation]]
- 2026-05-28: **UMAP production pipeline + strategy reclassification** — see [[../sessions/2026-05-28 UMAP production pipeline and strategy reclassification]]
- 2026-05-28 (PM): **Chi-squared test + evaluation reorganization** — see [[../sessions/2026-05-28 Chi-squared test and evaluation reorganization]]
- 2026-05-29: **Evaluation pipeline refactor + 3-level validation** — see [[../sessions/2026-05-29 Evaluation pipeline refactor and 3-level validation]]
- 2026-05-31: **Demo paper rewrite + eval seed from real data** — see [[../sessions/2026-05-31 Demo paper rewrite and eval seed from real data]]
- 2026-06-01 (AM): **Live rule-revision demo theater + live-run fixes** — see [[../sessions/2026-06-01 Live rule-revision demo theater and live-run fixes]]
- 2026-06-01 (PM): **Centroid OOD gate + honest induced revision + viz palette** — see [[../sessions/2026-06-01 Centroid OOD gate induced revision and viz palette]]
- 2026-06-01 (eve): **KNN K=7 rewrite + reflection fixes + demo paper update** — see [[../sessions/2026-06-01 KNN rewrite reflection fixes and demo paper update]]
- 2026-06-03: **KNN config wiring + Lemlist integration + deployment research** — see [[../sessions/2026-06-03 KNN config wiring Lemlist integration and deployment research]]
- 2026-06-03 (PM): **Lemlist all-outcome follow-up + dialogue quality fixes** — see [[../sessions/2026-06-03 Lemlist all-outcome follow-up and dialogue quality fixes]]
- 2026-06-08 (PM): **GCP deploy guide + VM setup attempt** — see [[../sessions/2026-06-08 GCP deploy guide and VM setup attempt]]
- 2026-06-05: **Evaluation pipeline on full data + UMAP cluster viz** — see [[../sessions/2026-06-05 Evaluation pipeline full data and UMAP cluster viz]]

## Session log

- [[../sessions/2026-06-08 GCP deploy guide and VM setup attempt]]
- [[../sessions/2026-06-05 Evaluation pipeline full data and UMAP cluster viz]]
- [[../sessions/2026-06-03 Lemlist all-outcome follow-up and dialogue quality fixes]]
- [[../sessions/2026-06-03 KNN config wiring Lemlist integration and deployment research]]
- [[../sessions/2026-06-01 KNN rewrite reflection fixes and demo paper update]]
- [[../sessions/2026-06-01 Centroid OOD gate induced revision and viz palette]]
- [[../sessions/2026-06-01 Live rule-revision demo theater and live-run fixes]]
- [[../sessions/2026-05-31 Demo paper rewrite and eval seed from real data]]
- [[../sessions/2026-05-29 Evaluation pipeline refactor and 3-level validation]]
- [[../sessions/2026-05-28 Chi-squared test and evaluation reorganization]]
- [[../sessions/2026-05-28 UMAP production pipeline and strategy reclassification]]
- [[../sessions/2026-05-27 Evaluation cleanup and pitch escalation]]
- [[../sessions/2026-05-27 Clustering integration and demo paper rewrite]]
- [[../sessions/2026-05-26 Bandit evaluation framework and presentation overhaul]]
- [[../sessions/2026-05-26 Evaluation module and cold outreach clustering]]
- [[../sessions/2026-05-25 Evaluation literature review and presentation rewrite]]
- [[../sessions/2026-05-25 Pipedrive person mail extraction for evaluation]]
- [[../sessions/2026-05-22 VN UX overhaul and frontend polish]]
- [[../sessions/2026-05-21 Pipedrive mail API exploration for evaluation data]]
- [[../sessions/2026-05-20 Evaluation methodology discussion with supervisor]]
- [[../sessions/2026-05-20 Demo paper rewrite and live clustering]]
- [[../sessions/2026-05-19 Avatar regen Phase 5 prompts and clustering fix]]
- [[../sessions/2026-05-18 Phase 8 frontend overhaul and Lemlist decision]]
- [[../sessions/2026-05-15 Frontend polish and evaluation discussion]]
- [[../sessions/2026-05-14 Demo paper rewrite and email enrichment]]
- [[../sessions/2026-05-14 Outreach module and orchestrator workflow]]
- [[../sessions/2026-05-13 Vault restructure and KNN clustering task]]
- [[../sessions/2026-05-13 Phase 6 — research profiles dataset 253 to 502]]
- [[../sessions/2026-04-30 Phase 5 prep — prompt audit + Defy fact research]]
- [[../sessions/2026-04-29 Phase 4.1-4.4 shipped, OpenAI live-mode validated]]
- [[../sessions/2026-04-28 Phase 1B-2-3 shipped, live-mode booth wired]]
- [[../sessions/2026-04-28 Re-pivot to VN Pitch Floor, vocabulary swap]]
- [[../sessions/2026-04-21 Pivot to Lounge demo, skeleton shipped]]

## Project conventions

- All Obsidian notes are written in **English** (project-wide rule, see `CLAUDE.md` at repo root)
- File names are **statements, not categories** (e.g. "LLM generates by default templates are fallback.md")
- Wiki-links `[[note name]]` between related notes; frontmatter with `tags` and `date`
- Phase commits: `Phase N.M — <short title>` for code, `Obsidian — <session summary>` for vault-only changes
- Secrets (RapidAPI key, OpenAI key, `.env`) are never committed; mock fallbacks must keep the booth working
