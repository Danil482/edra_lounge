"""One-time setup: create Lemlist campaign + email step via API.

Run: python scripts/setup_lemlist_campaign.py
Requires LEMLIST_API_KEY in .env
"""

import sys

import httpx

from backend.config import settings

api_key = settings.lemlist_api_key
if not api_key:
    print("ERROR: LEMLIST_API_KEY not set in .env")
    sys.exit(1)

auth = httpx.BasicAuth("", api_key)
base = "https://api.lemlist.com/api"

# ── 1. Create campaign ──────────────────────────────────────────────
print("Creating campaign...")
r = httpx.post(
    f"{base}/campaigns",
    auth=auth,
    json={
        "name": "EDRA Booth Follow-up",
        "autoReview": True,
        "autoReviewConditions": ["deliverable", "risky", "unverified"],
    },
    timeout=30.0,
)
print(f"  Status: {r.status_code}")
if r.status_code >= 400:
    print(f"  Error: {r.text[:500]}")
    sys.exit(1)

campaign = r.json()
campaign_id = campaign["_id"]
sequence_id = campaign.get("sequenceId", "")
print(f"  Campaign ID: {campaign_id}")
print(f"  Sequence ID: {sequence_id}")

# ── 2. Add email step to the sequence ───────────────────────────────
print("Adding email step...")

email_body = (
    "Hi {{firstName}},\n"
    "\n"
    "Thank you for visiting our booth and exploring the EDRA research demo! "
    "Here is a quick summary of our conversation:\n"
    "\n"
    "{{conversationSummary}}\n"
    "\n"
    "I'd love to continue the discussion and explore how "
    "Experience-Driven Rule Adaptation could benefit {{companyName}}.\n"
    "\n"
    "Would you be open to a brief call this week?\n"
    "\n"
    "Best regards,\n"
    "Daniel Khasanov\n"
    "DEFY Group | Research Team\n"
    "daniel@defygroup.ai"
)

r = httpx.post(
    f"{base}/sequences/{sequence_id}/steps",
    auth=auth,
    json={
        "type": "Email",
        "subject": "Great connecting at the booth, {{firstName}}",
        "message": email_body,
        "delay": 0,
    },
    timeout=30.0,
)
print(f"  Status: {r.status_code}")
if r.status_code >= 400:
    print(f"  Error: {r.text[:500]}")
    sys.exit(1)

step = r.json()
print(f"  Step ID: {step.get('_id', 'unknown')}")

# ── 3. Start the campaign ───────────────────────────────────────────
print("Starting campaign...")
r = httpx.post(
    f"{base}/campaigns/{campaign_id}/start",
    auth=auth,
    timeout=30.0,
)
print(f"  Status: {r.status_code}")
if r.status_code >= 400:
    print(f"  Error: {r.text[:500]}")

# ── Done ────────────────────────────────────────────────────────────
print()
print("=" * 60)
print(f"CAMPAIGN ID: {campaign_id}")
print("=" * 60)
print()
print("Add this to your .env:")
print(f"LEMLIST_CAMPAIGN_ID={campaign_id}")
