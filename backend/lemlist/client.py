"""Add leads to a Lemlist campaign (httpx, no SDK)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)


@dataclass
class LeadResult:
    success: bool
    lead_id: str | None = None
    error: str | None = None


async def add_lead_to_campaign(
    *,
    email: str,
    campaign_id: str,
    api_key: str,
    **personalization: str,
) -> LeadResult:
    payload: dict[str, str] = {"email": email, **personalization}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"https://api.lemlist.com/api/campaigns/{campaign_id}/leads/",
                auth=httpx.BasicAuth("", api_key),
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
            lead_id = data.get("_id") or data.get("leadId")
            log.info("lemlist lead added: email=%s lead_id=%s", email, lead_id)
            return LeadResult(success=True, lead_id=lead_id)
    except httpx.HTTPStatusError as e:
        msg = f"HTTP {e.response.status_code}: {e.response.text[:300]}"
        log.warning("lemlist lead failed: email=%s error=%s", email, msg)
        return LeadResult(success=False, error=msg)
    except Exception as e:
        msg = f"{e.__class__.__name__}: {str(e)[:300]}"
        log.warning("lemlist lead failed: email=%s error=%s", email, msg)
        return LeadResult(success=False, error=msg)
