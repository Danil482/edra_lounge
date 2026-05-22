"""HDBSCAN clustering over episode summary embeddings + UMAP projection for UI.

Re-cluster on every N new episodes (N = settings.recluster_every).

Heavy dependencies (`sentence_transformers`, `hdbscan`, `umap`) are imported
lazily inside the relevant function bodies so unrelated unit tests don't pay
the import cost.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from backend.config import settings

if TYPE_CHECKING:
    from backend import schemas


_embedder = None
_LOCAL_MODEL_PATH = Path(__file__).parent.parent / "models" / "all-MiniLM-L6-v2"


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        model_path = str(_LOCAL_MODEL_PATH) if _LOCAL_MODEL_PATH.exists() else settings.embedding_model
        _embedder = SentenceTransformer(model_path)
    return _embedder


def preload_embedder() -> bool:
    """Eagerly load the MiniLM model. Returns True on success, False if unavailable."""
    try:
        _get_embedder()
        return True
    except Exception:  # noqa: BLE001
        return False


def embed(texts: list[str]) -> list[list[float]]:
    model = _get_embedder()
    vecs = model.encode(texts, show_progress_bar=False)
    return vecs.tolist()


def cluster_episodes(
    episodes: "list[schemas.Episode]",
) -> dict[int, list[str]]:
    """Run HDBSCAN. Returns {label: [episode_id, ...]}. Label -1 (noise) dropped."""
    if len(episodes) < settings.n_min:
        return {}

    import hdbscan  # type: ignore[import-untyped]

    X = np.array([ep.summary_embedding for ep in episodes])
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=settings.n_min,
        min_samples=max(2, settings.n_min // 2),
    )
    labels = clusterer.fit_predict(X)

    out: dict[int, list[str]] = {}
    for ep, label in zip(episodes, labels):
        if label == -1:
            continue
        out.setdefault(int(label), []).append(ep.id)
    return out


def project_umap(embeddings: list[list[float]]) -> list[tuple[float, float]]:
    """Project embeddings to 2D for cluster visualisation panel."""
    if len(embeddings) < 4:
        return [(0.0, 0.0)] * len(embeddings)

    import umap  # type: ignore[import-untyped]

    reducer = umap.UMAP(n_components=2, random_state=settings.rng_seed)
    coords = reducer.fit_transform(np.array(embeddings))
    return [(float(x), float(y)) for x, y in coords]


def success_ratio(episodes: "list[schemas.Episode]") -> float:
    """Cluster success metric per TASK.md §4.5: accepted / (accepted + rejected).

    The 'exploring' and 'abandoned' outcomes are excluded — neither a clean
    win nor a clean loss for the rule.
    """
    if not episodes:
        return 0.0
    accepted = sum(1 for ep in episodes if ep.outcome == "accepted")
    rejected = sum(1 for ep in episodes if ep.outcome == "rejected")
    denom = accepted + rejected
    if denom == 0:
        return 0.0
    return accepted / denom
