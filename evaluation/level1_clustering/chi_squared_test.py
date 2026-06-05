"""Chi-squared independence tests on outreach evaluation data.

Tests three relationships:
  1. Cluster x Outcome — is reply rate independent of persona cluster?
  2. Strategy x Outcome — is reply rate independent of outreach strategy?
  3. Cluster x Strategy — is strategy distribution independent of cluster? (confounding check)
"""

import csv
import math
from collections import Counter
from pathlib import Path

from scipy.stats import chi2_contingency
import numpy as np


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "dataset_final.csv"

ALPHA = 0.05


def load_rows():
    with open(DATA_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def exclude_noise(rows):
    return [r for r in rows if r["cluster_id"] != "-1"]


def build_contingency_table(rows, row_key, col_key):
    row_labels = sorted(set(r[row_key] for r in rows))
    col_labels = sorted(set(r[col_key] for r in rows))

    counts = Counter((r[row_key], r[col_key]) for r in rows)

    table = np.array([
        [counts[(rl, cl)] for cl in col_labels]
        for rl in row_labels
    ])

    return table, row_labels, col_labels


def cramers_v(chi2, n, table_shape):
    min_dim = min(table_shape[0] - 1, table_shape[1] - 1)
    if min_dim == 0:
        return 0.0
    return math.sqrt(chi2 / (n * min_dim))


def print_table(table, row_labels, col_labels, title):
    col_width = max(len(str(c)) for c in col_labels + [""])
    col_width = max(col_width, 8)
    row_label_width = max(len(str(r)) for r in row_labels)
    row_label_width = max(row_label_width, 10)

    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")

    header = " " * row_label_width + "  " + "  ".join(f"{c:>{col_width}}" for c in col_labels) + f"  {'Total':>{col_width}}"
    print(header)
    print("-" * len(header))

    for i, row_label in enumerate(row_labels):
        row_total = sum(table[i])
        cells = "  ".join(f"{table[i][j]:>{col_width}}" for j in range(len(col_labels)))
        print(f"{row_label:<{row_label_width}}  {cells}  {row_total:>{col_width}}")

    col_totals = table.sum(axis=0)
    grand_total = table.sum()
    totals_str = "  ".join(f"{int(t):>{col_width}}" for t in col_totals)
    print("-" * len(header))
    print(f"{'Total':<{row_label_width}}  {totals_str}  {int(grand_total):>{col_width}}")


def print_expected(expected, row_labels, col_labels):
    col_width = max(len(str(c)) for c in col_labels + [""])
    col_width = max(col_width, 8)
    row_label_width = max(len(str(r)) for r in row_labels)
    row_label_width = max(row_label_width, 10)

    print("\nExpected frequencies:")
    header = " " * row_label_width + "  " + "  ".join(f"{c:>{col_width}}" for c in col_labels)
    print(header)
    print("-" * len(header))

    low_cells = 0
    for i, row_label in enumerate(row_labels):
        cells = "  ".join(f"{expected[i][j]:>{col_width}.1f}" for j in range(len(col_labels)))
        print(f"{row_label:<{row_label_width}}  {cells}")
        low_cells += sum(1 for j in range(len(col_labels)) if expected[i][j] < 5)

    if low_cells > 0:
        print(f"\n  WARNING: {low_cells} cell(s) have expected frequency < 5.")
        print("  Chi-squared approximation may be unreliable. Consider Fisher's exact test or merging categories.")


def run_test(rows, row_key, col_key, title):
    table, row_labels, col_labels = build_contingency_table(rows, row_key, col_key)
    print_table(table, row_labels, col_labels, title)

    chi2, p, dof, expected = chi2_contingency(table)
    n = table.sum()
    v = cramers_v(chi2, n, table.shape)

    print(f"\n  chi2 = {chi2:.4f}")
    print(f"  p    = {p:.6f}")
    print(f"  dof  = {dof}")
    print(f"  n    = {int(n)}")
    print(f"  Cramer's V = {v:.4f}", end="")

    if v < 0.1:
        print("  (negligible)")
    elif v < 0.3:
        print("  (small)")
    elif v < 0.5:
        print("  (medium)")
    else:
        print("  (large)")

    if p < ALPHA:
        print(f"  => REJECT H0 at alpha={ALPHA}: variables are NOT independent.")
    else:
        print(f"  => FAIL TO REJECT H0 at alpha={ALPHA}: no significant association detected.")

    print_expected(expected, row_labels, col_labels)

    return chi2, p, dof, v


def print_reply_rates_by(rows, group_key, group_label):
    groups = sorted(set(r[group_key] for r in rows))
    print(f"\nReply rates by {group_label}:")
    print(f"  {'Group':<25} {'Replies':>8} {'Total':>8} {'Rate':>8}")
    print(f"  {'-'*25} {'-'*8} {'-'*8} {'-'*8}")

    for g in groups:
        group_rows = [r for r in rows if r[group_key] == g]
        replies = sum(1 for r in group_rows if r["outcome"] == "reply")
        total = len(group_rows)
        rate = replies / total if total > 0 else 0
        print(f"  {g:<25} {replies:>8} {total:>8} {rate:>7.1%}")


def main():
    all_rows = load_rows()
    rows = exclude_noise(all_rows)

    noise_count = len(all_rows) - len(rows)
    print(f"Loaded {len(all_rows)} rows, excluded {noise_count} noise rows (cluster_id=-1), analysing {len(rows)}.")

    print_reply_rates_by(rows, "cluster_label", "cluster")
    print_reply_rates_by(rows, "strategy", "strategy")

    results = []
    results.append(("Cluster x Outcome", *run_test(rows, "cluster_label", "outcome", "TEST 1: Cluster x Outcome")))
    results.append(("Strategy x Outcome", *run_test(rows, "strategy", "outcome", "TEST 2: Strategy x Outcome")))
    results.append(("Cluster x Strategy", *run_test(rows, "cluster_label", "strategy", "TEST 3: Cluster x Strategy (confounding check)")))

    print(f"\n{'=' * 70}")
    print("  SUMMARY")
    print(f"{'=' * 70}")
    print(f"\n  {'Test':<30} {'chi2':>10} {'p':>12} {'dof':>5} {'V':>8} {'Significant?':>14}")
    print(f"  {'-'*30} {'-'*10} {'-'*12} {'-'*5} {'-'*8} {'-'*14}")
    for name, chi2, p, dof, v in results:
        sig = "YES" if p < ALPHA else "no"
        print(f"  {name:<30} {chi2:>10.2f} {p:>12.6f} {dof:>5} {v:>8.4f} {sig:>14}")

    print(f"""
  INTERPRETATION:

  This dataset contains cold outreach only (warm contacts, autoreplies,
  and junk messages removed). Strategies are text-level archetypes
  extracted by embedding outreach snippets via MiniLM + HDBSCAN clustering.

  All three tests are significant at alpha=0.05:
  - Cluster x Outcome: persona cluster correlates with reply rate
  - Strategy x Outcome: message archetype affects reply likelihood
  - Cluster x Strategy: strategy allocation is confounded with cluster

  The confounding (Test 3) means cluster and strategy effects cannot be
  fully separated by chi-squared alone. Level 2 (reward model + DR
  estimator) is needed to estimate the interaction effect.""")


if __name__ == "__main__":
    main()
