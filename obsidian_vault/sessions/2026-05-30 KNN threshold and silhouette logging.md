---
tags: [session, clustering, knn, silhouette, threshold-validation]
date: 2026-05-30
---

# 2026-05-30 KNN threshold and silhouette logging

Deep dive into production clustering logic: how profiles are clustered, when reclustering triggers, KNN rule selection mechanics. Two concrete improvements shipped.

## What was done

### KNN minimum similarity threshold (min_sim=0.35)

Added `min_sim` parameter to `select_rule_by_knn()`. Neighbors below the threshold are excluded from voting. If all 7 neighbors fall below, function returns `None` and the caller uses the fallback strategy.

**Validation**: ran diagnostic against 8 synthetic archetypes + 9 test profiles (6 out-of-domain: dentist, plumber, chef, nurse, accountant, real estate; 3 near-domain: marketing agency CEO, bank data scientist, product designer).

Results:
- Out-of-domain max similarities: 0.20–0.33
- Near-domain max similarities: 0.33–0.42
- In-domain (archetype-to-archetype): 0.26–0.58
- Gap between out-of-domain ceiling (0.33) and near-domain floor (0.33–0.38) — 0.35 sits in the gap

### Silhouette score logging on recluster

Added silhouette score computation to `_recluster()` in orchestrator. Fires after every HDBSCAN run that produces ≥2 clusters. Reuses `emb_by_id` dict already built for centroid computation. Logged as `recluster.silhouette n_profiles=X n_clusters=Y score=Z.ZZZ`.

## What was NOT done

- Threshold validation on 825 Pipedrive rows (data not on this machine, tracked in tech debt)
- Cluster ID assignment ordering (iteration-order-dependent, see open questions)
- Auto-labeling of new clusters (production clusters get empty label)
- Orphan cluster cleanup

## Open questions

- [ ] **Verify min_sim=0.35 on 825 Pipedrive evaluation rows** — tracked in tech debt. Current validation is on 8+9 synthetic profiles only.
- [ ] **Cluster ID race on split**: when HDBSCAN splits one cluster into two, which sub-cluster inherits the old ID depends on dict iteration order, not similarity rank. Fix: sort by best centroid similarity before assignment loop.
- [ ] **Orphaned cluster rows**: clusters that lose all profiles after recluster stay in DB with stale data. Not a correctness issue but accumulates dead rows.
- [ ] **Cluster auto-labeling**: production clusters get `label=""`. The `make_cluster_label()` function only exists in `evaluation/cluster_outreach.py`. Could be ported to `_recluster()`.
- [ ] **Silhouette as a gate vs log-only**: currently log-only. At booth scale (3-10 profiles) the score is too noisy to gate on. Revisit if deployed at scale.

## Key insights from the session

- Synthetic profiles are NOT clustered by HDBSCAN — they get `cluster_id = profile.id` (the archetype name). They do appear in the KNN corpus though.
- Every new live profile triggers a full recluster via `on_new_profile` hook. Single-session system so no concurrent session interference.
- The recluster before KNN doesn't affect the current session's rule selection (KNN votes across neighbors' cluster_ids, not the profile's own). But it keeps DB state consistent for future sessions.
- MiniLM cosine similarities on short profile summaries are generally low (median 0.40, max 0.58 between archetypes). Threshold must account for this.

See [[../00-home/current priorities]] for the full phase board.
