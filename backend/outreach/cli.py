"""CLI entry point for the outreach pipeline.

Usage: python -m backend.outreach.cli <subcommand> [options]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import UTC, datetime, timedelta

from backend.memory.ids import short_id
from backend.outreach.csv_source import load_csv_metadata, load_profiles
from backend.outreach.generate import classify_response, generate_outreach_message
from backend.outreach.sender import send_email
from backend.outreach.state import (
    OutreachRow,
    contacted_profile_ids,
    create_outreach_row,
    get_outreach_row,
    init_outreach_db,
    list_by_batch,
    list_by_status,
    list_sent_before,
    outreach_session_factory,
    update_status,
)
from backend.schemas import PitchStrategy, Profile

log = logging.getLogger(__name__)

DEFAULT_STRATEGY = PitchStrategy(
    framing="applied-curiosity",
    tone="warm",
    opener_type="reference-to-signal",
    word_target="medium",
    ask_size="chat",
)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    parser = argparse.ArgumentParser(prog="outreach", description="EDRA outreach pipeline CLI")
    parser.add_argument("--db", default=None, help="Path to outreach.db (default: PROJECT_ROOT/outreach.db)")
    sub = parser.add_subparsers(dest="command", required=True)

    # prepare
    p_prepare = sub.add_parser("prepare", help="Generate outreach drafts for a batch")
    p_prepare.add_argument("--iteration", type=int, required=True)
    p_prepare.add_argument("--batch-size", type=int, default=20)
    p_prepare.add_argument("--platform", default="email")
    p_prepare.add_argument("--min-confidence", default="High")

    # review
    p_review = sub.add_parser("review", help="List draft/reviewed rows for a batch")
    p_review.add_argument("--batch", required=True)
    p_review.add_argument("--format", choices=["table", "full"], default="table")

    # mark-reviewed
    p_mark = sub.add_parser("mark-reviewed", help="Transition drafts to reviewed")
    p_mark.add_argument("--batch", required=True)
    p_mark.add_argument("--ids", nargs="*", default=None)

    # send
    p_send = sub.add_parser("send", help="Send reviewed outreach messages")
    p_send.add_argument("--batch", required=True)
    p_send.add_argument("--dry-run", action="store_true")
    p_send.add_argument("--test-email", default=None)

    # record-response
    p_resp = sub.add_parser("record-response", help="Record a response for a sent row")
    p_resp.add_argument("--id", required=True, dest="row_id")
    p_resp.add_argument("--text", required=True)
    p_resp.add_argument("--received-at", default=None)

    # classify
    p_classify = sub.add_parser("classify", help="LLM-classify responses in a batch")
    p_classify.add_argument("--batch", required=True)

    # check-cutoffs
    p_cutoff = sub.add_parser("check-cutoffs", help="Expire sent rows past cutoff")
    p_cutoff.add_argument("--cutoff-days", type=int, default=14)

    # status
    sub.add_parser("status", help="Show outreach pipeline status")

    args = parser.parse_args()
    asyncio.run(_dispatch(args))


async def _dispatch(args: argparse.Namespace) -> None:
    db_path = args.db
    await init_outreach_db(db_path)

    handlers = {
        "prepare": _cmd_prepare,
        "review": _cmd_review,
        "mark-reviewed": _cmd_mark_reviewed,
        "send": _cmd_send,
        "record-response": _cmd_record_response,
        "classify": _cmd_classify,
        "check-cutoffs": _cmd_check_cutoffs,
        "status": _cmd_status,
    }
    await handlers[args.command](args, db_path)


async def _cmd_prepare(args: argparse.Namespace, db_path: str | None) -> None:
    profiles = load_profiles(min_confidence=args.min_confidence)
    csv_rows = load_csv_metadata(min_confidence=args.min_confidence)
    csv_by_name: dict[str, dict[str, str]] = {
        (r.get("Name") or "").strip(): r for r in csv_rows
    }

    factory = outreach_session_factory(db_path)
    async with factory() as session:
        already = await contacted_profile_ids(session)

    candidates = [p for p in profiles if p.id not in already]
    batch = candidates[: args.batch_size]
    if not batch:
        print("No new candidates available.")
        return

    batch_id = f"batch_{args.iteration}_{datetime.now(UTC).strftime('%Y%m%d')}"
    created = 0

    for profile in batch:
        text = await generate_outreach_message(
            profile,
            platform=args.platform,
        )

        csv_row = csv_by_name.get(profile.name, {})

        row = OutreachRow(
            id=short_id("out"),
            profile_id=profile.id,
            csv_name=profile.name,
            linkedin_url=profile.source_identifier,
            email=csv_row.get("Email", ""),
            segment=(csv_row.get("Segment") or "").strip(),
            geo=(csv_row.get("Geo") or "").strip(),
            confidence=(csv_row.get("Conf.") or "").strip(),
            iteration=args.iteration,
            batch_id=batch_id,
            strategy_source="improvised",
            pitch_strategy=DEFAULT_STRATEGY.model_dump(),
            outreach_text=text,
            platform=args.platform,
            status="draft",
            sent_at=None,
            response_text=None,
            response_received_at=None,
            response_classification=None,
            edra_outcome=None,
            edra_final_interest=None,
            episode_id=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            notes=None,
        )
        async with factory() as session:
            await create_outreach_row(session, row)
        created += 1
        print(f"  [{created}/{len(batch)}] {profile.name} -> draft")

    print(f"\nBatch {batch_id}: {created} drafts created.")


async def _cmd_review(args: argparse.Namespace, db_path: str | None) -> None:
    factory = outreach_session_factory(db_path)
    async with factory() as session:
        rows = await list_by_batch(session, args.batch)

    rows = [r for r in rows if r.status in ("draft", "reviewed")]
    if not rows:
        print("No draft/reviewed rows for this batch.")
        return

    for r in rows:
        if args.format == "full":
            print(f"--- {r.id} [{r.status}] {r.csv_name} ---")
            print(r.outreach_text)
            print()
        else:
            subject = r.outreach_text.split("\n", 1)[0] if r.outreach_text else ""
            print(f"{r.id}  {r.status:<10}  {r.csv_name:<30}  {subject[:60]}")


async def _cmd_mark_reviewed(args: argparse.Namespace, db_path: str | None) -> None:
    factory = outreach_session_factory(db_path)
    async with factory() as session:
        rows = await list_by_batch(session, args.batch)

    targets = rows
    if args.ids:
        target_ids = set(args.ids)
        targets = [r for r in rows if r.id in target_ids]

    count = 0
    for r in targets:
        if r.status != "draft":
            continue
        async with factory() as session:
            await update_status(session, r.id, "reviewed")
        count += 1
    print(f"Marked {count} rows as reviewed.")


async def _cmd_send(args: argparse.Namespace, db_path: str | None) -> None:
    factory = outreach_session_factory(db_path)
    async with factory() as session:
        rows = await list_by_batch(session, args.batch)

    targets = [r for r in rows if r.status == "reviewed"]
    if not targets:
        print("No reviewed rows ready to send.")
        return

    sent = 0
    for r in targets:
        recipient_email = args.test_email or r.email
        if not recipient_email:
            print(f"  SKIP {r.id} ({r.csv_name}): no email address")
            continue

        lines = r.outreach_text.split("\n", 1)
        subject = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""

        if args.dry_run:
            print(f"  DRY-RUN {r.id} -> {recipient_email}")
            print(f"    Subject: {subject}")
            print(f"    Body: {body[:100]}...")
            print()
            continue

        result = await send_email(recipient_email, subject, body)
        if result.success:
            async with factory() as session:
                await update_status(session, r.id, "sent", sent_at=datetime.now(UTC))
            sent += 1
            print(f"  SENT {r.id} -> {recipient_email} (msg_id={result.message_id})")
        else:
            print(f"  FAIL {r.id} -> {recipient_email}: {result.error}")

        if sent < len(targets):
            await asyncio.sleep(2)

    print(f"\n{sent}/{len(targets)} emails sent.")


async def _cmd_record_response(args: argparse.Namespace, db_path: str | None) -> None:
    received_at = datetime.now(UTC)
    if args.received_at:
        received_at = datetime.fromisoformat(args.received_at).replace(tzinfo=UTC)

    factory = outreach_session_factory(db_path)
    async with factory() as session:
        await update_status(
            session,
            args.row_id,
            "response_received",
            response_text=args.text,
            response_received_at=received_at,
        )
    print(f"Recorded response for {args.row_id}.")


async def _cmd_classify(args: argparse.Namespace, db_path: str | None) -> None:
    factory = outreach_session_factory(db_path)
    async with factory() as session:
        rows = await list_by_batch(session, args.batch)

    targets = [r for r in rows if r.status == "response_received"]
    if not targets:
        print("No responses to classify.")
        return

    for r in targets:
        classification = await classify_response(r.outreach_text, r.response_text or "")
        print(f"  {r.id} ({r.csv_name}): {classification}")
        async with factory() as session:
            await update_status(
                session,
                r.id,
                "classified",
                response_classification=classification,
            )


async def _cmd_check_cutoffs(args: argparse.Namespace, db_path: str | None) -> None:
    cutoff_dt = datetime.now(UTC) - timedelta(days=args.cutoff_days)
    factory = outreach_session_factory(db_path)
    async with factory() as session:
        rows = await list_sent_before(session, cutoff_dt)

    expired = 0
    for r in rows:
        async with factory() as session:
            await update_status(session, r.id, "cutoff_expired")
        expired += 1
        print(f"  EXPIRED {r.id} ({r.csv_name}), sent {r.sent_at}")

    print(f"\n{expired} rows marked as cutoff_expired.")


async def _cmd_status(args: argparse.Namespace, db_path: str | None) -> None:
    factory = outreach_session_factory(db_path)

    status_counts: dict[str, int] = {}
    for status in ("draft", "reviewed", "sent", "response_received", "cutoff_expired", "classified", "ingested"):
        async with factory() as session:
            rows = await list_by_status(session, status)
        status_counts[status] = len(rows)

    total_contacted = sum(v for k, v in status_counts.items() if k != "draft")

    try:
        profiles = load_profiles(min_confidence="Medium")
    except FileNotFoundError:
        profiles = []

    async with factory() as session:
        already = await contacted_profile_ids(session)

    remaining = len(profiles) - len(already)

    print("Outreach pipeline status:")
    print(f"  Total contacted: {total_contacted}")
    print(f"  Remaining pool:  {remaining}")
    print(f"  State distribution:")
    for status, count in status_counts.items():
        if count > 0:
            print(f"    {status}: {count}")


if __name__ == "__main__":
    main()
