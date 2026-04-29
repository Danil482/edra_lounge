---
tags: [home, priorities, status]
date: 2026-04-29
---

# Current Priorities

Контекст пивота → [[../sessions/2026-04-28 Re-pivot to VN Pitch Floor, vocabulary swap]]
Сессия 2026-04-28 (Phase 1B/2/3) → [[../sessions/2026-04-28 Phase 1B-2-3 shipped, live-mode booth wired]]
Сессия 2026-04-29 (Phase 4.1-4.4) → [[../sessions/2026-04-29 Phase 4.1-4.4 shipped, OpenAI live-mode validated]]

Каркас от 2026-04-21 был построен под café-метафору. После пивота 2026-04-28 проехали Phase 1B → 2 → 3 за одну сессию (booth готов в синтетике + live(mock)). 2026-04-29 — Phase 4.1 → 4.4 за одну сессию: новый RapidAPI-провайдер (после двух sunset'нувшихся), OpenAI как третий LLM-mode, переписанные промпты под 3-кнопочную UX-модель, LLM-driven continuations с историей, видимое логирование, avatar plumbing. **Booth полностью функционален с реальным LinkedIn-фетчем + OpenAI-генерацией, 71/71 теста зелёных, end-to-end сессия проверена против настоящего профиля автора.**

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

## 🟡 Phase 5 — Polish + scenarios (TBD)

После сегодняшнего e2e-прогона приоритеты сместились с "заработает ли вообще" на "качество и устойчивость".

### Промпты
- [ ] **Continuation diversity** — все ответы LLM сейчас в одном русле ("ещё одна credential": партнёрство, cohort size, case study, scoping call). Нужна явная ротация типов через категории в промпте: 1) social proof, 2) personal story, 3) tool/method specific, 4) call to action. Сделать `last_category` трекинг в Session и инструктировать LLM не повторять
- [ ] **Skeptical-ветка scenario test** — прогнать сессии где визитёр жмёт `Skeptical, why Defy?`. Промпт говорит "defuse with one specific reason Defy is legitimate" — реально ли LLM выдаёт конкретику или generic reassurance? Доработать если generic
- [ ] **Negative — graceful close** — проверить что ответ на `Not interested` короткий и не пытается re-pitch'нуть. Промпт явно запрещает push, но проверим
- [ ] **Opener_type=question** — сейчас редизайнен как rhetorical yes/no setup. Прогнать против разных profile signals — нет ли регрессий с открытыми вопросами

### Scenario testing
- [ ] **Mixed dialog patterns** — pos/skep/pos/neg/pos и вариации. Посмотреть что LLM делает на резкие повороты тона, как gauge ведёт себя
- [ ] **Edge case профили** — пустой headline / без experiences / только bio / только headline. Парсер не должен падать, опенер должен gracefully degrade
- [ ] **Длинные сессии** — поднять `MAX_TURNS` или `interest`-threshold временно и посмотреть что LLM делает на 7+ турне (не зацикливается ли)

### UI polish
- [ ] **Avatar caching strategy** — signed URLs от LinkedIn живут ~3 месяца, потом 404. Сейчас cache хранит URL forever. Парсить `e=` query param и invalidate cache при истечении, либо проксировать аватары через `/avatar/<profile_id>` endpoint
- [ ] **`cluster_id: —` для live** — пока live-профили не классифицируются, в правой панели всегда `—`. Либо скрыть field в live-режиме, либо реализовать живую классификацию (см. ниже)
- [ ] **Idle screen** — что показывается когда нет активной сессии? Текущий fallback на placeholder + `— no active session —` функциональный но скучный. Маленький карусель из synthetic archetypes "next visitor может быть ..."?
- [ ] **Кнопки choices после terminate** — сейчас остаются enabled, юзер может кликнуть → 409. Нужно дизейблить когда `current_session.dialogue.last.visitor_choice` → не null И terminated

### Frontend bugfix
- [ ] **`session ended` → 409 заглушка** — после terminate frontend кликает Tell me more → 409 в console. Не ломает UX но шумно. Поправить в applyChoices: если последний step имеет visitor_choice и interest на пределе — disable buttons

### Архитектурный вопрос
- [ ] **Profile classification для live + 2-уровневая кластеризация** *(отложенный диалог с юзером)* — сейчас `classify_profile` для live возвращает None, поэтому live попадает в "uncovered" и factory-loop спавнит agent stub через 30s. Без живой классификации persona-rules не применяются к real LinkedIn визитёрам. **Открытый вопрос**: эмбедить надо profile-summary (для классификации live) или episode-summary (для induction)? Может нужны два уровня кластеризации — один для профилей (поведение), один для эпизодов (что сработало). Юзер пометил это как "пока отложим, не очень понятно"

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
