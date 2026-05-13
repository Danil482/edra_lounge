# EDRA — Refactor Task: Profile-Based Clustering with KNN Rule Application

**Status**: Not started
**Depends on**: Phase 4 implementation (complete), LinkedIn raw JSON cache available
**Estimated effort**: 1–1.5 days for a single developer with AI agent
**Priority**: Core change — shifts the system from episode-space clustering to profile-space clustering with KNN-based rule lookup

---

## 0. Why this refactor

The current implementation clusters **episode summaries** — text descriptions of how conversations went. This conflates "who the visitor is" with "how the conversation unfolded". A postdoc who got a socratic pitch and accepted lands in a different cluster than a postdoc who got a direct pitch and rejected, even though both are the same archetype.

The new approach clusters **profile summaries** — text derived from the visitor's LinkedIn data (headline, experience, skills, posts). This answers the right question: "what kind of person is this?" Rules are then applied not by hard cluster assignment, but by a **KNN vote** over the profile corpus.

### What changes

| Aspect | Current | New |
|---|---|---|
| What is clustered | Episode summaries | Profile summaries from LinkedIn JSON |
| Embedding input | LLM-generated episode summary text | Structured text extracted from raw LinkedIn API response |
| Cluster assignment | Hard: profile → nearest cluster centroid | Soft: KNN vote over top-K nearest profiles |
| Rule lookup | One rule per cluster, hard match | Weighted by cluster representation in top-K neighbors |
| Cold start | Episodes needed before clusters form | Profiles accumulate from first visit |

---

## 1. LinkedIn JSON → Profile Summary

The raw LinkedIn API response (cached at `data/linkedin_cache/<slug>.json`) contains structured data. The summary pipeline extracts a deterministic text representation for embedding.

### 1.1 Available fields in the JSON

From the **profile endpoint** (`data/linkedin_raw/profile__*.json`):

```
data.full_name          — "Danil Onishchenko"
data.headline           — "AI researcher at DEFY Group"
data.location.city      — "United Kingdom"
data.location.country_code — "GB"
data.bio                — free-text bio (often null)
data.experiences.data[] — array of:
  .title                — "Artificial Intelligence Researcher"
  .description          — free text with achievements/skills
  .company.name         — "DEFY Group"
  .date.start / .end    — "Feb 2026" / "Present"
  .skills[]             — ["Python", "Deep Learning", "FastAPI", ...]
  .employment_type      — "Full-time" / "Internship" / ...
```

From the **posts endpoint** (`data/linkedin_raw/posts__*.json`):

```
data[] — array of post objects (text, reactions, comments)
       — often empty for profiles with no public posts
```

### 1.2 Summary generation function

```python
def summarize_profile_from_json(profile_json: dict, posts_json: dict) -> str:
    """Build a deterministic text summary from raw LinkedIn API response.

    The output is a structured concatenation of profile fields optimized
    for embedding — not a human-readable bio.
    """
    d = profile_json["data"]
    parts = []

    # Identity + headline
    if d.get("headline"):
        parts.append(d["headline"])

    # Location
    loc = d.get("location", {})
    if loc.get("city"):
        parts.append(loc["city"])

    # Bio
    if d.get("bio"):
        parts.append(d["bio"])

    # Experiences (most recent 3)
    for exp in (d.get("experiences", {}).get("data", []))[:3]:
        exp_parts = []
        if exp.get("title"):
            exp_parts.append(exp["title"])
        if exp.get("company", {}).get("name"):
            exp_parts.append(f"at {exp['company']['name']}")
        if exp.get("description"):
            # Truncate long descriptions to keep embedding input balanced
            desc = exp["description"][:300]
            exp_parts.append(desc)
        if exp.get("skills"):
            exp_parts.append("Skills: " + ", ".join(exp["skills"][:10]))
        if exp_parts:
            parts.append(" | ".join(exp_parts))

    # Posts (most recent 3 post texts)
    for post in (posts_json.get("data", []))[:3]:
        text = post.get("text", "")
        if text:
            parts.append(f"Post: {text[:500]}")

    return " /// ".join(parts)
```

