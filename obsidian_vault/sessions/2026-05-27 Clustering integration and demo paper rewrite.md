---
tags: [session, clustering, knn, demo-paper, farseev-skill, intern-review]
date: 2026-05-27
---

# 2026-05-27 Clustering integration and demo paper rewrite

Session covered three major tracks: updating the Farseev academic voice skill from 7 publications, rewriting the demo paper with bandit evaluation framing, and integrating the intern's clustering refactor from a remote branch.

## What was done

### Farseev academic voice skill v2.0

Updated `.claude/skills/farseev-academic-voice.md` from 7 papers in `papers/aleks_papers/` (Against Opacity MM'23, Fusing TOIS'25, MindFuse MM'25, SOMONITOR, SOMIN demo, Will.pdf, patent). Key additions:
- Voice evolution tracked: pre-2024 (cautious hedging) vs post-2024 (confident pragmatism)
- 6 new writing patterns: Research Question enumeration, Numbered Step narration, Three Philosophies taxonomy, "More Than Just" elevation, Validation Escalation, Real-Life Incident flagging
- New vocabulary with era tags: "co-strategist", "brave new", "poster child of", "in-flight", "performance telemetry", "proto-causal inference"
- 5 new collaborators, new systems (MindFuse, SOINSPIRE, SoWide-ViT)
- Bold abstract template (MindFuse 2025 style)

### Demo paper rewrite (edra_demo.tex + edra_demo.bib)

Complete rewrite of `papers/edra_demo.tex` for ACM MM '26 (Rio de Janeiro, not Dublin):
- Evaluation section replaced: dropped 502-profile longitudinal arm (no reward signal), replaced with three-level contextual bandit framework on 976 Pipedrive cold outreach rows
- Level 1: clustering quality (silhouette + chi-squared)
- Level 2: DR policy comparison (4 policies via doubly robust estimator)
- Level 3: prequential learning curve (Gama et al.)
- Result placeholders marked with `\textbf{[X.XXX]}` for post-evaluation fill-in
- Introduction sharpened: asymmetry framing, hierarchical contribution build ("First... Building on... Finally...")
- Demo section updated: VN inner monologue, emotion system, contextual buttons
- Paper trimmed to fit 2-page limit: compressed intro related work, removed KNN motivation line, shortened demo and conclusion, Figure 1 reduced to 0.7\textwidth
- Bib: added LinUCB (Li et al. WWW'10), Dudik DR (ICML'11), Gama prequential (MLJ'13); removed uncited NeSyPR
- Conference location fixed: Dublin → Rio de Janeiro across 3 files

### Clustering refactor integration from intern's branch

Intern pushed `origin/clustering` branch (1 commit, 39 files). Analyzed the diff, identified good additions vs problematic deletions, cherry-picked additions only:

**Integrated (new functionality):**
- `backend/clustering/knn.py` — standalone KNN rule selection by cosine similarity
- `backend/clustering/summarize.py` — deterministic text summaries from LinkedIn JSON and synthetic archetypes
- `cluster_profiles()`, `embed_single()`, `match_cluster_to_existing()` in cluster.py
- `summary_text` + `cluster_id` fields on ProfileRow/Profile schema
- `set_profile_cluster()`, `active_rules_by_cluster()` store functions
- `on_new_profile` reactive hook in orchestrator — triggers recluster on profile persist
- Profile-based `_recluster()` with centroid matching and cluster ID stability
- KNN rule lookup in `start_session()` replacing old `classify_profile`
- `knn_k=7`, `cluster_merge_threshold=0.85` config values
- 16 new tests in `test_clustering_refactor.py`

**Rejected (regressions):**
- Deletion of `resolve_session` endpoint (breaks Phase 11 Accept/Decline UX)
- Removal of inner thought mechanic from `generate.py` (breaks VN monologue)
- 500+ lines of frontend regressions (welcome flow, thought mechanic, resolve buttons)
- Deletion of 5 Obsidian session notes
- Deletion of entire `evaluation/` module
- Deletion of `.env.example`
- `n_min` change from 3 to 2

**Additional fixes:**
- Cold-start behavior: `cluster_id = None` on session when no rule exists (improvise, don't fake a cluster)
- Synthetic profiles get `profile.cluster_id = profile.id` for reclustering, but session cluster_id is None until a rule is induced
- `normalize_embeddings=True` added to `embed()` — code now matches paper's L2 normalization claim
- Test updated: `sess.cluster_id is None` on cold start instead of archetype ID
- **220 tests green** (2 pre-existing cluster_viz failures)

## What was NOT done

- LinkedIn enrichment for 635 Pipedrive profiles (still sole blocker for Level 1 evaluation)
- Actual evaluation results (all placeholders)
- Demo paper compilation verification at exactly 2 pages (iterating in Overleaf)
- EvolveR and ReasoningBank bib entries still have placeholder author names
- Farseev skill file not committed (lives in `.claude/skills/`, may be gitignored)

## Key decisions

- **Cherry-pick, not merge** — intern's branch had good clustering code mixed with destructive deletions. Took additions only, rejected all regressions.
- **cluster_id = None on cold start** — if no rule exists for a cluster, the agent improvises. Don't fake a cluster_id just because the profile is synthetic.
- **normalize_embeddings=True** — embed() now L2-normalizes so dot product = cosine similarity, matching the paper's equation.
- **Level 3 stays in paper** — even as short placeholder, it shows the evaluation is comprehensive.
- **Conclusion merged into demo section** — saved space for 2-page fit.

## Open questions

- [ ] Does the paper fit exactly in 2 pages after latest trims? (verify in Overleaf)
- [ ] Fill EvolveR/ReasoningBank real author names in bib
- [ ] LinkedIn enrichment pipeline for 635 Pipedrive profiles — how to execute at scale?
- [ ] Tell intern to delete `clustering` branch and start fresh from main

## Next session — entry points

1. LinkedIn enrichment for 635 profiles → re-cluster → fill Level 1 placeholders
2. Build reward model (LogReg) + DR estimator → fill Level 2 placeholders
3. Prequential simulation → fill Level 3 placeholder
4. Final paper compilation and submission (deadline: 2026-06-11)
5. Tell intern to rebase or start fresh from main

See [[../00-home/current priorities]] for the full phase board.
