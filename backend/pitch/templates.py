"""Deterministic opener / continuation templates for the no-LLM path.

A fully-static rule fires without any LLM call (TASK.md §7 guarantees the
LLM is reserved for the five touchpoints; pitch generation for static rules
is not on that list). To keep the dialogue legible we render the opener
from a slot-keyed template library, and continuations from a tone-keyed
fallback library.

Templates are deliberately short — the demo's narrative weight is in the
strategy choice, not the prose. Word counts loosely respect the
`word_target` slot: short ≈ 30, medium ≈ 80, long ≈ 120.
"""

from __future__ import annotations

from backend import schemas


# ── Opener templates, keyed by opener_type ───────────────────────────────

def render_opener(
    profile: schemas.Profile,
    strategy: schemas.PitchStrategy,
) -> str:
    """Pick the right template by opener_type and substitute profile fields."""
    signal = _first_signal(profile)
    domain = profile.domain
    role = profile.role

    if strategy.opener_type == "question":
        return (
            f"We run HDBSCAN clustering over marketing episodes to find "
            f"which outreach strategies survive domain drift. Your "
            f"{domain} work probably overlaps with what we're seeing."
        )
    if strategy.opener_type == "reference-to-signal":
        if signal:
            return (
                f"Noticed your post — \"{_truncate(signal, 80)}\" — it "
                f"connects to our ToucHire system, a multi-agent setup "
                f"that cut outreach time by 85% in production."
            )
        return (
            f"Your {domain} work keeps coming up in our group's threads. "
            f"We have three papers at SIGIR '26 in Melbourne, and the "
            f"overlap with your area is hard to ignore."
        )
    if strategy.opener_type == "shared-context":
        return (
            f"We're both working at the {domain} / applied AI boundary. "
            f"Our group just published a Dynamic RAG system that beat "
            f"ChatGPT and Gemini on professional content ranking."
        )
    if strategy.opener_type == "credential-anchor":
        return (
            f"I'm with Farseev's group — ten-plus papers at MM, SIGIR, "
            f"WSDM, two hundred citations. We're looking at a {domain} "
            f"collaboration worth a fifteen-minute conversation."
        )
    # cold
    return (
        f"Quick one — our lab runs five research streams in marketing AI "
        f"and multimedia analytics, and {domain} is one of the threads "
        f"we want to push on."
    )


def render_continuation(
    profile: schemas.Profile,
    strategy: schemas.PitchStrategy,
    history: list[schemas.DialogueStep],
) -> str:
    """Mid-session reply, conditioned on the visitor's last choice and tone."""
    last = history[-1] if history else None
    last_choice = last.visitor_choice if last else None

    if last_choice == "positive":
        return _continuation_positive(profile, strategy)
    if last_choice == "skeptical":
        return _continuation_skeptical(profile, strategy)
    if last_choice == "negative":
        return _continuation_negative(profile, strategy)
    return _continuation_neutral(profile, strategy)


# ── Continuation library, keyed by tone × visitor_choice ─────────────────

# Continuation templates are the fallback path — they fire only when the LLM
# is offline. Each one is a STATEMENT or NARROW PROPOSAL (yes/no shape) the
# visitor can plausibly answer with one of the three buttons. No open
# questions: the visitor cannot type free text.

def _continuation_positive(p: schemas.Profile, s: schemas.PitchStrategy) -> str:
    if s.tone == "socratic":
        return (
            f"Glad that tracks. Concrete example: ToucHire runs nine "
            f"agents on a shared blackboard and cut outreach time by "
            f"85% in a live deployment."
        )
    if s.tone == "warm":
        return (
            f"Good to hear. We're presenting at SIGIR and MM this year, "
            f"three papers in Melbourne alone. I can send the abstracts "
            f"so you can judge the overlap yourself."
        )
    if s.tone == "direct":
        return (
            f"Good. Next step: a thirty-minute scoping call this week. "
            f"I'll send our SOINSPIRE and ToucHire papers first so we "
            f"can talk specifics."
        )
    if s.tone == "playful":
        return (
            f"Nice. Our Dynamic RAG system hit nDCG@10 of 0.829, above "
            f"ChatGPT and Gemini on content ranking. Worth fifteen "
            f"minutes to walk through it."
        )
    return (
        f"Good. I'll send our recent papers on video memorability, "
        f"agent architectures, and Dynamic RAG so you can see the "
        f"research threads."
    )


def _continuation_skeptical(p: schemas.Profile, s: schemas.PitchStrategy) -> str:
    if s.tone == "socratic":
        return (
            f"Fair. Verifiable version: ten-plus papers at ACM venues, "
            f"two hundred citations, five papers accepted at MM '26 and "
            f"SIGIR '26. Research group, not a sales team."
        )
    if s.tone == "warm":
        return (
            f"Reasonable — most outreach sounds like recruiting in a "
            f"trench coat. We publish at MM and SIGIR; the ToucHire and "
            f"SOINSPIRE papers are public and citable."
        )
    if s.tone == "direct":
        return (
            f"Fair point. Numbers: 85% reduction in outreach time on "
            f"ToucHire, nDCG@10 of 0.829 on SOINSPIRE, five conference "
            f"papers this year. One scoping call, you decide."
        )
    if s.tone == "playful":
        return (
            f"Skepticism is the right default. The justification: "
            f"200,000+ influencer profiles indexed, results published "
            f"at SIGIR."
        )
    return (
        f"Fair pushback. We publish at ACM Multimedia and SIGIR. "
        f"This is a research conversation, not a recruiting pitch."
    )


def _continuation_negative(p: schemas.Profile, s: schemas.PitchStrategy) -> str:
    if s.tone == "socratic":
        return f"Understood. Door stays open if the framing shifts."
    if s.tone == "warm":
        return f"Heard. If anything changes, the door stays open."
    if s.tone == "direct":
        return f"OK. Thanks for the time."
    if s.tone == "playful":
        return f"Loud and clear. Back to actual work."
    return f"Understood. Thanks for the candor."


def _continuation_neutral(p: schemas.Profile, s: schemas.PitchStrategy) -> str:
    return (
        f"To make this concrete: a thirty-minute scoping call. I'll send "
        f"our recent SIGIR and MM papers beforehand, you decide from there."
    )


# ── Internal-thought rendering ───────────────────────────────────────────

def render_thought(
    strategy: schemas.PitchStrategy,
    rule_id: str | None,
    is_opener: bool,
) -> str:
    """The italic in-parens line shown above the agent_reply in the VN textbox.

    Surfaces which rule (or improvisation) drove this turn so the demo can
    explain itself when Expert View is on (TASK.md §10.6).
    """
    head = f"rule {rule_id}" if rule_id else "improvising"
    shape = (
        f"{strategy.framing}/{strategy.tone}/{strategy.opener_type}"
        if is_opener
        else f"{strategy.framing}/{strategy.tone}"
    )
    return f"({head}: {shape})"


# ── Helpers ──────────────────────────────────────────────────────────────

def _first_signal(profile: schemas.Profile) -> str | None:
    if profile.recent_signals:
        return profile.recent_signals[0]
    return None


def _truncate(text: str, n: int) -> str:
    text = text.strip().rstrip(".")
    if len(text) <= n:
        return text
    return text[: n - 1].rstrip() + "…"
