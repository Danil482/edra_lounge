"""
Run the production clustering algorithm on Pipedrive evaluation data.

Production pipeline: MiniLM-384d with normalize_embeddings=True, HDBSCAN on
raw 384d vectors (no UMAP dimensionality reduction for clustering).
UMAP is used only for 2D visualization.

Usage:
    python -m evaluation.cluster_production
    python -m evaluation.cluster_production --min-cluster-size 10 --recompute
    python -m evaluation.cluster_production --viz evaluation/data/custom_viz.html
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.metrics import silhouette_score

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = Path(__file__).resolve().parent / "data" / "cold_outreach_clean.csv"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "data" / "clustered_production.csv"
EMBEDDINGS_CACHE = Path(__file__).resolve().parent / "data" / "embeddings_production.npy"
UMAP_VIZ_CACHE = Path(__file__).resolve().parent / "data" / "umap_viz_production.npy"
UMAP_CLUSTER_CACHE = Path(__file__).resolve().parent / "data" / "umap_cluster_production.npy"
DEFAULT_VIZ = Path(__file__).resolve().parent / "data" / "cluster_viz_production.html"
LOCAL_MODEL_PATH = PROJECT_ROOT / "backend" / "models" / "all-MiniLM-L6-v2"
_UMAP_N_COMPONENTS = 15


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_production_text(row: dict[str, str]) -> str:
    job = row.get("job_title", "").strip()
    org = row.get("organization", "").strip()
    labels = row.get("labels", "").strip()
    name = row.get("name", "").strip()

    seniority = "unknown seniority"
    for level, keywords in [
        ("C-level", ["ceo", "cmo", "cfo", "cto", "coo", "chief"]),
        ("Founder", ["founder", "co-founder"]),
        ("Partner", ["partner", "managing partner"]),
        ("Director", ["director", "vp", "vice president", "president"]),
        ("Manager", ["manager", "head", "lead"]),
        ("Specialist", ["specialist", "analyst", "executive", "coordinator", "associate", "officer"]),
    ]:
        if any(kw in job.lower() for kw in keywords):
            seniority = level
            break

    function = "general"
    for func, keywords in [
        ("marketing", ["marketing", "brand", "content", "social media", "creative"]),
        ("digital", ["digital", "online", "e-commerce", "ecommerce"]),
        ("sales", ["sales", "business development", "partnerships", "commercial"]),
        ("growth", ["growth", "acquisition", "performance"]),
        ("media", ["media", "advertising", "communications", "pr"]),
        ("product", ["product", "technology", "engineering", "data"]),
        ("strategy", ["strategy", "consulting", "analytics", "insights"]),
    ]:
        if any(kw in job.lower() for kw in keywords):
            function = func
            break

    parts = [f"{seniority} in {function}"]
    if org:
        parts.append(f"at {org}")
    if name:
        parts.append(f"name: {name}")
    if labels:
        parts.append(f"segment: {labels}")
    return ". ".join(parts)


def compute_embeddings(texts: list[str]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    model_path = str(LOCAL_MODEL_PATH) if LOCAL_MODEL_PATH.exists() else "all-MiniLM-L6-v2"
    model = SentenceTransformer(model_path)
    # normalize_embeddings=True matches production (backend/clustering/cluster.py:embed)
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=True)


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


def reduce_for_clustering(embeddings: np.ndarray, *, recompute: bool) -> np.ndarray:
    if not recompute and UMAP_CLUSTER_CACHE.exists():
        cached = np.load(UMAP_CLUSTER_CACHE)
        if cached.shape[0] == embeddings.shape[0]:
            print(f"Loaded cached UMAP-{_UMAP_N_COMPONENTS}d from {UMAP_CLUSTER_CACHE}")
            return cached

    from umap import UMAP

    reduced = UMAP(
        n_components=_UMAP_N_COMPONENTS, random_state=42, metric="cosine",
    ).fit_transform(embeddings)
    np.save(UMAP_CLUSTER_CACHE, reduced)
    print(f"Saved UMAP-{_UMAP_N_COMPONENTS}d to {UMAP_CLUSTER_CACHE} ({reduced.shape})")
    return reduced


def run_hdbscan(embeddings: np.ndarray, min_cluster_size: int, min_samples: int) -> np.ndarray:
    import hdbscan as _hdbscan

    clusterer = _hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
    )
    return clusterer.fit_predict(embeddings)


def umap_2d(embeddings: np.ndarray, *, recompute: bool) -> np.ndarray:
    """UMAP 2D projection for visualization only — clustering was done on 384d."""
    if not recompute and UMAP_VIZ_CACHE.exists():
        cached = np.load(UMAP_VIZ_CACHE)
        if cached.shape[0] == embeddings.shape[0]:
            print(f"Loaded cached UMAP-2D from {UMAP_VIZ_CACHE} ({cached.shape})")
            return cached
        print(f"UMAP-2D cache mismatch, recomputing...")

    from umap import UMAP

    coords = UMAP(n_components=2, random_state=42, metric="cosine").fit_transform(embeddings)
    np.save(UMAP_VIZ_CACHE, coords)
    print(f"Saved UMAP-2D to {UMAP_VIZ_CACHE} ({coords.shape})")
    return coords


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

    sil_score = None

    print("=== Production Clustering Report ===")
    print(f"Pipeline: MiniLM-384d (normalize=True) + UMAP-{_UMAP_N_COMPONENTS}d + HDBSCAN")
    print(f"Total samples: {total}")
    print(f"Clustered: {n_clustered} ({100 * n_clustered / total:.1f}%)")
    print(f"Noise: {n_noise} ({100 * n_noise / total:.1f}%)")
    print(f"Clusters found: {len(cluster_ids)}")

    if n_clustered > 1 and len(cluster_ids) > 1:
        mask = labels != -1
        sil_score = silhouette_score(embeddings[mask], labels[mask])
        print(f"Silhouette score: {sil_score:.3f} (on clustered samples only)")
    else:
        print("Silhouette score: N/A (not enough clusters)")

    sil_str = f"{sil_score:.3f}" if sil_score is not None else "N/A"
    print(f"\nComparison — Surrogate pipeline: silhouette=0.739, 6 clusters. "
          f"Production pipeline: silhouette={sil_str}, {len(cluster_ids)} clusters.")

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


def build_strategy_matrix(
    rows: list[dict[str, str]],
    labels: np.ndarray,
    cluster_labels: dict[int, str],
) -> dict:
    cluster_ids = sorted(set(labels))

    cluster_rows: dict[int, list[dict[str, str]]] = {}
    for row, label in zip(rows, labels):
        cluster_rows.setdefault(int(label), []).append(row)

    all_types = sorted({r["outreach_type"] for r in rows})

    matrix = []
    for otype in all_types:
        row_data = {"type": otype, "cells": {}}
        for cid in cluster_ids:
            c_rows = [r for r in cluster_rows.get(cid, []) if r["outreach_type"] == otype]
            if not c_rows:
                row_data["cells"][int(cid)] = None
            else:
                replies = sum(1 for r in c_rows if r["outcome"] == "reply")
                pct = replies / len(c_rows)
                row_data["cells"][int(cid)] = {
                    "replies": replies,
                    "total": len(c_rows),
                    "pct": pct,
                }
        matrix.append(row_data)

    col_headers = []
    for cid in cluster_ids:
        label_str = cluster_labels.get(int(cid), f"C{cid}")
        col_headers.append({"id": int(cid), "label": label_str})

    return {"columns": col_headers, "rows": matrix}


def build_viz_data(
    rows: list[dict[str, str]],
    labels: np.ndarray,
    coords_2d: np.ndarray,
    cluster_labels: dict[int, str],
    embeddings: np.ndarray,
) -> str:
    n_clustered = int(np.sum(labels != -1))
    cluster_ids = set(labels)
    cluster_ids.discard(-1)

    sil_score = None
    if n_clustered > 1 and len(cluster_ids) > 1:
        mask = labels != -1
        sil_score = float(silhouette_score(embeddings[mask], labels[mask]))

    points = []
    for i, (row, label) in enumerate(zip(rows, labels)):
        points.append({
            "x": float(coords_2d[i, 0]),
            "y": float(coords_2d[i, 1]),
            "cluster": int(label),
            "name": row.get("name", ""),
            "job_title": row.get("job_title", ""),
            "org": row.get("organization", ""),
            "outcome": row.get("outcome", ""),
            "label": cluster_labels.get(int(label), "Unknown"),
        })

    stats = {
        "total": len(rows),
        "clustered": n_clustered,
        "noise": len(rows) - n_clustered,
        "clustered_pct": round(100 * n_clustered / len(rows), 1),
        "n_clusters": len(cluster_ids),
        "silhouette": round(sil_score, 3) if sil_score is not None else None,
    }

    legend = []
    for cid in sorted(cluster_ids):
        count = int(np.sum(labels == cid))
        legend.append({
            "id": int(cid),
            "label": cluster_labels.get(int(cid), f"C{cid}"),
            "count": count,
        })
    noise_count = int(np.sum(labels == -1))
    if noise_count:
        legend.append({"id": -1, "label": "Noise", "count": noise_count})

    matrix = build_strategy_matrix(rows, labels, cluster_labels)

    return json.dumps({
        "points": points,
        "stats": stats,
        "legend": legend,
        "matrix": matrix,
    })


def generate_html(viz_data_json: str, output_path: Path) -> None:
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EDRA Production Clustering — Pipedrive Evaluation</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0A0A0A;
    color: #E0E0E0;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    padding: 20px;
}}
h1 {{
    font-size: 1.4rem;
    color: #FFFFFF;
    margin-bottom: 6px;
}}
.subtitle {{
    font-size: 0.85rem;
    color: #888;
    margin-bottom: 20px;
}}
.layout {{
    display: grid;
    grid-template-columns: 1fr 280px;
    grid-template-rows: auto 1fr auto;
    gap: 16px;
    max-width: 1400px;
    margin: 0 auto;
}}
.stats-panel {{
    grid-column: 1 / -1;
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
}}
.stat-card {{
    background: #141414;
    border: 1px solid #2A2A2A;
    border-radius: 8px;
    padding: 12px 20px;
    min-width: 140px;
}}
.stat-card .value {{
    font-size: 1.6rem;
    font-weight: 700;
    color: #FFFFFF;
}}
.stat-card .label {{
    font-size: 0.75rem;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 2px;
}}
.canvas-wrap {{
    grid-column: 1;
    grid-row: 2;
    background: #141414;
    border: 1px solid #2A2A2A;
    border-radius: 8px;
    padding: 12px;
    position: relative;
    min-height: 500px;
}}
.canvas-wrap canvas {{
    width: 100%;
    height: 100%;
    display: block;
}}
.legend-panel {{
    grid-column: 2;
    grid-row: 2;
    background: #141414;
    border: 1px solid #2A2A2A;
    border-radius: 8px;
    padding: 16px;
    overflow-y: auto;
    max-height: 600px;
}}
.legend-panel h3 {{
    font-size: 0.9rem;
    color: #FFFFFF;
    margin-bottom: 12px;
}}
.legend-item {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    font-size: 0.82rem;
}}
.legend-dot {{
    width: 12px;
    height: 12px;
    border-radius: 50%;
    flex-shrink: 0;
}}
.legend-count {{
    color: #888;
    margin-left: auto;
}}
.heatmap-section {{
    grid-column: 1 / -1;
    background: #141414;
    border: 1px solid #2A2A2A;
    border-radius: 8px;
    padding: 16px;
    overflow-x: auto;
}}
.heatmap-section h3 {{
    font-size: 0.9rem;
    color: #FFFFFF;
    margin-bottom: 12px;
}}
table.heatmap {{
    border-collapse: collapse;
    font-size: 0.8rem;
    width: 100%;
}}
table.heatmap th, table.heatmap td {{
    padding: 8px 12px;
    text-align: center;
    border: 1px solid #2A2A2A;
}}
table.heatmap th {{
    background: #1A1A1A;
    color: #CCC;
    font-weight: 600;
}}
table.heatmap td.empty {{
    color: #555;
}}
table.heatmap td .cell-detail {{
    font-size: 0.7rem;
    color: #999;
    display: block;
}}
.tooltip {{
    position: absolute;
    background: #1E1E1E;
    border: 1px solid #444;
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 0.78rem;
    pointer-events: none;
    display: none;
    z-index: 100;
    max-width: 300px;
    line-height: 1.5;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
}}
.tooltip .tt-name {{ color: #FFF; font-weight: 600; }}
.tooltip .tt-dim {{ color: #999; }}
.tooltip .tt-reply {{ color: #4CAF50; }}
.tooltip .tt-noreply {{ color: #F44336; }}
</style>
</head>
<body>

<h1>EDRA Production Clustering</h1>
<p class="subtitle">MiniLM-384d (normalized) + UMAP-15d + HDBSCAN — Pipedrive evaluation dataset (same pipeline as production)</p>

<div class="layout">
    <div class="stats-panel" id="stats"></div>
    <div class="canvas-wrap">
        <canvas id="scatter"></canvas>
        <div class="tooltip" id="tooltip"></div>
    </div>
    <div class="legend-panel" id="legend">
        <h3>Clusters</h3>
    </div>
    <div class="heatmap-section" id="heatmap-section">
        <h3>Strategy x Cluster Reply Rates</h3>
        <div id="heatmap"></div>
    </div>
</div>

<script>
const DATA = {viz_data_json};

const CLUSTER_COLORS = [
    '#4FC3F7', '#FF7043', '#66BB6A', '#AB47BC', '#FFA726',
    '#26C6DA', '#EF5350', '#8D6E63', '#78909C', '#D4E157',
    '#EC407A', '#7E57C2', '#29B6F6', '#FFCA28', '#26A69A',
    '#5C6BC0', '#FF8A65', '#9CCC65', '#BA68C8', '#42A5F5',
];
const NOISE_COLOR = '#444444';

function getColor(clusterId) {{
    if (clusterId === -1) return NOISE_COLOR;
    return CLUSTER_COLORS[clusterId % CLUSTER_COLORS.length];
}}

function renderStats() {{
    const s = DATA.stats;
    const container = document.getElementById('stats');
    const cards = [
        {{ value: s.total, label: 'Total samples' }},
        {{ value: s.clustered + ' (' + s.clustered_pct + '%)', label: 'Clustered' }},
        {{ value: s.noise, label: 'Noise' }},
        {{ value: s.n_clusters, label: 'Clusters' }},
        {{ value: s.silhouette !== null ? s.silhouette.toFixed(3) : 'N/A', label: 'Silhouette' }},
    ];
    container.innerHTML = cards.map(c =>
        '<div class="stat-card"><div class="value">' + c.value + '</div><div class="label">' + c.label + '</div></div>'
    ).join('');
}}

function renderLegend() {{
    const container = document.getElementById('legend');
    let html = '<h3>Clusters</h3>';
    DATA.legend.forEach(item => {{
        const color = getColor(item.id);
        const label = item.id === -1 ? 'Noise' : 'C' + item.id + ': ' + item.label;
        html += '<div class="legend-item">'
            + '<div class="legend-dot" style="background:' + color + '"></div>'
            + '<span>' + label + '</span>'
            + '<span class="legend-count">n=' + item.count + '</span>'
            + '</div>';
    }});
    container.innerHTML = html;
}}

function renderScatter() {{
    const canvas = document.getElementById('scatter');
    const wrap = canvas.parentElement;
    const dpr = window.devicePixelRatio || 1;
    const w = wrap.clientWidth - 24;
    const h = Math.max(wrap.clientHeight - 24, 400);
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);

    const pts = DATA.points;
    let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity;
    pts.forEach(p => {{
        if (p.x < xMin) xMin = p.x;
        if (p.x > xMax) xMax = p.x;
        if (p.y < yMin) yMin = p.y;
        if (p.y > yMax) yMax = p.y;
    }});

    const pad = 30;
    const xRange = xMax - xMin || 1;
    const yRange = yMax - yMin || 1;
    function toCanvasX(x) {{ return pad + (x - xMin) / xRange * (w - 2 * pad); }}
    function toCanvasY(y) {{ return pad + (y - yMin) / yRange * (h - 2 * pad); }}

    ctx.fillStyle = '#141414';
    ctx.fillRect(0, 0, w, h);

    const noise = pts.filter(p => p.cluster === -1);
    const clustered = pts.filter(p => p.cluster !== -1);

    noise.forEach(p => {{
        ctx.beginPath();
        ctx.arc(toCanvasX(p.x), toCanvasY(p.y), 2, 0, Math.PI * 2);
        ctx.fillStyle = NOISE_COLOR;
        ctx.globalAlpha = 0.4;
        ctx.fill();
    }});
    ctx.globalAlpha = 1.0;

    clustered.forEach(p => {{
        ctx.beginPath();
        ctx.arc(toCanvasX(p.x), toCanvasY(p.y), 4, 0, Math.PI * 2);
        ctx.fillStyle = getColor(p.cluster);
        ctx.globalAlpha = 0.8;
        ctx.fill();
    }});
    ctx.globalAlpha = 1.0;

    const tooltip = document.getElementById('tooltip');
    canvas.addEventListener('mousemove', function(e) {{
        const rect = canvas.getBoundingClientRect();
        const mx = (e.clientX - rect.left);
        const my = (e.clientY - rect.top);

        let closest = null;
        let closestDist = 100;
        pts.forEach(p => {{
            const cx = toCanvasX(p.x);
            const cy = toCanvasY(p.y);
            const d = Math.sqrt((mx - cx) ** 2 + (my - cy) ** 2);
            if (d < closestDist) {{
                closestDist = d;
                closest = p;
            }}
        }});

        if (closest && closestDist < 15) {{
            const outcomeClass = closest.outcome === 'reply' ? 'tt-reply' : 'tt-noreply';
            tooltip.innerHTML = '<div class="tt-name">' + escHtml(closest.name) + '</div>'
                + '<div class="tt-dim">' + escHtml(closest.job_title) + '</div>'
                + '<div class="tt-dim">' + escHtml(closest.org) + '</div>'
                + '<div>Cluster: ' + (closest.cluster === -1 ? 'Noise' : 'C' + closest.cluster + ' (' + escHtml(closest.label) + ')') + '</div>'
                + '<div class="' + outcomeClass + '">Outcome: ' + closest.outcome + '</div>';
            tooltip.style.display = 'block';
            tooltip.style.left = (e.clientX - wrap.getBoundingClientRect().left + 12) + 'px';
            tooltip.style.top = (e.clientY - wrap.getBoundingClientRect().top + 12) + 'px';
        }} else {{
            tooltip.style.display = 'none';
        }}
    }});

    canvas.addEventListener('mouseleave', function() {{
        tooltip.style.display = 'none';
    }});
}}

function escHtml(s) {{
    const d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
}}

function renderHeatmap() {{
    const m = DATA.matrix;
    const container = document.getElementById('heatmap');
    let html = '<table class="heatmap"><thead><tr><th>Strategy</th>';
    m.columns.forEach(c => {{
        const hdr = c.id === -1 ? 'Noise' : 'C' + c.id;
        html += '<th title="' + escHtml(c.label) + '">' + hdr + '</th>';
    }});
    html += '</tr></thead><tbody>';

    m.rows.forEach(row => {{
        html += '<tr><th>' + escHtml(row.type) + '</th>';
        m.columns.forEach(col => {{
            const cell = row.cells[col.id];
            if (cell === null || cell === undefined) {{
                html += '<td class="empty">--</td>';
            }} else {{
                const pct = Math.round(cell.pct * 100);
                const r = Math.round(255 * (1 - cell.pct));
                const g = Math.round(180 * cell.pct);
                const bg = 'rgba(' + r + ',' + g + ',50,0.35)';
                html += '<td style="background:' + bg + '">'
                    + pct + '%<span class="cell-detail">' + cell.replies + '/' + cell.total + '</span></td>';
            }}
        }});
        html += '</tr>';
    }});
    html += '</tbody></table>';
    container.innerHTML = html;
}}

renderStats();
renderLegend();
renderScatter();
renderHeatmap();

window.addEventListener('resize', renderScatter);
</script>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")
    print(f"Saved interactive visualization to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run production clustering algorithm on Pipedrive evaluation data"
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-cluster-size", type=int, default=8)
    parser.add_argument("--min-samples", type=int, default=4)
    parser.add_argument("--recompute", action="store_true", help="Force recompute embeddings and UMAP")
    parser.add_argument("--viz", type=Path, default=DEFAULT_VIZ)
    args = parser.parse_args()

    input_path: Path = args.input
    output_path: Path = args.output
    viz_path: Path = args.viz

    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    rows = load_rows(input_path)
    print(f"Loaded {len(rows)} rows from {input_path}")

    texts = [build_production_text(row) for row in rows]
    embeddings = get_embeddings(texts, recompute=args.recompute)
    print(f"Embedding shape: {embeddings.shape} (384d, normalized)")

    reduced = reduce_for_clustering(embeddings, recompute=args.recompute)
    labels = run_hdbscan(reduced, args.min_cluster_size, args.min_samples)
    cluster_labels = print_report(rows, labels, reduced)

    save_output(rows, labels, cluster_labels, output_path)

    print("\nComputing UMAP 2D projection for visualization...")
    coords_2d = umap_2d(embeddings, recompute=args.recompute)

    viz_json = build_viz_data(rows, labels, coords_2d, cluster_labels, reduced)
    generate_html(viz_json, viz_path)


if __name__ == "__main__":
    main()
