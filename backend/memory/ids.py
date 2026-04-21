"""ID generation. Deterministic under fixed RNG seed for reproducible demo."""

import random
import string

_alphabet = string.ascii_lowercase + string.digits


def short_id(prefix: str, rng: random.Random | None = None) -> str:
    """Generate `<prefix>_<6char>` ID. Pass seeded rng for deterministic output."""
    r = rng or random
    return f"{prefix}_{''.join(r.choices(_alphabet, k=6))}"


def next_rule_id(existing: list[str]) -> str:
    """Monotonic human-friendly rule IDs: R.01, R.02, ... R.12, R.13."""
    if not existing:
        return "R.01"
    nums = []
    for eid in existing:
        try:
            nums.append(int(eid.split(".")[1]))
        except (IndexError, ValueError):
            continue
    nxt = (max(nums) + 1) if nums else 1
    return f"R.{nxt:02d}"
