"""Run the full EDRA evaluation pipeline.

Usage:
    python -m evaluation.run_pipeline
    python -m evaluation.run_pipeline --recompute  (force recompute embeddings)
"""

from __future__ import annotations

import subprocess
import sys
import time

STEPS = [
    (
        "evaluation.level0_data.prepare",
        "Filter tier1+tier2 into clean.csv",
        False,
    ),
    (
        "evaluation.level1_clustering.classify_strategies",
        "Embed snippets, assign strategy archetypes",
        True,
    ),
    (
        "evaluation.level1_clustering.cluster_recipients",
        "Embed profiles, cluster recipients, produce dataset_final.csv",
        True,
    ),
    (
        "evaluation.level1_clustering.chi_squared_test",
        "Chi-squared independence tests",
        False,
    ),
    (
        "evaluation.level2_policy.dr_estimator",
        "Doubly-robust policy comparison",
        False,
    ),
    (
        "evaluation.level3_learning.prequential_simulation",
        "Prequential learning curve simulation",
        False,
    ),
]


def main() -> None:
    recompute = "--recompute" in sys.argv

    t0 = time.perf_counter()
    total = len(STEPS)

    for i, (module, description, accepts_recompute) in enumerate(STEPS, 1):
        print(f"\n{'=' * 80}")
        print(f"  STEP {i}/{total}: {description}")
        print(f"  module: {module}")
        print(f"{'=' * 80}\n")

        cmd = [sys.executable, "-m", module]
        if recompute and accepts_recompute:
            cmd.append("--recompute")

        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"\nFAILED at step {i}/{total}: {module} (exit code {result.returncode})")
            sys.exit(result.returncode)

    elapsed = time.perf_counter() - t0
    minutes = int(elapsed // 60)
    seconds = elapsed % 60

    print(f"\n{'=' * 80}")
    print(f"  PIPELINE COMPLETE — all {total} steps succeeded")
    print(f"  Total time: {minutes}m {seconds:.1f}s")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
