---
tags: [session, pivot, skeleton, architecture]
date: 2026-04-21
---

# 2026-04-21 Pivot to Lounge demo, skeleton shipped

Фокус работы перенесён с доктор-пропозала (EDRA repo, Pipedrive, 635 эпизодов, куча data-quality проблем) на **3-недельную демку для research-конференции** — EDRA Lounge, бар с синтетическими визитёрами.

## Решения этой сессии

1. **Отдельный репозиторий.** Сначала начали было внутри EDRA на ветке `lounge`, потом решили вынести в sibling `C:\Users\dania\PycharmProjects\edra-lounge\` — чтобы не было двойного чтения кода между research-track и demo-track. Ветку `lounge` в EDRA удалили.
2. **Отказ от n8n.** Вся оркестрация живёт внутри FastAPI-процесса как asyncio-таски. TASK.md §§2, 6, 12 зафиксировали это жёстко.
3. **Двухслойная архитектура:** Python backend + vanilla HTML/JS frontend. Никаких worker-ов, очередей, воркфлоу-движков.

## Что построено (каркас)

- Структура `backend/` ровно по TASK.md §13: `app / orchestrator / memory / clustering / induction / monitor / reflection / factory / simulator / llm / routers`
- Все 7 Pydantic-моделей из §4 дословно (Persona, Offer, Episode, Cluster, Rule+RuleSlot, Revision, Agent)
- SQLAlchemy ORM для 6 таблиц
- LLM-клиент на httpx (не SDK) с двумя режимами — `LLM_MODE=local` (Ollama) и `LLM_MODE=remote` (Anthropic)
- Симулятор: preference matrix 6×6×5×4; `topic_affinity` дословно из §5.2, остальные аффинности с заметкой TODO(author-tune)
- Две drift-функции: `ai_bubble_pops` (swap hype↔foundations + enthusiastic↔skeptical у tech-founder) и `GradualPostdocShift` (15-шаговая линейная интерполяция)
- Оркестратор: класс с `start()/stop()`, тремя резиентными loop-ами (tick 20s / consistency 10s / factory 30s) и реактивным хуком `on_new_episode`
- SSE разнесён: `POST /rules/{id}/revise` возвращает `Revision{id, status=pending}` синхронно; `GET /reflections/stream/{id}` стримит
- 5 промптов в маркетинговом словаре (§7: persona × tension → angle × expression) с fixed-tag output
- `seeded_run.yaml` на 3 дня, триггеры drift A/B привязаны к game clock
- Фронт-стабы (`index.html` + `styles.css` + `app.js`) — polling работает, SSE-подписка TODO
- Тесты: `test_preferences.py` (unique top-3 invariant), `test_orchestrator.py` (§14 loop-resilience)

## Промпты — важная правка

§7 TASK.md требует: **внутренне** промпты оперируют маркетинговым словарём (persona, tension/pain point, angle, insight), но **выход** — фиксированный тэг-словарь (hype/foundations/.../coffee/beer/...). Сначала писал промпты в café-терминах, пришлось переписать все 5 — научный фрейминг проекта это (persona, tension) → (angle, expression), кафе-словарь только на UI.

## Что НЕ в каркасе (намеренно)

Бизнес-логика внутри модулей стои́т на `# TODO(phase1)`:
- Не персистим ClusterRow-ы — кластеры ре-расчитываются в памяти на каждом тике
- `_pick_rule_for_persona` возвращает None → бармен всегда импровизирует (пока не появятся первые rule-ы)
- SSE-хэндлер — закомментированный sketch (сама reflection.stream_revision написана и unit-тестируема)
- UMAP-проекция в `/state.clusters_viz` пока пустой список

Это честный Phase 1 skeleton — контракты зафиксированы, инфраструктура работает end-to-end (health check + polling + orchestrator loops), **бизнес-логика не подставлена**. Следующая сессия — снимать TODO(phase1) в порядке `induce → CS monitor → reflect SSE → factory spawn`.

## Repo hygiene

- `N8N_GUIDE.md` удалён — противоречит §12 non-goals
- Makefile больше не знает об отдельном процессе оркестратора
- README переписан под 2-слойную модель (3 фазы вместо 4, Phase 3 теперь booth-ready а не n8n)

## Следующая сессия — entry points

1. Заполнить самое тяжёлое TODO(phase1) — `orchestrator._try_induce_all` (pull eligible clusters + persist Rule rows + generate `R.XX` ID)
2. Реализовать `routers/clusters.py::recompute_clusters` — HDBSCAN + upsert ClusterRows + LLM-лейбл через cluster_label prompt
3. Добить SSE-хендлер в `routers/reflections.py` — рабочий EventSourceResponse вокруг `reflection.stream_revision`
4. Прогнать вручную `make seed && make demo`, убедиться что при пустой БД фронт не падает и польлинг крутится

## Файлы

- Мокап `edra_lounge_mockup.html` — автор ещё дорабатывает, пока не в репо
- TASK.md — в репо, но untracked (автор правит итеративно)
