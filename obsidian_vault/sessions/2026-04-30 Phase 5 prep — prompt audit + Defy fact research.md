---
tags: [session, phase-5, prompts, defy-brand, research, blocked-on-founders]
date: 2026-04-30
---

# 2026-04-30 Phase 5 prep — prompt audit + Defy fact research

Сессия чисто аналитическая, **кода не трогали**. Цель — разобрать что плохо в текущих промптах перед тем как переписывать, и найти достаточный фактический материал про Defy чтобы убрать галлюцинации. Завершилось с компактным questionnaire к founders + неожиданным архитектурным разрывом.

## Что сделано

1. **Восстановили контекст** из `current priorities.md` + последней сессии 2026-04-29
2. **Прочитали все 6 промптов** в `backend/llm/prompts/` (opener, continuation, summary, induce, reflect, cluster_label) + `pitch/generate.py` + `pitch/templates.py` + `pitch/classify.py` + `llm/client.py`
3. **Аудит промптов** — сформулировали what's good / what's broken / how to fix
4. **Изучили публичный Defy** — `defygroup.ai` (через WebFetch) + WebSearch (LinkedIn под логином, недоступен напрямую)
5. **Сформулировали 6 вопросов к founders** в компактной английской форме — готовы к отправке
6. **Открыли стратегический вопрос Путь A/B/C** — что делать с расхождением между EDRA-вокабом и реальным Defy ICP

## Аудит промптов — что нашли

### ✅ Что работает хорошо
- Slot-aware структура (framing/tone/opener_type/word_target/ask_size) — EDRA-нативный язык
- 3-кнопочное ограничение явно прописано (Phase 4.3 закрыл этот баг)
- Ветвление по `last_choice` в continuation — positive/skeptical/negative разнесены
- Запрет повторов прописан
- Good/bad shape examples в opener.txt работают как few-shot
- History block format корректно отражает что визитёр сказал только клик кнопки

### ❌ Корневая проблема: **никакой конкретики про Defy в промптах**
- `system="You are a research-liaison agent."` — это ВЕСЬ shared context
- Никаких фактов про что Defy делает, кто founders, какие коллаборации, что предлагает
- Поэтому в e2e-сессии 2026-04-29 каждый турн = свежая галлюцинация ("we partnered with major retail brand", "cohort of 20 brands", "case studies showcasing methodologies")
- Skeptical-ветка просит "name one specific reason Defy is legitimate" — **прямо просит галлюцинировать** при отсутствии фактов
- Continuation diversity (главный пейн поинт) = прямое следствие: без фактов LLM выбирает единственную безопасную траекторию (enterprise sales credentials × N)

### ❌ Побочные дефекты
- **System message нулевой** — каждый промпт переоткрывает контекст с нуля
- **Нет инструкции «не выдумывай»** — LLM по умолчанию confabulates
- **Diversity через директиву, а не через state** — promрompt не передаёт `used_categories`, нет ротации
- **Reference-to-signal на live данных рискованный** — `recent_signals` парсится из experiences[] (часто только job titles), LLM ловит ключевое слово в headline и строит пафос про "your competitive pricing analysis"
- **Edge cases профилей не обработаны** — пустой headline, нет recent_signals, профиль явно не fit для Defy
- **Refusal behavior отсутствует** — нет инструкций когда отказаться от pitch'а
- **Inconsistent casing** — `DEFY.group` / `Defy.group` / `Defy` (три варианта в templates.py)
- **`word_target` теряется** в continuation prompt
- **system message** = одна строка («You are a research-liaison agent.»)

## Phase 5 план (5 sub-stages)

1. **5.1 — Defy fact sheet** (наивысший приоритет, всё остальное на нём)
   - Создать `backend/llm/prompts/_defy_brand.txt` (или `backend/data/brand.yaml`)
   - Положения, продукты, founders, proof points, out-of-scope, engagement formats
   - Инжектить как `{defy_facts}` в opener + continuation
2. **5.2 — Refactor opener/continuation промптов**
   - Поднять system до 200-300 слов: brand voice + role + boundaries + «не выдумывай»
   - Удалить дубликаты правил про buttons (вынести в system)
   - Добавить категории ответа в continuation (specific-defy-fact / methodology-hook / profile-callback / concrete-next-step / soft-personal)
   - Передавать `used_categories` из Session → LLM требуется выбрать unused
3. **5.3 — Refusal behavior**
   - Что делать если профиль не fit
   - Что делать если signal — только job title, не пост
   - Что делать после positive×4 (не больше credentials)
   - Что делать с ask_size=`none`
4. **5.4 — Scenario test harness**
   - Pytest harness для positive×5, skeptical→positive→positive, negative-first, mixed, empty-headline, mismatched-domain
   - Asserts: ≤35 words, no open questions, mentions brand, on negative no CTA-verbs, on skeptical includes proof point
5. **5.5 — Minor cleanup**
   - Унифицировать casing
   - Передавать `word_target` в continuation
   - Templates: переписать чтобы тоже использовали `_defy_brand.txt` (fallback не должен расходиться с LLM)

## Что нашли про Defy

### Публично подтверждённое
**Positioning (verbatim с defygroup.ai):**
> "AI-powered creative technology for agency partners. We arm agencies with intelligent tools that automate boring tasks, surface pitch winning insights, and free your team to do strategic work that actually matters."

