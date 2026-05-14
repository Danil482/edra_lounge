"""Email sending via Resend API (httpx, no SDK)."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from backend.config import settings


@dataclass
class SendResult:
    success: bool
    message_id: str | None = None
    error: str | None = None


async def send_email(
    to: str,
    subject: str,
    body: str,
    *,
    from_email: str = "",
    from_name: str = "",
) -> SendResult:
    sender_email = from_email or settings.outreach_from_email
    sender_name = from_name or settings.outreach_from_name
    api_key = settings.resend_api_key
    if not api_key:
        return SendResult(success=False, error="RESEND_API_KEY not configured")

    payload = {
        "from": f"{sender_name} <{sender_email}>",
        "to": [to],
        "subject": subject,
        "text": body,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
            return SendResult(success=True, message_id=data.get("id"))
    except httpx.HTTPStatusError as e:
        return SendResult(success=False, error=f"HTTP {e.response.status_code}: {e.response.text[:300]}")
    except Exception as e:
        return SendResult(success=False, error=f"{e.__class__.__name__}: {str(e)[:300]}")