**Design choices**:
- Delimiter `///` is unlikely to appear in profile text and helps the embedder see field boundaries
- Most recent 3 experiences — older ones add noise for archetype detection
- Skills included — they are strong signals for clustering (a Python/ML person vs a Power BI/Excel person)
- Posts truncated at 500 chars — enough to capture topic, not enough to blow up embedding input
- Deterministic: same JSON in → same summary out → same embedding out

### 1.3 Synthetic profiles

Synthetic profiles (from `archetypes.yaml`) don't have LinkedIn JSON. Their summary is built from the existing fields: `role · domain · headline · recent_signals · archetype_summary`. This is the current behavior and remains unchanged.

---

## 2. Embedding and storage

### 2.1 Embedding

The summary text from §1.2 is embedded with `all-MiniLM-L6-v2` → 384-dim vector. Stored in `ProfileRow.embedding`.

```python
def embed_profile_summary(summary: str) -> list[float]:
    model = _get_embedder()  # lazy-loaded SentenceTransformer
    return model.encode(summary, normalize_embeddings=True).tolist()
```

Normalization enables cosine similarity via dot product.

### 2.2 When embedding happens

- **Live mode**: after LinkedIn fetch + parse, before `start_session` returns the first dialogue step. The raw JSON is already cached on disk; the summary is generated from it and embedded once.
- **Synthetic mode**: at profile load time from `archetypes.yaml` (existing behavior).
- **Re-embedding**: if the summary function changes (new fields added), a one-time backfill re-embeds all cached profiles. Script: iterate `data/linkedin_cache/*.json`, regenerate summary, re-embed, update DB.

### 2.3 Episode embeddings

Episode summaries are still generated and stored in `EpisodeRow.summary_embedding` — but they are **not used for clustering**. They exist for:
- Retrieval of similar past dialogues for few-shot prompting during improvisation
- Potential future use (contrastive learning, drift detection)

---

## 3. Clustering (HDBSCAN over profile embeddings)

### 3.1 What is clustered

Only `ProfileRow.embedding` vectors enter HDBSCAN. Episodes are never clustered as independent points.

```python
def cluster_profiles(profiles: list[ProfileRow]) -> dict[int, list[str]]:
    """Run HDBSCAN over profile embeddings.
    Returns {cluster_label: [profile_id, ...]}.
    """
    embeddings = np.array([p.embedding for p in profiles])
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=settings.n_min,
        min_samples=max(2, settings.n_min // 2),
    )
    labels = clusterer.fit_predict(embeddings)

    out: dict[int, list[str]] = {}
    for profile, label in zip(profiles, labels):
        if label == -1:
            continue
        out.setdefault(int(label), []).append(profile.id)
    return out
```

### 3.2 When re-clustering happens

Same trigger as today: every `recluster_every` (default 3) new profiles via `on_new_episode` hook. But now it re-clusters the **profile corpus**, not the episode corpus.

### 3.3 Cluster metadata

Each `ClusterRow` stores:
- `profile_ids` — which profiles belong to this cluster
- `centroid_embedding` — mean of profile embeddings in the cluster
- `size` — number of profiles
- `success_ratio` — computed over episodes whose profiles are in this cluster

---

## 4. KNN rule application (the core change)

### 4.1 The problem with hard assignment

Hard cluster assignment ("this profile belongs to cluster 3, apply rule for cluster 3") is brittle:
- A profile on the boundary between two clusters gets assigned to one arbitrarily
- HDBSCAN noise points (label=-1) get no rule at all, even if they're close to a well-covered cluster
- Re-clustering can reassign profiles, creating discontinuity

### 4.2 KNN vote

When a new visitor arrives, instead of assigning them to one cluster, find the **K nearest neighbors** in the profile corpus and let the neighbors vote.

