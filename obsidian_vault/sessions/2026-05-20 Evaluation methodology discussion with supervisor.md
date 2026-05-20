---
tags: [session, evaluation, methodology, supervisor, contextual-bandit, prequential]
date: 2026-05-20
---

# 2026-05-20 Evaluation methodology discussion with supervisor

Discussion-only session (no code written) about evaluation methodology for EDRA with the PhD supervisor. Identified prequential evaluation as the correct protocol, mapped EDRA to contextual bandit framework, compiled a 6-paper reading list, and confirmed that no published evaluation framework exists for adaptive closed-loop outreach.

## What was done

### Supervisor meeting — evaluation methodology

1. **Confirmed: no existing dataset fits EDRA** — this is expected for novel applied ML work. The 4 HuggingFace datasets evaluated in the AM session (Open Email Marketing, XCampaign, Marketing-Emails, SaaS Sales Conversations) were the right ones to check, but none have the cluster-conditional profile features + 5-slot strategies that EDRA requires.

2. **Supervisor's proxy validation idea** — use historical outreach data (e.g. from colleague Philipp's Lemlist/LinkedIn campaigns), generate EDRA messages for the same profiles, measure semantic distance to messages that got positive engagement.

3. **Identified flaw in proxy approach** — semantic proximity to successful messages does not equal effectiveness. A message can be semantically similar to a winner and still fail. Also breaks down after iteration 1: EDRA would learn from test data, making subsequent comparisons circular (training on test set).

4. **Correct protocol: prequential evaluation** (test-then-train) from online learning literature. Each batch is first used as a test set (measure performance before learning), then as training data (update rules). This solves the "can't learn on test set" problem because evaluation happens before learning on each batch.

5. **Three-level evaluation framework designed:**
   - Level 1: Clustering quality (silhouette score + human evaluation)
   - Level 2: Cluster-conditional rules vs. baselines (off-policy evaluation on historical data)
   - Level 3: Adaptive learning curve over outreach batches (prequential)

6. **EDRA maps to contextual bandit framework** — context = cluster, arm = strategy. This gives formal metrics: cumulative regret, per-arm reward estimates.

7. **Literature review confirms gap** — nobody has published an evaluation framework for adaptive LLM-driven outreach with closed-loop feedback. This is itself a publishable contribution.

### Reading list compiled (6 papers)

- Li et al. WSDM 2011 — "Unbiased Offline Evaluation of Contextual-bandit-based News Article Recommendation Systems" (replay method for off-policy evaluation)
- Gama et al. 2013 — "On evaluating stream learning algorithms" (prequential evaluation protocol)
- Zhao et al. AAAI 2024 — ExpeL: LLM Agents Are Experiential Learners (Section 4 evaluation, competitor positioning)
- Li et al. WWW 2010 — LinUCB: A Contextual-Bandit Approach to Personalized News Article Recommendation (contextual bandit formalism)
- Dudik et al. ICML 2011 — Doubly Robust Policy Evaluation and Learning (off-policy evaluation)
- Karanam et al. 2025 — literature review confirming the gap in adaptive outreach evaluation

## What was NOT done

- No code written this session
- No evaluation implemented yet
- Papers not yet read by the user
- No changes to demo paper

## Key decisions

- **For demo paper (MM '26, 2 pages):** qualitative demo is sufficient, no full quantitative evaluation needed at this stage.
- **For PhD:** build own dataset through the 502-profile outreach campaign + use Philipp's historical data for offline evaluation using the replay method (Li et al. WSDM 2011).
- **Request Philipp's data** — user will ask colleague Philipp for historical outreach data from Lemlist/LinkedIn. Expected format: (profile, message, response yes/no).
- **Contextual bandit framing** — EDRA maps naturally: context = cluster, arm = strategy. Cumulative regret is the primary metric for the adaptive learning evaluation.

## Open questions

- [ ] Will Philipp share outreach data? What format and size?
- [ ] Lemlist warm-up still pending (~2026-05-26)
- [ ] IRB decision still pending
- [ ] Demo paper needs Overleaf compilation to verify 2-page fit

## Next session — entry points

1. Once Philipp's data arrives — design offline evaluation protocol using replay method (Li et al. WSDM 2011)
2. Read the 6 papers, especially prequential evaluation (Gama et al. 2013) and ExpeL Section 4
3. Welcome message + Accept/Decline buttons (frontend, from previous session backlog)
4. Phase 5.4 scenario test harness

See [[../00-home/current priorities]] for the full phase board.
