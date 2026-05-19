---
tags: [decision, prompts, phase-5, papers]
date: 2026-05-19
---

# Prompt Improvement Plan Based on Lab Papers

Phase 5.1 was blocked on founder questionnaire since 2026-04-30. On 2026-05-19 we analyzed 5 lab papers and found they provide enough factual material to build a rich fact sheet without founder input. The booth agent should talk about the **research group's published work**, not about Defy commercial products. This is a refinement of [[Hybrid path C balances Defy facts with research vocab]].

## Papers Analyzed

| Paper | Venue | Key Numbers |
|---|---|---|
| **HourglassNet** (video memorability) | MM '26 BNI | 5%+ Spearman improvement, 76% higher CTR in luxury brand case study |
| **EDRA** (doctoral proposal) | MM '26 Doctoral | Episodic memory + HDBSCAN + rule induction + revision |
| **ToucHire** (influencer marketing agents) | SIGIR '26 Industrial | 85% time-to-outreach reduction, 54% response rate increase, 12x campaign capacity |
| **SOINSPIRE** (content generation) | SIGIR '26 Demo | nDCG@10=0.829, outperforms ChatGPT (0.750) and Gemini (0.769) |
| **Agouda** (contextual advertising) | SIGIR '26 Doctoral | BERTopic dual-stream, privacy-compliant video ad placement |

## 7 Research Streams for Fact Sheet

1. Video memorability prediction (HourglassNet)
2. Self-improving LLM agents (EDRA)
3. Influencer marketing automation (ToucHire)
4. Professional content generation (SOINSPIRE)
5. Privacy-compliant contextual advertising (Agouda)
6. Marketing strategy co-creation (MindFuse, MM '25)
7. Autonomous marketing pipelines (Blueprint + AgencyOS, SIGIR '26)

## Core Techniques (recurring across papers)

HDBSCAN clustering, sentence embeddings (MiniLM, CLIP-ViT-B/32, all-mpnet-base-v2), vector databases (HNSW), multi-agent architectures, RAG/Dynamic RAG, BERTopic, multimodal cross-attention fusion, human-AI collaboration paradigm.

## Prompt Architecture (4 phases)

### Phase 5.1 — Lab Fact Sheet (`_lab_facts.txt`)
- Lab identity, 7 research streams with paper references
- Concrete deployed numbers from each paper
- Core techniques list
- Conference presence 2026: MM (Dublin + Rio) + SIGIR (Melbourne)
- **No longer blocked on founders** — papers provide sufficient material

### Phase 5.2 — System Message Refactor (`_system.txt`)
- ~500 words: Identity + Facts + Anti-hallucination boundaries + Style
- Replace single-line system message in `generate.py`
- 6 response categories with rotation: `lab-paper-reference`, `methodology-hook`, `deployment-result`, `profile-callback`, `concrete-next-step`, `honest-framing`
- `used_categories` tracked in Session, passed to continuation prompt

### Phase 5.3 — Refusal Behavior
- **Hard refusal**: domains with zero overlap (geology, law, pure math) — honest acknowledgement
- **Soft refusal**: tenuous connection — don't stretch, offer papers if curious
- **Stalled conversation**: 4+ positive turns — pivot to concrete next step
- **ask_size=none**: no CTAs, soft door-open only
- Domain mapping: strong fit (marketing, AI/ML, IR, NLP, CV, multimodal, e-commerce), moderate (data science, HCI, cognitive science), refusal (pure math, physics, engineering, life sciences, law)

### Phase 5.4 — Scenario Test Harness
- Strong-fit × positive, skeptical, stalled paths
- Moderate-fit × cautious narrow framing
- Weak-fit × graceful refusal
- Empty headline × cautious generic opening
- ask_size=none × no CTA

## Caveats

- **HourglassNet is anonymous submission** — reference only as "ongoing work on video memorability" until published
- **Google Scholar gap** — only 2025-2026 papers covered; earlier work (multimodal profiling, SoMin platform) should be added when available
- **Founders** — if they reply, their answers augment the fact sheet (client examples, engagement format) but the plan does not depend on them
