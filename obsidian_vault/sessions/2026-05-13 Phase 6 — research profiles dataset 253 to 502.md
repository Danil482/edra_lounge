---
tags: [session, phase-6, dataset, research-profiles, linkedin]
date: 2026-05-13
---

# 2026-05-13 Phase 6 — Research profiles dataset expanded 253 → 502

Pure data-collection session. **No production code touched** — only `research_profiles_master.csv` extended from ~253 rows (collected previously by the user via Codex) to **502 verified rows**, ready as a high-quality, balanced pool of LinkedIn profiles for future outreach testing.

This is the prep substrate for the **Phase 5 prompt rework** (still blocked on founders). When prompts are rewritten with real Defy facts and category-rotation, we will have ready candidates to send hand-crafted test messages to.

## What was done

1. **Recovered context** from `current priorities.md` + the 2026-04-30 Phase 5 prep session — confirmed Phase 5 is still blocked on a 6-question questionnaire to founders. Decided to use today on Phase 6 dataset prep.
2. **Distribution audit** of the existing 253 rows — found `Research` segment at 56% (too heavy), Bay Area at 24% (overrepresented), large gaps in Applied Eng, OSS infra, Germany beyond sovereign-AI cluster, APAC beyond Singapore, Eastern Europe, LatAm.
3. **10 sequential / parallel batches** of subagent collection runs, each targeting a specific gap. Each batch was schema-validated (LinkedIn URL must contain `linkedin.com`), dedup-checked against the live names index, and appended to the master CSV.
4. **Final audit** — 0 schema violations, 0 duplicate names, 0 duplicate LinkedIn URLs across all 502 rows. 376 High confidence (75%), 117 Medium (23%), 9 Low (2%).

## Batch breakdown

| # | Focus | Yielded | Notes |
|---|---|---|---|
| 1 | OSS / eval / agent / infra practitioners | 21 | Dropped 4 schema violators (Omar Khattab, Rémi Louf, Diego Devesa, Ying Sheng — non-linkedin.com URLs) |
| 2 | Applied AI engineers in production (non-Bay) | 25 | Dropped 2 dupes (Lewis Tunstall, Loubna Ben Allal) |
| 3 | APAC beyond Singapore (JP/KR/IN/AU/CN/Asia-SE) | 25 | Clean |
| 4 | Germany beyond sovereign-AI cluster | 21 | Dropped Helge Ritter (slug unverifiable) |
| 5 | France beyond HF/Mistral leadership | 17 | Clean — INRIA + ENS + Kyutai + Photoroom + Dust + Giskard |
| 6 | Canada beyond Mila/Cohere | 18 | Vector Institute / Waterloo / UBC / Alberta / RBC Borealis / Layer 6 / Taalas |
| 7 | Industry research scientists outside FAANG+OpenAI+Anthropic+DeepMind | 23 | Dropped 2 dupes (Shafiq Joty, Balaji Vasan Srinivasan) |
| 8 | AI safety / alignment / interpretability / evals | 37 | Anthropic interp + Apollo + Redwood + METR + UK AISI + DeepMind safety + GovAI + CSET + ETH SPY |
| 9 | AI for science (bio/chem/climate/medical/robotics) | 24 | Dropped Kevin White (invented slug "kevin-white-tempus") |
| 10 | Under-represented regions (IL/IT/ES/EE/LatAm/TR/Pittsburgh/Boston) | 29 | Clean |
| 11 (final) | Closing top-up (Stanford CRFM / UW / HF / xAI / Cornell) | 10 | Clean |

Total appended: **249** profiles (252 collected by subagents, 3 dropped as cross-batch dupes or schema violators).

## Final distribution

**By confidence**: High 376 (75%) / Medium 117 (23%) / Low 9 (2%).

**By segment** (top 6):
- Research — 226 (45%, was 56% — relative share dropped despite +84 new researchers)
- Research/Leadership — 69
- Applied Eng — 65 (was 33 — biggest growth, gap closed)
- Founder/Research — 48
- Founder/Infra — 30 (was 9)
- Research/Safety — 13 (was 5)

