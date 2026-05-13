---
tags: [integration, embeddings, miniLM, sentence-transformers]
date: 2026-05-13
---

# MiniLM encodes text into 384-dim embeddings

`all-MiniLM-L6-v2` from sentence-transformers is the embedding backbone. It converts episode summaries and profile archetypes into 384-dimensional vectors for [[HDBSCAN clusters episodes by summary embeddings|HDBSCAN clustering]].

## Usage points

- `clustering/cluster.py → embed()` — lazy-loads the model on first call, batch-encodes texts
- Profile archetype summaries → stored in `ProfileRow.embedding`
- Episode summaries → stored in `EpisodeRow.summary_embedding`
- Cluster centroids → stored in `ClusterRow.centroid_embedding`

## Configuration

- `EMBEDDING_MODEL=all-MiniLM-L6-v2` (in `backend/config.py`)
- Model is downloaded on first run (~80MB) and cached by sentence-transformers

## Design note

The model runs in-process (no separate inference server). This is consistent with the [[EDRA runs three asyncio loops inside FastAPI|single-process architecture]].
