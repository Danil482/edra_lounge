"""
Remove auto-replies from cold outreach data.

Usage:
    python -m evaluation.level0_data.filter_autoreplies
    python -m evaluation.level0_data.filter_autoreplies --input path/to/input.csv --output path/to/output.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

DEFAULT_INPUT = Path(__file__).resolve().parent.parent / "data" / "cold_outreach.csv"
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "data" / "cold_outreach_clean.csv"

INPUT_COLUMNS = [
    "email", "name", "organization", "job_title", "labels", "linkedin_url",
    "pipedrive_person_id", "thread_count", "outreach_subject", "outreach_snippet",
    "outreach_body_preview", "reply_snippet", "reply_body_preview", "outcome",
    "outreach_timestamp", "reply_timestamp", "thread_id", "outreach_message_id",
    "reply_message_id", "outreach_type",
]

OUTPUT_COLUMNS = INPUT_COLUMNS + ["reply_quality"]

EXPIRED_RE = re.compile(r"^\s*\?Expires=0\s*$")

AUTO_REPLY_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"out[\s\-]+of[\s\-]+office",
        r"\bOOO\b",
        r"on\s+(?:annual\s+)?leave",
        r"on\s+sick\s+leave",
        r"on\s+parental\s+leave",
        r"on\s+vacation",
        r"on\s+holiday",
        r"away\s+from\s+(?:the\s+)?office",
        r"currently\s+(?:out|away|unavailable)",
        r"will\s+be\s+back",
        r"will\s+return",
        r"returning\s+on",
        r"limited\s+access\s+to\s+email",
        r"maternity",
        r"paternity",
        r"auto[\s\-]+repl(?:y|ies)",
        r"auto[\s\-]+response",
        r"automatic\s+repl(?:y|ies)",
        r"automated\s+(?:response|message|reply)",
        r"this\s+is\s+an\s+auto",
    ]
]

BOUNCE_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"no\s+longer\s+with",
        r"no\s+longer\s+work",
        r"left\s+the\s+company",
        r"moved\s+on\s+from",
        r"this\s+mailbox\s+is",
        r"delivery\s+fail",
        r"Undeliverable",
        r"Mail\s+delivery\s+failed",
        r"Address\s+not\s+found",
        r"unsubscribe",
        r"has\s+left\b",
        r"have\s+been\s+leav(?:ing|ed)",
        r"resigned",
        r"departed",
        r"please\s+contact\s+\S+.*?\s+for\s+",
    ]
]

ENGAGEMENT_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"let'?s\s+(?:get\s+in\s+touch|connect|catch\s+up|chat|talk|meet|schedule|set\s+up)",
        r"available\s+(?:on|for|at)\b",
        r"booked\s+a\s+(?:slot|call|meeting|time)",
        r"\binterested\b",
        r"sounds\s+(?:good|great|interesting)",
        r"would\s+love",
        r"happy\s+to\b",
        r"let\s+me\s+(?:check|know|aim|get\s+back)",
        r"I'?ll\s+(?:check|forward|share|send|look)",
        r"send\s+me\b",
        r"call\s+me\b",
        r"schedule\s+a\b",
        r"put\s+(?:you\s+)?in\s+touch",
        r"can\s+we\b",
        r"could\s+(?:you|we)\b",
        r"when\s+are\s+you",
        r"when\s+is\b",
        r"when\s+would\b",
        r"looking\s+forward",
        r"free\s+between",
        r"works\s+for\b",
        r"copied\b",
        r"\bcc'?d\b",
        r"forwarded\b",
        r"will\s+reach\s+out",
        r"they\s+will\s+reach\s+out",
    ]
]


def _matches_any(text: str, patterns: list[re.Pattern]) -> bool:
    return any(p.search(text) for p in patterns)


def classify_reply(reply_text: str) -> str:
    if not reply_text or EXPIRED_RE.match(reply_text):
        return "expired"

    has_bounce = _matches_any(reply_text, BOUNCE_PATTERNS)
    if has_bounce:
        return "auto"

    has_auto = _matches_any(reply_text, AUTO_REPLY_PATTERNS)
    if not has_auto:
        return "genuine"

    has_engagement = _matches_any(reply_text, ENGAGEMENT_PATTERNS)
    return "genuine" if has_engagement else "auto"


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove auto-replies from cold outreach data")
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
    removed = 0
    kept_rows: list[dict[str, str]] = []

    with input_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1

            if row["outcome"] != "reply":
                row["reply_quality"] = "no_reply"
                kept_rows.append(row)
                continue

            reply_snippet = row.get("reply_snippet", "") or ""
            reply_body = row.get("reply_body_preview", "") or ""
            combined = (reply_snippet + " " + reply_body).strip()

            classification = classify_reply(combined)

            if classification == "auto":
                removed += 1
                continue

            row["reply_quality"] = classification
            kept_rows.append(row)

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(kept_rows)

    kept = len(kept_rows)
    quality_counts = Counter(r["reply_quality"] for r in kept_rows)
    type_counts = Counter(r["outreach_type"] for r in kept_rows)
    quality_by_type: dict[str, Counter] = {}
    for r in kept_rows:
        ot = r["outreach_type"]
        if ot not in quality_by_type:
            quality_by_type[ot] = Counter()
        quality_by_type[ot][r["reply_quality"]] += 1

    print(f"Total input rows:  {total}")
    print(f"Removed (auto):    {removed}")
    print(f"Kept:              {kept}")
    print()
    print("Breakdown by reply_quality:")
    for quality in sorted(quality_counts, key=quality_counts.get, reverse=True):
        print(f"  {quality:25s} {quality_counts[quality]:>5d}")
    print()
    print("Breakdown by outreach_type:")
    for otype in sorted(type_counts, key=type_counts.get, reverse=True):
        print(f"  {otype:25s} {type_counts[otype]:>5d}")
    print()
    print("Breakdown by reply_quality within each type:")
    for otype in sorted(quality_by_type, key=lambda k: type_counts[k], reverse=True):
        print(f"  {otype}:")
        for quality in sorted(quality_by_type[otype], key=quality_by_type[otype].get, reverse=True):
            print(f"    {quality:25s} {quality_by_type[otype][quality]:>5d}")


if __name__ == "__main__":
    main()
