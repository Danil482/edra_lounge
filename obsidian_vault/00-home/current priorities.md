---
tags: [home, priorities, status]
date: 2026-04-28
---

# Current Priorities

Контекст пивота → [[../sessions/2026-04-28 Re-pivot to VN Pitch Floor, vocabulary swap]]

Каркас от 2026-04-21 был построен под café-метафору (Persona/Offer/topic/style/drink). Автор переписал TASK.md и зафиксировал финальный мокап `frontend/edra_design_mockup.html`. Тема — VN-сцена с research-outreach pitch для DEFY.group. Скелет надо реструктурировать (vocabulary swap), а не строить с нуля — научная начинка (clustering → induction → CS → reflection → factory) остаётся.

## Phase 1A — Vocabulary swap (срочно, ~2 дня)

Цель: репо компилируется и тесты проходят на новых контрактах. UI и LLM пока могут быть заглушками.

- [ ] **Schemas** — `backend/schemas.py` под TASK.md §4.1–4.7
  - Новые литералы `FRAMING`, `TONE`, `OPENER_TYPE`, `WORD_TARGET`, `ASK_SIZE` (TASK.md §4.3)
  - `Profile` (с `source_kind`, `source_identifier`, `recent_signals`, `seniority`, `embedding`, `ttl_seconds`) заменяет `Persona`
  - `PitchStrategy` (5 слотов) заменяет `Offer` (4 поля)
  - `DialogueStep` — новый класс
  - `Episode.dialogue: list[DialogueStep]`, `final_interest: int`, `outcome` literal стал `accepted|exploring|rejected|abandoned`
  - `RuleSlot.name` literal под 5 слотов pitch-strategy
- [ ] **ORM** — `backend/memory/models.py`: `PersonaRow` → `ProfileRow`, JSON-колонка `pitch_strategy` вместо `offer`, новая `dialogue` JSON, новые поля `source_kind`/`source_identifier`/`recent_signals`/`ttl_seconds`/`fetched_at`. Мигрировать запросы в `memory/store.py` и `memory/seed.py`.
- [ ] **ProfileSource** — новый модуль `backend/profile_source/`
  - `__init__.py`: `ProfileSource` Protocol (TASK.md §4.1) + exceptions `ProfileNotFound`, `ProfileSourceUnavailable`
  - `synthetic.py`: `SyntheticProfileSource` — fetch by archetype id из `data/archetypes.yaml`
  - `linkedin_rapidapi.py`: оставить как stub `raise NotImplementedError`, реализация в Phase 3
- [ ] **Archetypes data** — `backend/data/archetypes.yaml`
  - 6 default + 2 spawnable (TASK.md §5.1) с full `Profile` (все поля)
  - Per-archetype preference function данные — affinity по 5 слотам + `combo_bonuses` + terminal-acceptance thresholds
- [ ] **Simulator preferences** — `backend/simulator/preferences.py` целиком переписать под §5.2
  - 5 affinity dicts: `framing_affinity`, `tone_affinity`, `opener_affinity`, `word_target_affinity`, `ask_size_affinity`
  - `combo_bonuses` — sparse list of `{if: {...}, bonus: float}` (НЕ плотный тензор, иначе 11250 ячеек)
  - `preference(archetype_id, strategy, history) -> int` возвращает `interest_delta ∈ [-2, +2]`, фактор fatigue `−0.1 * len(history)`
  - `discretise(score)` round-to-int + clip в [-2, +2]
- [ ] **Drift handlers** — `backend/simulator/drift.py` переписать
  - `ai_bubble_pops`: swap `framing[applied-curiosity]` ↔ `framing[skeptical-respect]` и `tone[playful]` ↔ `tone[direct]` для `arch_tech_founder_applied`
  - `postdoc_burnout`: linearly interpolate `arch_postdoc_cv_ambitious.framing[strategic-alignment]` 0.9 → 0.4 за 15 эпизодов
