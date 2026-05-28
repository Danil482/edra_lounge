"""
Filter Pipedrive outreach data to cold outreach only.

Usage:
    python -m backend.evaluation.filter_cold_outreach
    python -m backend.evaluation.filter_cold_outreach --input path/to/input.csv --output path/to/output.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

DEFAULT_INPUT = Path(r"C:\Users\dania\PycharmProjects\EDRA\data\eval_tier1_replied_mail.csv")
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "data" / "cold_outreach.csv"

INPUT_COLUMNS = [
    "email", "name", "organization", "job_title", "labels", "linkedin_url",
    "pipedrive_person_id", "thread_count", "outreach_subject", "outreach_snippet",
    "outreach_body_preview", "reply_snippet", "reply_body_preview", "outcome",
    "outreach_timestamp", "reply_timestamp", "thread_id", "outreach_message_id",
    "reply_message_id",
]

OUTPUT_COLUMNS = INPUT_COLUMNS + ["outreach_type"]

EXCLUDE_SUBJECT_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"Platform Access Credentials",
        r"Access Credentials Inside",
        r"Thank You for the Call",
        r"thanks for the meeting",
        r"Thanks for meeting",
        r"Materials\s*[\|/]\s*Slides",
        r"Decks\s*/\s*Materials",
        r"Marketing Mondays",
        r"Pitch Competition Results",
        r"Claude Integration",
        r"Step by Step Guide",
        r"Welcome to",
        r"Please Confirm Your Email",
        r"Registration of Interest",
        r"Draft for Review",
        r"Contract Finalization",
        r"Invoice",
        r"Meeting Minutes",
        r"Recording & Trial",
        r"Trial Sign[\s-]?Up",
        r"Onboarding",
        r"Share Allotment",
        r"Investor Update",
        r"Sprint",
        r"ACTION REQUIRED",
        r"Prep for Tomorrow",
        r"Setup\s*\|\s*Help Us Finalize",
    ]
]

# "IMPORTANT" and "Workshop" together — handled separately
_IMPORTANT_RE = re.compile(r"IMPORTANT", re.IGNORECASE)
_WORKSHOP_RE = re.compile(r"Workshop", re.IGNORECASE)

FOLLOW_UP_RE = re.compile(
    r"Checking in since you didn't reply|Following up|Checking in",
    re.IGNORECASE,
)
FEATURE_ANNOUNCEMENT_RE = re.compile(
    r"New Feature|New SOMIN Feature|Owned Content Scoring|Content Ideation|Case Study",
    re.IGNORECASE,
)
COLD_PERSONAL_RE = re.compile(
    r"Prof\.\s*Aleks\s*Farseev|Prof\.\s*Aleks(?!\s*Farseev)",
    re.IGNORECASE,
)
WARM_INTRO_SUBJECT_RE = re.compile(
    r"meet you at|met you at|nice to meet|catch up at|meeting at|"
    r"great to e-meet|nice meeting you|great meeting|"
    r"Startup Village|ATx|MarTech|SXSW|Cannes|PI LIVE|"
    r"conference|event|summit|huddle",
    re.IGNORECASE,
)
WARM_INTRO_SNIPPET_RE = re.compile(
    r"meet you at|met you at|nice to meet|catch up at|"
    r"great to e-meet|nice meeting you|great meeting|"
    r"thanks to our friends|as discussed over|intro from|"
    r"referred by|reference:|introduction from|Dentsu intro|"
    r"leaving a request on our website|"
    r"haven.t logged in|haven.t had a chance to log in|"
    r"Your SOMONITOR (?:Platform|account) is Ready|"
    r"Extending Your .+ Trial|Setup .+ Quick Intro|"
    r"Complete Your .+ Setup|Exploring .+ Capabilities",
    re.IGNORECASE,
)
RE_ENGAGEMENT_RE = re.compile(
    r"re-engaging|reaching back|Happy New Year|Personal Update",
    re.IGNORECASE,
)


def should_exclude(row: dict[str, str]) -> bool:
    subject = row["outreach_subject"].strip()
    snippet = row["outreach_snippet"].strip()

    if not subject and not snippet:
        return True

    if subject.startswith("Re:"):
        return True
    if subject.startswith("Fw:") or subject.startswith("Fwd:"):
        return True

    for pattern in EXCLUDE_SUBJECT_PATTERNS:
        if pattern.search(subject):
            return True

    if _IMPORTANT_RE.search(subject) and _WORKSHOP_RE.search(subject):
        return True

    return False


def classify_outreach_type(row: dict[str, str]) -> str:
    subject = row.get("outreach_subject", "")
    snippet = row.get("outreach_snippet", "")
    if RE_ENGAGEMENT_RE.search(subject):
        return "exclude_re_engagement"
    if FOLLOW_UP_RE.search(subject):
        return "follow_up"
    if FEATURE_ANNOUNCEMENT_RE.search(subject):
        return "feature_announcement"
    if COLD_PERSONAL_RE.search(subject):
        return "cold_personal"
    if WARM_INTRO_SUBJECT_RE.search(subject) or WARM_INTRO_SNIPPET_RE.search(snippet):
        return "warm_intro"
    return "cold_template"


def main() -> None:
    parser = argparse.ArgumentParser(description="Filter cold outreach from Pipedrive mail export")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    input_path: Path = args.input
    output_path: Path = args.output

    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    excluded = 0
    included_rows: list[dict[str, str]] = []

    with input_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            if should_exclude(row):
                excluded += 1
                continue
            otype = classify_outreach_type(row)
            if otype == "exclude_re_engagement":
                excluded += 1
                continue
            row["outreach_type"] = otype
            included_rows.append(row)

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(included_rows)

    included = len(included_rows)
    type_counts = Counter(r["outreach_type"] for r in included_rows)
    outcome_by_type: dict[str, Counter] = {}
    for r in included_rows:
        ot = r["outreach_type"]
        if ot not in outcome_by_type:
            outcome_by_type[ot] = Counter()
        outcome_by_type[ot][r["outcome"]] += 1

    print(f"Total input rows:  {total}")
    print(f"Excluded:          {excluded}")
    print(f"Included:          {included}")
    print()
    print("Breakdown by outreach_type:")
    for otype in sorted(type_counts, key=type_counts.get, reverse=True):
        print(f"  {otype:25s} {type_counts[otype]:>5d}")
    print()
    print("Breakdown by outcome within each type:")
    for otype in sorted(outcome_by_type, key=lambda k: type_counts[k], reverse=True):
        print(f"  {otype}:")
        for outcome in sorted(outcome_by_type[otype], key=outcome_by_type[otype].get, reverse=True):
            print(f"    {outcome:25s} {outcome_by_type[otype][outcome]:>5d}")


if __name__ == "__main__":
    main()
