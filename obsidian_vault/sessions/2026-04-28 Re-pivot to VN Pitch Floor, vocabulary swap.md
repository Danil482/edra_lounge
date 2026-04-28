---
tags: [session, pivot, vocabulary, vn, profile-source, mockup-v2]
date: 2026-04-28
---

# 2026-04-28 Re-pivot to VN Pitch Floor, vocabulary swap

Автор переписал TASK.md и заменил мокап. Проект остаётся EDRA (Experience-Driven Rule Adaptation) и сохраняет всю научную начинку (episodic memory → clustering → induction → consistency monitor → reflective revision → agent factory), но **тематический wrapper и почти весь vocabulary поменялись**. Переходим со 2026-04-21 каркаса (café/lounge) на VN Pitch Floor.

## Что поменялось — суть пивота

| Слой | Было (2026-04-21, café) | Стало (2026-04-28, VN/research-outreach) |
|---|---|---|
| **Метафора** | Бар-менеджер, бариста подбирает напитки | Visual novel: anime-агент EDRA представляет research-collaboration от DEFY.group, посетитель приходит со своим LinkedIn |
| **Главный объект ввода** | `Persona` (vibe, role, domain) | `Profile` (от `ProfileSource`, с `recent_signals`, `seniority`, `headline`, `embedding`) |
| **Что подаёт агент** | `Offer` = (topic, style, drink, opener) | `PitchStrategy` = (framing, tone, opener_type, word_target, ask_size) — 5 слотов, не 4 |
| **Тип сессии** | Однократный offer → outcome_score | **Многошаговый диалог** (3–7 шагов) с `DialogueStep`, выбором посетителя (positive/skeptical/negative) и interest gauge от −5 до +5 |
| **Vocabulary промптов** | persona × tension → angle × expression (маркетинг-словарь) | research-outreach: те же поля, но термины §4.3 — `framing/tone/opener_type/word_target/ask_size` напрямую |
| **Архетипы** | 6: persona_phd_nlp, _postdoc_cv, _tech_founder, _senior_prof, _industry_pm, _vc_investor | 6 default + 2 spawnable: arch_phd_nlp_introvert, arch_postdoc_cv_ambitious, arch_tech_founder_applied, arch_senior_prof_meta, arch_industry_pm_pragmatic, arch_research_engineer_skeptic, **+ arch_vc_investor + arch_journalist_curious** |
| **Drift A** | hype↔foundations + enthusiastic↔skeptical у tech-founder | applied-curiosity↔skeptical-respect (framing) + playful↔direct (tone) у tech-founder |
| **Drift B** | postdoc career affinity линейно | postdoc strategic-alignment 0.9 → 0.4 за 15 эпизодов |
| **Источник профилей** | Только синтетика | **Новая абстракция `ProfileSource`** — protocol + Synthetic + LinkedIn-RapidAPI (Phase 3) |
| **Frontend** | Lounge mockup (черновик автора) | `frontend/edra_design_mockup.html` — финальный VN-мокап (1465 строк, готов к портированию verbatim) |
| **Live mode** | Не было | Phase 3: посетитель вставляет LinkedIn URL, RapidAPI fetch, profile purge после end-of-session |

## Что в науке НЕ поменялось

Архитектура и закрытый цикл — те же. Конкретно остаются как есть:
- 6 ORM таблиц (но `personas` → `profiles`, `offer` → `pitch_strategy` + новая `dialogue` колонка)
- 3 asyncio-loop оркестратора (tick / consistency / factory) + `on_new_episode`
- 5 LLM-touchpoint точек (TASK.md §7) — текстовое содержимое промптов меняется, состав остаётся
- HDBSCAN на 384-dim MiniLM, n_min=5, θ_induce=0.6, CS-окно
- SSE-разделение POST `/rules/{id}/revise` + GET `/reflections/stream/{id}`
- Hybrid rule с static + dynamic слотами
- Acceptance checklist почти один-в-один (новые пункты — protocol-conformance test и privacy-purge test)

## Что в каркасе остаётся жить

Из артефактов 2026-04-21 переживают пивот:
- `backend/llm/client.py` — без изменений (httpx, local/remote, streaming)
- `backend/orchestrator.py` — структура классов, loops, exception-resilience (логика внутри `_pick_rule_for_persona` теперь `_pick_rule_for_profile`, реализация всё равно была заглушкой)
- `backend/db.py` — engine/session, без изменений
- `backend/config.py` — добавятся `RAPIDAPI_KEY`, `LIVE_MODE`
- `backend/clustering/cluster.py` — HDBSCAN остаётся
- `backend/induction/induce.py` — каркас остаётся, промпт и slot-vocabulary меняются
- `backend/monitor/consistency.py` — формула CS остаётся
- `backend/reflection/revise.py` — каркас остаётся
- `backend/factory/factory.py` — каркас остаётся
- `seeded_run.yaml` — нужно обновить под новые архетипы и drift-семантику
- Тест-каркас (`tests/test_orchestrator.py`) — без изменений по форме

## Что выбрасываем целиком

