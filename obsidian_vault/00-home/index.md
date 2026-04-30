---
tags: [home, index]
date: 2026-04-30
---

# EDRA — Vault Home

Booth demo + research artifact для **EDRA** (Experience-Driven Rule Adaptation). Тематический wrapper — visual-novel сцена с anime-агентом, представляющим research-collaboration от **DEFY.group**. Бывший рабочий заголовок "Lounge / Café Manager" устарел на 2026-04-28 — см. [[../sessions/2026-04-28 Re-pivot to VN Pitch Floor, vocabulary swap]].

Spec: [`../../TASK.md`](../../TASK.md) (живой документ, переписан 2026-04-28)
Mockup: [`../../frontend/edra_pitch_mockup.html`](../../frontend/edra_pitch_mockup.html) (финальный, портируется verbatim)

## Архитектура (2 слоя)

1. **Backend** (Python / FastAPI) — [`../../backend/`](../../backend/)
   - `orchestrator.py` — три asyncio-loop (tick / consistency / factory) + `on_new_episode` reactive hook
   - Core modules: `memory`, `clustering`, `induction`, `monitor`, `reflection`, `factory`, `simulator`, `pitch`, `llm`
   - **Новое**: `profile_source/` — Protocol + Synthetic + LinkedIn-RapidAPI (load-bearing для научного фрейминга, TASK.md §4.1)
   - Никаких external orchestrators. Всё в-процессе FastAPI / asyncio.
2. **Frontend** (vanilla HTML/JS) — [`../../frontend/`](../../frontend/)
   - VN-сцена: anime portrait в центре, VN textbox внизу, interest gauge от −5 до +5, три hover-out панели (top/left/right)
   - Polling `GET /state` каждую секунду + SSE на `/reflections/stream/{id}` во время revision

## Vocabulary cheat-sheet (после пивота 2026-04-28)

| Концепт | Тип | Значения / форма |
|---|---|---|
| `Profile` | объект | `id, source_kind, source_identifier, name, role, domain, seniority, headline, recent_signals[], archetype_summary, embedding, fetched_at, ttl_seconds` |
| `PitchStrategy` | объект | 5 слотов: `framing, tone, opener_type, word_target, ask_size` (TASK.md §4.3) |
| `FRAMING` | literal | `strategic-alignment, peer-collaboration, knowledge-share, applied-curiosity, skeptical-respect, follow-up-comment` |
| `TONE` | literal | `formal, warm, socratic, direct, playful` |
| `OPENER_TYPE` | literal | `question, reference-to-signal, shared-context, credential-anchor, cold` |
| `WORD_TARGET` | literal | `short ~30, medium ~80, long ~120` |
| `ASK_SIZE` | literal | `chat, co-author, intro, trial, none` |
| `Episode.dialogue` | list | `[DialogueStep]` 3–7 шагов, каждый с `agent_thought, agent_reply, visitor_choice, interest_delta` |
| `Episode.outcome` | literal | `accepted, exploring, rejected, abandoned` |
| Interest gauge | int | `−5..+5`; ±5 завершает сессию |

## Где научный track?

Doctoral-proposal с реальными Pipedrive-данными живёт в **EDRA repo** (`../EDRA/`). Тот трек на паузе — Lounge/PitchFloor (этот репо) — фокус до закрытия booth-демки.

## Status

- 2026-04-21: репо отчленили от EDRA, Phase 1 skeleton (café vocab) сделан
- 2026-04-28 (утро): автор переписал TASK.md → пивот на VN Pitch Floor + research-outreach vocab; финальный мокап `edra_pitch_mockup.html` в репо. См. [[../sessions/2026-04-28 Re-pivot to VN Pitch Floor, vocabulary swap]]
- 2026-04-28 (день): **Phase 1B → 2 → 3 завершены за одну сессию**. Booth работает в синтетике и live(mock); 62/62 теста зелёных. См. [[../sessions/2026-04-28 Phase 1B-2-3 shipped, live-mode booth wired]]. Открытые задачи Phase 4 — в [[current priorities]]
- 2026-04-29: **Phase 4.1 → 4.4 завершены за одну сессию**. Real LinkedIn fetch (после двух sunset'нувшихся RapidAPI провайдеров → `fresh-linkedin-scraper-api`) + OpenAI как третий LLM-mode + LLM-driven continuations с историей + visible logging + avatar plumbing. End-to-end проверено против реального профиля автора, 71/71 теста зелёных. См. [[../sessions/2026-04-29 Phase 4.1-4.4 shipped, OpenAI live-mode validated]]. Открытые задачи Phase 5 — в [[current priorities]]
- 2026-04-30: **Phase 5 prep — аналитическая сессия, кода не трогали**. Аудит всех 6 промптов, identified корневая проблема — отсутствие конкретики про Defy в system message → галлюцинации. Public research реального DEFY.group (defygroup.ai + WebSearch): **Defy = AI-SaaS для creative agencies** (3 продукта Monitor/Automate/Report, founders Ian Cassidy + Alek Farseev) — расхождение с EDRA-вокабом (academic outreach). Сформирован questionnaire к founders (6 вопросов, английский). Phase 5 разбит на 5 sub-stages, 5.1 BLOCKED на ответы founders. См. [[../sessions/2026-04-30 Phase 5 prep — prompt audit + Defy fact research]]

## Navigation

- [[current priorities]] — статус фаз + Phase 5 backlog + questionnaire к founders + tech debt
- [[../sessions/2026-04-30 Phase 5 prep — prompt audit + Defy fact research]] — аналитическая сессия: аудит промптов + Defy research + questionnaire к founders + Путь A/B/C
- [[../sessions/2026-04-29 Phase 4.1-4.4 shipped, OpenAI live-mode validated]] — implementation сессия Phase 4.1/4.2/4.3/4.4 + e2e против реального LinkedIn
- [[../sessions/2026-04-28 Phase 1B-2-3 shipped, live-mode booth wired]] — implementation сессия Phase 1B/2/3 + UI iteration
- [[../sessions/2026-04-28 Re-pivot to VN Pitch Floor, vocabulary swap]] — пивот-сессия, что выкидываем / что оставляем
- [[../sessions/2026-04-21 Pivot to Lounge demo, skeleton shipped]] — историческая сессия с café-каркасом (vocab устарел, инфраструктура жива)
