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
            f"Quick one for someone working on {domain} as a {role.lower()} — "
            f"what's the part of your current line of work that you wish more "
            f"people were paying attention to?"
        )
    if strategy.opener_type == "reference-to-signal":
        if signal:
            return (
                f"Saw your note — \"{_truncate(signal, 80)}\" — and it's been "
                f"sitting with me. We're putting together a cohort of {domain} "
                f"researchers willing to push on exactly that thread; would you "
                f"be open to comparing notes?"
            )
        return (
            f"Your work on {domain} keeps surfacing in our internal threads. "
            f"Would you be open to comparing notes?"
        )
    if strategy.opener_type == "shared-context":
        return (
            f"We're both circling the same question in {domain} — how to make "
            f"the next round of work hold up under scrutiny. I'd love a short "
            f"conversation to see where the angles overlap."
        )
    if strategy.opener_type == "credential-anchor":
        return (
            f"I run research liaison for DEFY.group; we're scoping a small "
            f"{domain} cohort and your name came up twice in the same week. "
            f"Worth a fifteen-minute exchange?"
        )
    # cold
    return (
        f"Quick reach — interested in a brief exchange on {domain}?"
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

def _continuation_positive(p: schemas.Profile, s: schemas.PitchStrategy) -> str:
    if s.tone == "socratic":
        return (
            f"Glad that lands. What's the question you'd most want a small "
            f"working group to commit to, if it had three months and no other "
            f"obligations?"
        )
    if s.tone == "warm":
        return (
            f"That's the response I was hoping for. The cohort is intentionally "
            f"small — three or four people who'd push each other. Want me to "
            f"send the brief?"
        )
    if s.tone == "direct":
        return (
            f"Good. Concrete next step: a thirty-minute scoping call this week, "
            f"and I send a one-page brief beforehand. Does that work?"
        )
    if s.tone == "playful":
        return (
            f"Excellent — refreshing to find someone who doesn't squint at the "
            f"word 'collaboration'. What would make this actually fun for you?"
        )
    return (
        f"Good. I'll write up a short brief on the cohort and send it your way."
    )


def _continuation_skeptical(p: schemas.Profile, s: schemas.PitchStrategy) -> str:
    if s.tone == "socratic":
        return (
            f"Fair. What would have to be true about the framing for it to "
            f"warrant your time?"
        )
    if s.tone == "warm":
        return (
            f"That's reasonable — most outreach we get sounds like recruiting in "
            f"a trench coat. What signal would tell you this isn't that?"
        )
    if s.tone == "direct":
        return (
            f"Fair point. The honest version: this is exploratory, no contract, "
            f"no equity ask. One scoping call and you decide if a second one "
            f"is worth your time."
        )
    if s.tone == "playful":
        return (
            f"Skeptical is the right opening move — I'd be worried if you "
            f"weren't. What would change your mind?"
        )
    return (
        f"That's a fair pushback. What would have to be different for this to "
        f"be worth a conversation?"
    )


def _continuation_negative(p: schemas.Profile, s: schemas.PitchStrategy) -> str:
    if s.tone == "socratic":
        return (
            f"Understood. Last question, then I'll get out of your way: was it "
            f"the framing or the ask that didn't fit?"
        )
    if s.tone == "warm":
        return (
            f"Heard. I won't push — if anything shifts, the door stays open."
        )
    if s.tone == "direct":
        return (
            f"OK. Closing the loop here. Thanks for the time."
        )
    if s.tone == "playful":
        return (
            f"Read loud and clear. I'll let you get back to actual work."
        )
    return f"Understood. Thanks for the candor."


def _continuation_neutral(p: schemas.Profile, s: schemas.PitchStrategy) -> str:
    return (
        f"Just to make this concrete — what would a useful next step look like "
        f"from your side?"
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
