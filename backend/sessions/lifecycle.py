"""Session lifecycle: start → take_turn → end.

Three async functions form the public surface, plus a synthetic-session
runner used by the orchestrator. Each lifecycle step is idempotent w.r.t.
the in-memory store and persists state only at session end (when the full
Episode is written and `on_new_episode` fires).

Termination rules (TASK.md §1.2 / §4.4):
  - interest reaches +5 → outcome = "accepted", session ends
  - interest reaches -5 → outcome = "rejected", session ends
  - turn limit (MAX_TURNS = 7) hit:
      final_interest > 0  → outcome = "exploring"  (positive momentum, no commit)
      final_interest <= 0 → outcome = "abandoned"  (no traction)

The interest gauge is computed by the synthetic preference function for
synthetic profiles; live-mode visitors provide their interest delta
indirectly via `visitor_choice` (Phase 3 maps choice → delta heuristically).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend import schemas
from backend.llm import client as llm
from backend.memory import store as memory_store
from backend.memory.ids import short_id
from backend.pitch import (
    classify_profile,
    generate_turn,
    lookup_applicable_rule,
)
from backend.pitch import strategy as strategy_mod
from backend.profile_source import (
    Profile,
    ProfileSource,
    ProfileNotFound,
    ProfileSourceUnavailable,
)
from backend.sessions.store import MAX_TURNS, Session, session_store
from backend.simulator import preferences


log = logging.getLogger(__name__)

# Same set of "expected when Ollama is offline" exceptions as in pitch.generate.
# Logged as a one-line warning instead of a full traceback so the demo log
# stays scannable; unexpected exceptions still go through log.exception.
_LLM_OFFLINE_EXCEPTIONS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout)


# ── Public errors ────────────────────────────────────────────────────────

class SessionNotFound(Exception):
    """The given session_id is unknown to the store."""


class SessionAlreadyEnded(Exception):
    """take_turn called against a finished session."""


# ── start_session ────────────────────────────────────────────────────────

async def start_session(
    *,
    db: AsyncSession,
    profile_source: ProfileSource,
    source_kind: str,
    identifier: str,
    day: int = 1,
) -> tuple[Session, schemas.DialogueStep]:
    """Resolve identifier → Profile → cluster → rule → first DialogueStep.

    Persists the Profile (so `recent_episodes.profile_id` joins later) and
    pushes the Session onto the store as the active session.

    Raises:
      ProfileNotFound: identifier didn't resolve.
      ProfileSourceUnavailable: transient fetch failure (live-mode caller
        should fall back to synthetic).
    """
    if profile_source.source_kind != source_kind:
        # Phase 1B ships a single source per process; if a caller asks for a
        # different kind we surface ProfileSourceUnavailable so the UI offers
        # the synthetic fallback rather than 500-ing.
        raise ProfileSourceUnavailable(
            f"active source is '{profile_source.source_kind}', requested '{source_kind}'"
        )

    profile = await profile_source.fetch(identifier)

    if not profile.embedding:
        from backend.clustering.cluster import embed
        text = f"{profile.name}, {profile.role}. {profile.headline}. {profile.archetype_summary}"
        profile.embedding = embed([text])[0]

    log.info(
        "session.profile-fetched id=%s name=%r role=%r avatar_url=%s",
        profile.id,
        profile.name,
        profile.role,
        (profile.avatar_url[:80] + "...") if profile.avatar_url else "None",
    )
    await memory_store.upsert_profile(db, profile)

    cluster_id = await classify_profile(db, profile)
    applicable_rule = await lookup_applicable_rule(db, cluster_id)
    pitch_strategy = strategy_mod.assemble_strategy(applicable_rule)

    sess = Session(
        id=short_id("sess"),
        profile=profile,
        cluster_id=cluster_id,
        applicable_rule_id=applicable_rule.id if applicable_rule else None,
        pitch_strategy=pitch_strategy,
        dialogue=[],
        interest=0,
        day=day,
    )
    session_store.add(sess, active=True)

    first_step, used_strategy = await generate_turn(
        profile=profile,
        history=[],
        applicable_rule=applicable_rule,
        pitch_strategy=pitch_strategy,
    )
    sess.pitch_strategy = used_strategy
    sess.dialogue.append(first_step)
    log.info(
        "session.start id=%s profile=%s cluster=%s rule=%s",
        sess.id,
        profile.id,
        cluster_id,
        applicable_rule.id if applicable_rule else None,
    )
    return sess, first_step


# ── take_turn ────────────────────────────────────────────────────────────

async def take_turn(
    *,
    db: AsyncSession,
    session_id: str,
    visitor_choice: schemas.VISITOR_CHOICE,
    interest_delta_override: int | None = None,
) -> tuple[Session, schemas.DialogueStep, bool]:
    """Apply the visitor's choice to the most recent step, then either
    generate the next agent step or terminate.

    Args:
      visitor_choice: the booth visitor's reaction to the last agent reply.
      interest_delta_override: synthetic mode passes the preference-function
        delta directly; HTTP/live mode leaves this None and we fall back to
        a heuristic mapping (positive=+1, skeptical=0, negative=-1).

    Returns:
      (session, last_or_next_step, terminated).
      When terminated is True, last_or_next_step is the just-finalised step
      (no new agent reply is generated — the caller should now hit `end_session`).
    """
    sess = session_store.get(session_id)
    if sess is None:
        raise SessionNotFound(session_id)
    if sess.ended:
        raise SessionAlreadyEnded(session_id)
    if not sess.dialogue:
        raise SessionAlreadyEnded(f"{session_id}: no opener step recorded")

    delta = (
        interest_delta_override
        if interest_delta_override is not None
        else _heuristic_delta_from_choice(visitor_choice)
    )
    delta = max(-2, min(2, delta))

    last_step = sess.dialogue[-1]
    finalised = last_step.model_copy(
        update={"visitor_choice": visitor_choice, "interest_delta": delta}
    )
    sess.dialogue[-1] = finalised
    sess.interest = max(-5, min(5, sess.interest + delta))

    log.info(
        "session.turn id=%s turn=%d choice=%s interest=%+d (delta=%+d)",
        sess.id,
        len(sess.dialogue),
        visitor_choice,
        sess.interest,
        delta,
    )

    if _should_terminate(sess):
        sess.ended = True
        sess.outcome = _resolve_outcome(sess)
        log.info(
            "session.terminate id=%s turns=%d interest=%+d outcome=%s",
            sess.id,
            len(sess.dialogue),
            sess.interest,
            sess.outcome,
        )
        return sess, finalised, True

    next_step, _strat = await generate_turn(
        profile=sess.profile,
        history=sess.dialogue,
        applicable_rule=None if sess.applicable_rule_id is None else _stub_rule(sess),
        pitch_strategy=sess.pitch_strategy,
        used_categories=sess.used_categories,
    )
    sess.dialogue.append(next_step)
    log.info(
        "session.next-step id=%s turn=%d reply=%r",
        sess.id,
        next_step.turn,
        next_step.agent_reply[:80],
    )
    return sess, next_step, False


def _heuristic_delta_from_choice(choice: schemas.VISITOR_CHOICE) -> int:
    if choice == "positive":
        return 1
    if choice == "negative":
        return -1
    return 0


def _should_terminate(sess: Session) -> bool:
    if sess.interest >= 5 or sess.interest <= -5:
        return True
    return len(sess.dialogue) >= MAX_TURNS


def _resolve_outcome(sess: Session) -> schemas.OUTCOME:
    if sess.interest >= 4:
        return "accepted"
    if sess.interest <= -4:
        return "rejected"
    if sess.interest > 0:
        return "exploring"
    return "abandoned"


def _stub_rule(sess: Session) -> schemas.Rule:
    """Lightweight Rule placeholder used to flag rule_applied on continuations.

    Continuations don't re-fetch the live Rule from DB — we just need a
    handle for the `rule_applied` field on the new DialogueStep. Faithful to
    the fact that the SAME rule is in force for the whole session.
    """
    return schemas.Rule(
        id=sess.applicable_rule_id or "R.??",
        cluster_id=sess.cluster_id or "",
        slots=[
            schemas.RuleSlot(name="framing", kind="static", value=sess.pitch_strategy.framing),
            schemas.RuleSlot(name="tone", kind="static", value=sess.pitch_strategy.tone),
            schemas.RuleSlot(name="opener_type", kind="static", value=sess.pitch_strategy.opener_type),
            schemas.RuleSlot(name="word_target", kind="static", value=sess.pitch_strategy.word_target),
            schemas.RuleSlot(name="ask_size", kind="static", value=sess.pitch_strategy.ask_size),
        ],
        induced_at=datetime.utcnow(),
    )


# ── resolve_session (explicit accept / decline) ─────────────────────────

async def resolve_session(
    *,
    db: AsyncSession,
    session_id: str,
    decision: str,
    on_new_episode: Any | None = None,
) -> tuple[schemas.Episode, schemas.OUTCOME]:
    """Terminate a session via explicit visitor decision (Accept/Decline button).

    Sets interest to the terminal value (+5 or -5) and immediately persists
    the episode. Returns (episode, outcome).
    """
    sess = session_store.get(session_id)
    if sess is None:
        raise SessionNotFound(session_id)
    if sess.ended:
        raise SessionAlreadyEnded(session_id)

    if decision == "accept":
        sess.interest = 5
        sess.outcome = "accepted"
    else:
        sess.interest = -5
        sess.outcome = "rejected"
    sess.ended = True

    log.info(
        "session.resolve id=%s decision=%s interest=%+d outcome=%s",
        sess.id,
        decision,
        sess.interest,
        sess.outcome,
    )

    episode = await end_session(
        db=db,
        session_id=sess.id,
        on_new_episode=on_new_episode,
    )
    return episode, sess.outcome


# ── end_session ──────────────────────────────────────────────────────────

async def end_session(
    *,
    db: AsyncSession,
    session_id: str,
    on_new_episode: Any | None = None,
) -> schemas.Episode:
    """Finalise the session into an Episode, persist, fire the hook.

    Generates the LLM-summary (TASK.md §7 #1) and embeds it for later
    clustering. If `on_new_episode` is provided, it's awaited with the new
    Episode after persistence.
    """
    sess = session_store.get(session_id)
    if sess is None:
        raise SessionNotFound(session_id)
    if not sess.ended:
        # Force-end (operator hit "end early"); resolve outcome from current state.
        sess.ended = True
        sess.outcome = _resolve_outcome(sess)

    summary = await _summarise(sess)
    episode = schemas.Episode(
        id=short_id("ep"),
        timestamp=datetime.utcnow(),
        day=sess.day,
        profile_id=sess.profile.id,
        cluster_id=sess.cluster_id,
        pitch_strategy=sess.pitch_strategy,
        dialogue=list(sess.dialogue),
        final_interest=sess.interest,
        outcome=sess.outcome or _resolve_outcome(sess),
        summary=summary,
        summary_embedding=[],  # filled by clustering recompute pass
        rule_applied_top=sess.applicable_rule_id,
    )
    await memory_store.save_episode(db, episode)
    session_store.discard_active(session_id)

    if on_new_episode is not None:
        try:
            await on_new_episode(episode)
        except Exception:  # noqa: BLE001
            log.exception("on_new_episode hook failed for episode=%s", episode.id)

    return episode


async def _summarise(sess: Session) -> str:
    """LLM summary of the completed session — falls back to a structural
    one-liner when the LLM is unavailable (offline tests, no Ollama)."""
    try:
        prompt = llm.render(
            "summary",
            profile_name=sess.profile.name,
            profile_role=sess.profile.role,
            profile_domain=sess.profile.domain,
            profile_seniority=sess.profile.seniority,
            framing=sess.pitch_strategy.framing,
            tone=sess.pitch_strategy.tone,
            opener_type=sess.pitch_strategy.opener_type,
            word_target=sess.pitch_strategy.word_target,
            ask_size=sess.pitch_strategy.ask_size,
            dialogue_formatted=_format_dialogue(sess.dialogue),
            outcome=sess.outcome or "exploring",
            final_interest=sess.interest,
        )
        text = await llm.complete(
            prompt,
            system="You write neutral structural pattern summaries.",
        )
        text = text.strip().strip('"')
        if text:
            return text
    except _LLM_OFFLINE_EXCEPTIONS as e:
        log.warning("summary LLM unavailable (%s); using structural fallback", e.__class__.__name__)
    except Exception:  # noqa: BLE001
        log.exception("summary LLM failed; using structural fallback")
    return _fallback_summary(sess)


def _format_dialogue(steps: list[schemas.DialogueStep]) -> str:
    lines = []
    for s in steps:
        choice = s.visitor_choice or "—"
        lines.append(
            f"  T{s.turn} agent: {s.agent_reply[:100]}…  "
            f"visitor: {choice} (Δ={s.interest_delta:+d})"
        )
    return "\n".join(lines) if lines else "  (no steps)"


def _fallback_summary(sess: Session) -> str:
    ps = sess.pitch_strategy
    return (
        f"{sess.profile.role} in {sess.profile.domain} approached with "
        f"{ps.framing}/{ps.tone} pitch over {len(sess.dialogue)} turns; "
        f"closed at interest {sess.interest:+d} ({sess.outcome or 'exploring'})."
    )


# ── Synthetic-session runner ─────────────────────────────────────────────

async def run_synthetic_session(
    *,
    db: AsyncSession,
    profile_source: ProfileSource,
    archetype_id: str,
    day: int,
    on_new_episode: Any | None = None,
) -> schemas.Episode:
    """Run a complete synthetic visit start→end. Used by the orchestrator tick.

    The visitor's reactions are computed via the preference function (no LLM,
    deterministic given the seeded affinity tables). Returns the persisted
    Episode after `on_new_episode` has been awaited.
    """
    if profile_source.source_kind != "synthetic":
        raise ValueError("run_synthetic_session requires a synthetic ProfileSource")

    sess, _first_step = await start_session(
        db=db,
        profile_source=profile_source,
        source_kind="synthetic",
        identifier=archetype_id,
        day=day,
    )

    while not sess.ended:
        delta = preferences.preference(
            archetype_id,
            sess.pitch_strategy,
            history=sess.dialogue,
        )
        choice = preferences.visitor_choice_from_delta(delta)
        try:
            sess, _step, _terminated = await take_turn(
                db=db,
                session_id=sess.id,
                visitor_choice=choice,
                interest_delta_override=delta,
            )
        except SessionAlreadyEnded:
            break

    return await end_session(
        db=db,
        session_id=sess.id,
        on_new_episode=on_new_episode,
    )
