# Deploy EDRA demo on GCP Compute Engine

## Prerequisites

- GCP project with billing enabled ($300 trial credits)
- Editor role on the project (ask project owner)
- gcloud CLI installed locally: https://cloud.google.com/sdk/docs/install

## 1. Configure gcloud

```bash
gcloud init
# Login, select project (e.g. active-brand-498516-d7)

gcloud services enable compute.googleapis.com
```

## 2. Create firewall rule

```bash
gcloud compute firewall-rules create allow-http \
  --allow tcp:80 \
  --target-tags http-server \
  --description "Allow HTTP on port 80"
```

## 3. Create VM

```bash
gcloud compute instances create edra-demo \
  --zone=europe-west1-b \
  --machine-type=e2-medium \
  --image-family=ubuntu-2404-lts-amd64 \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB \
  --tags=http-server
```

Note the EXTERNAL_IP in the output.

## 4. Disable OS Login (if needed)

If `gcloud compute ssh` fails with "Permission denied (publickey)" and shows
your full email as the username, OS Login is on. Disable it for this VM:

```bash
gcloud compute instances add-metadata edra-demo --zone=europe-west1-b \
  --metadata=enable-oslogin=FALSE
```

## 5. SSH into VM

```bash
gcloud config set ssh/putty_force_connect false   # Windows: use OpenSSH, not Plink
gcloud compute ssh edra-demo --zone=europe-west1-b
```

When prompted "Are you sure you want to continue connecting" — type `yes` (full word).

## 6. Install system deps (on VM)

Ubuntu 24.04 ships Python 3.12 — that's sufficient, no PPA needed.

```bash
sudo apt-get update
sudo apt-get install -y python3.12-venv build-essential
```

## 7. Clone repo and set up

```bash
git clone https://github.com/Danil482/edra_lounge.git
cd edra_lounge

python3.12 -m venv .venv
source .venv/bin/activate
pip install .
```

## 8. Upload .env and gitignored data files

From your **local machine** (PowerShell), after the repo is cloned on the VM:

```powershell
# .env with API keys
gcloud compute scp .env edra-demo:~/edra_lounge/.env --zone=europe-west1-b

# Gitignored data files
gcloud compute scp evaluation/data/dataset_final.csv edra-demo:~/edra_lounge/evaluation/data/ --zone=europe-west1-b
gcloud compute scp evaluation/data/umap_profiles.npy edra-demo:~/edra_lounge/evaluation/data/ --zone=europe-west1-b
gcloud compute scp data/viz_coords_2d.json edra-demo:~/edra_lounge/data/ --zone=europe-west1-b
```

## 9. Download MiniLM model (on VM)

```bash
cd ~/edra_lounge
source .venv/bin/activate
python -c "\
from sentence_transformers import SentenceTransformer; \
m = SentenceTransformer('all-MiniLM-L6-v2'); \
m.save('backend/models/all-MiniLM-L6-v2')"
```

## 10. Seed the database

```bash
python -m backend.seed_from_eval
```

## 11. Run with screen + uvicorn

Start uvicorn in a detached screen session so it survives SSH disconnect:

```bash
screen -dmS edra sudo .venv/bin/python -m uvicorn backend.app:api --host 0.0.0.0 --port 80
```

Useful screen commands:

```bash
screen -r edra          # attach to see logs
# Ctrl+A, D             # detach (leave running)
screen -ls              # list sessions
screen -X -S edra quit  # stop the server
```

## 12. Verify

```bash
# On the VM
curl -s http://localhost/health

# From local machine
curl http://<EXTERNAL_IP>/health
```

Open `http://<EXTERNAL_IP>/` in a browser.

## Useful commands

```bash
# Get VM external IP
gcloud compute instances describe edra-demo --zone=europe-west1-b \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)'

# Stop/start VM (saves money when not demoing)
gcloud compute instances stop edra-demo --zone=europe-west1-b
gcloud compute instances start edra-demo --zone=europe-west1-b

# Delete everything
gcloud compute instances delete edra-demo --zone=europe-west1-b
gcloud compute firewall-rules delete allow-http
```

## Updating the app

```bash
gcloud compute ssh edra-demo --zone=europe-west1-b

cd ~/edra_lounge
git pull
source .venv/bin/activate
pip install .  # only if dependencies changed

# Restart uvicorn
screen -X -S edra quit
screen -dmS edra sudo .venv/bin/python -m uvicorn backend.app:api --host 0.0.0.0 --port 80
```

## Cost

| Resource | Cost |
|---|---|
| e2-medium VM | ~$28/month |
| 30 GB SSD | ~$3/month |
| **Total GCP** | **~$31/month** |

OpenAI API billed separately. Stop the VM when not in use to cut costs.