```python
async def select_rule_by_knn(
    new_profile: Profile,
    corpus: list[ProfileRow],
    rules: dict[int, Rule],   # cluster_id -> active Rule
    k: int = 7,
) -> Rule | None:
    """Find the best rule for a new profile via KNN vote over the corpus.

    Returns the rule from the cluster most represented in the top-K
    nearest profiles, or None if no neighbors have active rules.
    """
    if not corpus:
        return None

    new_emb = np.array(new_profile.embedding)
    # Cosine similarity (embeddings are L2-normalized)
    similarities = [
        np.dot(new_emb, np.array(p.embedding))
        for p in corpus
    ]

    # Top-K indices
    top_k_idx = np.argsort(similarities)[-k:][::-1]

    # Count cluster votes among top-K neighbors
    cluster_votes: dict[int, float] = {}
    for idx in top_k_idx:
        neighbor = corpus[idx]
        if neighbor.cluster_id is None:
            continue
        cid = neighbor.cluster_id
        if cid not in rules:
            continue
        # Weight by similarity (closer neighbors vote stronger)
        cluster_votes[cid] = cluster_votes.get(cid, 0.0) + similarities[idx]

    if not cluster_votes:
        return None

    # Cluster with highest weighted vote wins
    best_cluster = max(cluster_votes, key=cluster_votes.get)
    return rules[best_cluster]
```

### 4.3 Behavior by case

| Scenario | What happens |
|---|---|
| Top-K all from one cluster with a rule | That cluster's rule applies (high confidence) |
| Top-K split across 2-3 clusters | Cluster with highest weighted vote wins (soft boundary) |
| Top-K all noise (no cluster) | No rule → agent improvises |
| Top-K from clusters without rules | No rule → agent improvises |
| Corpus is empty (cold start) | No neighbors → agent improvises |

### 4.4 K selection

Default `K=7`. Tunable via config. Odd number avoids ties. For a corpus of ~50 profiles, K=7 means ~14% of the corpus votes — enough to be robust, small enough to be local. As corpus grows, K can stay fixed or scale as `sqrt(N)`.

---

## 5. Code changes

### 5.1 New: `backend/clustering/summarize.py`

Profile summary generation from LinkedIn JSON (§1.2). Pure function, no DB access, no side effects.

### 5.2 Modified: `backend/clustering/cluster.py`