- [ ] **Tests phase 1A** — `tests/test_preferences.py` (unique-top-3 invariant per archetype) + `tests/test_profile_source.py` (protocol conformance + import-graph isolation TASK.md §14)

## Phase 1B — Multi-turn dialogue + sessions API (~2 дня)

- [ ] **Pitch module** — `backend/pitch/`
  - `generate_turn(profile, history, applicable_rule | None) -> DialogueStep`
  - Static rule (все слоты static) → собрать pitch без LLM-вызова
  - Hybrid rule (есть dynamic slot, обычно opener) → `fill_dynamic_slot()` через `prompts/opener.txt`
  - No applicable rule → improvise через LLM с few-shot из последних N эпизодов кластера
  - Возвращает `DialogueStep` с `turn`, `agent_thought`, `agent_reply`, `rule_applied`
- [ ] **Sessions router** — `backend/routers/sessions.py`
  - `POST /sessions/start` — `body: {source_kind, identifier}` → ProfileSource.fetch → классификация в кластер → возврат `{session_id, profile_id, classified_cluster_id, applicable_rule_id}`
  - `POST /sessions/{id}/turn` — `body: {visitor_choice}` → preference function вычисляет `interest_delta` + следующий `DialogueStep`
  - `POST /sessions/{id}/end` — финализирует, summary через LLM, persist Episode, trigger `on_new_episode`
  - In-memory session store (dict, без TTL — Phase 3 добавит cleanup)
- [ ] **Pull TODO(phase1) маркеры из 2026-04-21**, теперь под новый vocab:
  - `orchestrator._try_induce_all` — генерация `R.XX` IDs, Persist Rule
  - `orchestrator._pick_rule_for_profile` (был `_pick_rule_for_persona`) — лучший active rule для cluster
  - `routers/clusters.py::recompute_clusters` — HDBSCAN end-to-end + LLM-label
  - `routers/rules.py::induce/consistency_of/revise` — wire к induction/monitor/reflection модулям
- [ ] **Five LLM prompts переписать** в research-outreach vocab
  - `prompts/summary.txt` — 1 предложение по completed episode (теперь по dialogue)
  - `prompts/induce.txt` — генерация Rule с 5 слотами (framing/tone/opener_type/word_target/ask_size)
  - `prompts/cluster_label.txt` — human-readable cluster label типа "mid-career CV researchers"
  - `prompts/reflect.txt` — proposal revised rule (streaming)
  - `prompts/opener.txt` — fill dynamic opener slot

## Phase 2 — VN frontend (~3 дня)

- [ ] **Port mockup verbatim** — копировать CSS из `frontend/edra_design_mockup.html` в `frontend/styles.css` без правок. HTML-структуру сохранить, превратить в шаблон с data-bindings через JS.
- [ ] **app.js** — polling каждые 1000ms `GET /state`, SSE-подписка на `/reflections/stream/{id}` когда `active_revision != null`
- [ ] **VN typewriter effect** — символ-за-символом ~30cps, ▼ marker по завершении печати
- [ ] **Interest gauge animation** — CSS transform smooth (TASK.md §10), не stepped. Mapping cell.-on / .-warm / .-hot по знаку и величине
- [ ] **Hover-out edge panels** — три панели (top masthead, left rulebook+reflection, right profile detail) уже размечены в мокапе, JS добавляет `mouseenter/mouseleave` triggers и swap content из `/state`
- [ ] **Visitor choice buttons** — 3 кнопки positive/skeptical/negative, click отправляет `/sessions/{id}/turn`
- [ ] **Operator buttons** (top panel) — `💥 AI Bubble Pops` `POST /simulator/drift/ai_bubble_pops`, `👤+ New Segment` `POST /simulator/inject_archetype`, `⚙ Expert View` toggle (скрывает thought line + reflection evidence)
- [ ] **Agent emotion mapping** — fallback placeholder slot пока без PNG; реальные ассеты Phase 3 (см. NovelAI prompts в нижней части мокапа)
- [ ] **Cluster UMAP viz** — `clusters_viz: list[{id, label, points}]` в state; рендер 2D точек для side-panel (опционально для Phase 2)
- [ ] **Reflection console** — token-by-token streaming через EventSource в left panel; accept/edit/keep buttons → `POST /revisions/{id}/decision`

