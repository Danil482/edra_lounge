"""Update the Lemlist campaign email step to use outcome-based personalization.

Run:  PYTHONPATH=. python scripts/update_lemlist_template.py
Requires LEMLIST_API_KEY and LEMLIST_CAMPAIGN_ID in .env
"""

import sys

import httpx

from backend.config import settings

api_key = settings.lemlist_api_key
campaign_id = settings.lemlist_campaign_id

if not api_key:
    print("ERROR: LEMLIST_API_KEY not set in .env")
    sys.exit(1)
if not campaign_id:
    print("ERROR: LEMLIST_CAMPAIGN_ID not set in .env")
    sys.exit(1)

auth = httpx.BasicAuth("", api_key)
base = "https://api.lemlist.com/api"

print("=" * 60)
print("Fetching campaign sequences...")
print("=" * 60)

r = httpx.get(f"{base}/campaigns/{campaign_id}/sequences", auth=auth, timeout=30.0)
if r.status_code >= 400:
    print(f"  HTTP {r.status_code}: {r.text[:500]}")
    sys.exit(1)

raw = r.json()
sequences = list(raw.values()) if isinstance(raw, dict) else raw

sequence_id = None
step_id = None

for seq in sequences:
    for step in seq.get("steps", []):
        if step.get("type", "").lower() == "email" and step_id is None:
            sequence_id = seq.get("_id")
            step_id = step.get("_id")

if not step_id:
    print("  No email step found. Create one in the Lemlist UI first.")
    sys.exit(1)

print(f"  Found email step: sequence={sequence_id}, step={step_id}")
print()

new_subject = "{{outcomeSubject}}"
new_body = (
    "Hi {{firstName}},<br><br>"
    "{{outcomeMessage}}<br><br>"
    "Best regards,<br>"
    "Daniel Onishchenko<br>"
    "DEFY Group &middot; Research Team<br>"
    "daniel@defygroup.ai"
)

print("=" * 60)
print("Updating email step template...")
print("=" * 60)

r = httpx.patch(
    f"{base}/sequences/{sequence_id}/steps/{step_id}",
    auth=auth,
    json={"type": "email", "subject": new_subject, "message": new_body},
    timeout=30.0,
)

if r.status_code < 400:
    updated = r.json()
    print(f"  Updated successfully!")
    print(f"  Subject: {updated.get('subject', '???')}")
    print(f"  Message preview: {updated.get('message', '???')[:200]}")
else:
    print(f"  HTTP {r.status_code}: {r.text[:500]}")
    print("  FAILED. Update the template manually in the Lemlist UI.")
    sys.exit(1)

print()
print("DONE -- template now uses {{outcomeSubject}} and {{outcomeMessage}}")
