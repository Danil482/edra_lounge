---
tags: [home, priorities, status]
date: 2026-04-30
---

# Current Priorities

Контекст пивота → [[../sessions/2026-04-28 Re-pivot to VN Pitch Floor, vocabulary swap]]
Сессия 2026-04-28 (Phase 1B/2/3) → [[../sessions/2026-04-28 Phase 1B-2-3 shipped, live-mode booth wired]]
Сессия 2026-04-29 (Phase 4.1-4.4) → [[../sessions/2026-04-29 Phase 4.1-4.4 shipped, OpenAI live-mode validated]]
Сессия 2026-04-30 (Phase 5 prep) → [[../sessions/2026-04-30 Phase 5 prep — prompt audit + Defy fact research]]

Каркас от 2026-04-21 был построен под café-метафору. После пивота 2026-04-28 проехали Phase 1B → 2 → 3 за одну сессию (booth готов в синтетике + live(mock)). 2026-04-29 — Phase 4.1 → 4.4 за одну сессию: новый RapidAPI-провайдер (после двух sunset'нувшихся), OpenAI как третий LLM-mode, переписанные промпты под 3-кнопочную UX-модель, LLM-driven continuations с историей, видимое логирование, avatar plumbing. **Booth полностью функционален с реальным LinkedIn-фетчем + OpenAI-генерацией, 71/71 теста зелёных, end-to-end сессия проверена против настоящего профиля автора.** 2026-04-30 — аналитическая сессия: аудит промптов, research реального Defy, обнаружено архитектурное расхождение (EDRA-вокаб ≠ Defy ICP), сформирован questionnaire к founders.

## ✅ Phase 1A — Vocabulary swap (готово, 2026-04-28)

См. коммит `fd5f4d6 Phase 1A — Vocabulary swap to VN Pitch Floor`.

## ✅ Phase 1B — Multi-turn dialogue + sessions API (готово, 2026-04-28)

См. коммит `227e0d4 Phase 1B — Multi-turn pitch sessions, rule pipeline wired`.

## ✅ Phase 2 — VN frontend (готово, 2026-04-28)

См. коммит `3773700 Phase 2 — Frontend port (Defy Brand V2.0)`.

## ✅ Phase 3 — Live mode + booth ready (готово, 2026-04-28)

См. коммит `d6a9525 Phase 3 — Live LinkedIn mode + privacy purge + Wi-Fi fallback` + UI fixes (`bb77896` + `ffd978a`).

## ✅ Phase 4 — Real LinkedIn + OpenAI + production-grade dialog (готово, 2026-04-29)

Все четыре подфазы плюс diagnostic-логирование:
- `c533f84` Phase 4.1 — 2-endpoint flow + disk cache (linkedin-data-api)
- `fd238c7` Phase 4.2 — OpenAI provider + switch to fresh-linkedin-scraper-api (после двух dead providers + parser hardening под реальную форму)
- `5eb9970` Phase 4.3 — Opener prompt fits visitor reaction buttons + LinkedIn avatar plumbing
- `d70aeda` Phase 4.4 — LLM-driven continuations + visible logging
- `3491146` + `5ff5ec4` — verbose diagnostic logging для следующих итераций

End-to-end проверка: реальный URL автора → cache hit → OpenAI генерит опенер про "competitive pricing" → 5 unique LLM-ответов → terminate на interest=+5 = `accepted`. Сожжено ~3 RapidAPI квоты за всю сессию.

## 🟡 Phase 5 — Промпты и сценарии (в работе, BLOCKED на founders)

После сегодняшнего e2e-прогона приоритеты сместились с "заработает ли вообще" на "качество и устойчивость". 2026-04-30 провели аудит промптов — корневая проблема не в diversity директиве, а в **отсутствии конкретики про Defy в промптах**: LLM галлюцинирует факты в каждом турне ("we partnered with major retail brand", "cohort of 20 brands") потому что в system message — единственная строка "You are a research-liaison agent." и ничего больше. Diversity-проблема — следствие: без фактов LLM выбирает единственную безопасную траекторию (enterprise sales credentials × N).

### 🚨 Архитектурное расхождение — Путь A/B/C (решение отложено до ответов founders)

Реальный Defy = **AI-SaaS для creative agencies** (3 продукта: Monitor / Automate / Report; founders Ian Cassidy + Alek Farseev), а текущий EDRA-вокаб предполагает **academic outreach** (PhD / postdoc / prof архетипы, ASK_SIZE=`co-author`/`intro`/`trial`).

- **Путь A**: переписать архетипы под agency ICP — ломает preference matrix, drift events, тесты
- **Путь B**: оставить research-narrative как booth-wrapper — на booth диссонанс с реальным DEFY.group в LinkedIn, skeptical-defusing невозможен без выдумок
- **Путь C (рекомендую)**: гибрид — research-archetypes остаются в синтетике, но промпты переписаны на реальные Defy-факты, refusal behavior закрывает edge cases когда визитёр явно вне ICP

### Phase 5.1 — Defy fact sheet 🔒 BLOCKED (наивысший приоритет)

Ждёт ответы от founders на questionnaire (см. ниже). Когда ответы придут:
- [ ] Создать `backend/llm/prompts/_defy_brand.txt` со всеми фактами (positioning, 3 продукта, founders, proof points, out-of-scope, engagement)
- [ ] Загружать в `llm.client.render()` как `{defy_facts}`, инжектить в `opener.txt` + `continuation.txt`
- [ ] Унифицировать casing (`Defy` без `.group`? или `Defy.group` везде?)

### Phase 5.2 — Refactor opener/continuation промптов

- [ ] Поднять `system` message до 200-300 слов: brand voice + role + boundaries + «не выдумывай факты, не названных в `{defy_facts}`»
- [ ] Удалить из opener/continuation дублирующиеся правила про buttons (вынести в system)
- [ ] Добавить **категории ответа** в continuation: `specific-defy-fact` / `methodology-hook` / `profile-callback` / `concrete-next-step` / `soft-personal`
- [ ] Передавать `used_categories: list[str]` из Session → LLM требуется выбрать unused (решает diversity-проблему через state, не директиву)
- [ ] Возвращать `category` в результате continuation → обновлять Session
- [ ] Передавать `word_target` в continuation prompt (сейчас теряется)

### Phase 5.3 — Refusal behavior

- [ ] «Если профиль не имеет signal'ов релевантных Defy work — не натягивай. Скажи общо.»
- [ ] «Если signal — только job title (не пост) — используй как hint, но не приписывай человеку убеждения/публикации.»
- [ ] «Если визитёр уже proceeded × 4 — не предлагай больше credentials. Переходи на narrow concrete next step.»
- [ ] «Если ask_size=`none` — никаких CTA, только soft door-open.»

### Phase 5.4 — Scenario test harness

- [ ] Pytest harness который замокает LLM (или прогонит реальный OpenAI) для:
  - positive×5 (baseline)
  - skeptical→positive→positive (defusing→advance)
  - positive→skeptical→positive (mid-dialog skepticism)
  - negative первым турном (immediate close)
  - positive→negative (late close после прогресса)
  - empty headline / no signals (graceful)
  - mismatched domain профиль
- [ ] Asserts: ≤35 words, no `?` в конце (кроме rhetorical), mentions Defy ≥1×, на `negative` нет CTA-глаголов, на `skeptical` есть цитата из `{defy_facts}`
- [ ] **Можно начать ДО разблокировки 5.1** чтобы зафиксировать baseline и поймать regressions от рефакторинга

### Phase 5.5 — Minor cleanup

- [ ] Templates: переписать чтобы тоже использовали `_defy_brand.txt` (fallback не должен расходиться с LLM)
- [ ] **`*.log` → .gitignore** (uvicorn.log болтается untracked со 2026-04-29)

## 🔒 Открытые вопросы к founders (questionnaire 2026-04-30, на английском в session note)

1. **Anonymized case examples** — 2-3 коротких anonymized client examples ("top-20 UK agency used Monitor for 6 weeks before a pitch...") для использования на booth
2. **Permission to cite founder credentials** — public OK упоминать Ian's SHARE Creative / Samy / 50+ relationships и Alek's Singapore AI prof background?
3. **Out-of-scope** — 3-5 явных границ (not recruiting? not consulting hours? not data licensing? not for in-house brand teams?)
4. **Engagement format & next-step shape** — demo → trial → paid pilot? Длительность пилота, cadence, deliverables? Какой буквальный next step когда агент говорит "let's talk pilot"?
5. **Booth ICP & lead product** — agency founders/MDs/planners/CDs/mixed? Какой из Monitor/Automate/Report — lead продукт для открытия разговора?
6. **Conferences / shared-context anchors** — какие события Defy посещает/спонсирует (Cannes, SXSW, agency-circle)?

## 🟢 UI polish (не blocked, можно делать параллельно с 5.x)

- [ ] **Avatar caching strategy** — signed URLs от LinkedIn живут ~3 месяца, потом 404. Сейчас cache хранит URL forever. Парсить `e=` query param и invalidate cache при истечении, либо проксировать аватары через `/avatar/<profile_id>` endpoint
- [ ] **`cluster_id: —` для live** — пока live-профили не классифицируются, в правой панели всегда `—`. Либо скрыть field в live-режиме, либо реализовать живую классификацию
- [ ] **Idle screen** — что показывается когда нет активной сессии? Текущий fallback функциональный но скучный. Маленький карусель из synthetic archetypes "next visitor может быть ..."?
- [ ] **Кнопки choices после terminate** — сейчас остаются enabled, юзер может кликнуть → 409. Нужно дизейблить когда `current_session.dialogue.last.visitor_choice` → не null И terminated

### Frontend bugfix
- [ ] **`session ended` → 409 заглушка** — после terminate frontend кликает Tell me more → 409 в console. Не ломает UX но шумно. Поправить в applyChoices: если последний step имеет visitor_choice и interest на пределе — disable buttons

### Отложенный архитектурный диалог
- [ ] **Profile classification для live + 2-уровневая кластеризация** *(отложенный диалог с юзером, плюс параллельный план в `TASK_refactor_clustering.md` 2026-04-30)* — `TASK_refactor_clustering.md` уже содержит детальный план разделения profile-space и episode-space embeddings с HDBSCAN только над profile-space. Юзер: "пока отложим, не очень понятно", но план готов как референс к реализации

## Технический долг

- [ ] **`datetime.utcnow()` deprecation** — ~50 мест по коду. Sweep на `datetime.now(UTC)`
- [ ] **SQLAlchemy DateTime UTC migration** — связан с предыдущим
- [x] **`Profile.id` для live = `li:<vanity-handle>`** — сделано в Phase 4.2 (`_username_from_input` нормализует, slug-fallback только если handle не парсится)
- [ ] **`*.log` → .gitignore** — uvicorn.log от tee-эксперимента болтается untracked

## Acceptance gates (TASK.md §14, статус)

- [x] `make demo` <30s
- [x] UI === мокап (Defy Brand V2.0)
- [x] 5-минутный сценарий §9 разворачивается на seed=42
- [x] AI Bubble Pops → CS-drop → revision <60s
- [x] +Segment → factory spawn ≤3 эпизода
- [x] Expert View toggle работает
- [x] LLM_MODE=local + LIVE_MODE=false → нет сетевых вызовов
- [x] make reset воспроизводит ту же траекторию
- [x] 5+ промптов задокументированы (`opener.txt`, `continuation.txt`, `induce.txt`, `cluster_label.txt`, `reflect.txt`, `summary.txt`)
- [x] Loops survive in-loop exceptions
- [x] **import-graph test**
- [x] **live LinkedIn URL → 5-turn dialogue** ✅ end-to-end проверено 2026-04-29 против реального профиля
- [x] **privacy purge test**
- [x] pytest passes (71/71)

## Что выкидываем — финальный список (для архива)

Из 2026-04-21:
- ~~Pydantic 7 моделей под café-vocab~~
- ~~Preference matrix 6×6×5×4 (плотный тензор)~~
- ~~Frontend stubs~~
- ~~Lounge mockup~~

Из 2026-04-28:
- ~~Single-endpoint RapidAPI provider (`fresh-linkedin-profile-data`)~~ — заменён в Phase 4.1, потом ещё раз в 4.2
- ~~`linkedin-data-api.p.rapidapi.com`~~ — sunset на стороне провайдера 2026-04-29

Из 2026-04-29:
- ~~Static template-based continuations~~ — заменены LLM-driven с history (Phase 4.4); templates остались только как offline-fallback
- ~~`LLM_MODE` ограниченный двумя значениями (`local`/`remote`)~~ — расширен до `local`/`remote`/`openai`

Что пережило: `llm/client.py` (расширен под третий провайдер), `db.py` (+миграция), `config.py` (+OpenAI поля), весь test scaffold, формула CS, HDBSCAN-pipeline, 3-loop оркестратор, 6 ORM-таблиц.
