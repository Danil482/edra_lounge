"""Outreach message generation and response classification via LLM."""

from __future__ import annotations

from backend.llm import client as llm
from backend.schemas import Profile

VALID_CLASSIFICATIONS = frozenset({
    "interested", "curious", "neutral", "declining", "hostile",
})


async def generate_outreach_message(
    profile: Profile,
    *,
    platform: str = "email",
    sender_name: str = "Daniil Onishchenko",
    sender_role: str = "Research Engineer",
) -> str:
    prompt = llm.render(
        "outreach",
        sender_name=sender_name,
        sender_role=sender_role,
        profile_name=profile.name,
        profile_role=profile.role,
        profile_domain=profile.domain,
        profile_seniority=profile.seniority,
        profile_headline=profile.headline,
        profile_recent_signals=" / ".join(profile.recent_signals)
        if profile.recent_signals
        else "(none)",
    )
    text = await llm.complete(prompt, system="You are a research outreach assistant.")
    return text.strip()


async def classify_response(outreach_text: str, response_text: str) -> str:
    prompt = llm.render(
        "classify_response",
        outreach_text=outreach_text,
        response_text=response_text,
    )
    text = await llm.complete(prompt)
    word = text.strip().lower().split()[0] if text.strip() else ""
    if word in VALID_CLASSIFICATIONS:
        return word
    return "neutral"
