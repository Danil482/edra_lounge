"""Doubly-robust policy estimator — Level 2 evaluation.

Compares four outreach policies using DR estimation (Dudik et al. 2011)
with bootstrap confidence intervals. Reads the unified dataset.csv and
umap_profiles.npy produced by cluster_recipients.py.

Usage:
    python -m evaluation.level2_policy.dr_estimator
"""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import LabelEncoder

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATASET_CSV = DATA_DIR / "dataset.csv"
UMAP_PATH = DATA_DIR / "umap_profiles.npy"

N_BOOTSTRAP = 1000
PROPENSITY_CLIP = 0.02
MIN_OBS_PER_CLUSTER = 5
BOOTSTRAP_CI = 0.95


def load_data() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    with open(DATASET_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    X_umap = np.load(UMAP_PATH)
    assert X_umap.shape[0] == len(rows), (
        f"UMAP rows ({X_umap.shape[0]}) != CSV rows ({len(rows)})"
    )

    strategies = sorted(set(r["strategy"] for r in rows))
    action_encoder = LabelEncoder()
    action_encoder.fit(strategies)

    actions = action_encoder.transform([r["strategy"] for r in rows])
    rewards = np.array([1.0 if r["outcome"] == "reply" else 0.0 for r in rows])
    cluster_ids = np.array([int(r["cluster_id"]) for r in rows])

    return X_umap, actions, rewards, cluster_ids, list(action_encoder.classes_)


def train_reward_model(
    X_umap: np.ndarray,
    actions: np.ndarray,
    rewards: np.ndarray,
    n_actions: int,
) -> tuple[LogisticRegression, float]:
    action_onehot = np.zeros((len(actions), n_actions))
    action_onehot[np.arange(len(actions)), actions] = 1.0
    X_full = np.hstack([X_umap, action_onehot])

    model = LogisticRegression(max_iter=1000, solver="lbfgs")
    cv_scores = cross_val_score(model, X_full, rewards, cv=5, scoring="roc_auc")
    cv_auc = cv_scores.mean()

    model.fit(X_full, rewards)
    return model, cv_auc


def predict_reward(
    model: LogisticRegression,
    X_umap: np.ndarray,
    action: int,
    n_actions: int,
) -> np.ndarray:
    n = X_umap.shape[0]
    action_onehot = np.zeros((n, n_actions))
    action_onehot[:, action] = 1.0
    X_full = np.hstack([X_umap, action_onehot])
    return model.predict_proba(X_full)[:, 1]


def compute_cluster_propensity(
    actions: np.ndarray,
    cluster_ids: np.ndarray,
    n_actions: int,
) -> np.ndarray:
    propensity = np.zeros(len(actions))
    for cid in set(cluster_ids):
        mask = cluster_ids == cid
        cluster_actions = actions[mask]
        n_cluster = mask.sum()
        for a in range(n_actions):
            a_mask = cluster_actions == a
            prop = max(a_mask.sum() / n_cluster, PROPENSITY_CLIP)
            propensity[mask & (actions == a)] = prop
    return propensity


def dr_estimate(
    policy_actions: np.ndarray,
    actual_actions: np.ndarray,
    rewards: np.ndarray,
    propensity: np.ndarray,
    reward_model: LogisticRegression,
    X_umap: np.ndarray,
    n_actions: int,
) -> np.ndarray:
    n = len(rewards)
    scores = np.zeros(n)

    for a in range(n_actions):
        mu_a = predict_reward(reward_model, X_umap, a, n_actions)
        pi_mask = policy_actions == a
        scores += pi_mask * mu_a

    match = policy_actions == actual_actions
    mu_chosen = np.zeros(n)
    for i in range(n):
        a = int(actual_actions[i])
        onehot = np.zeros((1, n_actions))
        onehot[0, a] = 1.0
        x = np.hstack([X_umap[i:i+1], onehot])
        mu_chosen[i] = reward_model.predict_proba(x)[0, 1]

    correction = match * (rewards - mu_chosen) / propensity
    scores += correction

    return scores


def bootstrap_ci(
    scores: np.ndarray,
    n_bootstrap: int = N_BOOTSTRAP,
    ci: float = BOOTSTRAP_CI,
) -> tuple[float, float, float]:
    rng = np.random.default_rng(42)
    n = len(scores)
    means = np.array([
        rng.choice(scores, size=n, replace=True).mean()
        for _ in range(n_bootstrap)
    ])
    alpha = (1 - ci) / 2
    lo = np.quantile(means, alpha)
    hi = np.quantile(means, 1 - alpha)
    return float(scores.mean()), float(lo), float(hi)


def global_best_action(actions: np.ndarray, rewards: np.ndarray, n_actions: int) -> int:
    best_rate = -1.0
    best_action = 0
    for a in range(n_actions):
        mask = actions == a
        if mask.sum() == 0:
            continue
        rate = rewards[mask].mean()
        if rate > best_rate:
            best_rate = rate
            best_action = a
    return best_action


def edra_policy(
    cluster_ids: np.ndarray,
    actions: np.ndarray,
    rewards: np.ndarray,
    n_actions: int,
) -> np.ndarray:
    g_best = global_best_action(actions, rewards, n_actions)
    cluster_best: dict[int, int] = {}

    for cid in set(cluster_ids):
        mask = cluster_ids == cid
        best_rate = -1.0
        best_action = g_best

        for a in range(n_actions):
            a_mask = mask & (actions == a)
            if a_mask.sum() < MIN_OBS_PER_CLUSTER:
                continue
            rate = rewards[a_mask].mean()
            if rate > best_rate:
                best_rate = rate
                best_action = a

        cluster_best[int(cid)] = best_action

    return np.array([cluster_best[int(c)] for c in cluster_ids])


def main() -> None:
    print("Loading data...")
    X_umap, actions, rewards, cluster_ids, strategy_names = load_data()
    n = len(rewards)
    n_actions = len(strategy_names)
    d = X_umap.shape[1]

    print(f"  {n} rows, {n_actions} strategies, {d}d context")
    print(f"  Overall reply rate: {rewards.mean():.3f}")
    print(f"  Clusters: {sorted(set(cluster_ids.tolist()))}")

    # --- Strategy reply rates ---
    print(f"\n{'='*80}")
    print("  STRATEGY REPLY RATES")
    print(f"{'='*80}")
    print(f"\n  {'Strategy':<40} {'N':>6} {'Replies':>8} {'Rate':>8}")
    print(f"  {'-'*40} {'-'*6} {'-'*8} {'-'*8}")

    for a_idx, name in enumerate(strategy_names):
        mask = actions == a_idx
        total = mask.sum()
        replies = rewards[mask].sum()
        rate = replies / total if total > 0 else 0
        print(f"  {name:<40} {total:>6} {int(replies):>8} {rate:>8.3f}")

    # --- Per-cluster best strategy ---
    print(f"\n{'='*80}")
    print("  PER-CLUSTER BEST STRATEGY (min {0} obs)".format(MIN_OBS_PER_CLUSTER))
    print(f"{'='*80}")
    print(f"\n  {'Cluster':>8} {'N':>6} {'Best Strategy':<40} {'Rate':>8}")
    print(f"  {'-'*8} {'-'*6} {'-'*40} {'-'*8}")

    for cid in sorted(set(cluster_ids)):
        mask = cluster_ids == cid
        cluster_n = mask.sum()
        best_rate = -1.0
        best_name = "(fallback to global)"

        for a_idx in range(n_actions):
            a_mask = mask & (actions == a_idx)
            if a_mask.sum() < MIN_OBS_PER_CLUSTER:
                continue
            rate = rewards[a_mask].mean()
            if rate > best_rate:
                best_rate = rate
                best_name = strategy_names[a_idx]

        rate_str = f"{best_rate:.3f}" if best_rate >= 0 else "n/a"
        print(f"  {int(cid):>8} {int(cluster_n):>6} {best_name:<40} {rate_str:>8}")

    # --- Reward model ---
    print(f"\n{'='*80}")
    print("  REWARD MODEL (LogReg on UMAP-{0}d + action one-hot)".format(d))
    print(f"{'='*80}")

    reward_model, cv_auc = train_reward_model(X_umap, actions, rewards, n_actions)
    print(f"\n  5-fold CV AUC: {cv_auc:.4f}")

    # --- Propensity scores ---
    propensity = compute_cluster_propensity(actions, cluster_ids, n_actions)
    print(f"  Propensity range: [{propensity.min():.4f}, {propensity.max():.4f}]")

    # --- Define policies ---
    most_common_action = int(np.bincount(actions).argmax())
    g_best = global_best_action(actions, rewards, n_actions)

    policies: dict[str, np.ndarray] = {
        "pi_uniform": np.full(n, most_common_action),
        "pi_random": np.full(n, -1),
        "pi_best_single": np.full(n, g_best),
        "pi_edra": edra_policy(cluster_ids, actions, rewards, n_actions),
    }

    print(f"\n  pi_uniform action: {strategy_names[most_common_action]} (most common, n={int((actions == most_common_action).sum())})")
    print(f"  pi_best_single action: {strategy_names[g_best]} (highest global reply rate)")

    # --- DR estimation ---
    print(f"\n{'='*80}")
    print(f"  DOUBLY-ROBUST POLICY ESTIMATES ({N_BOOTSTRAP} bootstrap, {BOOTSTRAP_CI*100:.0f}% CI)")
    print(f"{'='*80}")

    print(f"\n  {'Policy':<18} {'V_DR':>8} {'95% CI':>20} {'vs uniform':>12}")
    print(f"  {'-'*18} {'-'*8} {'-'*20} {'-'*12}")

    uniform_mean = None
    results: dict[str, tuple[float, float, float]] = {}

    for name, policy_actions in policies.items():
        if name == "pi_random":
            rng = np.random.default_rng(42)
            scores_all = []
            for _ in range(N_BOOTSTRAP):
                random_actions = rng.integers(0, n_actions, size=n)
                sc = dr_estimate(
                    random_actions, actions, rewards, propensity,
                    reward_model, X_umap, n_actions,
                )
                scores_all.append(sc.mean())
            scores_arr = np.array(scores_all)
            alpha = (1 - BOOTSTRAP_CI) / 2
            mean_val = float(scores_arr.mean())
            lo = float(np.quantile(scores_arr, alpha))
            hi = float(np.quantile(scores_arr, 1 - alpha))
        else:
            scores = dr_estimate(
                policy_actions, actions, rewards, propensity,
                reward_model, X_umap, n_actions,
            )
            mean_val, lo, hi = bootstrap_ci(scores)

        results[name] = (mean_val, lo, hi)
        if name == "pi_uniform":
            uniform_mean = mean_val

        delta_str = ""
        if uniform_mean is not None and name != "pi_uniform":
            delta = mean_val - uniform_mean
            delta_str = f"{delta:+.4f}"

        ci_str = f"[{lo:.4f}, {hi:.4f}]"
        print(f"  {name:<18} {mean_val:>8.4f} {ci_str:>20} {delta_str:>12}")

    # --- Verdict ---
    print(f"\n{'='*80}")
    print("  VERDICT")
    print(f"{'='*80}")

    v_uniform = results["pi_uniform"][0]
    v_random = results["pi_random"][0]
    v_best = results["pi_best_single"][0]
    v_edra = results["pi_edra"][0]

    print(f"\n  Does cluster-conditional policy (EDRA) beat single-strategy baselines?")
    print(f"    V_DR(pi_edra)        = {v_edra:.4f}")
    print(f"    V_DR(pi_uniform)     = {v_uniform:.4f}")
    print(f"    V_DR(pi_best_single) = {v_best:.4f}")
    print(f"    V_DR(pi_random)      = {v_random:.4f}")

    edra_vs_uniform = v_edra - v_uniform
    edra_vs_best = v_edra - v_best

    print(f"\n    EDRA vs uniform:     {edra_vs_uniform:+.4f}", end="")
    if edra_vs_uniform > 0.005:
        print(" -- EDRA wins")
    elif edra_vs_uniform < -0.005:
        print(" -- uniform wins")
    else:
        print(" -- roughly tied")

    print(f"    EDRA vs best_single: {edra_vs_best:+.4f}", end="")
    if edra_vs_best > 0.005:
        print(" -- EDRA wins")
    elif edra_vs_best < -0.005:
        print(" -- best_single wins")
    else:
        print(" -- roughly tied")

    ranking = sorted(results.items(), key=lambda x: x[1][0], reverse=True)
    print(f"\n  Policy ranking:")
    for rank, (name, (mean_val, lo, hi)) in enumerate(ranking, 1):
        ci_str = f"[{lo:.4f}, {hi:.4f}]"
        print(f"    {rank}. {name:<18} {mean_val:.4f}  {ci_str}")


if __name__ == "__main__":
    main()
