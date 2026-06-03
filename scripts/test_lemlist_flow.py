"""End-to-end test of Lemlist campaign API: test all 3 outcome variants.

Run:  PYTHONPATH=. python scripts/test_lemlist_flow.py
Requires LEMLIST_API_KEY and LEMLIST_CAMPAIGN_ID in .env

Tests the personalization flow for accepted, declined (rejected), and
exploring (abandoned) outcomes by adding a lead with each variant's
outcomeSubject/outcomeMessage, verifying the contact fields, then removing.
"""

import sys
import time

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
test_email = "danial92335@mail.ru"

OUTCOME_CONFIGS = [
    {
        "label": "ACCEPTED",
        "outcomeSubject": "Great meeting you, {{firstName}}!",
        "outcomeMessage": (
            "Thank you for stopping by the EDRA research demo and for your "
            "interest in collaborating!\n\nHere's a quick recap of what we "
            "discussed:\n{{conversationSummary}}\n\nI'd love to continue our "
            "conversation about how Experience-Driven Rule Adaptation could "
            "help {{companyName}}.\n\nWould you have 15 minutes for a quick "
            "call this week?"
        ),
    },
    {
        "label": "DECLINED",
        "outcomeSubject": "Thanks for stopping by, {{firstName}}",
        "outcomeMessage": (
            "Thank you for stopping by the EDRA research demo! I appreciate "
            "you taking the time to explore it.\n\nEven though the timing "
            "wasn't right this time, I wanted to share a brief summary of "
            "what we covered:\n{{conversationSummary}}\n\nIf you ever want "
            "to revisit the topic or have questions about Experience-Driven "
            "Rule Adaptation, don't hesitate to reach out."
        ),
    },
    {
        "label": "EXPLORING",
        "outcomeSubject": "Let's continue our conversation, {{firstName}}",
        "outcomeMessage": (
            "Thank you for stopping by the EDRA research demo! It was great "
            "chatting with you.\n\nHere's a quick recap of what we discussed:"
            "\n{{conversationSummary}}\n\nI noticed we didn't get to finish "
            "our conversation. If you'd like to pick up where we left off or "
            "learn more about how EDRA could help {{companyName}}, I'm happy "
            "to chat."
        ),
    },
]


def _dump_error(r: httpx.Response) -> None:
    if r.status_code >= 400:
        print(f"  HTTP {r.status_code}: {r.text[:1000]}")


def remove_lead() -> None:
    r = httpx.delete(
        f"{base}/campaigns/{campaign_id}/leads/{test_email}",
        params={"action": "remove"},
        auth=auth,
        timeout=30.0,
    )
    print(f"  Remove lead: HTTP {r.status_code}")


def add_lead(outcome_config: dict) -> tuple[str | None, dict | None]:
    payload = {
        "email": test_email,
        "firstName": "Test",
        "lastName": "User",
        "companyName": "Test Company",
        "jobTitle": "Test Role",
        "linkedinUrl": "https://linkedin.com/in/test",
        "conversationSummary": (
            "We discussed how EDRA uses cluster-conditional rules to personalize "
            "outreach strategies. The visitor showed interest in applying the "
            "framework to their own sales pipeline."
        ),
        "archetype": "Sales Director",
        "outcomeSubject": outcome_config["outcomeSubject"],
        "outcomeMessage": outcome_config["outcomeMessage"],
    }

    r = httpx.post(
        f"{base}/campaigns/{campaign_id}/leads/",
        auth=auth,
        json=payload,
        timeout=30.0,
    )
    if r.status_code < 400:
        data = r.json()
        lead_id = data.get("_id") or data.get("leadId")
        print(f"  Lead added! ID: {lead_id}")
        return lead_id, data
    else:
        _dump_error(r)
        print("  FAILED to add lead.")
        return None, None


def verify_lead(lead_response: dict | None, outcome_config: dict) -> bool:
    if not lead_response:
        print("  No lead response to verify.")
        return False

    stored_subject = lead_response.get("outcomeSubject", "<missing>")
    stored_message = lead_response.get("outcomeMessage", "<missing>")
    expected_subject = outcome_config["outcomeSubject"]

    print(f"  outcomeSubject: {str(stored_subject)[:80]}")
    print(f"  outcomeMessage: {str(stored_message)[:80]}...")

    if stored_subject == expected_subject:
        print("  Subject matches expected value.")
    else:
        print(f"  MISMATCH: expected {expected_subject!r}, got {stored_subject!r}")
        return False

    r = httpx.get(f"{base}/campaigns/{campaign_id}/leads", auth=auth, timeout=30.0)
    if r.status_code >= 400:
        _dump_error(r)
        return False

    leads = r.json()
    if not isinstance(leads, list):
        print(f"  Unexpected response type: {type(leads)}")
        return False

    for lead in leads:
        cid = lead.get("contactId", "???")
        r2 = httpx.get(f"{base}/contacts/{cid}", auth=auth, timeout=30.0)
        if r2.status_code >= 400:
            continue
        contact = r2.json()
        if contact.get("email") != test_email:
            continue

        print(f"  Verified contact in campaign: {contact.get('email')}")
        print(f"    firstName: {contact.get('fields', {}).get('firstName', '<missing>')}")
        return True

    print("  Lead not found in campaign leads.")
    return False


# ── Main flow ────────────────────────────────────────────────────────

print("=" * 60)
print("STEP 0: Fetch campaign details")
print("=" * 60)

r = httpx.get(f"{base}/campaigns/{campaign_id}", auth=auth, timeout=30.0)
_dump_error(r)
if r.status_code < 400:
    campaign = r.json()
    print(f"  Name:   {campaign.get('name', '???')}")
    print(f"  Status: {campaign.get('status', '???')}")
print()

passed = 0
failed = 0

for i, cfg in enumerate(OUTCOME_CONFIGS, 1):
    label = cfg["label"]
    print("=" * 60)
    print(f"TEST {i}/3: {label}")
    print("=" * 60)

    print(f"\n  [a] Remove existing lead...")
    remove_lead()
    time.sleep(1)

    print(f"\n  [b] Add lead with {label} personalization...")
    lead_id, lead_data = add_lead(cfg)
    if not lead_id:
        print(f"  FAIL: could not add lead for {label}")
        failed += 1
        print()
        continue
    time.sleep(1)

    print(f"\n  [c] Verify personalization fields...")
    ok = verify_lead(lead_data, cfg)
    if ok:
        print(f"\n  PASS: {label}")
        passed += 1
    else:
        print(f"\n  FAIL: {label}")
        failed += 1

    print(f"\n  [d] Cleanup...")
    remove_lead()
    time.sleep(1)
    print()

print("=" * 60)
print(f"RESULTS: {passed} passed, {failed} failed out of 3")
print("=" * 60)