## Phase 3 — Live mode + booth ready (~3 дня)

- [ ] **LinkedInRapidAPISource** — реализация. Auth через `RAPIDAPI_KEY` env, retry, timeout. Маппинг RapidAPI response → `Profile`.
- [ ] **Live profile purge** — hook на `POST /sessions/{id}/end` (или background task) удаляет PII из ProfileRow для `source_kind != "synthetic"`. Test `tests/test_privacy_purge.py`.
- [ ] **Wi-Fi fallback** — UI: если `LinkedInRapidAPISource.fetch` raises `ProfileSourceUnavailable`, предложить выбрать synthetic архетип
- [ ] **Anime PNG ассеты** — 6 emotions × 720×1080 transparent через NovelAI (мастер-промпт в мокапе), сложить в `frontend/assets/agent/`
- [ ] **Visitor portrait** — synthetic: hand-drawn line-art SVG per archetype в `frontend/assets/visitor/`; live: filter chain (grayscale + blur + tint) на LinkedIn headshot
- [ ] **make booth** — health-wait + `start chrome --kiosk http://localhost:8000`
- [ ] **make reset** — clear SQLite, re-seed, <5s
- [ ] **Operator cheat-sheet PDF** — 2 страницы: button meanings + scripted-scenario timing + live-mode fallback
- [ ] **Docker-compose** — backend + Ollama bundle для офлайн-booth

## Acceptance gates (TASK.md §14, выровнено)

- [ ] `make demo` <30s
- [ ] UI === мокап (layout, fonts Archivo Black / Cormorant Garamond / IBM Plex Mono, palette night/amber/rose/teal)
- [ ] 5-минутный сценарий §9 разворачивается unattended на свежем seed=42
- [ ] AI Bubble Pops → CS-drop → revision <60s
- [ ] +Segment → factory spawn ≤3 эпизода
- [ ] Expert View toggle работает
- [ ] LLM_MODE=local + LIVE_MODE=false → нет сетевых вызовов
- [ ] make reset воспроизводит ту же траекторию
- [ ] 5 промптов задокументированы
- [ ] Loops survive in-loop exceptions
- [ ] **NEW**: import-graph test — никакой модуль core не импортит linkedin_rapidapi
- [ ] **NEW**: live LinkedIn URL → 3-turn dialogue
- [ ] **NEW**: privacy purge test (PII не в SQLite старше 1 часа для не-synthetic profiles)
- [ ] pytest passes

## Open questions (TASK.md §15 — defaults уже выбраны)

1. Ollama model: `llama3.1:8b-instruct` (default)
2. Live-mode fetch cap per booth-day: **уточнить с автором**, default 100/day
3. Revision: deprecate-with-pointer (default, для ablation)
4. Reset seed: same seed (default, reproducible)
5. Take-home card для live visitor: **уточнить**, по умолчанию НЕ ship Phase 3 (только если останется время)
6. Phase 3+ ProfileSource implementations кроме LinkedIn: defer

## Что выкидываем из 2026-04-21 done-list

Эти были выполнены, но vocabulary устарел:
- Pydantic 7 моделей — переписать целиком (Persona→Profile, Offer→PitchStrategy, +DialogueStep)
- ORM 6 таблиц — мигрировать колонки
- Preference matrix 6×6×5×4 — заменить на 5 affinity dicts + sparse combo_bonuses
- Drift swap-функции — пересобрать под framing/tone слоты
- 5 промптов — переписать
- Frontend stubs — выкинуть, портировать `edra_design_mockup.html`

Что переживает: `llm/client.py`, `orchestrator.py` (структура), `db.py`, `config.py`, тест-каркас, формула CS, HDBSCAN-pipeline.
