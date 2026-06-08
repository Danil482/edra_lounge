---
tags: [session, deployment, gcp, devops]
date: 2026-06-08
---

# 2026-06-08 GCP deploy guide and VM setup attempt

Evening session: created Dockerfile (then scrapped it), wrote DEPLOY.md for bare-metal deploy on GCP Compute Engine, attempted gcloud setup but blocked on IAM permissions.

## What was done

### 1. Dockerfile + .dockerignore (created then deleted)
- Built single-stage Dockerfile: Python 3.13-slim, pip install, MiniLM download, seed_from_eval at build time, evaluation data cleanup
- Created .dockerignore excluding vault, papers, tests, caches
- **Deleted both** after deciding bare-metal deploy is simpler for a single demo server

### 2. DEPLOY.md — bare-metal deploy guide
- Full CLI-only instructions for GCP Compute Engine (no Console UI)
- Steps: gcloud init → firewall rule → create VM (e2-medium, Ubuntu 24.04) → scp gitignored files → install Python 3.13 (deadsnakes PPA) → venv + pip install → MiniLM download → seed DB → systemd service
- systemd unit for auto-restart and log management via journalctl
- Update flow: `git pull && systemctl restart edra`
- Cost estimate: ~$31/month

### 3. gcloud CLI setup
- Installed gcloud SDK on Windows
- Authenticated as daniel@defygroup.ai
- Selected project `active-brand-498516-d7` (Aleks's project with $300 credits)
- Enabled Compute Engine API successfully
- **Blocked on IAM**: daniel@defygroup.ai lacks `compute.firewalls.create` and other permissions — needs Editor role from Aleks

## What was NOT done
- VM not created (blocked on permissions)
- No actual deployment
- Docker image not built (Docker Desktop not running + decided to go bare-metal)

## Key decisions
- **Bare-metal > Docker** for this demo — fewer moving parts, easier to debug, `git pull && restart` update flow
- **systemd service** for process management instead of Docker restart policy
- **Python 3.13 via deadsnakes PPA** on Ubuntu 24.04
- **europe-west1-b** as target zone (can change)

## Open questions
- When will Aleks grant Editor role on `active-brand-498516-d7`?
- Git repo URL — need actual org/repo path for `git clone` on VM
- `demo.defygroup.ai` DNS or bare IP?

## Next session — entry points
1. **Aleks grants Editor** → create firewall + VM → deploy following DEPLOY.md
2. **Upload .env with OPENAI_API_KEY** to VM after creation
3. **Live quality check** after deploy — run 2-3 conversations via public IP
4. **Resume Lemlist campaign** → test full E2E through deployed instance

See [[../00-home/current priorities]] for the full phase board. Prior session: [[2026-06-08 Pyproject audit and GCP deployment decision]].
