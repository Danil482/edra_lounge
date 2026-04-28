---
tags: [session, phase-1b, phase-2, phase-3, live-mode, linkedin, privacy-purge, ui-fixes]
date: 2026-04-28
---

# 2026-04-28 Phase 1B → 2 → 3 shipped, live-mode booth wired

После пивота на VN Pitch Floor (см. [[2026-04-28 Re-pivot to VN Pitch Floor, vocabulary swap]]) прошли все три оставшиеся фазы за одну сессию. Booth сейчас полностью функционален в синтетическом и live-режимах; LLM (Ollama) пока не установлен — fallback-пути ловят `httpx.ConnectError/ConnectTimeout/ReadTimeout` одной строкой и продолжают демо.

## Что сделано

### Phase 1B — Multi-turn pitch sessions
- `backend/pitch/` — `generate.py` (3 пути: static / hybrid / improvise), `templates.py` (deterministic openers + continuations по tone × visitor_choice), `strategy.py` (DEFAULT_IMPROVISED_STRATEGY = peer-collaboration/warm/reference-to-signal/medium/chat), `classify.py` (synthetic = archetype_id, lookup_applicable_rule по latest active)
- `backend/sessions/lifecycle.py` — `start_session` / `take_turn` / `end_session`, ±5 termination, MAX_TURNS=7, _summarise с offline fallback
- `backend/sessions/store.py` — process-local Session dict + active-session pointer
- `backend/routers/sessions.py` — `POST /sessions/start | /turn | /end`, выставляет `orch.live_session_active`
- Orchestrator wiring — `_try_induce_all` (LLM или mode-of-slots fallback), `_check_all_rule_cs` создаёт pending Revision (LLM-stream lazy через SSE endpoint), `_evaluate_factory` спавнит Agent для uncovered cluster, `on_new_episode` hook перекластерует и пытается индуцировать
- Cluster.size = `len(episodes)`, **не** distinct profile_ids — синтетика гоняет один archetype много раз, distinct остался бы 1 и induction не триггерилась бы
- Fallback induction: mode-of-slots среди accepted эпизодов (или всех, если accepted=0) — boots a static rule без LLM
- Tests: 48 → потом 62

### Phase 2 — Frontend port (Defy Brand V2.0)
- Скопировал v3-мокап `edra_pitch_mockup.html` verbatim в `styles.css` (1217 lines CSS) + `index.html` (data-binding skeleton)
- `frontend/app.js` ≈ 340 LOC: poll каждые 1000ms, typewriter ~30 cps, gauge с `.cell-on/-warm/-hot` по знаку и величине, hover-out edge panels, choice buttons, operator buttons, reflection console через `EventSource`
- Brand: Playfair Display + DM Sans, palette `#0A0A0A` / `#F9F9F7` / `#F3F1EC` / `#CC0000`, 50/40/10 ratio, никаких rounded corners / shadows / decorative gradients

### Phase 3 — Live LinkedIn mode + privacy purge + fallback
- `LinkedInRapidAPISource` — реальный httpx fetch против fresh-linkedin-profile-data.p.rapidapi.com с status-aware error mapping: 404 → `ProfileNotFound`, 429/5xx/network → `ProfileSourceUnavailable`. Маппинг JSON → Profile (full_name, role, domain, seniority-эвристика по title + years, recent_signals из posts капается на 3 строки)
- `RAPIDAPI_KEY=mock` sentinel — без реального ключа (без HTTP-запроса) возвращает hand-crafted профиль автора (Danil Onishchenko, headline + 3 поста). Используется для booth-демки без RapidAPI-подписки
- `purge_expired_live_profiles` в `backend/memory/store.py` — non-synthetic ProfileRow удаляются после `now - fetched_at >= ttl_seconds` (default 3600 для live). Запускается из factory loop каждые 30s. Synthetic неприкосновенны
- Wi-Fi fallback — `GET /sessions/sources` отдаёт active source kind + полный список synthetic archetypes. Frontend на 503 от `/sessions/start` открывает диалог с dropdown архетипов
- Orchestrator tick loop теперь no-op в live-режиме (booth ждёт реальных визитёров через HTTP, а не auto-play синтетику). В синтетическом режиме self-playing demo как раньше
- Makefile: `make reset` (rm db + reseed <5s), `make booth` (reset → uvicorn → poll /health → kiosk Chrome)
- Тесты: 14 новых (LinkedIn mocked-httpx success/404/429/5xx/network/malformed + mock-key bypass + seniority heuristic + 6 privacy-purge кейсов)

### UI iteration после первого запуска
- **Live-форма сначала** была persistent bar `top:0` — пересекалась с hover top-panel и визуально шумела даже когда никто live-сессию не стартует
- **Textbox / choices overlap** — `.textbox bottom:110px` + `min-height:184` пересекался с `.choices bottom:60px height:~80`; рамка textbox шла поверх текста кнопок
- **Фикс**: live-форма стала модалом, открывается кликом на operator-кнопку `Start Live` (видна только в live-режиме). Esc закрывает, Enter подтверждает. Choices подняты до `bottom:110px`, textbox до `bottom:220px` — стек чистый: gauge [0,92] → choices [110,~190] → textbox [220,…]

## Финальное состояние

- 62/62 теста зелёных
- `make demo` стартует в синтетическом режиме без ошибок (только LLM-offline warnings одной строкой)
- `LIVE_MODE=true RAPIDAPI_KEY=mock make demo` стартует в live-режиме, кнопка `Start Live` видна, модал открывается, `https://www.linkedin.com/in/danil-onishchenko-30876037a/` → mock-профиль автора попадает в правую панель, в textbox opener со ссылкой на пост
- 8 коммитов от Phase 1A до UI-fix

## Открытые вопросы / следующие шаги

См. `current priorities.md`. Кратко:
1. **Реальный LinkedIn parsing** — нужен RAPIDAPI_KEY и проверка mapping `_map_payload_to_profile` против настоящего ответа RapidAPI. Сейчас всё под mock-payload, реального запроса пока никто не делал
2. **Live-mode по умолчанию** — поставить `LIVE_MODE=true` дефолтом в `backend/config.py` (или через `.env.example`), синтетика остаётся через `LIVE_MODE=false`
3. **Профиль в правой панели** — визуально проверить, как mock и реальный профиль отрисовываются в hover-right panel, не вылезают ли длинные headline / signals за рамки, корректно ли показывается `source_kind: linkedin_rapidapi`

## Технический долг

- ~50 мест с `datetime.utcnow()` — Python 3.13 убирает, нужен sweep на `datetime.now(UTC)`
- Profile.id для live: `li:https--wwwlinkedincom-in-danil-onishchenko-30876037a` — функционально работает но визуально некрасиво в логах, можно делать `li:<vanity-handle>` через regex
- `classify_profile` для live-mode возвращает `None` (cluster_id), потому что нет встроенного embedding; до Phase 4 живой профиль попадает в "uncovered" pile и factory спавнит agent через 30s. Не блокирует демо, но в UI показывается `cluster_id: —`
- LIVE_MODE=true пока не поставлен дефолтом — стартует в синтетике, что неправильный сигнал для booth
