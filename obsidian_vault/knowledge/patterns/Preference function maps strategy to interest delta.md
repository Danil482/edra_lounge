---
tags: [pattern, simulator, preferences, scoring]
date: 2026-05-13
---

# Preference function maps strategy to interest delta

The synthetic visitor preference function (`backend/simulator/preferences.py`) scores how well a pitch strategy matches a visitor archetype, producing an interest delta per turn.

## Formula

```
base = 0.25*framing + 0.25*tone + 0.20*opener + 0.15*word_target + 0.15*ask_size
+ combo bonuses
- 0.10*history_length  (fatigue)
→ discretise to [-2, +2]
```

## Archetype affinities

Defined in `archetypes.yaml` — each archetype has per-slot affinity scores. Loaded lazily and cached.

## Drift events

- **`ai_bubble_pops()`** — instant swap of affinity pairs for tech-founder archetype (simulates market shock)
- **`GradualPostdocShift`** — linear interpolation of framing affinity over 15 episodes (simulates attitude creep)

Drift is scheduled via game-clock in the tick loop (day 3 @ 10:00 for bubble, gradual for postdoc).

## Live mode note

In live mode, visitor reactions come from button clicks, not the preference function. The function is only used for synthetic auto-play.
