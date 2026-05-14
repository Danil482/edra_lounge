---
tags: [session, paper, novelty, email-enrichment, humanizer]
date: 2026-05-14
---

# 2026-05-14 Demo paper rewrite and email enrichment

Full rewrite of `edra_demo.tex` for ACM MM 2026 demo track (2-page limit), novelty verification via literature search, and email enrichment of the 502-profile research dataset.

## What was done

### Demo paper rewrite (edra_demo.tex)
1. **Complete rewrite** from ~6 pages to 2-page ACM sigconf format per MM '26 demo submission guidelines.
2. **Fixed critical factual error**: clustering is over *profiles* (not episodes). KNN rule lookup (K=7) formalized. Episodes used only for rule generation phase.
3. **Removed all synthetic/simulation content**: YAML schedules, "AI Bubble Pops" drift events, SyntheticProfileSource, game clock, scripted 5-minute scenarios.
4. **Removed implementation details**: SQLAlchemy tables, module paths, test counts, LLM integration (httpx, three providers), ProfileSource protocol.
5. **Added formalization**: 3 equations (profile embedding, KNN weighted vote, Consistency Score).
6. **Added 2 figure placeholders** with detailed GENERATE prompts for diagram generation: system architecture (full-width) and booth UI (single-column). Architecture diagram generated and inserted as `EDRA_workflow.png`.
7. **Added Real-World Validation section**: 502 profiles, GPT-4o-mini generation, Resend API delivery, metrics referenced from companion doctoral proposal.
8. **Structure**: 5 sections (Introduction with inline related work, EDRA Framework, Validation on 502 Researchers, Becoming the Subject, Conclusion).

### Novelty verification
9. **Thorough literature search** across 25+ systems (2023-2026). Found 3 high-threat systems:
   - **ExpeL** (AAAI 2024) — extracts task-general insights from episodes, but offline, no monitoring
   - **EvolveR** (Oct 2025) — closes feedback loop via RL, but task-general, no user clustering
   - **ReasoningBank** (Google, Sep 2025) — continuous extract-consolidate loop, but task-general
10. **Narrowed novelty claim**: from "no prior system closes the loop" (too broad, factually wrong) to "cluster-conditional rule adaptation" (per profile cluster, degradation-triggered). No other system differentiates rules by user type.
11. **Updated paper**: added ExpeL, EvolveR, ReasoningBank to Introduction and bib. Repositioned contributions around cluster-conditional novelty.

### Farseev voice and humanizer
12. **Installed humanizer skill** (`~/.claude/skills/humanizer/SKILL.md`) — 29-pattern anti-AI-slop detector based on Wikipedia's "Signs of AI writing" guide.
13. **Farseev academic voice applied**: "we strongly believe", "in our opinion", hierarchical contributions, provocative section titles, active voice throughout.
14. **Humanizer audit pass**: zero em dashes, no AI vocabulary (delve/tapestry/landscape/pivotal/crucial), no rule-of-three abuse, no copula avoidance.

### Email enrichment
15. **Enriched dataset created** at `data/research_profiles/research_profiles_enriched.csv` with Email and Email_Source columns.
16. **64 unique emails found** from ~375 High-confidence profiles searched (17% hit rate). Sources: university faculty pages (~50), personal websites (~8), Google Scholar (~3), org directories (~3).
17. Industry researchers (Google DeepMind, Meta FAIR, OpenAI) almost never have public emails. Academics have highest availability.

### Resend domain verification
18. **Investigated** Akamai CDN/WAF block (error 97.xxx from edgesuite.net) — resolved via incognito mode (cached cookies were the cause).
19. **Domain `defygroup.ai` exists in Resend** but verification blocked on DNS records — need domain owner (founders) to add MX/SPF/DKIM records.

## What was NOT done

- **Resend domain verification** — blocked on founder access to defygroup.ai DNS
- **Supplementary slides/video** for MM '26 demo submission (required: <=10 slides or <=5 min video)
- **Paper compilation check** — not verified that the 2-page paper actually fits (need Overleaf build)
- **Medium/Low confidence profiles** not searched for emails (~127 remaining)
- **Obsidian code changes not committed** — papers/, .env.example remain unstaged per user request

## Key decisions

- **Novelty is cluster-conditional**: not "we close the loop" (others do too), but "we close the loop per user-type cluster with degradation-triggered revision"
- **ExpeL, EvolveR, ReasoningBank must be cited** — omitting them would be dishonest and reviewers would catch it
- **Humanizer skill** installed permanently at `~/.claude/skills/humanizer/` for future use across projects
- **Resend domain issue** is an Akamai cookie/geo block, not a Resend problem — incognito mode works

## Open questions

- [ ] Does the paper actually fit in 2 pages when compiled? Need Overleaf build verification
- [ ] Supplementary material format: PowerPoint (10 slides) or video (5 min)?
- [ ] Domain verification for `defygroup.ai` — who has DNS access?
- [ ] Phase 5.1 still blocked on founder questionnaire (no update since 2026-04-30)
- [ ] IRB decision for outreach campaign
- [ ] EvolveR and ReasoningBank bib entries have placeholder authors — need to fill in real author names before submission

## Next session — entry points

1. **Compile paper in Overleaf** — verify 2-page fit, fix any overflow
2. **Create supplementary slides** (10 slides max: concept, novelty, impact, demo walkthrough, interactivity)
3. **Generate booth UI screenshot** for Fig 2 placeholder (or use real frontend screenshot)
4. **Fill in real bib entries** for EvolveR and ReasoningBank (currently placeholder authors)
5. **Review enriched email dataset** — pick 20 High-confidence profiles for first outreach batch
6. **If founders reply** — Resend domain verification + Phase 5.1

See [[../00-home/current priorities]] for the full phase board.
