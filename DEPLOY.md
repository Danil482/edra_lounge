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

## 4. Upload gitignored data files

From the repo root on your local machine:

```bash
gcloud compute scp evaluation/data/dataset_final.csv edra-demo:~ --zone=europe-west1-b
gcloud compute scp evaluation/data/umap_profiles.npy edra-demo:~ --zone=europe-west1-b
gcloud compute scp data/viz_coords_2d.json edra-demo:~ --zone=europe-west1-b
```

## 5. SSH into VM

```bash
gcloud compute ssh edra-demo --zone=europe-west1-b
```

## 6. Install Python 3.13 and system deps

```bash
sudo apt-get update
sudo apt-get install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install -y python3.13 python3.13-venv python3.13-dev build-essential
```

## 7. Clone repo and set up

```bash
git clone https://github.com/defy-group/edra-lounge.git
cd edra-lounge

# Move gitignored data files into place
mkdir -p evaluation/data data
cp ~/dataset_final.csv evaluation/data/
cp ~/umap_profiles.npy evaluation/data/
cp ~/viz_coords_2d.json data/

# Create venv and install
python3.13 -m venv .venv
source .venv/bin/activate
pip install .
```

## 8. Download MiniLM model

```bash
python -c "\
from sentence_transformers import SentenceTransformer; \
m = SentenceTransformer('all-MiniLM-L6-v2'); \
m.save('backend/models/all-MiniLM-L6-v2')"
```

## 9. Seed the database

```bash
python -m backend.seed_from_eval
```

## 10. Create .env

```bash
cat > .env << 'EOF'
LLM_MODE=openai
OPENAI_API_KEY=<your-key>
OPENAI_MODEL=gpt-4.1
LIVE_MODE=true
RAPIDAPI_KEY=mock
LEMLIST_API_KEY=
LEMLIST_CAMPAIGN_ID=
EOF
```

## 11. Run as a systemd service

Create a service so uvicorn starts automatically and survives SSH disconnect:

```bash
sudo tee /etc/systemd/system/edra.service << EOF
[Unit]
Description=EDRA Demo
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/edra-lounge
Environment=PATH=$HOME/edra-lounge/.venv/bin:/usr/bin
ExecStart=$HOME/edra-lounge/.venv/bin/python -m uvicorn backend.app:api --host 0.0.0.0 --port 80
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable edra
sudo systemctl start edra
```

## 12. Verify

```bash
# On the VM
sudo systemctl status edra
curl -s http://localhost/health

# From local machine
curl http://<EXTERNAL_IP>/health
```

Open `http://<EXTERNAL_IP>/` in a browser.

## Useful commands

```bash
# View logs
sudo journalctl -u edra -f

# Restart after code changes
cd ~/edra-lounge && git pull
sudo systemctl restart edra

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

cd ~/edra-lounge
git pull
source .venv/bin/activate
pip install .  # only if dependencies changed
sudo systemctl restart edra
```

## Cost

| Resource | Cost |
|---|---|
| e2-medium VM | ~$28/month |
| 30 GB SSD | ~$3/month |
| **Total GCP** | **~$31/month** |

OpenAI API billed separately. Stop the VM when not in use to cut costs.
