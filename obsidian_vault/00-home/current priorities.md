---
tags: [home, priorities, status]
date: 2026-04-28
---

# Current Priorities

Контекст пивота → [[../sessions/2026-04-28 Re-pivot to VN Pitch Floor, vocabulary swap]]
Сессия 2026-04-28 (Phase 1B/2/3) → [[../sessions/2026-04-28 Phase 1B-2-3 shipped, live-mode booth wired]]

Каркас от 2026-04-21 был построен под café-метафору (Persona/Offer/topic/style/drink). После пивота 2026-04-28 проехали все три фазы (1B → 2 → 3) за одну сессию: skeleton реструктурирован под VN-сцену с research-outreach pitch для DEFY.group, реализованы multi-turn dialogue + sessions API + frontend port + live LinkedIn режим с privacy purge. **Booth функционально готов в синтетическом и live(mock)-режимах, 62/62 теста зелёных.**

## ✅ Phase 1A — Vocabulary swap (готово, 2026-04-28)

См. коммит `fd5f4d6 Phase 1A — Vocabulary swap to VN Pitch Floor`. Schemas, ORM, ProfileSource, archetypes.yaml, simulator preferences/drift, тесты — всё под новые контракты TASK.md §4.1–4.7.

## ✅ Phase 1B — Multi-turn dialogue + sessions API (готово, 2026-04-28)

См. коммит `227e0d4 Phase 1B — Multi-turn pitch sessions, rule pipeline wired`. `backend/pitch/`, `backend/sessions/`, `routers/sessions.py`, orchestrator wiring, 5 LLM-промптов в research-outreach vocab.

## ✅ Phase 2 — VN frontend (готово, 2026-04-28)

См. коммит `3773700 Phase 2 — Frontend port (Defy Brand V2.0)`. Mockup ported verbatim в split files, `app.js` wired, typewriter / gauge / hover panels / choices / operator buttons / reflection console — всё работает.

## ✅ Phase 3 — Live mode + booth ready (готово, 2026-04-28)

См. коммит `d6a9525 Phase 3 — Live LinkedIn mode + privacy purge + Wi-Fi fallback`. `LinkedInRapidAPISource` с реальным httpx, mock-key sentinel для booth без RapidAPI-подписки, privacy purge через factory loop, fallback dialog, `make booth` / `make reset` готовы.

UI fixes после первого запуска (`bb77896` + `ffd978a`): live-форма перенесена в модал, `op-live-toggle` в operator-панели; textbox/choices vertical overlap починен.

## 🟡 Phase 4 — Booth polish + real LinkedIn (TBD)

Открытые задачи после боевого использования mock-режима:

- [ ] **Реальный LinkedIn parsing** — получить RAPIDAPI_KEY, проверить `_map_payload_to_profile` против настоящего ответа `fresh-linkedin-profile-data.p.rapidapi.com`. Сейчас mapping проверен только против hand-crafted mock payload — реальный JSON может отличаться по именам полей (e.g. `experiences[].duration.years` vs `years`). Пройти через 3-5 настоящих профилей разной seniority + индустрий, докрутить эвристики где надо. Acceptance: live LinkedIn URL → 3-turn dialogue без ошибок маппинга
- [ ] **Live-mode по умолчанию** — `backend/config.py: live_mode: bool = True`, синтетика остаётся через `LIVE_MODE=false` или `.env`. Цель: booth-laptop стартует сразу в режиме, под который он развёрнут, без env-переменных. Не забыть обновить `make booth` и `Makefile` хелпы. Сейчас стартует в synthetic, что неправильный сигнал для оператора у booth
- [ ] **Визуально проверить профиль в правой панели** — как mock-профиль автора и реальный LinkedIn-профиль рендерятся в hover-right panel (`#visitor-name`, `#visitor-role`, `#visitor-headline`, `#visitor-signals`). Длинные headline могут вылезти за рамки 360px панели; recent_signals по 140 chars × 3 — нужно проверить vertical clip. Также: `cluster_id: —` для live (потому что embedding-классификация для live-режима не реализована) — UX-fix или скрыть field
- [ ] **`classify_profile` для live-режима** — сейчас возвращает None для non-synthetic, поэтому live-профиль попадает в uncovered cluster и factory создаёт agent stub. Реализовать sentence-transformers embedding + cosine-NN до существующих cluster centroids. Без этого live-режим даёт `cluster_id: —` и applicable_rule всегда null

## Технический долг

- [ ] **`datetime.utcnow()` deprecation** — ~50 мест по коду, Python 3.13 убирает. Sweep на `datetime.now(UTC)`. Не блокирует, но засоряет pytest output 49 warnings
- [ ] **Profile.id для live** — сейчас `li:https--wwwlinkedincom-in-danil-onishchenko-30876037a` (через `_slugify`). Уродливо в логах. Извлекать vanity handle: `li:<handle>`
- [ ] **datetime UTC migration in ORM models** — для миграции выше нужно проверить SQLAlchemy DateTime defaults (сейчас `default=datetime.utcnow` без UTC tz)

## Acceptance gates (TASK.md §14, статус)

- [x] `make demo` <30s — старт ~3s
- [x] UI === мокап (Defy Brand V2.0)
- [x] 5-минутный сценарий §9 разворачивается на seed=42
- [x] AI Bubble Pops → CS-drop → revision <60s (через operator-кнопку)
- [x] +Segment → factory spawn ≤3 эпизода
- [x] Expert View toggle работает
- [x] LLM_MODE=local + LIVE_MODE=false → нет сетевых вызовов (offline-fallbacks ловят ConnectError)
- [x] make reset воспроизводит ту же траекторию (deterministic seed)
- [x] 5 промптов задокументированы (под новый vocab)
- [x] Loops survive in-loop exceptions (try/except в каждом цикле)
- [x] **import-graph test** — никакой core-модуль не импортит linkedin_rapidapi (AST-walk test passes)
- [ ] **live LinkedIn URL → 3-turn dialogue** — против mock работает; против реального RapidAPI не проверяли
- [x] **privacy purge test** — 6 кейсов в `tests/test_privacy_purge.py` зелёные
- [x] pytest passes (62/62)

## Что выкидываем — финальный список (для архива)

Из 2026-04-21:
- ~~Pydantic 7 моделей под café-vocab~~ — переписали на Profile/PitchStrategy/DialogueStep
- ~~Preference matrix 6×6×5×4 (плотный тензор)~~ — заменили на 5 affinity dicts + sparse combo_bonuses
- ~~Frontend stubs~~ — выкинули, портировали `edra_pitch_mockup.html` v3
- ~~Lounge mockup `edra_design_mockup.html`~~ — заменили на `edra_pitch_mockup.html` (Defy Brand V2.0)

Что пережило: `llm/client.py`, `db.py`, `config.py`, тест-каркас, формула CS, HDBSCAN-pipeline, 3-loop оркестратор, 6 ORM таблиц (с переименованными колонками).
