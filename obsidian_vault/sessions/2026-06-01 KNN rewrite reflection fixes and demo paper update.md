---
tags: [session, knn, revision, reflection, demo-theater, demo-paper, startup, prompt]
date: 2026-06-01
---

# 2026-06-01 (evening) KNN K=7 rewrite, reflection fixes, demo paper update

Third session on 2026-06-01. Driven by a live-run test that surfaced three bugs in the demo theater revision flow, followed by reverting centroid-based assignment to K=7 weighted KNN voting to match the paper, and updating the demo paper to reflect all recent changes.

## What was done

### 1. Diagnosed and fixed three revision bugs

**Bug A — REVISION marker mismatch.** The LLM returned `--- REVISION---` (with space) but the code looked for exact `---REVISION---`. Marker not found → entire output classified as reasoning → empty revision JSON → parse crash. Fixed: replaced exact string match with regex `r'-{3}\s*REVISION\s*-{3}'` tolerating whitespace.

**Bug B — Fallback producing identical rule.** When parse fails, `mode_of_slots_rule(rule, succeeding)` is the fallback. If `succeeding` is empty (no accepted post-induction episodes), mode_of_slots copies the original rule's values → proposed = current (no diff). Fixed: added `_slots_match` safety net in both success and error branches; logs explicit error when fallback also matches current.

**Bug C — Revision auto-triggers on startup with dirty DB.** Orphan injected episodes from previous runs persisted in DB; consistency loop found `should_revise` true on startup before any user action. Fixed: `Orchestrator.start()` now deletes episodes with summary starting "injected contradiction" and resets `under_revision` rules + their pending revisions.

### 2. Strengthened the reflection prompt

`reflect.txt` rewritten with explicit instructions: contradicting = "CURRENT rule's strategy, FAILED"; succeeding = "DIFFERENT strategy, SUCCEEDED". Added IMPORTANT block warning the LLM that a no-op proposal means it made an error. Episode formatting changed from unlabeled positional `pitch=(X/Y/Z/W/V)` to labeled `pitch={framing=X, tone=Y, ...}` so the LLM can map values to slot names.

### 3. Reverted centroid-based assignment to K=7 weighted KNN voting

The centroid approach introduced in the PM session was functionally correct but diverged from the paper's "K-nearest neighbors (K=7) weighted voting" claim. Since the segment-suffix bug (the primary motivation for centroid) was already fixed, KNN is viable again. New `select_rule_by_knn`:
- Computes cosine similarity to all corpus profiles
- Takes top K=7 neighbors
- OOD gate: mean cosine of K neighbors < `MIN_AVG_SIMILARITY` (0.40) → improvise
- Cosine-weighted vote across ruled clusters → winning cluster's rule

Added `store.profiles_for_knn()` returning (profile_id, embedding, cluster_id) tuples. Caller in `lifecycle.py` updated. Cluster-viz default k changed from 5 to 7 to match.

### 4. Updated demo paper (edra_demo.tex)

Factual updates to match current code:
- Abstract: "Nearest-Neighbor rules" preserved (now matches code again), 632→744 interactions
- Step III: already says "K-nearest neighbors (K=7)" (matches code)
- Expert View: Rulebook Panel — "accept/edit/keep" → single OK button, before/after diff; Operator Controls — removed "current day", "AI Bubble Pops" → "Inject Contradiction", "domain-drift" → "contradicting evidence"

### 5. Committed all accumulated code

Four atomic commits covering Phase 13+14 accumulated work:
1. KNN K=7 weighted voting, seed geometry fix, viz palette
2. Honest induced revision, reflection fixes, startup cleanup
3. Frontend revision diff, inject button, edge-handle bars
4. Tests for KNN voting, injection groups, consistency sort

## What was NOT done

- **Live verification of K=7 KNN** — threshold 0.40 is a starting point, needs calibration on real LinkedIn profiles
- **2 pre-existing `test_cluster_viz` failures** still not fixed (archetype-label count mismatch)
- **Paper not committed** — `papers/` is in .gitignore (Overleaf is the source of truth)
- **Obsidian session notes for Phase 13/14** were written in previous sessions; code commits now match

## Key decisions

- **KNN over centroid** — code must match the paper; centroid was principled but created a three-way divergence (paper=KNN, viz=KNN, assignment=centroid). K=7 weighted voting is the unified approach.
- **MIN_AVG_SIMILARITY = 0.40** — starting point, between OOD centroid range (0.26-0.28) and genuine member p5 (0.45). Needs live calibration.
- **Startup cleanup is automatic** — orphan injected episodes deleted at server start, no manual `make reset` needed between demo runs.
- **Regex marker over exact match** — LLMs produce whitespace variations; rigid matching is fragile.
- **Demo theater framing** — injection is honest "reversible demo theater showing the revision mechanic on operator-injected evidence", not a claim of autonomous discovery. Paper's "The Demonstration" section describes workflow, not evaluation.

## Open questions

- Does a real marketing LinkedIn profile clear the 0.40 KNN mean-similarity threshold? Only a live run answers this.
- Keep 0.40 or retune after live data?
- Fix or delete the 2 `test_cluster_viz` failures?
- Should the "Inject Contradiction" framing in the paper more explicitly state it's operator-triggered, not autonomous?

## Next session — entry points

1. **Live-verify KNN K=7**: restart backend + hard-refresh. Check: (a) a real marketing LinkedIn URL gets assigned to a cluster; (b) neighbor panel shows K=7 with roles; (c) Inject Contradiction → streams reasoning → before→after diff → OK rollback.
2. **Calibrate MIN_AVG_SIMILARITY** on live LinkedIn profiles if they fail the 0.40 gate.
3. **Fix the 2 `test_cluster_viz` failures** (archetype-label string mismatches).
4. **Compile demo paper in Overleaf** — verify 2-page fit with the updated text.
5. **Screenshot architecture diagram** → `papers/EDRA_workflow.png` (still pending from Phase 14).

See [[../00-home/current priorities]] for the full phase board. Prior session: [[2026-06-01 Centroid OOD gate induced revision and viz palette]].
