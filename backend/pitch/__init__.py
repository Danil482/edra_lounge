"""Pitch generation — produces the next DialogueStep given (Profile, history,
applicable rule | None).

Phase 1A: package shell only. Phase 1B fills `generate_turn(profile, history,
rule)`:
  - static rule (all 5 slots static) → assemble pitch without an LLM call
  - hybrid rule (≥ 1 dynamic slot) → fill dynamic slots via LLM (e.g. opener)
  - no rule → improvise via LLM with cluster's recent episodes as few-shot
"""
