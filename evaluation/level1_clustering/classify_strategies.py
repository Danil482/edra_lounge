"""
Embed message snippets via MiniLM, cluster into strategy archetypes, output with_strategies.csv.

Usage:
    python -m evaluation.level1_clustering.classify_strategies
    python -m evaluation.level1_clustering.classify_strategies --recompute
    python -m evaluation.level1_clustering.classify_strategies --input evaluation/data/clean.csv --output evaluation/data/with_strategies.csv
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from collections import Counter
from pathlib import Path

import hdbscan
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

LABEL_OVERRIDES = {
    "ai_somin_hi": "general_intro",
    "somin_long_ta": "personalized_opener",
    "aleks_farseev_catch": "mass_newsletter",
    "vc_lx_grant_vc_fro": "vc_fundraising",
    "successfully_helps_company_successfully_efficiency": "company_pitch",
    "ai_somin_deck": "event_followup",
    "marketing_swiftly_automate_campaign_performance": "tech_demo",
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_INPUT = DATA_DIR / "clean.csv"
DEFAULT_OUTPUT = DATA_DIR / "with_strategies.csv"
EMBEDDINGS_CACHE = DATA_DIR / "embeddings_snippets.npy"
UMAP_CACHE = DATA_DIR / "umap_snippets.npy"
LOCAL_MODEL_PATH = PROJECT_ROOT / "backend" / "models" / "all-MiniLM-L6-v2"


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def compute_embeddings(snippets: list[str]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    model_path = str(LOCAL_MODEL_PATH) if LOCAL_MODEL_PATH.exists() else "all-MiniLM-L6-v2"
    model = SentenceTransformer(model_path)
    return model.encode(snippets, show_progress_bar=True, normalize_embeddings=True)


def get_embeddings(snippets: list[str], *, recompute: bool) -> np.ndarray:
    if not recompute and EMBEDDINGS_CACHE.exists():
        cached = np.load(EMBEDDINGS_CACHE)
        if cached.shape[0] == len(snippets):
            print(f"Loaded cached embeddings from {EMBEDDINGS_CACHE} ({cached.shape})")
            return cached
        print(f"Cache shape mismatch ({cached.shape[0]} vs {len(snippets)}), recomputing...")

    embeddings = compute_embeddings(snippets)
    EMBEDDINGS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.save(EMBEDDINGS_CACHE, embeddings)
    print(f"Saved embeddings to {EMBEDDINGS_CACHE} ({embeddings.shape})")
    return embeddings


def reduce_umap(embeddings: np.ndarray, *, recompute: bool) -> np.ndarray:
    if not recompute and UMAP_CACHE.exists():
        cached = np.load(UMAP_CACHE)
        if cached.shape[0] == embeddings.shape[0]:
            print(f"Loaded cached UMAP from {UMAP_CACHE} ({cached.shape})")
            return cached
        print(f"UMAP cache shape mismatch, recomputing...")

    from umap import UMAP
    reduced = UMAP(n_components=10, random_state=42, metric="cosine").fit_transform(embeddings)
    np.save(UMAP_CACHE, reduced)
    print(f"Saved UMAP to {UMAP_CACHE} ({reduced.shape})")
    return reduced


def run_hdbscan(reduced: np.ndarray) -> np.ndarray:
    clusterer = hdbscan.HDBSCAN(min_cluster_size=30, min_samples=10)
    return clusterer.fit_predict(reduced)


def label_cluster(snippets: list[str]) -> str:
    """TF-IDF over snippets in a single cluster; join top 2-3 terms as snake_case label."""
    if len(snippets) < 2:
        return "singleton"

    tfidf = TfidfVectorizer(
        max_features=200,
        stop_words="english",
        ngram_range=(1, 2),
        max_df=0.9,
        min_df=2,
    )
    try:
        matrix = tfidf.fit_transform(snippets)
    except ValueError:
        return "generic"

    mean_scores = np.asarray(matrix.mean(axis=0)).flatten()
    feature_names = tfidf.get_feature_names_out()
    top_indices = mean_scores.argsort()[::-1]

    terms = []
    for idx in top_indices:
        term = feature_names[idx]
        if len(terms) >= 3:
            break
        # skip terms that are substrings of already-selected terms
        if any(term in t or t in term for t in terms):
            continue
        terms.append(term)
        if len(terms) >= 3:
            break

    if not terms:
        return "generic"

    return "_".join("_".join(t.split()) for t in terms)


def assign_strategies(
    rows: list[dict[str, str]],
    labels: np.ndarray,
) -> tuple[list[str], list[int]]:
    """Return (strategy_labels, strategy_ids) aligned with rows, sorted by cluster size descending."""
    cluster_ids = set(labels)
    cluster_ids.discard(-1)

    cluster_snippets: dict[int, list[str]] = {}
    for row, label in zip(rows, labels):
        cluster_snippets.setdefault(int(label), []).append(row["clean_snippet"])

    # sort clusters by size descending for stable id assignment
    sorted_clusters = sorted(cluster_ids, key=lambda c: len(cluster_snippets[c]), reverse=True)

    raw_labels: dict[int, str] = {}
    stable_ids: dict[int, int] = {}
    for new_id, original_id in enumerate(sorted_clusters):
        raw_labels[original_id] = label_cluster(cluster_snippets[original_id])
        stable_ids[original_id] = new_id

    raw_labels[-1] = "noise"
    stable_ids[-1] = -1

    # deduplicate labels by appending the id
    label_counts = Counter(raw_labels.values())
    final_labels: dict[int, str] = {}
    seen: dict[str, int] = {}
    for original_id in sorted_clusters:
        base = raw_labels[original_id]
        if label_counts[base] > 1:
            occurrence = seen.get(base, 0)
            seen[base] = occurrence + 1
            final_labels[original_id] = f"{base}_{occurrence}"
        else:
            final_labels[original_id] = base
    final_labels[-1] = "noise"

    strategy_labels = [final_labels[int(l)] for l in labels]
    strategy_ids = [stable_ids[int(l)] for l in labels]
    return strategy_labels, strategy_ids


def print_report(
    rows: list[dict[str, str]],
    labels: np.ndarray,
    strategy_labels: list[str],
    strategy_ids: list[int],
) -> None:
    total = len(rows)
    noise_mask = labels == -1
    n_noise = int(noise_mask.sum())
    n_clustered = total - n_noise
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)

    print(f"\n{'=' * 70}")
    print("  CLUSTERING REPORT")
    print(f"{'=' * 70}")
    print(f"  Input rows:     {total}")
    print(f"  Clustered rows: {n_clustered}")
    print(f"  Noise rows:     {n_noise} (excluded from output)")
    print(f"  Clusters found: {n_clusters}")

    has_outcome = "outcome" in rows[0] if rows else False

    # per-strategy table
    strat_data: dict[str, dict] = {}
    for row, slabel, sid in zip(rows, strategy_labels, strategy_ids):
        if slabel == "noise":
            continue
        if slabel not in strat_data:
            strat_data[slabel] = {"id": sid, "count": 0, "replies": 0, "snippets": []}
        strat_data[slabel]["count"] += 1
        if has_outcome and row.get("outcome") == "reply":
            strat_data[slabel]["replies"] += 1
        strat_data[slabel]["snippets"].append(row["clean_snippet"][:50])

    print(f"\n  {'Strategy':<40} {'ID':>4} {'Size':>6}", end="")
    if has_outcome:
        print(f" {'Reply%':>8}", end="")
    print(f"  {'Top opening phrase'}")
    print(f"  {'-'*40} {'-'*4} {'-'*6}", end="")
    if has_outcome:
        print(f" {'-'*8}", end="")
    print(f"  {'-'*40}")

    for slabel in sorted(strat_data, key=lambda s: strat_data[s]["count"], reverse=True):
        d = strat_data[slabel]
        top_phrase = Counter(d["snippets"]).most_common(1)[0][0] if d["snippets"] else ""
        print(f"  {slabel:<40} {d['id']:>4} {d['count']:>6}", end="")
        if has_outcome:
            rate = 100 * d["replies"] / d["count"] if d["count"] else 0
            print(f" {rate:>7.1f}%", end="")
        print(f"  {top_phrase}")

    print(f"\n  Final output row count: {n_clustered}")


def save_output(
    rows: list[dict[str, str]],
    labels: np.ndarray,
    strategy_labels: list[str],
    strategy_ids: list[int],
    output_path: Path,
) -> None:
    fieldnames = list(rows[0].keys())
    if "strategy" not in fieldnames:
        fieldnames.append("strategy")
    if "strategy_id" not in fieldnames:
        fieldnames.append("strategy_id")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    kept = 0
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row, label, slabel, sid in zip(rows, labels, strategy_labels, strategy_ids):
            if label == -1:
                continue
            row["strategy"] = slabel
            row["strategy_id"] = str(sid)
            writer.writerow(row)
            kept += 1

    print(f"\nSaved {kept} rows to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Embed snippets, cluster into strategy archetypes, output with_strategies.csv"
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--recompute", action="store_true", help="Force recompute embeddings and UMAP")
    args = parser.parse_args()

    input_path: Path = args.input
    output_path: Path = args.output

    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    rows = load_rows(input_path)
    print(f"Loaded {len(rows)} rows from {input_path}")

    snippets = [row["clean_snippet"] for row in rows]
    embeddings = get_embeddings(snippets, recompute=args.recompute)
    reduced = reduce_umap(embeddings, recompute=args.recompute)
    labels = run_hdbscan(reduced)

    n_noise = int((labels == -1).sum())
    print(f"HDBSCAN: {len(set(labels)) - (1 if -1 in labels else 0)} clusters, {n_noise} noise samples removed")

    strategy_labels, strategy_ids = assign_strategies(rows, labels)

    overridden = 0
    for old_label, new_label in LABEL_OVERRIDES.items():
        count = strategy_labels.count(old_label)
        if count > 0:
            strategy_labels = [new_label if s == old_label else s for s in strategy_labels]
            overridden += 1
    print(f"Label overrides applied: {overridden}/{len(LABEL_OVERRIDES)}")

    print_report(rows, labels, strategy_labels, strategy_ids)
    save_output(rows, labels, strategy_labels, strategy_ids, output_path)


if __name__ == "__main__":
    main()
