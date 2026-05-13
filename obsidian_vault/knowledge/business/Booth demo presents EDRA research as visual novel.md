---
tags: [business, booth, demo, visual-novel]
date: 2026-05-13
---

# Booth demo presents EDRA research as visual novel

The EDRA Lounge is a conference booth demo. It wraps the EDRA (Experience-Driven Rule Adaptation) research system in a visual-novel scene with an anime agent named Edra.

## What a visitor sees

1. Operator enters the visitor's LinkedIn URL
2. The system fetches their profile (or uses synthetic data offline)
3. Edra opens with a personalised pitch referencing the visitor's signals
4. Visitor responds via three buttons: positive / skeptical / negative
5. Conversation runs 3-7 turns until interest hits ±5 or max turns
6. Behind the scenes: clustering, rule induction, and revision happen automatically

## What the demo proves

EDRA's core thesis: an agent can **learn pitch strategies** from interaction data, **detect when they stop working** (consistency score), and **revise them** (LLM-driven reflection). The booth makes this visible via the [[Frontend polls state and streams revisions via SSE|VN UI]].

## Brand

Defy V2.0 design system — see [[Frontend polls state and streams revisions via SSE]] for palette and typography. The mockup `edra_pitch_mockup.html` is the source of truth.