**3 продукта:**
- **Defy Monitor** — competitive intelligence dashboards (competitor ad tracking, audience personas, theme explorer; "first-party data, not scraped, not generic, live always-on")
- **Defy Automate** — agentic AI workflows
- **Defy Report** — campaign performance dashboards

**Founders:**
- **Ian Cassidy** (CEO) — 20 лет в агентствах, основал SHARE Creative, привёл Samy к PE-exit, 50+ relationships с agency founders
- **Alek Farseev** (CTO) — AI professor/researcher в Singapore

**Локация:** UK-based.

**Note:** "Active pilots with named agencies" упомянуты в job-постинге, но имена под NDA.

### Чего НЕТ в публичных источниках
- Имена клиентов / case studies (только "active pilots")
- Pricing / tiers
- Engagement format details (pilot length, cadence, deliverables)
- Out-of-scope (что Defy явно не делает)
- Конкретные "boring tasks" которые автоматизирует Automate
- Geographic markets focus (только UK или EU/US?)

## 🚨 Архитектурное расхождение — Путь A/B/C

**Проблема**: текущий EDRA-вокабуляр предполагает **academic outreach**:
- Архетипы: `arch_phd_nlp_introvert`, `arch_postdoc_cv_ambitious`, `arch_senior_prof_meta`
- ASK_SIZE: `co-author`, `intro`, `trial` (academic frame)
- Engagement: «scoping call → cohort → research collaboration»

А реальный Defy ICP — **agency people**: founders, MDs, creative directors, strategy heads, planners. ASK у них другой: «pilot trial of Monitor for 6 weeks», не «co-author paper».

**Три пути:**

- **Путь A — выровнять EDRA под реальный Defy ICP**
  - Переписать `archetypes.yaml` под agency-archetypes
  - Переписать ASK_SIZE: `demo`, `pilot`, `tier-1-trial`, `intro-to-cofounder`
  - Минус: ломает preference matrix, тесты, drift events

- **Путь B — оставить research-narrative как booth-wrapper**
  - TASK.md §1.2: "DEFY is not a technical dependency; it is the brand identity used in outreach copy. `BRAND_CONFIG` parameterises this"
  - Минус: на booth когда визитёр посмотрит LinkedIn DEFY.group — диссонанс. Skeptical-defusing «name a real Defy collaboration» становится невозможным без выдумок

- **Путь C — гибрид (рекомендую)**
  - Оставить research-archetypes как fallback в синтетике
  - Переписать промпты Defy-фактами **из реального позиционирования**
  - Refusal behavior закрывает «что говорим визитёру вне ICP»
  - Live-mode визитёр (LinkedIn) — скорее всего как раз будет agency person, потому что booth ставится на agency-conference

**Решение пути отложено** — юзер выбирает после получения ответов от founders.

## Открытые вопросы к founders (questionnaire готов на английском)

1. **Anonymized case examples** — 2-3 short anonymized client examples (e.g. "top-20 UK agency used Monitor for 6 weeks before a pitch...") for booth use
2. **Permission to cite founder credentials** — public OK to mention Ian's SHARE Creative / Samy / 50+ relationships and Alek's Singapore AI prof background?
3. **Out-of-scope** — 3-5 explicit boundaries (not recruiting? not consulting hours? not data licensing? not for in-house brand teams?)
4. **Engagement format & next-step shape** — demo → trial → paid pilot? Pilot length, cadence, deliverables? When agent says "let's talk pilot" — what is literal next step?
5. **Booth ICP & lead product** — agency founders/MDs/planners/CDs/mixed? Lead product Monitor/Automate/Report?
6. **Conferences / shared-context anchors** — which events does Defy attend/sponsor (Cannes, SXSW, agency-circle)?

## Что НЕ делали в этой сессии

- **Кода не трогали** — только аналитика и research
- **Не коммитили обновления README.md** — это юзеровский WIP (точечный markdown-fix `./TASK.md` → `TASK.md`)
- **Не коммитили `TASK_refactor_clustering.md`** — это юзеровский WIP-план рефакторинга profile/episode embedding spaces, отдельная будущая работа
- **`uvicorn.log`** так и болтается untracked — добавление в .gitignore переехало в Phase 5.5 cleanup

## Следующая сессия

Стартует когда:
1. Юзер получил ответы от founders на questionnaire выше
2. Юзер выбрал Путь A/B/C (или гибрид)

Порядок работы:
- Фаза 5.1 — `_defy_brand.txt` со всеми ответами
- Фаза 5.2 — refactor промптов с инжектом фактов + категории
- Фаза 5.3 — refusal behavior
- Фаза 5.4 — scenario test harness
- Фаза 5.5 — cleanup

Если ответы founders задерживаются — можно начать с Фазы 5.4 (test harness) на текущих промптах, чтобы зафиксировать baseline + поймать regressions от рефакторинга 5.2.

## Что узнал нового

- **Defy ≠ research collective** — это AI-SaaS для creative/digital agencies (расхождение с тем как EDRA-промпты позиционируют агента)
- **WebFetch на главной странице мало** — без явного «list every internal link / heading / paragraph verbatim» он суммаризирует, теряя факты. Нужен второй проход с детальным prompt'ом
- **LinkedIn company pages под логином** — WebFetch вернёт только auth-страницу. WebSearch с фильтром по domain = workaround
- **Job postings — недооценённый источник** — BeBee-листинг "AI Program Manager" дал больше фактов про Defy (3 продукта, founders, pilots) чем сама defygroup.ai
