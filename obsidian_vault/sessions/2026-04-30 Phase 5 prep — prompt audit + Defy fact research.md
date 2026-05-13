---
tags: [session, phase-5, prompts, defy-brand, research, blocked-on-founders]
date: 2026-04-30
---

# 2026-04-30 Phase 5 prep — prompt audit + Defy fact research

Pure analytical session, **no code touched**. The goal was to understand what is wrong with the current prompts before rewriting them, and to find enough factual material on Defy to eliminate hallucinations. The session ended with a compact founder questionnaire and an unexpected architectural gap.

## What was done

1. **Recovered context** from `current priorities.md` + the latest 2026-04-29 session
2. **Read all 6 prompts** in `backend/llm/prompts/` (opener, continuation, summary, induce, reflect, cluster_label) + `pitch/generate.py` + `pitch/templates.py` + `pitch/classify.py` + `llm/client.py`
3. **Prompt audit** — articulated what is good / what is broken / how to fix
4. **Studied public Defy** — `defygroup.ai` (via WebFetch) + WebSearch (LinkedIn behind login, not directly accessible)
5. **Drafted 6 questions for founders** in compact English form — ready to send
6. **Opened the strategic question Path A/B/C** — what to do about the mismatch between the EDRA vocabulary and the real Defy ICP

## Prompt audit — what we found

### ✅ What works well
- Slot-aware structure (framing/tone/opener_type/word_target/ask_size) — native EDRA language
- 3-button constraint is explicitly spelled out (Phase 4.3 closed this bug)
- Branching by `last_choice` in continuation — positive/skeptical/negative are split apart
- Repetition prohibition is written down
- Good/bad shape examples in `opener.txt` work as a few-shot
- The history block format correctly reflects that the visitor said only a button click

### ❌ Root cause: **no concrete Defy material in the prompts**
- `system="You are a research-liaison agent."` — that is the ENTIRE shared context
- No facts about what Defy does, who the founders are, what collaborations exist, what is on offer
- That is why every turn in the 2026-04-29 e2e session became a fresh hallucination ("we partnered with major retail brand", "cohort of 20 brands", "case studies showcasing methodologies")
- The skeptical branch asks the LLM to "name one specific reason Defy is legitimate" — **literally asks it to hallucinate** in the absence of facts
- Continuation diversity (the main pain point) is a direct consequence: without facts the LLM picks the single safe trajectory (enterprise sales credentials × N)

### ❌ Side defects
- **System message is empty** — every prompt re-opens the context from zero
- **No "do not invent" instruction** — by default the LLM confabulates
- **Diversity through directive, not through state** — the prompt does not pass `used_categories`, there is no rotation
- **`reference-to-signal` is risky on live data** — `recent_signals` is parsed out of experiences[] (often just job titles), the LLM grabs a keyword from the headline and pumps "your competitive pricing analysis" into pathos
- **Profile edge cases are not handled** — empty headline, no `recent_signals`, a profile clearly not a fit for Defy
- **Refusal behaviour is missing** — no instruction for when to decline the pitch
- **Inconsistent casing** — `DEFY.group` / `Defy.group` / `Defy` (three variants in templates.py)
- **`word_target` is lost** in the continuation prompt
- **system message** = single line ("You are a research-liaison agent.")

## Phase 5 plan (5 sub-stages)

1. **5.1 — Defy fact sheet** (highest priority, everything else stands on it)
   - Create `backend/llm/prompts/_defy_brand.txt` (or `backend/data/brand.yaml`)
   - Positioning, products, founders, proof points, out-of-scope, engagement formats
   - Inject as `{defy_facts}` in opener + continuation
2. **5.2 — Refactor opener/continuation prompts**
   - Expand system to 200-300 words: brand voice + role + boundaries + "do not invent"
   - Remove duplicate button rules (move into system)
   - Add response categories in continuation (specific-defy-fact / methodology-hook / profile-callback / concrete-next-step / soft-personal)
   - Pass `used_categories` from Session → LLM is required to pick an unused one
3. **5.3 — Refusal behaviour**
   - What to do if a profile is not a fit
   - What to do if the only signal is a job title, not a post
   - What to do after positive×4 (no more credentials)
   - What to do with ask_size=`none`
4. **5.4 — Scenario test harness**
   - Pytest harness for positive×5, skeptical → positive → positive, negative-first, mixed, empty-headline, mismatched-domain
   - Asserts: ≤35 words, no open questions, mentions brand, no CTA verbs on negative, includes proof point on skeptical
5. **5.5 — Minor cleanup**
   - Unify casing
   - Pass `word_target` into continuation
   - Templates: rewrite to also consume `_defy_brand.txt` (fallback must not diverge from the LLM)

## What we found about Defy

### Publicly confirmed
**Positioning (verbatim from defygroup.ai):**
> "AI-powered creative technology for agency partners. We arm agencies with intelligent tools that automate boring tasks, surface pitch winning insights, and free your team to do strategic work that actually matters."

