---
tags: [session, deployment, gcp, devops]
date: 2026-06-08
---

# 2026-06-08 GCP deploy — IAM unblocked, firewall + VM created

Short session: verified IAM permissions are now granted, created firewall rule and VM, hit Plink/PuTTY SSH issue on Windows.

## What was done

### 1. IAM permissions verified
- Aleks granted `roles/editor` to daniel@defygroup.ai on `active-brand-498516-d7`
- Also has `roles/iam.dataScientist`
- `gcloud compute firewall-rules list` succeeds — Compute Engine fully accessible

### 2. Firewall rule created
- `allow-http`: tcp:80, target-tags=http-server

### 3. VM created
- `edra-demo`, europe-west1-b, e2-medium, Ubuntu 24.04 LTS, 30GB SSD, http-server tag
- External IP assigned

### 4. SSH issue diagnosed
- `gcloud compute ssh` on Windows uses Plink (PuTTY) by default
- Plink's host-key prompt doesn't accept input in PowerShell
- Workaround: switch to built-in OpenSSH (`gcloud config set ssh/putty_force_connect false`) or use `ssh` directly with gcloud-generated keys at `~/.ssh/google_compute_engine`

### 5. Fixed /doctor warning
- Removed invalid permission rule `"Write .claude/skills/**"` from `.claude/settings.local.json` (was being skipped at parse time anyway)

## What was NOT done
- SSH into VM (blocked by Plink issue, user will retry with OpenSSH tomorrow)
- Steps 4-12 of DEPLOY.md (scp data files, install Python, clone, seed, systemd)
- No code changes

## Key decisions
- User will run all deploy commands manually, Claude advises only

## Open questions
- SSH method: Plink workaround or direct OpenSSH?
- Git repo URL for `git clone` on VM (currently placeholder `https://github.com/defy-group/edra-lounge.git` in DEPLOY.md)
- `demo.defygroup.ai` DNS or bare IP?

## Next session — entry points
1. **SSH into VM** — fix Plink or use OpenSSH directly
2. **Follow DEPLOY.md steps 4-12**: scp data files → install Python 3.13 → clone repo → venv → MiniLM → seed DB → .env → systemd service
3. **Verify**: `curl http://<EXTERNAL_IP>/health` + open in browser
4. **Live quality check** with gpt-4.1: run 2-3 conversations

See [[../00-home/current priorities]] for the full phase board. Prior session: [[2026-06-08 GCP deploy guide and VM setup attempt]].
