"""Build EDRA Episodes from outreach data.

Maps (Profile, PitchStrategy, outreach_text, response_classification)
into the existing Episode schema. Outreach episodes have 1-2 dialogue
steps (the outreach message, and optionally the response observation).

Response classifications are mapped to EDRA outcomes per the design doc
section 3.3, and visitor_choice per section 4.3.
"""

from __future__ import annotations

from datetime import UTC, datetime

from backend.memory.ids import short_id
from backend.schemas import DialogueStep, Episode, PitchStrategy, Profile


RESPONSE_TO_OUTCOME: dict[str | None, str] = {
    "interested": "accepted",
    "curious": "exploring",
    "neutral": "exploring",
    "declining": "rejected",
    "hostile": "rejected",
    "connection_accepted_no_reply": "exploring",
    "connection_rejected": "rejected",
    "no_response": "abandoned",
    None: "abandoned",
}

RESPONSE_TO_FINAL_INTEREST: dict[str | None, int] = {
    "interested": 4,
    "curious": 2,
    "neutral": 0,
    "declining": -3,
    "hostile": -5,
    "connection_accepted_no_reply": 1,
    "connection_rejected": -4,
    "no_response": -1,
    None: -1,
}

RESPONSE_TO_VISITOR_CHOICE: dict[str | None, str] = {
    "interested": "positive",
    "curious": "skeptical",
    "neutral": "skeptical",
    "declining": "negative",
    "hostile": "negative",
    "connection_accepted_no_reply": "skeptical",
    "connection_rejected": "negative",
    "no_response": "negative",
    None: "negative",
}


def build_episode(
    profile: Profile,
    strategy: PitchStrategy,
    outreach_text: str,
    *,
    response_classification: str | None = None,
    response_text: str | None = None,
    iteration: int = 1,
    rule_applied: str | None = None,
    strategy_source: str = "factorial",
    platform: str = "email",
    batch_id: str = "",
) -> Episode:
    """Construct an Episode from outreach data.

    Args:
        profile: The recipient's Profile.
        strategy: The PitchStrategy used for this outreach.
        outreach_text: The generated outreach message that was sent.
        response_classification: One of the classification categories
            (interested/curious/neutral/declining/hostile), or a
            structural signal (connection_accepted_no_reply/
            connection_rejected/no_response), or None for no response.
        response_text: The actual text of the response, if any.
        iteration: Batch iteration number (stored as Episode.day).
        rule_applied: Rule ID if strategy was rule-guided (e.g. "R.03").
        strategy_source: "factorial", "rule:R.03", "control", etc.
        platform: "email", "linkedin_connection", "linkedin_dm".
        batch_id: e.g. "batch_2026-05-20".

    Returns:
        A fully formed Episode ready for persistence via save_episode().
    """
    outcome = RESPONSE_TO_OUTCOME.get(response_classification, "abandoned")
    final_interest = RESPONSE_TO_FINAL_INTEREST.get(response_classification, -1)
    visitor_choice = RESPONSE_TO_VISITOR_CHOICE.get(response_classification, "negative")

    thought_tag = (
        f"OUTREACH iteration={iteration} platform={platform} "
        f"batch={batch_id} strategy_source={strategy_source}"
    )

    dialogue: list[DialogueStep] = []

    if response_classification is not None and response_text:
        # Two-step episode: outreach message + response observation
        dialogue.append(
            DialogueStep(
                turn=1,
                agent_thought=thought_tag,
                agent_reply=outreach_text,
                visitor_choice=None,
                interest_delta=0,
                rule_applied=rule_applied,
            )
        )
        dialogue.append(
            DialogueStep(
                turn=2,
                agent_thought=f"Response classified as: {response_classification}",
                agent_reply="",
                visitor_choice=visitor_choice,
                interest_delta=final_interest,
                rule_applied=None,
            )
        )
    else:
        # Single-step episode: outreach message with outcome on the same step
        dialogue.append(
            DialogueStep(
                turn=1,
                agent_thought=thought_tag,
                agent_reply=outreach_text,
                visitor_choice=visitor_choice,
                interest_delta=final_interest,
                rule_applied=rule_applied,
            )
        )

    summary = _build_summary(profile, strategy, outcome, response_classification, platform)

    return Episode(
        id=short_id("ep_out"),
        timestamp=datetime.now(UTC),
        day=iteration,
        profile_id=profile.id,
        cluster_id=None,
        pitch_strategy=strategy,
        dialogue=dialogue,
        final_interest=final_interest,
        outcome=outcome,
        summary=summary,
        summary_embedding=[],
        rule_applied_top=rule_applied,
    )


def _build_summary(
    profile: Profile,
    strategy: PitchStrategy,
    outcome: str,
    classification: str | None,
    platform: str,
) -> str:
    seniority = profile.seniority
    domain = profile.domain if profile.domain != "unspecified" else ""
    role_desc = f"{seniority} {profile.role}"
    if domain:
        role_desc += f" at {domain}"

    strategy_desc = f"{strategy.framing}/{strategy.tone}"

    if classification and classification not in ("no_response", "connection_accepted_no_reply"):
        response_desc = f"responded ({classification})"
    elif classification == "connection_accepted_no_reply":
        response_desc = "accepted connection but did not reply"
    else:
        response_desc = "did not respond"

    return (
        f"{role_desc} approached via {platform} with "
        f"{strategy_desc} pitch; {response_desc}. "
        f"Outcome: {outcome}."
    )
