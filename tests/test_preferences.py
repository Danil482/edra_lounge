"""§5.2 invariant — each seeded persona must have a unique top-3 preferred offer.

If two personas share a top-3 combo, cluster-specific rules will not emerge
cleanly in the demo.
"""

import numpy as np

from backend.simulator import preferences


def _top_k_combos(matrix: np.ndarray, pi: int, k: int = 3) -> list[tuple[int, int, int]]:
    scores = matrix[pi]  # shape (T, S, D)
    flat = scores.reshape(-1)
    top = np.argsort(flat)[::-1][:k]
    out: list[tuple[int, int, int]] = []
    T, S, D = scores.shape
    for idx in top:
        ti = idx // (S * D)
        si = (idx % (S * D)) // D
        di = idx % D
        out.append((int(ti), int(si), int(di)))
    return out


def test_top3_combos_are_unique_per_persona():
    matrix = preferences.matrix()
    n_personas = matrix.shape[0]
    all_top3 = [frozenset(_top_k_combos(matrix, pi, 3)) for pi in range(n_personas)]

    for i in range(n_personas):
        for j in range(i + 1, n_personas):
            overlap = all_top3[i] & all_top3[j]
            assert not overlap, (
                f"personas {preferences.PERSONA_IDS[i]} and "
                f"{preferences.PERSONA_IDS[j]} share top-3 combos: {overlap}"
            )


def test_matrix_shape():
    m = preferences.matrix()
    assert m.shape == (
        len(preferences.PERSONA_IDS),
        len(preferences.TOPICS),
        len(preferences.STYLES),
        len(preferences.DRINKS),
    )


def test_outcome_thresholds():
    assert preferences.outcome_from_score(0.75) == "satisfied"
    assert preferences.outcome_from_score(0.50) == "neutral"
    assert preferences.outcome_from_score(0.20) == "rejected"
