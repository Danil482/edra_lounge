---
tags: [debugging, llm, prompts, hallucination, phase-5]
date: 2026-05-13
---

# Empty system prompts cause LLM to hallucinate brand facts

**Problem**: discovered during the 2026-04-30 prompt audit. The LLM invents facts every turn — "we partnered with major retail brand", "cohort of 20 brands" — because the system message contains only "You are a research-liaison agent." and nothing else.

**Root cause**: the prompts have no concrete Defy facts. Without facts, the LLM fills the gap with plausible-sounding fabrications. The "diversity directive" in the prompt was a red herring — the real issue is the absence of grounding material.

**Impact**: every conversation contains at least one hallucinated claim. This is unacceptable for a booth demo where visitors can check facts on their phone.

**Planned fix** (Phase 5.1 — blocked on founders):
1. Create `backend/llm/prompts/_defy_brand.txt` with real facts (products, founders, proof points, boundaries)
2. Inject as `{defy_facts}` into opener and continuation prompts
3. Add explicit instruction: "do not invent facts not listed in `{defy_facts}`"
4. Add response categories to force diversity via state, not directives

**Status**: blocked on [[Founder answers are needed to fix prompt hallucinations|founder questionnaire]] (6 questions, sent 2026-04-30).

See [[Hybrid path C balances Defy facts with research vocab]] for the vocabulary mismatch context.
