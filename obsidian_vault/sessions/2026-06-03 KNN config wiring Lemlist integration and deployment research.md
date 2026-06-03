---
tags: [session, knn, config, lemlist, integration, deployment, threshold]
date: 2026-06-03
---

# 2026-06-03 KNN config wiring, Lemlist integration, deployment research

Three tasks addressed: intern's clustering threshold concern, Lemlist follow-up email integration, and free deployment platform research.

## What was done

### 1. KNN threshold config wiring

Intern flagged a "threshold mismatch" between initial clustering and new-user assignment. Investigation found the VALUES being different (0.85 cluster_merge_threshold vs 0.40 KNN OOD gate) is architecturally correct — different operations measure different things. The real bug: `config.knn_k=7` existed in config but was completely unused — hardcoded `K_NEIGHBORS=7` in knn.py took precedence. Same for `MIN_AVG_SIMILARITY=0.40`.

Fixed: removed hardcoded constants from `backend/clustering/knn.py`, wired `settings.knn_k` and `settings.knn_min_avg_similarity` through from config. Also removed duplicate `cluster_merge_threshold` and `knn_k` declarations in config.py. Tests updated.

### 2. Lemlist follow-up integration

Built end-to-end integration for sending follow-up emails via Lemlist when a visitor accepts the collaboration at the booth:

- `backend/lemlist/client.py` — async `add_lead_to_campaign()` via httpx + Basic auth (no SDK, matches project convention)
- `backend/routers/sessions.py` — `ResolveIn` gained `visitor_email: str | None`; on accepted outcome, fires `asyncio.create_task` to add lead with personalization (firstName, lastName, companyName, jobTitle, linkedinUrl, conversationSummary, archetype)
- `frontend/app.js` — passes `state.visitorEmail` (from auth gate) in the resolve POST body
- Mock path: if `LEMLIST_API_KEY` is empty, logs and skips (default behavior)

Config fields added: `lemlist_api_key`, `lemlist_campaign_id` (both default empty).

### 3. Campaign creation blocked on plan

Attempted to create Lemlist campaign via API (`POST /api/campaigns`) — returned **402: route is available starting emailPro plan**. Created `scripts/setup_lemlist_campaign.py` for future use. User needs to create the campaign manually in Lemlist UI and paste the campaign ID into `.env`.

### 4. Deployment research

Analyzed free deployment options for the ML-heavy stack (PyTorch + sentence-transformers + UMAP/HDBSCAN):

| Platform | RAM | Verdict |
|---|---|---|
| HuggingFace Spaces (Docker) | 16 GB | Best fit — built for ML workloads |
| Render | 512 MB–1 GB | Too tight for PyTorch |
| Fly.io | 256 MB | Not viable |
| Railway | $5 credit | Burns fast with ML |

Recommendation: **HuggingFace Spaces** with Docker. No Dockerfile created yet (user chose not to proceed with deployment setup this session).

## What was NOT done

- Lemlist campaign not created (402 plan limitation — user needs to create in UI)
- Dockerfile / deployment config not created
- 2 pre-existing `test_cluster_viz` failures still unfixed
- Live KNN K=7 verification against real LinkedIn profile still pending
- Demo paper not compiled in Overleaf

## Key decisions

- **Threshold difference is correct** — 0.85 (cluster merge) vs 0.40 (KNN OOD gate) serve different purposes. Not a bug.
- **Config over hardcoded** — all KNN tuning params now live in Settings, tunable via env vars without code changes
- **Campaign-based Lemlist** — leads added to pre-configured campaign (not transactional sends). Lemlist handles deliverability, tracking, scheduling.
- **Fire-and-forget** — Lemlist API call runs as `asyncio.create_task` so it doesn't block the resolve response
- **HuggingFace Spaces** — recommended for deployment (16 GB RAM free, Docker, ML-native)

## Open questions

- Which Lemlist plan does the user have? Need emailPro for API campaign creation, or create manually in UI
- Campaign email template — user may want to customize subject/body in Lemlist UI
- Should follow-up also fire on "exploring" outcome (positive but not fully accepted)?
- Deployment: proceed with HuggingFace Spaces Dockerfile, or wait for CTO response on defygroup.ai hosting?

## Next session — entry points

1. **Create Lemlist campaign in UI** → paste campaign ID into `.env` as `LEMLIST_CAMPAIGN_ID` → test full flow (auth gate → conversation → accept → check Lemlist for lead)
2. **Live-verify KNN K=7** — restart backend, test real LinkedIn URL against 0.40 threshold
3. **Dockerfile for HuggingFace Spaces** — if deployment decision is made
4. **Fix 2 pre-existing `test_cluster_viz` failures** (archetype-label string mismatches)
5. **Compile demo paper in Overleaf** — verify 2-page fit

See [[../00-home/current priorities]] for the full phase board. Prior session: [[2026-06-01 KNN rewrite reflection fixes and demo paper update]].