**3 products:**
- **Defy Monitor** — competitive intelligence dashboards (competitor ad tracking, audience personas, theme explorer; "first-party data, not scraped, not generic, live always-on")
- **Defy Automate** — agentic AI workflows
- **Defy Report** — campaign performance dashboards

**Founders:**
- **Ian Cassidy** (CEO) — 20 years in agencies, founded SHARE Creative, led Samy to a PE exit, 50+ relationships with agency founders
- **Alek Farseev** (CTO) — AI professor/researcher in Singapore

**Location:** UK-based.

**Note:** "Active pilots with named agencies" are mentioned in a job posting, but the names are under NDA.

### What is NOT in public sources
- Client names / case studies (only "active pilots")
- Pricing / tiers
- Engagement format details (pilot length, cadence, deliverables)
- Out-of-scope (what Defy explicitly does not do)
- Specific "boring tasks" that Automate automates
- Geographic markets focus (UK only or EU/US?)

## 🚨 Architectural mismatch — Path A/B/C

**Problem**: the current EDRA vocabulary assumes **academic outreach**:
- Archetypes: `arch_phd_nlp_introvert`, `arch_postdoc_cv_ambitious`, `arch_senior_prof_meta`
- ASK_SIZE: `co-author`, `intro`, `trial` (academic frame)
- Engagement: "scoping call → cohort → research collaboration"

But the real Defy ICP is **agency people**: founders, MDs, creative directors, strategy heads, planners. Their ASK is different: "pilot trial of Monitor for 6 weeks", not "co-author paper".

**Three paths:**

- **Path A — align EDRA with the real Defy ICP**
  - Rewrite `archetypes.yaml` to agency archetypes
  - Rewrite ASK_SIZE: `demo`, `pilot`, `tier-1-trial`, `intro-to-cofounder`
  - Cons: breaks the preference matrix, tests, drift events

- **Path B — keep the research narrative as a booth wrapper**
  - TASK.md §1.2: "DEFY is not a technical dependency; it is the brand identity used in outreach copy. `BRAND_CONFIG` parameterises this"
  - Cons: at the booth, when a visitor checks DEFY.group on LinkedIn — visible mismatch. Skeptical defusing ("name a real Defy collaboration") becomes impossible without making things up

- **Path C — hybrid (recommended)**
  - Keep research archetypes as a fallback in synthetic mode
  - Rewrite prompts with Defy facts **from real positioning**
  - Refusal behaviour handles "what we say to a visitor outside ICP"
  - The live-mode visitor (LinkedIn) is most likely an agency person, because the booth is at an agency conference

**Path decision deferred** — the user picks after receiving founder answers.

## Open questions for founders (questionnaire ready in English)

1. **Anonymized case examples** — 2-3 short anonymized client examples (e.g. "top-20 UK agency used Monitor for 6 weeks before a pitch...") for booth use
2. **Permission to cite founder credentials** — public OK to mention Ian's SHARE Creative / Samy / 50+ relationships and Alek's Singapore AI prof background?
3. **Out-of-scope** — 3-5 explicit boundaries (not recruiting? not consulting hours? not data licensing? not for in-house brand teams?)
4. **Engagement format & next-step shape** — demo → trial → paid pilot? Pilot length, cadence, deliverables? When the agent says "let's talk pilot" — what is the literal next step?
5. **Booth ICP & lead product** — agency founders/MDs/planners/CDs/mixed? Lead product Monitor/Automate/Report?
6. **Conferences / shared-context anchors** — which events does Defy attend/sponsor (Cannes, SXSW, agency circle)?

## What we did NOT do in this session

- **No code touched** — only analysis and research
- **Did not commit README.md updates** — that is the user's WIP (a targeted markdown fix `./TASK.md` → `TASK.md`)
- **Did not commit `TASK_refactor_clustering.md`** — that is the user's WIP plan to refactor profile/episode embedding spaces, separate future work
- **`uvicorn.log`** stays untracked — adding it to .gitignore was moved into Phase 5.5 cleanup

## Next session

Starts when:
1. The user has received founder answers to the questionnaire above
2. The user has picked Path A/B/C (or a hybrid)

Order of work:
- Phase 5.1 — `_defy_brand.txt` with all the answers
- Phase 5.2 — refactor prompts with fact injection + categories
- Phase 5.3 — refusal behaviour
- Phase 5.4 — scenario test harness
- Phase 5.5 — cleanup

If founder answers are delayed — we can start with Phase 5.4 (test harness) against current prompts to lock in a baseline and catch regressions from the 5.2 refactor.

## What I learned new

- **Defy ≠ research collective** — it is AI-SaaS for creative/digital agencies (mismatch with how the EDRA prompts position the agent)
- **WebFetch on the home page is not enough** — without explicitly asking for "list every internal link / heading / paragraph verbatim", it summarises and loses facts. A second pass with a detailed prompt is needed
- **LinkedIn company pages behind login** — WebFetch returns only the auth page. WebSearch filtered by domain = workaround
- **Job postings are an underrated source** — a BeBee listing for "AI Program Manager" gave more facts about Defy (3 products, founders, pilots) than defygroup.ai itself