- `backend/schemas.py` — 80% перевыписать (Persona→Profile, Offer→PitchStrategy, новые TONE/FRAMING/OPENER_TYPE/WORD_TARGET/ASK_SIZE литералы, DialogueStep, обновлённый Episode)
- `backend/memory/models.py` — те же таблицы, но колонки и смысл меняются (PersonaRow→ProfileRow, новые поля `source_kind`, `source_identifier`, `recent_signals`, `ttl_seconds`, `dialogue` JSON в эпизодах, и т.д.)
- `backend/simulator/preferences.py` — целиком новая матрица: 6 личностей × 6 framings × 5 tones × 5 opener_types × 3 word_targets × 5 ask_sizes (= 11250 ячеек теоретически, но affinity-факторизованы и хранятся как 5 dicts + combo_bonuses, не плотным тензором)
- `backend/simulator/drift.py` — две функции переписать под новые поля
- `backend/llm/prompts/*.txt` — все 5 промптов переписать в research-outreach vocabulary с тэгами §4.3
- `backend/data/archetypes.yaml` — НОВЫЙ файл, не существовал; будет 6+2 архетипа с full Profile + preferences
- `frontend/index.html`, `frontend/styles.css`, `frontend/app.js` — выкинуть, портировать `edra_design_mockup.html` целиком
- `tests/test_preferences.py` — invariant остаётся (unique top combos), реализация под новые слоты

## Что строим заново

- `backend/profile_source/__init__.py` — `ProfileSource` Protocol + `ProfileNotFound`, `ProfileSourceUnavailable` exceptions
- `backend/profile_source/synthetic.py` — `SyntheticProfileSource` читает `archetypes.yaml`, instant-fetch by archetype id
- `backend/profile_source/linkedin_rapidapi.py` — Phase 3, `LinkedInRapidAPISource` через RapidAPI, retry+timeout, profile purge hook
- `backend/pitch/` — новый модуль: `generate_turn(profile, dialogue_history, applicable_rule | None) -> DialogueStep`. Static rules без LLM, hybrid rules → fill_dynamic_slot(), no rule → improvise через LLM с few-shot из cluster-эпизодов
- `backend/routers/sessions.py` — `POST /sessions/start`, `POST /sessions/{id}/turn`, `POST /sessions/{id}/end`. Stateful session store in-memory + persist on end
- `tests/test_profile_source.py` — protocol conformance + import-graph test (никакой модуль из core не импортит linkedin_rapidapi)

## Архивные имена файлов мокапов

`TASK.md` ссылается на `edra_pitch_mockup.html` в §1.3, §1.4, §10. Реальный файл в репо — `frontend/edra_design_mockup.html`. Это просто ре-name автором, **используем тот, что в репо**. Версия из `2026-04-21 session note` (`edra_lounge_mockup.html`) больше не актуальна.

## Risk areas / на что обратить внимание

1. **5-слотовая PitchStrategy → 11250 теоретических комбо**. Не строить плотный numpy тензор. Хранить affinity как 5 dicts (на каждый слот) + combo_bonuses sparse. См. §5.2 формулу — строго факторизованная сумма.
2. **TASK.md §14 пункт про import-graph test** — это новая acceptance-проверка изоляции `profile_source/linkedin_rapidapi.py` от core. Не пропустить.
3. **Live-mode privacy purge** — `tests/test_privacy_purge.py` проверяет, что в SQLite нет PII для `source_kind != "synthetic"` старше 1 часа.
4. **VN-мокап имеет hover-out edge handles на трёх краях**. Это не мелочь — три hidden панели (top/left/right) — масштабная разметка плюс CSS `transform: translateX(...)` с triggers. Лучше копировать стили из `edra_design_mockup.html` verbatim, не переписывать.
5. **Многошаговый диалог** — раньше эпизод был 1 step (offer→outcome), теперь 3–7 steps. SSE стриминга диалога **нет** в TASK.md §7 — диалог идёт обычными HTTP-вызовами `/sessions/{id}/turn`. SSE только для reflection (§7).
6. **Anime-PNG агента** — production-asset, не блокер для Phase 1. Mockup имеет fallback `.agent-slot-placeholder` — оставить его, картинки подключим в Phase 3.

## Следующая сессия — entry points

1. Перевыписать `backend/schemas.py` под §4.1–4.7 → новые литералы и DialogueStep, многошаговый Episode
2. Заменить `memory/models.py` ORM колонки (Persona→Profile, Offer→PitchStrategy)
3. Создать `backend/profile_source/` с Protocol + SyntheticProfileSource
4. Создать `backend/data/archetypes.yaml` — 6 default + 2 spawnable
5. Перевыписать `backend/simulator/preferences.py` — 5 affinity dicts + combo_bonuses
6. Перевыписать 5 промптов в `backend/llm/prompts/` — research-outreach vocab
7. Создать `backend/pitch/` модуль для генерации turn
8. Создать `backend/routers/sessions.py` для multi-turn API
9. Портировать `frontend/edra_design_mockup.html` → `index.html` + `styles.css` + `app.js` с polling и SSE
10. Прогнать `make demo` — 5-минутный сценарий (TASK.md §9) разворачивается на новом vocab

См. [[../00-home/current priorities]] для разбивки по фазам.
