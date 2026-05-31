---
tags: [session, demo-paper, evaluation, seed, architecture-diagram, supplementary, presentation]
date: 2026-05-31
---

# 2026-05-31 Demo paper rewrite and eval seed from real data

Supervisor review triggered a complete restructuring of `edra_demo.tex` from industry paper to demo paper format. Re-ran evaluation pipeline on doubled tier 2 data (13.8K rows). Seeded demo DB from 744 real outreach interactions.

## What was done

### Demo paper restructuring (edra_demo.tex)

Supervisor (Aleksandr) reviewed the paper and flagged it as "not a demo paper — all about how you built it." He provided SOInspire demo paper as a structural template. Changes:

1. **Merged Introduction + System Overview into one section** — 4 sections total (Intro, Demo, Eval, Conclusion) matching the SOInspire template structure
2. **System described via numbered bold components (I-IV)** — Profile Embedding, Rule Induction, KNN Application, Consistency Monitoring — instead of a separate architecture section
3. **Removed all 3 equations** — replaced with accessible prose
4. **Section 3 (The Demonstration) corrected** against actual UI — supervisor wrote it from memory, we fixed: added email auth gate, 12 emotional avatar states, thought monologue mechanic, dynamic response buttons, interest gauge, Accept/Decline buttons
5. **Expert View** described with 3 hover-triggered panels + operator controls ("AI Bubble Pops" drift injection)
6. **Evaluation section** compressed, math notation removed (plain "Estimated Reward" instead of $\hat{V}_{DR}$), Learning Dynamics placeholder deleted
7. **Style aligned to abstract** — dense, academic, accessible prose throughout (supervisor wrote the abstract)
8. **Conference metadata** uncommented (MM '26, Rio de Janeiro)
9. **Booth screenshot** (fig:booth) uncommented and placed in Demo section

### Architecture diagram

Created `papers/edra_architecture_diagram.html` — horizontal SVG diagram in Defy brand colors (#CC0000 / #0A0A0A / #F9F9F7), ~1200x480px. Needs screenshot to `papers/EDRA_workflow.png` for LaTeX.

### Supplementary slides

Created `papers/edra_supplementary_slides.html` — 10-slide presentation covering all 5 required ACM demo topics (concept, novelty, impact, what's shown, interactivity). Defy branded, keyboard-navigable.

### Bibliography fixes

- EvolveR author names filled (arXiv:2510.16079 — Rong Wu et al.)
- ReasoningBank author names filled (arXiv:2509.25140 — Siru Ouyang et al., Google Research)
- `edra-demo-2026` entry added (YouTube placeholder URL)

### Evaluation re-run on expanded tier 2 data

Tier 2 CSV grew from 6,757 to 13,806 rows (2 days of extraction). Pipeline results on 744 rows (was 632):

- **Chi-squared Cluster x Outcome**: V=0.346 (was 0.229) — cluster effect MUCH stronger with no-reply data
- **DR estimator**: EDRA 0.654, Best single 0.588, Uniform 0.510 (delta +0.066, was +0.102)
- **Prequential**: still shows DOWN trend — distribution shift (early=inbound, late=cold)
- Fixed UMAP/dataset.csv row mismatch bug in `cluster_recipients.py`

### Seed demo from evaluation data

Created `backend/seed_from_eval.py` — seeds `edra_lounge.db` from 744 real outreach interactions:
- 744 anonymized profiles (PII stripped, source_kind="synthetic")
- 744 episodes with real outcomes (accepted/rejected)
- 7 clusters with centroid embeddings and labels (Director CEO, Founder, Marketing Director, Marketing Investor, Marketing Manager, Mixed, Partner Venture)
- 7 rules — best strategy per cluster, all static 5-slot
- 7 agents — one per cluster

### Paper claims verification

Ran 20-point verification of paper claims against codebase. 18/20 exact match. 2 discrepancies fixed:
- "UMAP scatter plot" → "t-SNE scatter plot" (visualization uses t-SNE, not UMAP; UMAP is for clustering only)

## What was NOT done

- Screenshot EDRA_workflow.png from HTML (user needs to open in browser + screenshot)
- Compile paper in Overleaf — verify 2-page fit
- Update abstract numbers (still says 632, body says 744)
- Record demo video (supplementary material — later, before camera-ready)
- Google Cloud for Startups application for hosting
- Send CTO deployment message
- Run demo end-to-end with seeded DB to verify

## Key decisions

- **4-section structure** adopted: Intro (problem + system I-IV) → Demo → Eval → Conclusion — matching SOInspire template
- **papers/ stays in .gitignore** — managed via Overleaf, not git
- **Evaluation numbers updated to 744 rows** — tier 2 data doubled, chi-squared cluster effect much stronger (V=0.346 vs 0.229)
- **EDRA delta shrank** from +0.102 to +0.066 — still positive but more conservative with larger dataset
- **Real data seeding** — demo DB now uses anonymized CRM outreach data instead of synthetic archetypes

## Open questions

- [ ] Abstract still says 632 rows — update to 744? Or keep consistent with what supervisor approved?
- [ ] Should we report the smaller delta (+0.066) or keep the old number (+0.102) on fewer rows?
- [ ] Video for supplementary: when to record? Need running demo with seeded DB
- [ ] Deployment: Google Cloud for Startups vs Railway vs Fly.io?

## Next session — entry points

1. Screenshot architecture diagram → `EDRA_workflow.png`
2. Compile paper in Overleaf — verify 2-page fit
3. Send paper + slides to supervisor for review
4. Run demo end-to-end with seeded eval DB
5. Record demo video (3-5 min) for supplementary material
6. Google Cloud for Startups application
7. Deployment: Dockerize + deploy to cloud

See [[../00-home/current priorities]] for the full phase board.
