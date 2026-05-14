"""Tests for backend/outreach/ — CSV source, state machine, episode builder.

Covers the three outreach modules end-to-end with in-memory fixtures:
  - csv_source.py: seniority heuristic, role parsing, profile loading, metadata
  - state.py: OutreachRow CRUD, state machine transitions, query helpers
  - episode_builder.py: Episode construction from outreach data
"""

from __future__ import annotations

import textwrap
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.outreach.csv_source import (
    _parse_role_and_domain,
    _seniority_from_role,
    load_csv_metadata,
    load_profiles,
)
from backend.outreach.episode_builder import build_episode
from backend.outreach.state import (
    InvalidTransition,
    OutreachBase,
    OutreachRow,
    contacted_profile_ids,
    create_outreach_row,
    get_outreach_row,
    list_by_batch,
    list_by_profile,
    list_by_status,
    update_status,
)
from backend.schemas import PitchStrategy, Profile


# ── Shared fixtures ─────────────────────────────────────────────────────


CSV_HEADER = "Name,Segment,Geo,Conf.,Current role,LinkedIn,Why included"

CSV_ROWS = textwrap.dedent("""\
    Alice Smith,UX,US,High,Director of Research,https://www.linkedin.com/in/asmith/,Leads UX lab
    Bob Jones,AI,UK,Medium,PhD Student at Oxford,https://www.linkedin.com/in/bjones/,NLP thesis
    Carol Lee,HCI,DE,Low,Intern at SAP,https://linkedin.com/in/carollee,HCI intern
    ,Ops,FR,High,Manager,https://www.linkedin.com/in/noname/,Missing name
    Eve Blanc,Ops,FR,High,Manager,,Missing linkedin
""")


def _write_csv(tmp_path: Path, rows: str = CSV_ROWS) -> Path:
    csv_file = tmp_path / "test_profiles.csv"
    csv_file.write_text(f"{CSV_HEADER}\n{rows}", encoding="utf-8")
    return csv_file


def _sample_profile() -> Profile:
    return Profile(
        id="csv:testuser",
        source_kind="csv_research",
        source_identifier="https://www.linkedin.com/in/testuser/",
        name="Test User",
        role="Researcher",
        domain="AI",
        seniority="mid",
        headline="Researcher, AI",
        recent_signals=[],
        archetype_summary="Researcher at AI",
        embedding=None,
        fetched_at=datetime.now(UTC),
        ttl_seconds=None,
    )


def _sample_strategy() -> PitchStrategy:
    return PitchStrategy(
        framing="peer-collaboration",
        tone="warm",
        opener_type="reference-to-signal",
        word_target="medium",
        ask_size="chat",
    )


