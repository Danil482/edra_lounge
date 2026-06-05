"""GET /api/cluster-viz — 2D scatter plot data + nearest neighbors for the UI.

Returns UMAP projected coordinates for all clustered profiles, the current
visitor's position, and K nearest neighbors. The projection is cached and
recomputed only when the cluster set changes. Pre-computed coordinates from
seed_from_eval are loaded from data/viz_coords_2d.json when available.
"""

from __future__ import annotations

import json as _json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.db import get_session
from backend.memory import store
from backend.sessions.store import get_active_session

log = logging.getLogger(__name__)

_PRECOMPUTED_COORDS: dict[str, list[float]] | None = None
_PRECOMPUTED_PATH = Path("data/viz_coords_2d.json")


def _load_precomputed() -> dict[str, list[float]]:
    global _PRECOMPUTED_COORDS
    if _PRECOMPUTED_COORDS is None and _PRECOMPUTED_PATH.exists():
        _PRECOMPUTED_COORDS = _json.loads(_PRECOMPUTED_PATH.read_text(encoding="utf-8"))
        log.info("Loaded %d pre-computed 2D coords from %s", len(_PRECOMPUTED_COORDS), _PRECOMPUTED_PATH)
    return _PRECOMPUTED_COORDS or {}

router = APIRouter(prefix="/api", tags=["cluster-viz"])

ARCHETYPE_LABELS = {
    "arch_phd_nlp_introvert": "The Researcher",
    "arch_postdoc_cv_ambitious": "The Rising Star",
    "arch_tech_founder_applied": "The Founder",
    "arch_senior_prof_meta": "The Professor",
    "arch_industry_pm_pragmatic": "The Pragmatist",
    "arch_research_engineer_skeptic": "The Skeptic",
    "arch_vc_investor": "The Strategist",
    "arch_journalist_curious": "The Explorer",
}

CLUSTER_COLORS = [
    "#CC0000",  # brand red
    "#E8A23D",  # amber
    "#2FB7A8",  # teal
    "#6F8FE0",  # slate-blue
    "#C75FD6",  # magenta
    "#A7E05A",  # green
    "#E0C5A0",  # cream
    "#9AA0A8",  # grey
]

_cache: dict[str, Any] = {
    "fingerprint": None,
    "coords_2d": [],
    "profile_ids": [],
    "cluster_ids": [],
}


def _compute_fingerprint(clusters: list[schemas.Cluster]) -> str:
    parts = sorted(f"{c.id}:{c.size}:{len(c.profile_ids)}" for c in clusters)
    return "|".join(parts)


def _project_tsne(embeddings: np.ndarray) -> list[tuple[float, float]]:
    if len(embeddings) < 2:
        return [(0.5, 0.5)] * len(embeddings)

    from umap import UMAP

    reduced = UMAP(
        n_components=15,
        random_state=42,
        metric="cosine",
    ).fit_transform(embeddings)
    coords = UMAP(
        n_components=2,
        random_state=42,
        metric="euclidean",
    ).fit_transform(reduced)

    x_min, x_max = coords[:, 0].min(), coords[:, 0].max()
    y_min, y_max = coords[:, 1].min(), coords[:, 1].max()
    x_range = x_max - x_min if x_max > x_min else 1.0
    y_range = y_max - y_min if y_max > y_min else 1.0

    margin = 0.08
    normalized = []
    for x, y in coords:
        nx = margin + (1 - 2 * margin) * (x - x_min) / x_range
        ny = margin + (1 - 2 * margin) * (y - y_min) / y_range
        normalized.append((float(nx), float(ny)))
    return normalized


def _archetype_label(cluster_id: str, cluster_label: str) -> str:
    if cluster_id in ARCHETYPE_LABELS:
        return ARCHETYPE_LABELS[cluster_id]
    if cluster_label and cluster_label != cluster_id:
        words = cluster_label.split()
        if len(words) <= 3:
            return f"The {cluster_label}"
        return f"The {words[0]}"
    return "The Visitor"


def _cluster_color(idx: int) -> str:
    return CLUSTER_COLORS[idx % len(CLUSTER_COLORS)]