**By geography** (top 10, percentage of 502):
- US-Bay/CA — 21.5% (was 24% — relative share dropped via other regions growing faster)
- UK — 10.4%
- Canada — 9.4%
- Germany — 7.2%
- France/Iberia — 6.8%
- US-NY — 4.2%
- US-Seattle — 3.6%
- Japan — 3.4%
- Singapore — 3.2%
- China/HK — 2.6%

**New coverage added**:
- Italy — 6 rows (was 0)
- Eastern Europe (PL/CZ/HU/RO) — 11 rows (was 0)
- Latin America (BR/AR/CL) — 5 rows (was 1)
- Israel — 8 rows (was 3)
- Spain — 8 rows (was 1)
- Turkey — 2 rows (was 0)

## Quality controls applied

1. **Strict LinkedIn schema** — every appended row has a LinkedIn URL containing `linkedin.com` (any subdomain — `ca/uk/de/jp/in/...`). Personal sites, GitHub, Scholar, Twitter rejected at append time even when subagents tried to substitute.
2. **Source URL must be non-LinkedIn public page** — lab team page, conference bio, company team page, GitHub org page, arxiv paper, news article, blog post bio. Established the verification chain: source proves person + affiliation + AI relevance separately from LinkedIn.
3. **One-sentence specific `Why included`** — must name a real artifact: a paper, model, shipped product, talk, GitHub project. Vague justifications rejected.
4. **Dedup at two levels** — names lowercased + LinkedIn URL exact. Cross-batch dedup performed when running batches 8/9/10 in parallel.

## Known quality risks

Around 10-15 rows have LinkedIn slugs inferred from search snippets rather than directly visited (LinkedIn returns HTTP 999 to WebFetch behind auth). All flagged Medium or Low confidence. Before manual outreach, the following should be eyeball-clicked:

- Tom Moor (Linear) — slug `tom-moor-b6213b1ba`
- Wes Gurnee (Anthropic interp) — slug `wes-gurnee-b2b2b2149` looks suspicious
- Tan Zhi Xuan (NUS) — slug `tanzhixuan` inferred
- Roger Grosse (Toronto/Vector) — slug inferred
- Stephen Casper, Jacob Steinhardt, Trenton Bricken — slugs inferred from non-LinkedIn snippets
- Ohad Shamir (Weizmann), Ronen Eldan (MSR) — slugs inferred
- Hannaneh Hajishirzi (UW/AI2) — agent flagged that slug might redirect

## What was NOT done in this session

- **No production code touched** — Phase 5 prompts remain in the same state from 2026-04-30. The dataset is preparation for Phase 5, not a substitute for it.
- **Did not attempt to reach 500 with synthetic / hallucinated entries** — when subagents tried to fabricate LinkedIn URLs from training data (e.g. `kevin-white-tempus`), those rows were dropped. Precision over recall, per the user's prompt.
- **Phase 5.1 fact sheet still blocked** on founders' answers to the 2026-04-30 questionnaire.
- **HTML dashboard** (`research_profiles_dashboard.html`) generated for visual exploration of the dataset but kept out of git per user request.

## Repo housekeeping after this session

- `research_profiles_master.csv` — committed in this session (Phase 6 deliverable)
- `research_profiles_dashboard.html` — generated, gitignored
- `123.py`, `TASK_refactor_clustering.md`, `uvicorn.log`, `README.md` modifications — left as-is, user's WIP, not touched
- All Obsidian session notes translated from Russian to English in this session (project-wide language switch — see `CLAUDE.md` for the new rule)
- `CLAUDE.md` added at repo root with explicit project rules (English-only writing, no secrets in commits, atomic phase-style commits, etc.)

## Next session — entry points

1. **If founders have replied** to the Defy questionnaire: start Phase 5.1 (`_defy_brand.txt` fact sheet) using their answers + this dataset as the outreach pool.
2. **If still blocked**: start Phase 5.4 (scenario test harness) on current prompts to lock in a baseline, OR pick UI polish work from `current priorities.md` (avatar caching strategy, idle screen, choice-button disable post-terminate).
3. Optional — second-pass quality verification of the ~15 Medium/Low confidence rows flagged above. Manual eyeball click-through before any outreach.

See [[../00-home/current priorities]] for the full phase board.
