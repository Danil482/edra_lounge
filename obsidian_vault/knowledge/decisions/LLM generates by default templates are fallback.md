---
tags: [decision, architecture, llm, templates, pitch]
date: 2026-05-13
---

# LLM generates by default templates are fallback

**Decision**: the LLM is the primary generation path for openers and continuations. Templates only run when the LLM is offline or errors out.

**Why**: the booth's value proposition is adaptive, contextual pitch dialogue. Static templates cannot reference visitor signals, recent posts, or maintain conversation coherence. Templates exist as a safety net for Wi-Fi failures at a conference booth.

**Consequence**: template quality matters less than LLM prompt quality — but templates must not diverge from the LLM's tone and vocabulary. Phase 5.5 includes a task to make templates consume the same `_defy_brand.txt` fact sheet.

**Generation paths** (in `backend/pitch/generate.py`):
1. **Improvise** — no rule → LLM with default strategy
2. **Hybrid** — rule with dynamic slots → LLM fills them
3. **Static** — rule with all slots fixed → template render
4. **Fallback** — LLM call failed → template render

See [[Three LLM providers share one httpx client]] and [[Empty system prompts cause LLM to hallucinate brand facts]].
