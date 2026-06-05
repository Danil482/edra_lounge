"""Prequential (test-then-train) simulation — Level 3 evaluation.

Tests whether EDRA learns cluster-conditional strategies over time.
Protocol from Gama et al. 2013: sort chronologically, split into batches,
for each batch TEST current policy then TRAIN on it.

Four policies: pi_uniform, pi_edra (adaptive), pi_linucb (contextual bandit), pi_oracle.
Evaluation via self-normalized IPS (Swaminathan & Joachims 2015) per batch.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.preprocessing import LabelEncoder

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATASET_CSV = DATA_DIR / "dataset_final.csv"
UMAP_PATH = DATA_DIR / "umap_profiles.npy"

DEFAULT_VIZ = DATA_DIR / "learning_curve.html"

WINDOW_SIZE = 60
WINDOW_STEP = 20
LINUCB_ALPHA = 0.5
MIN_OBS_PER_CLUSTER = 3
PROPENSITY_CLIP = 0.02
IW_CAP = 10.0
MIN_MATCHES = 3


def load_data() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str], list[str]]:
    with open(DATASET_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    X_umap_all = np.load(UMAP_PATH)
    assert X_umap_all.shape[0] == len(rows), (
        f"UMAP rows ({X_umap_all.shape[0]}) != CSV rows ({len(rows)})"
    )

    order = sorted(range(len(rows)), key=lambda i: rows[i]["outreach_timestamp"])
    rows = [rows[i] for i in order]
    X_umap = X_umap_all[order]

    strategies = sorted(set(r["strategy"] for r in rows))
    action_encoder = LabelEncoder()
    action_encoder.fit(strategies)

    actions = action_encoder.transform([r["strategy"] for r in rows])
    rewards = np.array([1.0 if r["outcome"] == "reply" else 0.0 for r in rows])
    cluster_ids = np.array([int(r["cluster_id"]) for r in rows])
    timestamps = [r["outreach_timestamp"] for r in rows]

    return X_umap, actions, rewards, cluster_ids, list(action_encoder.classes_), timestamps


def sliding_windows(n: int, window: int, step: int) -> list[tuple[int, int]]:
    windows = []
    start = 0
    while start + window <= n:
        windows.append((start, start + window))
        start += step
    if start < n and start + window > n:
        windows.append((start, n))
    return windows


def compute_global_propensity(actions: np.ndarray, n_actions: int) -> np.ndarray:
    counts = np.zeros(n_actions)
    for a in actions:
        counts[a] += 1
    props = counts / len(actions)
    return np.clip(props, PROPENSITY_CLIP, None)


def snips_estimate(
    policy_actions: np.ndarray,
    actual_actions: np.ndarray,
    rewards: np.ndarray,
    propensity: np.ndarray,
) -> tuple[float, int]:
    """Self-normalized IPS. Returns (estimate, n_matches).

    Returns NaN when fewer than MIN_MATCHES rows match.
    """
    n = len(rewards)
    if n == 0:
        return float("nan"), 0

    weighted_reward = 0.0
    weight_sum = 0.0
    n_matches = 0

    for i in range(n):
        a_policy = int(policy_actions[i])
        a_actual = int(actual_actions[i])
        if a_policy != a_actual:
            continue
        n_matches += 1
        iw = min(1.0 / propensity[a_actual], IW_CAP)
        weighted_reward += rewards[i] * iw
        weight_sum += iw

    if n_matches < MIN_MATCHES:
        return float("nan"), n_matches

    return weighted_reward / weight_sum, n_matches


class UniformPolicy:
    def __init__(self, actions: np.ndarray):
        self.action = int(np.bincount(actions).argmax())

    def predict(self, X: np.ndarray, cluster_ids: np.ndarray) -> np.ndarray:
        return np.full(len(X), self.action)

    def update(self, X: np.ndarray, actions: np.ndarray, rewards: np.ndarray, cluster_ids: np.ndarray) -> None:
        pass


class OraclePolicy:
    def __init__(
        self,
        all_actions: np.ndarray,
        all_rewards: np.ndarray,
        all_cluster_ids: np.ndarray,
        n_actions: int,
    ):
        self.cluster_best: dict[int, int] = {}
        global_best = self._global_best(all_actions, all_rewards, n_actions)

        for cid in sorted(set(all_cluster_ids)):
            mask = all_cluster_ids == cid
            best_rate = -1.0
            best_action = global_best

            for a_idx in range(n_actions):
                a_mask = mask & (all_actions == a_idx)
                if a_mask.sum() < MIN_OBS_PER_CLUSTER:
                    continue
                rate = all_rewards[a_mask].mean()
                if rate > best_rate:
                    best_rate = rate
                    best_action = a_idx

            self.cluster_best[int(cid)] = best_action

    @staticmethod
    def _global_best(actions: np.ndarray, rewards: np.ndarray, n_actions: int) -> int:
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

    def predict(self, X: np.ndarray, cluster_ids: np.ndarray) -> np.ndarray:
        return np.array([self.cluster_best.get(int(c), 0) for c in cluster_ids])

    def update(self, X: np.ndarray, actions: np.ndarray, rewards: np.ndarray, cluster_ids: np.ndarray) -> None:
        pass


class EdraPolicy:
    def __init__(self, n_actions: int):
        self.n_actions = n_actions
        self.seen_actions: list[int] = []
        self.seen_rewards: list[float] = []
        self.seen_clusters: list[int] = []
        self.cluster_best: dict[int, int] = {}
        self.global_best: int = 0

    def predict(self, X: np.ndarray, cluster_ids: np.ndarray) -> np.ndarray:
        if not self.seen_actions:
            return np.full(len(X), self.global_best)
        return np.array([self.cluster_best.get(int(c), self.global_best) for c in cluster_ids])

    def update(self, X: np.ndarray, actions: np.ndarray, rewards: np.ndarray, cluster_ids: np.ndarray) -> None:
        self.seen_actions.extend(actions.tolist())
        self.seen_rewards.extend(rewards.tolist())
        self.seen_clusters.extend(cluster_ids.tolist())

        all_a = np.array(self.seen_actions)
        all_r = np.array(self.seen_rewards)
        all_c = np.array(self.seen_clusters)

        self.global_best = self._compute_global_best(all_a, all_r)
        self.cluster_best = self._compute_cluster_best(all_a, all_r, all_c)

    def _compute_global_best(self, actions: np.ndarray, rewards: np.ndarray) -> int:
        best_rate = -1.0
        best_action = 0
        for a in range(self.n_actions):
            mask = actions == a
            if mask.sum() == 0:
                continue
            rate = rewards[mask].mean()
            if rate > best_rate:
                best_rate = rate
                best_action = a
        return best_action

    def _compute_cluster_best(
        self, actions: np.ndarray, rewards: np.ndarray, cluster_ids: np.ndarray,
    ) -> dict[int, int]:
        result: dict[int, int] = {}
        for cid in sorted(set(cluster_ids)):
            mask = cluster_ids == cid
            best_rate = -1.0
            best_action = self.global_best

            for a_idx in range(self.n_actions):
                a_mask = mask & (actions == a_idx)
                if a_mask.sum() < MIN_OBS_PER_CLUSTER:
                    continue
                rate = rewards[a_mask].mean()
                if rate > best_rate:
                    best_rate = rate
                    best_action = a_idx

            result[int(cid)] = best_action
        return result


class LinUCBPolicy:
    def __init__(self, d: int, n_actions: int, alpha: float = LINUCB_ALPHA):
        self.d = d
        self.n_actions = n_actions
        self.alpha = alpha
        self.A = [np.eye(d) for _ in range(n_actions)]
        self.b = [np.zeros(d) for _ in range(n_actions)]

    def predict(self, X: np.ndarray, cluster_ids: np.ndarray) -> np.ndarray:
        n = X.shape[0]
        chosen = np.zeros(n, dtype=int)

        A_inv = [np.linalg.inv(self.A[a]) for a in range(self.n_actions)]
        theta = [A_inv[a] @ self.b[a] for a in range(self.n_actions)]

        for i in range(n):
            x = X[i]
            best_p = -np.inf
            best_a = 0
            for a in range(self.n_actions):
                p = theta[a] @ x + self.alpha * np.sqrt(x @ A_inv[a] @ x)
                if p > best_p:
                    best_p = p
                    best_a = a
            chosen[i] = best_a

        return chosen

    def update(self, X: np.ndarray, actions: np.ndarray, rewards: np.ndarray, cluster_ids: np.ndarray) -> None:
        for i in range(len(actions)):
            a = int(actions[i])
            x = X[i]
            r = rewards[i]
            self.A[a] += np.outer(x, x)
            self.b[a] += r * x


def format_ts(ts: str) -> str:
    return ts[:7] if ts else "?"


def nanmean(vals: list[float]) -> float:
    valid = [v for v in vals if not np.isnan(v)]
    return np.mean(valid) if valid else float("nan")


POLICY_COLORS = {
    "pi_uniform": "#FFFFFF",
    "pi_edra": "#CC0000",
    "pi_linucb": "#4FC3F7",
    "pi_oracle": "#4CAF50",
}


def generate_html(
    results: dict[str, list[float]],
    policy_names: list[str],
    batch_periods: list[str],
    output_path: Path,
) -> None:
    line_styles = {
        "pi_uniform": {"color": "#FFFFFF", "width": 2, "dash": [], "radius": 6},
        "pi_edra":    {"color": "#CC0000", "width": 3, "dash": [], "radius": 8},
        "pi_linucb":  {"color": "#4FC3F7", "width": 2, "dash": [8, 4], "radius": 6},
        "pi_oracle":  {"color": "#4CAF50", "width": 2, "dash": [3, 4], "radius": 6},
    }

    viz_policies = {"pi_uniform", "pi_edra"}
    series = []
    for name in policy_names:
        if name not in viz_policies:
            continue
        vals = results[name]
        avg = nanmean(vals)
        points = [None if np.isnan(v) else round(v, 4) for v in vals]
        style = line_styles.get(name, {"color": "#FFFFFF", "width": 2, "dash": [], "radius": 6})
        series.append({
            "name": name,
            "color": style["color"],
            "lineWidth": style["width"],
            "dash": style["dash"],
            "radius": style["radius"],
            "values": points,
            "avg": None if np.isnan(avg) else round(avg, 4),
        })

    period_labels = []
    for p in batch_periods:
        parts = p.split("->")
        period_labels.append(parts[-1].strip() if len(parts) == 2 else p)

    viz_data = json.dumps({"series": series, "periods": batch_periods, "periodLabels": period_labels})

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EDRA Prequential Learning Curve</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0A0A0A;
    color: #E0E0E0;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    padding: 24px;
    display: flex;
    flex-direction: column;
    align-items: center;
}}
h1 {{
    font-size: 1.4rem;
    color: #FFFFFF;
    margin-bottom: 4px;
}}
.subtitle {{
    font-size: 0.82rem;
    color: #888;
    margin-bottom: 24px;
}}
.chart-container {{
    background: #141414;
    border: 1px solid #2A2A2A;
    border-radius: 8px;
    padding: 20px;
    width: 100%;
    max-width: 960px;
    position: relative;
}}
canvas {{
    display: block;
    width: 100%;
    height: 380px;
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
    max-width: 280px;
    line-height: 1.6;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
}}
</style>
</head>
<body>

<h1>EDRA Prequential Learning Curve</h1>
<p class="subtitle">Self-Normalized IPS per batch (Swaminathan &amp; Joachims 2015)</p>

<div class="chart-container">
    <canvas id="chart"></canvas>
    <div class="tooltip" id="tooltip"></div>
</div>

<script>
const DATA = {viz_data};

const PAD_LEFT = 72;
const PAD_RIGHT = 24;
const PAD_TOP = 24;
const PAD_BOTTOM = 52;
const BASELINE_Y = 0.53;

let boundListeners = false;

function render() {{
    const canvas = document.getElementById('chart');
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);

    const plotW = w - PAD_LEFT - PAD_RIGHT;
    const plotH = h - PAD_TOP - PAD_BOTTOM;
    const nBatches = DATA.periods.length;

    const yMin = 0.0;
    const yMax = 1.0;
    const yRange = 1.0;

    function toX(i) {{ return PAD_LEFT + (i / (nBatches - 1)) * plotW; }}
    function toY(v) {{ return PAD_TOP + (1 - (v - yMin) / yRange) * plotH; }}

    ctx.fillStyle = '#141414';
    ctx.fillRect(0, 0, w, h);

    // --- horizontal grid at 0.2 steps ---
    ctx.setLineDash([]);
    ctx.font = '11px Segoe UI, system-ui, sans-serif';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    const gridLevels = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0];
    gridLevels.forEach(v => {{
        const y = toY(v);
        ctx.strokeStyle = '#2A2A2A';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(PAD_LEFT, y);
        ctx.lineTo(w - PAD_RIGHT, y);
        ctx.stroke();
        ctx.fillStyle = '#888';
        ctx.fillText(v.toFixed(1), PAD_LEFT - 10, y);
    }});

    // --- baseline reply rate ---
    const baseY = toY(BASELINE_Y);
    ctx.setLineDash([6, 4]);
    ctx.strokeStyle = '#666';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(PAD_LEFT, baseY);
    ctx.lineTo(w - PAD_RIGHT, baseY);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = '#777';
    ctx.font = '10px Segoe UI, system-ui, sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'bottom';
    ctx.fillText('baseline reply rate (0.53)', PAD_LEFT + 4, baseY - 3);

    // --- x-axis: batch numbers + period labels ---
    ctx.font = '11px Segoe UI, system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillStyle = '#888';
    for (let i = 0; i < nBatches; i++) {{
        const x = toX(i);
        ctx.textBaseline = 'top';
        ctx.fillStyle = '#CCC';
        ctx.fillText(String(i + 1), x, h - PAD_BOTTOM + 6);
        ctx.fillStyle = '#666';
        ctx.font = '9px Segoe UI, system-ui, sans-serif';
        ctx.fillText(DATA.periodLabels[i] || '', x, h - PAD_BOTTOM + 20);
        ctx.font = '11px Segoe UI, system-ui, sans-serif';
    }}

    // --- axis labels ---
    ctx.fillStyle = '#888';
    ctx.font = '11px Segoe UI, system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillText('Batch', PAD_LEFT + plotW / 2, h - 6);

    ctx.textAlign = 'left';
    ctx.textBaseline = 'bottom';
    ctx.fillStyle = '#888';
    ctx.fillText('V_SNIPS', 4, PAD_TOP - 4);

    // --- draw lines ---
    DATA.series.forEach(s => {{
        ctx.strokeStyle = s.color;
        ctx.lineWidth = s.lineWidth;
        ctx.setLineDash(s.dash);

        let segments = [];
        let current = [];
        for (let i = 0; i < nBatches; i++) {{
            if (s.values[i] !== null) {{
                current.push(i);
            }} else {{
                if (current.length > 0) {{ segments.push(current); current = []; }}
            }}
        }}
        if (current.length > 0) segments.push(current);

        segments.forEach(seg => {{
            ctx.beginPath();
            for (let j = 0; j < seg.length; j++) {{
                const x = toX(seg[j]);
                const y = toY(s.values[seg[j]]);
                if (j === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }}
            ctx.stroke();
        }});

        ctx.setLineDash([]);

        // --- data points (circles) ---
        for (let i = 0; i < nBatches; i++) {{
            if (s.values[i] !== null) {{
                const x = toX(i);
                const y = toY(s.values[i]);
                ctx.beginPath();
                ctx.arc(x, y, s.radius / 2, 0, Math.PI * 2);
                ctx.fillStyle = s.color;
                ctx.fill();
                ctx.strokeStyle = '#141414';
                ctx.lineWidth = 1.5;
                ctx.stroke();
            }} else {{
                // NaN marker: small "x" at mid-chart height
                const x = toX(i);
                const y = toY(0.5);
                const sz = 4;
                ctx.strokeStyle = s.color + '4D';
                ctx.lineWidth = 1.5;
                ctx.beginPath();
                ctx.moveTo(x - sz, y - sz);
                ctx.lineTo(x + sz, y + sz);
                ctx.stroke();
                ctx.beginPath();
                ctx.moveTo(x + sz, y - sz);
                ctx.lineTo(x - sz, y + sz);
                ctx.stroke();
            }}
        }}
    }});

    // --- in-chart legend (top-right) ---
    const legendX = w - PAD_RIGHT - 10;
    const legendLineH = 18;
    const legendPad = 10;
    const legendH = DATA.series.length * legendLineH + legendPad * 2;
    const legendW = 210;
    const lx = legendX - legendW;
    const ly = PAD_TOP + 8;

    ctx.fillStyle = 'rgba(20, 20, 20, 0.85)';
    ctx.strokeStyle = '#2A2A2A';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(lx, ly, legendW, legendH, 4);
    ctx.fill();
    ctx.stroke();

    ctx.font = '11px Segoe UI, system-ui, sans-serif';
    ctx.textBaseline = 'middle';
    DATA.series.forEach((s, idx) => {{
        const ey = ly + legendPad + idx * legendLineH + legendLineH / 2;
        const lineStartX = lx + 10;
        const lineEndX = lx + 32;

        ctx.strokeStyle = s.color;
        ctx.lineWidth = s.lineWidth;
        ctx.setLineDash(s.dash);
        ctx.beginPath();
        ctx.moveTo(lineStartX, ey);
        ctx.lineTo(lineEndX, ey);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.beginPath();
        ctx.arc((lineStartX + lineEndX) / 2, ey, 2.5, 0, Math.PI * 2);
        ctx.fillStyle = s.color;
        ctx.fill();

        ctx.textAlign = 'left';
        ctx.fillStyle = '#E0E0E0';
        ctx.fillText(s.name, lx + 38, ey);

        const avgStr = s.avg !== null ? s.avg.toFixed(3) : 'N/A';
        ctx.textAlign = 'right';
        ctx.fillStyle = '#888';
        ctx.fillText('avg ' + avgStr, lx + legendW - 10, ey);
    }});

    // --- tooltip on hover ---
    if (!boundListeners) {{
        boundListeners = true;

        const tooltip = document.getElementById('tooltip');

        canvas.addEventListener('mousemove', function(e) {{
            const rect = canvas.getBoundingClientRect();
            const scaleX = w / rect.width;
            const mx = (e.clientX - rect.left) * scaleX;

            let closestDist = 30;
            let closestBatch = -1;

            for (let i = 0; i < nBatches; i++) {{
                const x = toX(i);
                const dx = Math.abs(mx - x);
                if (dx < closestDist) {{
                    closestDist = dx;
                    closestBatch = i;
                }}
            }}

            if (closestBatch >= 0) {{
                let html = '<div style="color:#FFF;font-weight:600;margin-bottom:4px">'
                    + 'Batch ' + (closestBatch + 1) + '</div>'
                    + '<div style="color:#888;margin-bottom:6px;font-size:0.72rem">'
                    + DATA.periods[closestBatch] + '</div>';

                DATA.series.forEach(s => {{
                    const v = s.values[closestBatch];
                    const vStr = v !== null ? v.toFixed(4) : 'NaN';
                    const opacity = v !== null ? '1' : '0.4';
                    html += '<div style="color:' + s.color + ';opacity:' + opacity + '">'
                        + s.name + ': ' + vStr + '</div>';
                }});

                tooltip.innerHTML = html;
                tooltip.style.display = 'block';

                const containerRect = canvas.parentElement.getBoundingClientRect();
                let left = e.clientX - containerRect.left + 14;
                let top = e.clientY - containerRect.top - 10;
                if (left + 280 > containerRect.width) left = left - 294;
                if (top < 0) top = 4;
                tooltip.style.left = left + 'px';
                tooltip.style.top = top + 'px';
            }} else {{
                tooltip.style.display = 'none';
            }}
        }});

        canvas.addEventListener('mouseleave', function() {{
            tooltip.style.display = 'none';
        }});
    }}
}}

render();
window.addEventListener('resize', render);
</script>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")
    print(f"\nSaved learning curve to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prequential simulation — Level 3 evaluation")
    parser.add_argument("--viz", type=Path, default=DEFAULT_VIZ, help="Output path for learning curve HTML")
    args = parser.parse_args()

    print("Loading data...")
    X_umap, actions, rewards, cluster_ids, strategy_names, timestamps = load_data()
    n = len(rewards)
    n_actions = len(strategy_names)
    d = X_umap.shape[1]

    print(f"  {n} rows, {n_actions} strategies, {d}d context")
    print(f"  Time range: {timestamps[0][:10]} to {timestamps[-1][:10]}")
    print(f"  Overall reply rate: {rewards.mean():.3f}")
    print(f"  Clusters: {sorted(set(cluster_ids.tolist()))}")

    windows = sliding_windows(n, WINDOW_SIZE, WINDOW_STEP)
    n_windows = len(windows)

    oracle = OraclePolicy(actions, rewards, cluster_ids, n_actions)
    edra = EdraPolicy(n_actions)
    linucb = LinUCBPolicy(d, n_actions, alpha=LINUCB_ALPHA)
    uniform = UniformPolicy(actions)

    policies = [
        ("pi_uniform", uniform),
        ("pi_edra", edra),
        ("pi_linucb", linucb),
        ("pi_oracle", oracle),
    ]

    results: dict[str, list[float]] = {name: [] for name, _ in policies}
    match_counts: dict[str, list[int]] = {name: [] for name, _ in policies}
    batch_periods: list[str] = []
    trained_up_to = 0

    print(f"\n{'='*100}")
    print(f"  PREQUENTIAL SIMULATION — {n_windows} sliding windows (size={WINDOW_SIZE}, step={WINDOW_STEP}), SNIPS evaluation")
    print(f"  Self-Normalized IPS (Swaminathan & Joachims 2015), IW cap={IW_CAP:.0f}, min matches={MIN_MATCHES}")
    print(f"{'='*100}")

    col_w = 14
    print(f"\n  {'Win':>5}  {'Period':<25} {'n':>4}", end="")
    for name, _ in policies:
        print(f"  {name:>{col_w}}", end="")
    print()
    print(f"  {'-'*5}  {'-'*25} {'-'*4}", end="")
    for _ in policies:
        print(f"  {'-'*col_w}", end="")
    print()

    for win_idx, (start, end) in enumerate(windows):
        if start > trained_up_to:
            train_X = X_umap[trained_up_to:start]
            train_actions = actions[trained_up_to:start]
            train_rewards = rewards[trained_up_to:start]
            train_clusters = cluster_ids[trained_up_to:start]
            for name, policy in policies:
                policy.update(train_X, train_actions, train_rewards, train_clusters)
            trained_up_to = start

        win_X = X_umap[start:end]
        win_actions = actions[start:end]
        win_rewards = rewards[start:end]
        win_clusters = cluster_ids[start:end]
        win_ts = timestamps[start:end]
        win_n = end - start

        period = f"{format_ts(win_ts[0])}->{format_ts(win_ts[-1])}"
        batch_periods.append(period)

        if trained_up_to == 0:
            propensity = np.full(n_actions, 1.0 / n_actions)
        else:
            propensity = compute_global_propensity(actions[:trained_up_to], n_actions)

        batch_results = []
        batch_matches = []
        for name, policy in policies:
            predicted = policy.predict(win_X, win_clusters)
            v, n_match = snips_estimate(predicted, win_actions, win_rewards, propensity)
            results[name].append(v)
            match_counts[name].append(n_match)
            batch_results.append(v)
            batch_matches.append(n_match)

        print(f"  {win_idx+1:>5}  {period:<25} {win_n:>4}", end="")
        for v, m in zip(batch_results, batch_matches):
            if np.isnan(v):
                cell = f"  n/a({m})"
            else:
                cell = f"{v:.3f}({m})"
            print(f"  {cell:>{col_w}}", end="")
        print()

    # --- Summary ---
    print(f"\n{'='*100}")
    print(f"  SUMMARY (NaN batches excluded from averages)")
    print(f"{'='*100}")

    print(f"\n  {'Policy':<14} {'Avg V':>8} {'Valid':>6} {'1st half':>10} {'2nd half':>10} {'Trend':>14}")
    print(f"  {'-'*14} {'-'*8} {'-'*6} {'-'*10} {'-'*10} {'-'*14}")

    half = n_windows // 2

    for name, _ in policies:
        vals = results[name]
        avg = nanmean(vals)
        n_valid = sum(1 for v in vals if not np.isnan(v))
        first_half = nanmean(vals[:half])
        second_half = nanmean(vals[half:])

        if np.isnan(first_half) or np.isnan(second_half):
            trend = "N/A"
        else:
            delta = second_half - first_half
            trend = f"{delta:+.4f}"
            if delta > 0.01:
                trend += " UP"
            elif delta < -0.01:
                trend += " DOWN"
            else:
                trend += " FLAT"

        avg_str = f"{avg:.4f}" if not np.isnan(avg) else "N/A"
        fh_str = f"{first_half:.4f}" if not np.isnan(first_half) else "N/A"
        sh_str = f"{second_half:.4f}" if not np.isnan(second_half) else "N/A"
        print(f"  {name:<14} {avg_str:>8} {n_valid:>4}/8 {fh_str:>10} {sh_str:>10} {trend:>14}")

    # --- Verdict ---
    print(f"\n{'='*100}")
    print(f"  VERDICT")
    print(f"{'='*100}")

    edra_vals = results["pi_edra"]
    linucb_vals = results["pi_linucb"]
    uniform_vals = results["pi_uniform"]
    oracle_vals = results["pi_oracle"]

    edra_avg = nanmean(edra_vals)
    linucb_avg = nanmean(linucb_vals)
    uniform_avg = nanmean(uniform_vals)
    oracle_avg = nanmean(oracle_vals)

    edra_first = nanmean(edra_vals[:half])
    edra_second = nanmean(edra_vals[half:])

    print(f"\n  Does EDRA learn?")
    if np.isnan(edra_first) or np.isnan(edra_second):
        print(f"    INSUFFICIENT DATA — too few matching batches for trend analysis.")
    else:
        edra_improves = edra_second > edra_first
        print(f"    1st-half avg: {edra_first:.4f}")
        print(f"    2nd-half avg: {edra_second:.4f}")
        if edra_improves:
            print(f"    YES — V improves by {edra_second - edra_first:+.4f} from first to second half.")
        else:
            print(f"    NO — V does not improve ({edra_second - edra_first:+.4f}).")

    print(f"\n  Is EDRA competitive with LinUCB?")
    if np.isnan(edra_avg) or np.isnan(linucb_avg):
        print(f"    INSUFFICIENT DATA for comparison.")
    else:
        print(f"    EDRA avg V:   {edra_avg:.4f}")
        print(f"    LinUCB avg V: {linucb_avg:.4f}")
        delta = edra_avg - linucb_avg
        if delta > 0.005:
            print(f"    EDRA outperforms LinUCB by {delta:+.4f}.")
        elif delta < -0.005:
            print(f"    LinUCB outperforms EDRA by {-delta:+.4f}.")
        else:
            print(f"    Roughly tied (delta={delta:+.4f}).")

    print(f"\n  Policy ranking (avg V across valid batches):")
    ranking = sorted(
        [(name, nanmean(results[name])) for name, _ in policies],
        key=lambda x: x[1] if not np.isnan(x[1]) else -1,
        reverse=True,
    )
    for rank, (name, avg) in enumerate(ranking, 1):
        marker = ""
        if name == "pi_oracle":
            marker = " (upper bound)"
        elif name == "pi_uniform":
            marker = " (baseline)"
        avg_str = f"{avg:.4f}" if not np.isnan(avg) else "N/A"
        n_valid = sum(1 for v in results[name] if not np.isnan(v))
        print(f"    {rank}. {name:<14} {avg_str}  ({n_valid}/{n_windows} valid windows){marker}")

    if not np.isnan(edra_avg) and not np.isnan(uniform_avg):
        gap_to_uniform = edra_avg - uniform_avg
        print(f"\n  EDRA gap above uniform:  {gap_to_uniform:+.4f}")
    if not np.isnan(edra_avg) and not np.isnan(oracle_avg):
        gap_to_oracle = oracle_avg - edra_avg
        print(f"  EDRA gap below oracle:  {gap_to_oracle:+.4f}")

    policy_names = [name for name, _ in policies]
    generate_html(results, policy_names, batch_periods, args.viz)


if __name__ == "__main__":
    main()
