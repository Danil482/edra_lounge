"""
Cluster cold outreach data and produce evaluation metrics.

Usage:
    python -m evaluation.cluster_outreach
    python -m evaluation.cluster_outreach --min-cluster-size 20 --min-samples 3
    python -m evaluation.cluster_outreach --recompute
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
from sklearn.metrics import silhouette_score

# Windows console defaults to cp1252; org names contain Unicode
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = Path(__file__).resolve().parent / "data" / "cold_outreach.csv"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "data" / "clustered_outreach.csv"
EMBEDDINGS_CACHE = Path(__file__).resolve().parent / "data" / "embeddings.npy"
LOCAL_MODEL_PATH = PROJECT_ROOT / "backend" / "models" / "all-MiniLM-L6-v2"


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_text(row: dict[str, str]) -> str:
    parts = []
    job = row.get("job_title", "").strip()
    org = row.get("organization", "").strip()
    labels = row.get("labels", "").strip()

    if job and org:
        parts.append(f"{job} at {org}")
    elif job:
        parts.append(job)
    elif org:
        parts.append(org)

    if labels:
        parts.append(f"campaign: {labels}")

    return ", ".join(parts) if parts else "unknown"


def compute_embeddings(texts: list[str]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    model_path = str(LOCAL_MODEL_PATH) if LOCAL_MODEL_PATH.exists() else "all-MiniLM-L6-v2"
    model = SentenceTransformer(model_path)
    return model.encode(texts, show_progress_bar=True)


def get_embeddings(texts: list[str], *, recompute: bool) -> np.ndarray:
    if not recompute and EMBEDDINGS_CACHE.exists():
        cached = np.load(EMBEDDINGS_CACHE)
        if cached.shape[0] == len(texts):
            print(f"Loaded cached embeddings from {EMBEDDINGS_CACHE} ({cached.shape})")
            return cached
        print(f"Cache shape mismatch ({cached.shape[0]} vs {len(texts)}), recomputing...")

    embeddings = compute_embeddings(texts)
    EMBEDDINGS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.save(EMBEDDINGS_CACHE, embeddings)
    print(f"Saved embeddings to {EMBEDDINGS_CACHE} ({embeddings.shape})")
    return embeddings


def run_hdbscan(embeddings: np.ndarray, min_cluster_size: int, min_samples: int) -> np.ndarray:
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
    )
    return clusterer.fit_predict(embeddings)


def top_values(rows: list[dict[str, str]], field: str, n: int = 5) -> list[tuple[str, int]]:
    counter = Counter(
        row[field].strip() for row in rows if row.get(field, "").strip()
    )
    return counter.most_common(n)


def make_cluster_label(rows: list[dict[str, str]]) -> str:
    titles = []
    for row in rows:
        title = row.get("job_title", "").strip()
        if title:
            titles.extend(title.lower().split())

    stop_words = {
        "and", "of", "the", "at", "in", "for", "a", "an", "&", "-", "/",
        "to", "|", ",", "senior", "junior", "lead", "head", "chief",
        "vice", "associate", "assistant", "global", "regional",
    }
    word_counts = Counter(w for w in titles if w not in stop_words and len(w) > 2)
    top = word_counts.most_common(2)
    if not top:
        return "Mixed"
    return " ".join(w for w, _ in top).title()


def format_top(items: list[tuple[str, int]], max_items: int = 5) -> str:
    return ", ".join(f"{name} ({count})" for name, count in items[:max_items])


def print_report(
    rows: list[dict[str, str]],
    labels: np.ndarray,
    embeddings: np.ndarray,
) -> dict[int, str]:
    total = len(rows)
    cluster_ids = set(labels)
    cluster_ids.discard(-1)
    n_clustered = int(np.sum(labels != -1))
    n_noise = total - n_clustered

    print("=== Clustering Report ===")
    print(f"Total samples: {total}")
    print(f"Clustered: {n_clustered} ({100 * n_clustered / total:.1f}%)")
    print(f"Noise: {n_noise} ({100 * n_noise / total:.1f}%)")
    print(f"Clusters found: {len(cluster_ids)}")

    if n_clustered > 1 and len(cluster_ids) > 1:
        mask = labels != -1
        score = silhouette_score(embeddings[mask], labels[mask])
        print(f"Silhouette score: {score:.3f} (on clustered samples only)")
    else:
        print("Silhouette score: N/A (not enough clusters)")

    cluster_rows: dict[int, list[dict[str, str]]] = {}
    for row, label in zip(rows, labels):
        cluster_rows.setdefault(int(label), []).append(row)

    cluster_labels: dict[int, str] = {-1: "Noise"}

    print("\n=== Cluster Profiles ===")
    for cid in sorted(cluster_ids):
        c_rows = cluster_rows[cid]
        cluster_labels[cid] = make_cluster_label(c_rows)

        replies = sum(1 for r in c_rows if r["outcome"] == "reply")
        total_c = len(c_rows)
        reply_pct = 100 * replies / total_c if total_c else 0

        print(f"\nCluster {cid} (n={total_c}, label=\"{cluster_labels[cid]}\"):")
        print(f"  Top job titles: {format_top(top_values(c_rows, 'job_title'))}")
        print(f"  Top organizations: {format_top(top_values(c_rows, 'organization'))}")
        print(f"  Top labels: {format_top(top_values(c_rows, 'labels'))}")

        type_counts = Counter(r["outreach_type"] for r in c_rows)
        type_str = ", ".join(f"{t}={c}" for t, c in type_counts.most_common())
        print(f"  Strategy distribution: {type_str}")
        print(f"  Reply rate: {replies}/{total_c} ({reply_pct:.1f}%)")

    all_types = sorted({r["outreach_type"] for r in rows})
    all_cluster_ids = sorted(cluster_ids)

    COL_W = 18
    print("\n=== Strategy x Cluster Reply Rates ===")
    header = f"{'outreach_type':25s}" + "".join(f"{'C' + str(c):>{COL_W}s}" for c in all_cluster_ids) + f"{'Noise':>{COL_W}s}"
    print(header)
    print("-" * len(header))

    for otype in all_types:
        parts = [f"{otype:25s}"]
        for cid in list(all_cluster_ids) + [-1]:
            c_rows = [r for r in cluster_rows.get(cid, []) if r["outreach_type"] == otype]
            if not c_rows:
                parts.append(f"{'--':>{COL_W}s}")
            else:
                replies = sum(1 for r in c_rows if r["outcome"] == "reply")
                pct = 100 * replies / len(c_rows)
                cell = f"{replies}/{len(c_rows)} ({pct:.0f}%)"
                parts.append(f"{cell:>{COL_W}s}")
        print("".join(parts))

    noise_rows = cluster_rows.get(-1, [])
    if noise_rows:
        noise_replies = sum(1 for r in noise_rows if r["outcome"] == "reply")
        noise_pct = 100 * noise_replies / len(noise_rows) if noise_rows else 0
        print(f"\n=== Noise Profile ===")
        print(f"{len(noise_rows)} samples not assigned to any cluster")
        print(f"  Reply rate: {noise_replies}/{len(noise_rows)} ({noise_pct:.1f}%)")
        print(f"  Top job titles: {format_top(top_values(noise_rows, 'job_title'))}")
        print(f"  Top organizations: {format_top(top_values(noise_rows, 'organization'))}")

    return cluster_labels


def save_output(
    rows: list[dict[str, str]],
    labels: np.ndarray,
    cluster_labels: dict[int, str],
    output_path: Path,
) -> None:
    fieldnames = list(rows[0].keys())
    if "cluster_id" not in fieldnames:
        fieldnames.append("cluster_id")
    if "cluster_label" not in fieldnames:
        fieldnames.append("cluster_label")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row, label in zip(rows, labels):
            row["cluster_id"] = str(int(label))
            row["cluster_label"] = cluster_labels.get(int(label), "Unknown")
            writer.writerow(row)

    print(f"\nSaved clustered data to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cluster cold outreach data and produce evaluation metrics")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-cluster-size", type=int, default=15)
    parser.add_argument("--min-samples", type=int, default=5)
    parser.add_argument("--recompute", action="store_true", help="Force recompute embeddings")
    args = parser.parse_args()

    input_path: Path = args.input
    output_path: Path = args.output

    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    rows = load_rows(input_path)
    print(f"Loaded {len(rows)} rows from {input_path}")

    texts = [build_text(row) for row in rows]
    embeddings = get_embeddings(texts, recompute=args.recompute)
    labels = run_hdbscan(embeddings, args.min_cluster_size, args.min_samples)

    cluster_labels = print_report(rows, labels, embeddings)
    save_output(rows, labels, cluster_labels, output_path)


if __name__ == "__main__":
    main()