@router.get("/cluster-viz")
async def cluster_viz(
    session: AsyncSession = Depends(get_session),
    k: int = Query(default=7, ge=1, le=10),
):
    clusters = await store.list_clusters(session)
    if not clusters:
        return {
            "status": "cold_start",
            "points": [],
            "clusters": [],
            "current_visitor": None,
            "neighbors": [],
            "archetype_label": None,
        }

    profiles = await store.list_profiles(session)
    profiles_by_id = {p.id: p for p in profiles}

    embedded_profiles: list[schemas.Profile] = []
    for c in clusters:
        for pid in c.profile_ids:
            p = profiles_by_id.get(pid)
            if p and p.embedding and len(p.embedding) > 0:
                embedded_profiles.append(p)

    seen_ids: set[str] = set()
    unique_profiles: list[schemas.Profile] = []
    for p in embedded_profiles:
        if p.id not in seen_ids:
            seen_ids.add(p.id)
            unique_profiles.append(p)
    embedded_profiles = unique_profiles

    if not embedded_profiles:
        return {
            "status": "no_embeddings",
            "points": [],
            "clusters": [],
            "current_visitor": None,
            "neighbors": [],
            "archetype_label": None,
        }

    profile_cluster_map: dict[str, str] = {}
    for c in clusters:
        for pid in c.profile_ids:
            profile_cluster_map[pid] = c.id

    cluster_label_map = {c.id: c.label for c in clusters}
    cluster_ids_ordered = sorted({c.id for c in clusters})
    cluster_color_map = {cid: _cluster_color(i) for i, cid in enumerate(cluster_ids_ordered)}

    fingerprint = _compute_fingerprint(clusters)

    active_session = get_active_session()
    current_profile_id = active_session.profile.id if active_session else None
    current_has_embedding = False
    if current_profile_id:
        current_p = profiles_by_id.get(current_profile_id)
        if current_p and current_p.embedding:
            current_has_embedding = True

    need_reproject = (
        _cache["fingerprint"] != fingerprint
        or len(_cache["profile_ids"]) != len(embedded_profiles)
    )

    if need_reproject:
        precomputed = _load_precomputed()
        profile_ids = [p.id for p in embedded_profiles]
        embeddings_by_id = {p.id: p.embedding for p in embedded_profiles}

        coords: list[tuple[float, float]] = []
        missing_ids: list[int] = []
        for i, pid in enumerate(profile_ids):
            if pid in precomputed:
                c = precomputed[pid]
                coords.append((c[0], c[1]))
            else:
                coords.append((0.5, 0.5))
                missing_ids.append(i)

        if missing_ids and precomputed:
            known_embeddings = []
            known_coords = []
            for i, pid in enumerate(profile_ids):
                if pid in precomputed and embeddings_by_id.get(pid) is not None:
                    known_embeddings.append(embeddings_by_id[pid])
                    known_coords.append(coords[i])
            if known_embeddings:
                known_matrix = np.array(known_embeddings)
                known_coords_arr = np.array(known_coords)
                for idx in missing_ids:
                    emb = np.array(embeddings_by_id[profile_ids[idx]])
                    sims = known_matrix @ emb
                    top_k = np.argsort(sims)[-7:]
                    weights = sims[top_k]
                    weights = weights / (weights.sum() + 1e-9)
                    pos = (known_coords_arr[top_k] * weights[:, None]).sum(axis=0)
                    coords[idx] = (float(pos[0]), float(pos[1]))
            log.info("Pre-computed coords for %d profiles, interpolated %d new",
                     len(profile_ids) - len(missing_ids), len(missing_ids))
        elif not precomputed:
            t0 = time.monotonic()
            embeddings_matrix = np.array([p.embedding for p in embedded_profiles])
            coords = _project_tsne(embeddings_matrix)
            log.info("UMAP projection computed in %.1fms for %d profiles",
                     (time.monotonic() - t0) * 1000, len(embedded_profiles))
        else:
            log.info("Loaded pre-computed 2D coords for all %d profiles", len(profile_ids))

        arr = np.array(coords)
        margin = 0.05
        for dim in range(2):
            lo = np.percentile(arr[:, dim], 2)
            hi = np.percentile(arr[:, dim], 98)
            span = hi - lo if hi > lo else 1.0
            arr[:, dim] = margin + (1 - 2 * margin) * np.clip((arr[:, dim] - lo) / span, 0, 1)
        coords = [(float(arr[i, 0]), float(arr[i, 1])) for i in range(len(arr))]

        _cache["fingerprint"] = fingerprint
        _cache["coords_2d"] = coords
        _cache["profile_ids"] = profile_ids
        _cache["cluster_ids"] = [profile_cluster_map.get(p.id, "") for p in embedded_profiles]

    cluster_coords: dict[str, list[tuple[float, float]]] = {}
    for i, pid in enumerate(_cache["profile_ids"]):
        cid = _cache["cluster_ids"][i]
        cluster_coords.setdefault(cid, []).append(_cache["coords_2d"][i])

    points = []
    for cid, coord_list in cluster_coords.items():
        arr = np.array(coord_list)
        cx, cy = float(arr[:, 0].mean()), float(arr[:, 1].mean())
        points.append({
            "id": f"centroid:{cid}",
            "x": cx,
            "y": cy,
            "cluster_id": cid,
            "color": cluster_color_map.get(cid, "#777777"),
            "name": cluster_label_map.get(cid, cid),
            "role": f"n={len(coord_list)}",
            "is_current": False,
        })

    current_visitor_point = None
    current_cluster_id = None
    if active_session and current_profile_id and current_has_embedding:
        current_p = profiles_by_id[current_profile_id]
        cid = active_session.cluster_id or profile_cluster_map.get(current_profile_id, "")
        vx, vy = 0.5, 0.5
        if current_p.embedding and _cache["coords_2d"]:
            cur_vec = np.array(current_p.embedding)
            known_embs = []
            known_xy = []
            for i, pid in enumerate(_cache["profile_ids"]):
                p = profiles_by_id.get(pid)
                if p and p.embedding:
                    known_embs.append(p.embedding)
                    known_xy.append(_cache["coords_2d"][i])
            if known_embs:
                mat = np.array(known_embs)
                sims = mat @ cur_vec
                top_k = np.argsort(sims)[-7:]
                w = sims[top_k]
                w = w / (w.sum() + 1e-9)
                xy_arr = np.array(known_xy)
                pos = (xy_arr[top_k] * w[:, None]).sum(axis=0)
                vx, vy = float(pos[0]), float(pos[1])
        current_visitor_point = {
            "id": current_profile_id,
            "x": vx,
            "y": vy,
            "cluster_id": cid,
            "color": "#CC0000",
            "name": current_p.name,
            "role": current_p.role,
            "is_current": True,
        }
        current_cluster_id = cid

    neighbors = []
    if current_profile_id and current_has_embedding:
        current_p = profiles_by_id.get(current_profile_id)
        if current_p and current_p.embedding:
            current_vec = np.array(current_p.embedding)
            distances = []
            for p in embedded_profiles:
                if p.id == current_profile_id:
                    continue
                other_vec = np.array(p.embedding)
                similarity = float(np.dot(current_vec, other_vec) / (
                    np.linalg.norm(current_vec) * np.linalg.norm(other_vec) + 1e-9
                ))
                distances.append((p, similarity))
            distances.sort(key=lambda x: x[1], reverse=True)
            for p, sim in distances[:k]:
                neighbors.append({
                    "id": p.id,
                    "name": p.name,
                    "role": p.role,
                    "avatar_url": p.avatar_url,
                    "cluster_id": profile_cluster_map.get(p.id, ""),
                    "similarity": round(sim, 3),
                })

    archetype_label = None
    session_cluster = active_session.cluster_id if active_session else None
    if session_cluster:
        label = cluster_label_map.get(session_cluster, "")
        archetype_label = _archetype_label(session_cluster, label)

    cluster_info = []
    for cid in cluster_ids_ordered:
        label = cluster_label_map.get(cid, cid)
        cluster_info.append({
            "id": cid,
            "label": label,
            "color": cluster_color_map[cid],
            "archetype": _archetype_label(cid, label),
        })

    return {
        "status": "ok",
        "points": points,
        "clusters": cluster_info,
        "current_visitor": current_visitor_point,
        "neighbors": neighbors,
        "archetype_label": archetype_label,
    }
