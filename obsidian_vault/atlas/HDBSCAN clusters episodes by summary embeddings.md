---
tags: [atlas, clustering, hdbscan, embeddings, ml]
date: 2026-05-13
---

# HDBSCAN clusters episodes by summary embeddings

Visitor segmentation uses HDBSCAN over 384-dimensional vectors from [[MiniLM encodes text into 384-dim embeddings|MiniLM]].

## Pipeline

1. **Embed** — `embed(texts)` lazy-loads SentenceTransformer (`all-MiniLM-L6-v2`), batch-encodes episode summaries to vectors
2. **Cluster** — `cluster_episodes(embeddings)` runs HDBSCAN `fit_predict`; returns `{label: [episode_ids]}`; noise (label=-1) is dropped
3. **Metrics** — `success_ratio(episodes)` = accepted / (accepted + rejected); excludes exploring/abandoned
4. **Visualize** — `project_umap(embeddings)` projects to 2D for the UI cluster panel

## Trigger

Re-clustering runs on every `recluster_every` (default 3) new episodes via the [[on_new_episode hook bridges the three async loops|on_new_episode hook]]. Between re-clusters, new episodes are assigned to the nearest existing cluster centroid.

## Downstream consumers

- **Induction**: a cluster qualifies for rule induction when `size >= n_min` (5) and `success_ratio >= theta_induce` (0.6)
- **Factory**: uncovered clusters (no active rule) trigger Agent stub creation
- **Monitor**: per-rule CS computed over post-induction episodes within the cluster

## Key files

- `backend/clustering/cluster.py` — embed, cluster, project_umap, success_ratio
