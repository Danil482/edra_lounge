---
tags: [session, deployment, dependencies, gcp]
date: 2026-06-08
---

# 2026-06-08 Pyproject audit and GCP deployment decision

Short session: audited pyproject.toml against actual imports, added missing dependencies, discussed Google Cloud deployment after Aleks offered $300 GCP credits (valid until September 2026).

## What was done

### 1. pyproject.toml dependency audit
- Grepped all `from`/`import` statements across `backend/`, `evaluation/`, `scripts/`
- Found 3 missing packages:
  - `python-dotenv>=1.0` — required by `pydantic-settings` for `env_file=".env"` loading
  - `scipy>=1.12` — used in `evaluation/level1_clustering/chi_squared_test.py` (`chi2_contingency`)
  - `pillow>=10.0` — used in `scripts/chromakey_avatars.py` and `scripts/remove_avatar_bg.py` (added to `[dev]`)
- Updated description from stale "cafe-manager game" to "visual-novel pitch floor"
- User committed as `3ab33c6 Req update` before session wrapped

### 2. Google Cloud deployment analysis
- Aleks (co-founder) received $300 GCP trial credits, valid until September 2026
- **Recommendation: Compute Engine VM (e2-medium)** — 1 vCPU, 4 GB RAM, ~$28/month (~$85 for 3 months)
- Cloud Run rejected: SQLite is file-based, Cloud Run containers are stateless — would require Postgres migration (overkill for demo traffic)
- HuggingFace Spaces (previous recommendation) now deprioritized in favor of GCP (more control, custom domain possible)
- OpenAI API costs are separate, not covered by GCP credits

## What was NOT done
- Dockerfile not created yet (pending Aleks confirming credits are active)
- No live quality check with gpt-4.1
- Lemlist campaign not resumed

## Key decisions
- **GCP Compute Engine > Cloud Run** for EDRA demo — SQLite incompatible with stateless containers, and the architectural invariant says no external DB until real load
- **e2-medium is the sweet spot** — MiniLM + UMAP + FastAPI fit in 4 GB RAM, $85/3mo leaves $215 buffer
- **pyproject.toml is now complete** — all runtime and dev dependencies declared

## Open questions
- Does Aleks see the $300 credits in GCP billing console?
- Domain: `demo.defygroup.ai` (needs DNS access from CTO) or bare IP for now?
- When to create Dockerfile and deploy script?

## Next session — entry points
1. **Aleks confirms GCP credits** → create Dockerfile + deploy script
2. **Live quality check** with gpt-4.1: run 2-3 conversations
3. **Resume Lemlist campaign** → test full booth flow E2E
4. **Paper finalization**: screenshot new cluster viz, compile in Overleaf
5. **Fix 2 pre-existing `test_cluster_viz` failures**

See [[../00-home/current priorities]] for the full phase board. Prior session: [[2026-06-05 Evaluation pipeline full data and UMAP cluster viz]].
