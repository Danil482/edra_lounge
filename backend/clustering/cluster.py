"""HDBSCAN clustering over episode summary embeddings + UMAP projection for UI.

Re-cluster on every N new episodes (N = settings.recluster_every).
"""

from typing import TYPE_CHECKING

import numpy as np

from backend.config import settings

if TYPE_CHECKING:
    from backend import schemas


_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer(settings.embedding_model)
    return _embedder


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

    import hdbscan

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

    import umap

    reducer = umap.UMAP(n_components=2, random_state=settings.rng_seed)
    coords = reducer.fit_transform(np.array(embeddings))
    return [(float(x), float(y)) for x, y in coords]


def success_ratio(episodes: "list[schemas.Episode]") -> float:
    if not episodes:
        return 0.0
    n_sat = sum(1 for ep in episodes if ep.outcome == "satisfied")
    return n_sat / len(episodes)
