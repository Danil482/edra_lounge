---
tags: [decision, architecture, mock, offline, invariant]
date: 2026-05-13
---

# Mock API key enables offline booth demos

**Decision**: `RAPIDAPI_KEY=mock` short-circuits the LinkedIn fetch and returns a hand-crafted author profile. This path is load-bearing for offline demos and CI.

**Why**: the user does not maintain a live RapidAPI key during dev. Conference Wi-Fi is unreliable. The mock path ensures the booth always works with zero external dependencies.

**Consequence**: the mock path must be tested and maintained. It short-circuits *before* identifier parsing — regardless of what URL or handle is entered, the mock path returns the same author profile.

**Related**: the user is pragmatic about external deps — no Ollama install during dev, no real RapidAPI key. Any new network-dependent feature must have an offline fallback. See [[LinkedIn fetch survived two provider sunsets]].
