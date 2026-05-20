---
tags: [session, demo-paper, clustering, knn, seed-demo, rulebook, ui]
date: 2026-05-20
---

# 2026-05-20 Demo paper rewrite and live clustering

Rewrote the demo paper validation narrative (Section 3) from email-only to dual-modality (booth + longitudinal outreach), implemented KNN classification for live profiles, created seed_demo.py for pre-populated demos, fixed rulebook UI, and cached the MiniLM model locally.

## What was done

### Demo paper (edra_demo.tex)

1. **Section 3 rewritten** from "Validation on 502 Researchers" to "Evaluation" — dual-modality framing: live booth interactions as primary validation, 502-profile outreach as planned longitudinal arm.
2. **Abstract and conclusion updated** for channel-agnostic framing.
3. **Figure cross-references added** — `Figure~\ref{fig:architecture}` in Section 2, `Figure~\ref{fig:booth}` in Section 4.
4. **Booth UI screenshot inserted** — `edra_UI.png` replaces placeholder.
5. **Humanizer pass** — removed AI writing patterns: "genuine" qualifier, passive voice clusters, em-dash parentheticals, "deliberately" adverb, "channel-agnostic" repetition.
6. **Removed emphasis-only italics** — `\emph{static}`, `\emph{dynamic}`, `\emph{profiles}` dropped (AI marker), kept `\textit{}` for term definitions and UI labels (standard convention).
7. **Removed unpublished doctoral citation** — `\cite{edra-doctoral}` was referencing an unsubmitted draft.

### Backend — KNN classification for live profiles

8. **`classify.py` rewritten** — live profiles now classified via KNN (K=7): builds profile→cluster mapping from episodes, computes cosine similarities via matrix-vector dot, `np.argpartition` for top-K, weighted vote returns winning cluster_id.
9. **Auto-embedding in `start_session()`** — if a fetched profile has no embedding, computes one via MiniLM before upsert. Live LinkedIn profiles now get embeddings automatically.
10. **Local MiniLM model** — `scripts/download_model.py` saves `all-MiniLM-L6-v2` to `backend/models/`. `cluster.py` loads from local path first (0 HTTP requests), falls back to HF if missing. `backend/models/` added to `.gitignore`.

### seed_demo.py

11. **Created `backend/seed_demo.py`** — resets DB, seeds 8 profiles with embeddings, pre-creates rules from `top_k_strategies()` for each archetype, runs 18 synthetic sessions (3 per archetype × 6), triggers clustering and induction. Result: 8 profiles, 18 episodes, 6 clusters, 6 rules.
12. **Makefile target** — `make seed-demo` wired.

### Frontend — rulebook and cluster visualization

13. **Rulebook slot layout** — new `slot-grid`/`slot-pair`/`slot-val` CSS: each slot is a nowrap pair (label + tag), no mid-word wrapping.
14. **ARCHETYPE_LABELS** — added to both `app.js` (8 archetypes) and fixed stale IDs in `cluster_viz.py` backend. Cluster names now show "The Researcher", "The Skeptic" etc. instead of raw archetype IDs.
15. **User profile panel** — archetype and cluster fields now show human-readable labels via ARCHETYPE_LABELS mapping.
16. **t-SNE fix** — `n_iter` → `max_iter` (scikit-learn 1.8 renamed the parameter).

### CLAUDE.md

17. **Ruthless mentor mode** — added communication rules: no flattery, find weak spots, push back hard, verify with research.

## What was NOT done

- **Phase 5.4 scenario test harness** — not started
- **Demo paper compilation in Overleaf** — still pending
- **First outreach batch** — blocked on Lemlist warm-up (~2026-05-26)
- **Dataset-based validation** — evaluated 4 HuggingFace datasets (Open Email Marketing, XCampaign, Marketing-Emails, SaaS Sales Conversations); none suitable for EDRA evaluation

## Key decisions

- **Dual-modality validation** (Option B+C) — booth as primary, 502-profile outreach as longitudinal arm. Avoids overclaiming email results that don't exist yet.
- **No external datasets for validation** — XCampaign (CIKM '25, 15M rows) was the closest but lacks profile features and 5-slot strategies. EDRA's contribution is cluster-conditional adaptation, not recommender systems.
- **Ruthless mentor mode** — user explicitly requested honest, no-flattery feedback for all discussions. Added to CLAUDE.md as permanent rule.
- **Local model caching** — MiniLM saved to `backend/models/` to eliminate HF Hub network requests on every load.

## Open questions

- [ ] Lemlist warm-up completes ~2026-05-26
- [ ] IRB decision still pending
- [ ] Demo paper needs Overleaf compilation to verify 2-page fit
- [ ] Agent gives up too early on negative turns — needs persistence logic
- [ ] Welcome message before pitch — agent should introduce itself first

## Next session — entry points

1. **Welcome message** — agent introduces itself before diving into personalized pitch
2. **Accept / Decline buttons** — explicit user decision buttons (interest=±5 + popup)
3. **Agent persistence** — stop early termination on negative turns, try alternative approaches
4. **Phase 5.4 — Scenario test harness** — validate prompt quality
5. **Compile demo paper in Overleaf** — verify 2-page fit, insert booth screenshot
6. **Phase O.3** — Lemlist API integration (after ~2026-05-26)

See [[../00-home/current priorities]] for the full phase board.