- `cluster_episodes()` → renamed to `cluster_profiles()`
- Input: `list[ProfileRow]` instead of `list[Episode]`
- `embed()` stays but is only called for profile summaries
- `success_ratio()` stays (still computed per cluster, but over episodes linked to the cluster's profiles)

### 5.3 New: `backend/clustering/knn.py`

KNN vote function (§4.2). Pure function: takes a profile, a corpus, rules dict, returns a Rule or None.

### 5.4 Modified: `backend/sessions/lifecycle.py`

`start_session()` currently calls `lookup_applicable_rule()` via hard cluster assignment. Replace with:

```python
# Old: rule = await lookup_rule_for_cluster(profile.cluster_id)
# New:
corpus = await memory.all_profiles_with_embeddings()
active_rules = await memory.active_rules_by_cluster()
rule = select_rule_by_knn(profile, corpus, active_rules, k=settings.knn_k)
```

### 5.5 Modified: `backend/profile_source/linkedin_rapidapi.py`

After fetching profile + posts JSON:
1. Call `summarize_profile_from_json(profile_json, posts_json)` to generate summary text
2. Call `embed_profile_summary(summary)` to get embedding
3. Store both summary and embedding in the Profile object

### 5.6 Modified: `backend/orchestrator.py`

`on_new_episode` hook:
- Re-clustering now calls `cluster_profiles()` instead of `cluster_episodes()`
- Induction eligibility checked per profile-cluster, counting episodes linked to that cluster's profiles

### 5.7 Modified: `backend/config.py`

New setting:
```python
knn_k: int = 7  # number of neighbors for rule selection vote
```

---

## 6. Data flow (end to end)

```
Visitor enters LinkedIn URL
         ↓
LinkedInRapidAPISource.fetch()
  → profile JSON (cached to data/linkedin_cache/)
  → posts JSON (cached to data/linkedin_cache/)
         ↓
summarize_profile_from_json(profile_json, posts_json)
  → structured text: "AI researcher at DEFY Group /// United Kingdom
     /// Artificial Intelligence Researcher | at DEFY Group | Skills: Python, Deep Learning..."
         ↓
embed_profile_summary(summary)
  → 384-dim vector (L2-normalized)
         ↓
ProfileRow saved to DB (with embedding + summary)
         ↓
select_rule_by_knn(new_profile, corpus, rules, k=7)
  → find 7 nearest profiles in the corpus
  → count which clusters they belong to (weighted by similarity)
  → return the rule from the dominant cluster
         ↓
If rule found → generate_turn() with that rule's strategy
If no rule   → improvise (default strategy, optional few-shot from similar episodes)
         ↓
Session runs (3-7 turns)
         ↓
end_session() → Episode persisted
         ↓
on_new_episode hook:
  → periodic cluster_profiles() — re-HDBSCAN over all profile embeddings
  → check induction eligibility per cluster
  → monitor consistency per active rule
```

---

## 7. Testing

### 7.1 Unit tests

- `test_summarize_profile_deterministic` — same JSON in → same summary out
- `test_summarize_profile_handles_missing_fields` — null bio, empty experiences, empty posts → no crash, reasonable output
- `test_summarize_profile_truncates_long_descriptions` — experience description > 300 chars is truncated
- `test_embed_profile_summary_deterministic` — same summary → same vector
- `test_cluster_profiles_not_episodes` — verify HDBSCAN receives profile embeddings, not episode embeddings
- `test_knn_single_cluster_dominance` — top-K all from one cluster → that cluster's rule returned
- `test_knn_split_vote` — top-K from two clusters → higher weighted vote wins
- `test_knn_all_noise` — top-K all noise (no cluster) → None returned
- `test_knn_empty_corpus` — no profiles in DB → None returned
- `test_knn_no_active_rules` — neighbors have clusters but no rules → None returned

### 7.2 Integration tests

- `test_live_profile_gets_knn_rule` — fetch (mock) LinkedIn profile → embed → KNN against seeded corpus → rule applied
- `test_synthetic_profile_gets_knn_rule` — synthetic archetype → embed → KNN against other archetypes → rule applied
- `test_new_archetype_improvises_then_clusters` — 5 novel profiles (no matching cluster) → improvise → after re-clustering they form a cluster → next visitor gets a rule

### 7.3 Acceptance criteria

- [ ] Profile summaries generated from raw LinkedIn JSON (not from LLM-generated text)
- [ ] HDBSCAN runs only over profile embeddings, never episode embeddings
- [ ] Rule lookup uses KNN vote over top-K nearest profiles
- [ ] Synthetic profiles still work (summary from archetypes.yaml fields)
- [ ] Mock-key path still works end to end
- [ ] All existing tests pass (or are updated to match new semantics)
- [ ] New tests from §7.1 and §7.2 pass
- [ ] 5-minute scripted scenario runs without regression

---

## 8. Migration

### 8.1 Existing data

If profiles exist in the DB with old-style embeddings (from episode summaries or from archetype fields):
1. For LinkedIn profiles: re-generate summary from cached JSON, re-embed
2. For synthetic profiles: re-generate summary from archetype fields, re-embed
3. Re-run `cluster_profiles()` on the full corpus
4. Episode `cluster_id` values become stale — backfill from their profile's new cluster assignment

This is a one-time migration script, not a recurring operation.

### 8.2 Schema changes

- `ProfileRow` gets a new `summary_text` column (the text that was embedded, for debugging/audit)
- `ProfileRow.embedding` meaning changes from "episode-style embedding" to "profile summary embedding"
- No new tables needed

---

## 9. Risks and open questions

**9.1 KNN performance at scale.** With 50–500 profiles, brute-force KNN (dot product over all profiles) is instant. At 10K+ profiles, consider approximate NN (FAISS or annoy). Not needed now.

**9.2 Posts are often empty.** Both example JSONs have `data: []` for posts. The summary function handles this gracefully (just skips the posts section), but profiles without posts will cluster purely on headline + experience. This is fine — experiences and skills are the strongest signal for archetype detection anyway.

**9.3 Summary quality depends on profile completeness.** A profile with only a name and "Student" headline produces a thin summary and a noisy embedding. The KNN approach handles this better than hard assignment — a thin profile will have low similarity to all neighbors, so the vote is weak and the system falls back to improvisation.

**9.4 K tuning.** K=7 is a starting point. Too small → noisy votes (one outlier neighbor dominates). Too large → over-smoothing (every profile gets the same majority cluster). Expose as config and tune during scenario testing.

**9.5 What about the preference function in synthetic mode?** The preference function (`simulator/preferences.py`) uses archetypes, not clusters. It is unchanged by this refactor. In synthetic mode, the preference function still scores the match between strategy and archetype. The KNN lookup determines which rule/strategy to try; the preference function determines how the synthetic visitor reacts.