def _make_outreach_row(
    row_id: str = "out_001",
    profile_id: str = "csv:asmith",
    batch_id: str = "batch_2026-05-20",
    status: str = "draft",
) -> OutreachRow:
    now = datetime.now(UTC)
    return OutreachRow(
        id=row_id,
        profile_id=profile_id,
        csv_name="Alice Smith",
        linkedin_url="https://www.linkedin.com/in/asmith/",
        segment="UX",
        geo="US",
        confidence="High",
        iteration=1,
        batch_id=batch_id,
        strategy_source="factorial",
        pitch_strategy={"framing": "peer-collaboration", "tone": "warm"},
        outreach_text="Hello Alice, I noticed your work on UX research...",
        platform="email",
        status=status,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
async def outreach_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(OutreachBase.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


# ══════════════════════════════════════════════════════════════════════════
# csv_source.py — seniority heuristic
# ══════════════════════════════════════════════════════════════════════════


def test_senior_title_returns_senior_seniority():
    assert _seniority_from_role("Director of Research") == "senior"


def test_vp_title_returns_senior_seniority():
    assert _seniority_from_role("VP Engineering") == "senior"


def test_professor_returns_senior_seniority():
    assert _seniority_from_role("Professor of HCI") == "senior"


def test_lead_returns_senior_seniority():
    assert _seniority_from_role("Lead Researcher") == "senior"


def test_founder_returns_senior_seniority():
    assert _seniority_from_role("Co-Founder & CTO") == "senior"


def test_intern_returns_early_seniority():
    assert _seniority_from_role("Intern at SAP") == "early"


def test_phd_student_returns_early_seniority():
    assert _seniority_from_role("PhD Student at Oxford") == "early"


def test_junior_returns_early_seniority():
    assert _seniority_from_role("Junior Researcher") == "early"


def test_researcher_returns_mid_seniority():
    assert _seniority_from_role("Researcher") == "mid"


def test_manager_returns_mid_seniority():
    assert _seniority_from_role("Manager") == "mid"


def test_empty_role_returns_mid_seniority():
    assert _seniority_from_role("") == "mid"


# ══════════════════════════════════════════════════════════════════════════
# csv_source.py — role + domain parsing
# ══════════════════════════════════════════════════════════════════════════


def test_comma_separated_role_splits_into_role_and_domain():
    role, domain = _parse_role_and_domain("Director of Research, Google DeepMind")
    assert role == "Director of Research"
    assert domain == "Google DeepMind"


def test_single_role_returns_unspecified_domain():
    role, domain = _parse_role_and_domain("Researcher")
    assert role == "Researcher"
    assert domain == "unspecified"


def test_role_with_extra_commas_splits_only_on_first():
    role, domain = _parse_role_and_domain("Lead, AI Lab, MIT")
    assert role == "Lead"
    assert domain == "AI Lab, MIT"


def test_whitespace_is_stripped_from_role_and_domain():
    role, domain = _parse_role_and_domain("  Lead  ,  DeepMind  ")
    assert role == "Lead"
    assert domain == "DeepMind"


# ══════════════════════════════════════════════════════════════════════════
# csv_source.py — load_profiles
# ══════════════════════════════════════════════════════════════════════════


def test_load_profiles_high_only_returns_one_valid_row(tmp_path):
    csv_file = _write_csv(tmp_path)
    profiles = load_profiles(csv_file, min_confidence="High")
    # Alice=High (valid), noname=High (skipped: missing name), Eve=High (skipped: no linkedin)
    assert len(profiles) == 1
    assert profiles[0].name == "Alice Smith"


def test_load_profiles_medium_includes_high_and_medium(tmp_path):
    csv_file = _write_csv(tmp_path)
    profiles = load_profiles(csv_file, min_confidence="Medium")
    names = {p.name for p in profiles}
    assert names == {"Alice Smith", "Bob Jones"}


def test_load_profiles_low_includes_all_valid(tmp_path):
    csv_file = _write_csv(tmp_path)
    profiles = load_profiles(csv_file, min_confidence="Low")
    names = {p.name for p in profiles}
    assert names == {"Alice Smith", "Bob Jones", "Carol Lee"}


def test_load_profiles_id_format_is_csv_handle(tmp_path):
    csv_file = _write_csv(tmp_path)
    profiles = load_profiles(csv_file, min_confidence="Low")
    for p in profiles:
        assert p.id.startswith("csv:"), f"Expected csv: prefix, got {p.id}"


def test_load_profiles_source_kind_is_csv_research(tmp_path):
    csv_file = _write_csv(tmp_path)
    profiles = load_profiles(csv_file, min_confidence="High")
    for p in profiles:
        assert p.source_kind == "csv_research"


def test_load_profiles_ttl_is_none(tmp_path):
    csv_file = _write_csv(tmp_path)
    profiles = load_profiles(csv_file, min_confidence="High")
    for p in profiles:
        assert p.ttl_seconds is None


def test_load_profiles_skips_rows_with_missing_linkedin(tmp_path):
    csv = "Eve Blanc,Ops,FR,High,Manager,,Missing linkedin"
    csv_file = _write_csv(tmp_path, rows=csv)
    profiles = load_profiles(csv_file, min_confidence="High")
    assert len(profiles) == 0


def test_load_profiles_skips_rows_with_missing_name(tmp_path):
    csv = ",Ops,FR,High,Manager,https://www.linkedin.com/in/noname/,Missing name"
    csv_file = _write_csv(tmp_path, rows=csv)
    profiles = load_profiles(csv_file, min_confidence="High")
    assert len(profiles) == 0


def test_load_profiles_raises_on_missing_file():
    with pytest.raises(FileNotFoundError):
        load_profiles(Path("/nonexistent/file.csv"))


def test_load_profiles_seniority_is_correct_for_director(tmp_path):
    csv_file = _write_csv(tmp_path)
    profiles = load_profiles(csv_file, min_confidence="High")
    alice = [p for p in profiles if p.name == "Alice Smith"][0]
    assert alice.seniority == "senior"


def test_load_profiles_seniority_is_correct_for_phd_student(tmp_path):
    csv_file = _write_csv(tmp_path)
    profiles = load_profiles(csv_file, min_confidence="Medium")
    bob = [p for p in profiles if p.name == "Bob Jones"][0]
    assert bob.seniority == "early"


# ══════════════════════════════════════════════════════════════════════════
# csv_source.py — load_csv_metadata
# ══════════════════════════════════════════════════════════════════════════


def test_load_csv_metadata_returns_raw_dicts(tmp_path):
    csv_file = _write_csv(tmp_path)
    rows = load_csv_metadata(csv_file, min_confidence="High")
    assert len(rows) == 1
    assert rows[0]["Name"] == "Alice Smith"
    assert rows[0]["Conf."] == "High"


def test_load_csv_metadata_filters_by_confidence(tmp_path):
    csv_file = _write_csv(tmp_path)
    rows_high = load_csv_metadata(csv_file, min_confidence="High")
    rows_med = load_csv_metadata(csv_file, min_confidence="Medium")
    assert len(rows_med) > len(rows_high)


def test_load_csv_metadata_skips_invalid_rows(tmp_path):
    csv_file = _write_csv(tmp_path)
    rows = load_csv_metadata(csv_file, min_confidence="Low")
    names = [r["Name"] for r in rows]
    # Row with missing name and row with missing linkedin should be excluded
    assert "" not in names
    assert all(r.get("LinkedIn") for r in rows)


# ══════════════════════════════════════════════════════════════════════════
# state.py — OutreachRow creation
# ══════════════════════════════════════════════════════════════════════════


async def test_create_outreach_row_persists_and_returns(outreach_db):
    async with outreach_db() as session:
        row = _make_outreach_row()
        result = await create_outreach_row(session, row)
        assert result.id == "out_001"
        assert result.status == "draft"
        assert result.created_at is not None
        assert result.updated_at is not None


async def test_create_outreach_row_sets_timestamps_if_missing(outreach_db):
    async with outreach_db() as session:
        row = _make_outreach_row()
        row.created_at = None
        row.updated_at = None
        result = await create_outreach_row(session, row)
        assert result.created_at is not None
        assert result.updated_at is not None


async def test_get_outreach_row_returns_persisted_row(outreach_db):
    async with outreach_db() as session:
        await create_outreach_row(session, _make_outreach_row())
        fetched = await get_outreach_row(session, "out_001")
        assert fetched is not None
        assert fetched.csv_name == "Alice Smith"


async def test_get_outreach_row_returns_none_for_missing(outreach_db):
    async with outreach_db() as session:
        assert await get_outreach_row(session, "out_nope") is None


# ══════════════════════════════════════════════════════════════════════════
# state.py — state machine transitions
# ══════════════════════════════════════════════════════════════════════════


async def test_transition_draft_to_reviewed_succeeds(outreach_db):
    async with outreach_db() as session:
        await create_outreach_row(session, _make_outreach_row())
        row = await update_status(session, "out_001", "reviewed")
        assert row.status == "reviewed"


async def test_transition_draft_to_sent_raises_invalid(outreach_db):
    async with outreach_db() as session:
        await create_outreach_row(session, _make_outreach_row())
        with pytest.raises(InvalidTransition):
            await update_status(session, "out_001", "sent")


async def test_transition_reviewed_to_sent_succeeds(outreach_db):
    async with outreach_db() as session:
        await create_outreach_row(session, _make_outreach_row())
        await update_status(session, "out_001", "reviewed")
        row = await update_status(session, "out_001", "sent")
        assert row.status == "sent"


async def test_transition_sent_to_response_received_succeeds(outreach_db):
    async with outreach_db() as session:
        await create_outreach_row(session, _make_outreach_row())
        await update_status(session, "out_001", "reviewed")
        await update_status(session, "out_001", "sent")
        row = await update_status(session, "out_001", "response_received")
        assert row.status == "response_received"


async def test_transition_sent_to_cutoff_expired_succeeds(outreach_db):
    async with outreach_db() as session:
        await create_outreach_row(session, _make_outreach_row())
        await update_status(session, "out_001", "reviewed")
        await update_status(session, "out_001", "sent")
        row = await update_status(session, "out_001", "cutoff_expired")
        assert row.status == "cutoff_expired"


async def test_transition_classified_to_ingested_succeeds(outreach_db):
    async with outreach_db() as session:
        await create_outreach_row(session, _make_outreach_row())
        await update_status(session, "out_001", "reviewed")
        await update_status(session, "out_001", "sent")
        await update_status(session, "out_001", "response_received")
        await update_status(session, "out_001", "classified")
        row = await update_status(session, "out_001", "ingested")
        assert row.status == "ingested"


async def test_transition_ingested_to_anything_raises_invalid(outreach_db):
    async with outreach_db() as session:
        await create_outreach_row(session, _make_outreach_row())
        await update_status(session, "out_001", "reviewed")
        await update_status(session, "out_001", "sent")
        await update_status(session, "out_001", "response_received")
        await update_status(session, "out_001", "classified")
        await update_status(session, "out_001", "ingested")
        with pytest.raises(InvalidTransition):
            await update_status(session, "out_001", "draft")


async def test_transition_sent_to_draft_raises_invalid(outreach_db):
    async with outreach_db() as session:
        await create_outreach_row(session, _make_outreach_row())
        await update_status(session, "out_001", "reviewed")
        await update_status(session, "out_001", "sent")
        with pytest.raises(InvalidTransition):
            await update_status(session, "out_001", "draft")


async def test_update_status_with_extra_fields_sets_attributes(outreach_db):
    sent_time = datetime.now(UTC)
    async with outreach_db() as session:
        await create_outreach_row(session, _make_outreach_row())
        await update_status(session, "out_001", "reviewed")
        row = await update_status(session, "out_001", "sent", sent_at=sent_time)
        assert row.sent_at == sent_time


async def test_update_status_with_invalid_field_raises_attribute_error(outreach_db):
    async with outreach_db() as session:
        await create_outreach_row(session, _make_outreach_row())
        with pytest.raises(AttributeError):
            await update_status(session, "out_001", "reviewed", nonexistent_field="oops")


async def test_update_status_for_missing_row_raises_value_error(outreach_db):
    async with outreach_db() as session:
        with pytest.raises(ValueError):
            await update_status(session, "out_nope", "reviewed")


# ══════════════════════════════════════════════════════════════════════════
# state.py — query helpers
# ══════════════════════════════════════════════════════════════════════════


async def test_list_by_batch_returns_matching_rows(outreach_db):
    async with outreach_db() as session:
        await create_outreach_row(session, _make_outreach_row("out_a", batch_id="batch_1"))
        await create_outreach_row(session, _make_outreach_row("out_b", batch_id="batch_1"))
        await create_outreach_row(session, _make_outreach_row("out_c", batch_id="batch_2"))
        rows = await list_by_batch(session, "batch_1")
        assert len(rows) == 2
        assert {r.id for r in rows} == {"out_a", "out_b"}


async def test_list_by_status_returns_matching_rows(outreach_db):
    async with outreach_db() as session:
        await create_outreach_row(session, _make_outreach_row("out_a"))
        await create_outreach_row(session, _make_outreach_row("out_b"))
        await update_status(session, "out_a", "reviewed")
        drafts = await list_by_status(session, "draft")
        reviewed = await list_by_status(session, "reviewed")
        assert len(drafts) == 1
        assert drafts[0].id == "out_b"
        assert len(reviewed) == 1
        assert reviewed[0].id == "out_a"


async def test_list_by_profile_returns_matching_rows(outreach_db):
    async with outreach_db() as session:
        await create_outreach_row(
            session, _make_outreach_row("out_a", profile_id="csv:alice")
        )
        await create_outreach_row(
            session, _make_outreach_row("out_b", profile_id="csv:bob")
        )
        rows = await list_by_profile(session, "csv:alice")
        assert len(rows) == 1
        assert rows[0].profile_id == "csv:alice"


async def test_contacted_profile_ids_excludes_drafts(outreach_db):
    async with outreach_db() as session:
        await create_outreach_row(
            session, _make_outreach_row("out_a", profile_id="csv:alice")
        )
        await create_outreach_row(
            session, _make_outreach_row("out_b", profile_id="csv:bob")
        )
        await update_status(session, "out_a", "reviewed")
        ids = await contacted_profile_ids(session)
        assert "csv:alice" in ids
        assert "csv:bob" not in ids


async def test_contacted_profile_ids_returns_empty_when_all_drafts(outreach_db):
    async with outreach_db() as session:
        await create_outreach_row(session, _make_outreach_row("out_a"))
        ids = await contacted_profile_ids(session)
        assert ids == set()


# ══════════════════════════════════════════════════════════════════════════
# episode_builder.py — build_episode
# ══════════════════════════════════════════════════════════════════════════


def test_interested_response_produces_accepted_outcome():
    ep = build_episode(
        _sample_profile(),
        _sample_strategy(),
        "Hello, interested in collaborating?",
        response_classification="interested",
        response_text="Yes, let's talk!",
    )
    assert ep.outcome == "accepted"
    assert ep.final_interest == 4


def test_no_response_produces_abandoned_outcome():
    ep = build_episode(
        _sample_profile(),
        _sample_strategy(),
        "Hello, interested in collaborating?",
        response_classification="no_response",
    )
    assert ep.outcome == "abandoned"
    assert ep.final_interest == -1


def test_none_classification_produces_abandoned_outcome():
    ep = build_episode(
        _sample_profile(),
        _sample_strategy(),
        "Hello, interested in collaborating?",
        response_classification=None,
    )
    assert ep.outcome == "abandoned"
    assert ep.final_interest == -1


def test_curious_response_produces_exploring_outcome():
    ep = build_episode(
        _sample_profile(),
        _sample_strategy(),
        "Hello!",
        response_classification="curious",
        response_text="Interesting, tell me more.",
    )
    assert ep.outcome == "exploring"
    assert ep.final_interest == 2


def test_declining_response_produces_rejected_outcome():
    ep = build_episode(
        _sample_profile(),
        _sample_strategy(),
        "Hello!",
        response_classification="declining",
        response_text="Not interested, thanks.",
    )
    assert ep.outcome == "rejected"
    assert ep.final_interest == -3


def test_hostile_response_produces_rejected_outcome():
    ep = build_episode(
        _sample_profile(),
        _sample_strategy(),
        "Hello!",
        response_classification="hostile",
        response_text="Stop spamming me.",
    )
    assert ep.outcome == "rejected"
    assert ep.final_interest == -5


def test_two_step_dialogue_when_response_text_provided():
    ep = build_episode(
        _sample_profile(),
        _sample_strategy(),
        "Hello!",
        response_classification="interested",
        response_text="Sure, let's connect.",
    )
    assert len(ep.dialogue) == 2
    assert ep.dialogue[0].turn == 1
    assert ep.dialogue[0].agent_reply == "Hello!"
    assert ep.dialogue[0].visitor_choice is None
    assert ep.dialogue[1].turn == 2
    assert ep.dialogue[1].visitor_choice == "positive"
    assert ep.dialogue[1].interest_delta == 4


def test_single_step_dialogue_when_no_response_text():
    ep = build_episode(
        _sample_profile(),
        _sample_strategy(),
        "Hello!",
        response_classification="no_response",
    )
    assert len(ep.dialogue) == 1
    assert ep.dialogue[0].turn == 1
    assert ep.dialogue[0].agent_reply == "Hello!"
    assert ep.dialogue[0].visitor_choice == "negative"


def test_single_step_dialogue_when_classification_none():
    ep = build_episode(
        _sample_profile(),
        _sample_strategy(),
        "Hello!",
        response_classification=None,
        response_text=None,
    )
    assert len(ep.dialogue) == 1


def test_episode_id_starts_with_ep_out():
    ep = build_episode(
        _sample_profile(),
        _sample_strategy(),
        "Hello!",
    )
    assert ep.id.startswith("ep_out_")


def test_episode_summary_contains_role_strategy_and_outcome():
    ep = build_episode(
        _sample_profile(),
        _sample_strategy(),
        "Hello!",
        response_classification="interested",
        response_text="Great idea!",
    )
    assert "Researcher" in ep.summary
    assert "peer-collaboration" in ep.summary
    assert "accepted" in ep.summary


def test_episode_day_matches_iteration():
    ep = build_episode(
        _sample_profile(),
        _sample_strategy(),
        "Hello!",
        iteration=7,
    )
    assert ep.day == 7


def test_episode_profile_id_matches_input():
    profile = _sample_profile()
    ep = build_episode(profile, _sample_strategy(), "Hello!")
    assert ep.profile_id == profile.id


def test_episode_pitch_strategy_matches_input():
    strategy = _sample_strategy()
    ep = build_episode(_sample_profile(), strategy, "Hello!")
    assert ep.pitch_strategy == strategy


def test_episode_rule_applied_top_is_set_when_provided():
    ep = build_episode(
        _sample_profile(),
        _sample_strategy(),
        "Hello!",
        rule_applied="R.03",
    )
    assert ep.rule_applied_top == "R.03"


def test_episode_thought_tag_contains_metadata():
    ep = build_episode(
        _sample_profile(),
        _sample_strategy(),
        "Hello!",
        iteration=2,
        platform="linkedin_dm",
        batch_id="batch_2026-05-20",
        strategy_source="rule:R.03",
    )
    thought = ep.dialogue[0].agent_thought
    assert "iteration=2" in thought
    assert "linkedin_dm" in thought
    assert "batch_2026-05-20" in thought
    assert "rule:R.03" in thought


def test_episode_summary_platform_mentioned():
    ep = build_episode(
        _sample_profile(),
        _sample_strategy(),
        "Hello!",
        platform="linkedin_connection",
        response_classification="neutral",
        response_text="Hmm.",
    )
    assert "linkedin_connection" in ep.summary


def test_connection_accepted_no_reply_produces_exploring():
    ep = build_episode(
        _sample_profile(),
        _sample_strategy(),
        "Hello!",
        response_classification="connection_accepted_no_reply",
    )
    assert ep.outcome == "exploring"
    assert ep.final_interest == 1


def test_connection_rejected_produces_rejected():
    ep = build_episode(
        _sample_profile(),
        _sample_strategy(),
        "Hello!",
        response_classification="connection_rejected",
    )
    assert ep.outcome == "rejected"
    assert ep.final_interest == -4
