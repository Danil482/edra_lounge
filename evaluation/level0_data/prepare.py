"""
Step 0 of the evaluation pipeline: load tier1+tier2 raw CSVs,
filter, clean, output a single clean.csv.

Usage:
    python -m evaluation.level0_data.prepare
    python -m evaluation.level0_data.prepare --tier1 path/to/tier1.csv --tier2 path/to/tier2.csv
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

DEFAULT_TIER1 = Path(r"C:\Users\dania\PycharmProjects\EDRA\data\eval_tier1_replied_mail.csv")
DEFAULT_TIER2 = Path(r"C:\Users\dania\PycharmProjects\EDRA\data\eval_tier2_no_reply_mail.csv")
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "clean.csv"

COLUMNS = [
    "email", "name", "organization", "job_title", "labels", "linkedin_url",
    "pipedrive_person_id", "thread_count", "outreach_subject", "outreach_snippet",
    "outreach_body_preview", "reply_snippet", "reply_body_preview", "outcome",
    "outreach_timestamp", "reply_timestamp", "thread_id", "outreach_message_id",
    "reply_message_id",
]


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def val(row: dict, key: str) -> str:
    return (row.get(key) or "").strip()


# ---------------------------------------------------------------------------
# Step 1: Combine + dedup
# ---------------------------------------------------------------------------

def combine_and_dedup(tier1: list[dict], tier2: list[dict]) -> list[dict]:
    combined = tier1 + tier2
    seen: set[str] = set()
    deduped: list[dict] = []
    for row in combined:
        email = val(row, "email").lower()
        if email and email not in seen:
            seen.add(email)
            deduped.append(row)
    return deduped


# ---------------------------------------------------------------------------
# Step 2: Filter cold outreach
# ---------------------------------------------------------------------------

COLD_SUBJECT_PATTERNS = [
    r"Platform Access Credentials",
    r"Access Credentials Inside",
    r"Thank You for the Call",
    r"thanks for the meeting",
    r"Thanks for meeting",
    r"Materials|Slides",
    r"Decks/Materials",
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
    r"Trial Sign-Up",
    r"Onboarding",
    r"Share Allotment",
    r"Investor Update",
    r"Sprint",
    r"ACTION REQUIRED",
    r"Prep for Tomorrow",
    r"Setup|Help Us Finalize",
]

COLD_SUBJECT_RE = re.compile(
    "|".join(COLD_SUBJECT_PATTERNS),
    re.IGNORECASE,
)

IMPORTANT_WORKSHOP_RE = re.compile(r"(?=.*IMPORTANT)(?=.*Workshop)", re.IGNORECASE)

RE_ENGAGEMENT_RE = re.compile(
    r"re-engaging|reaching back|Happy New Year|Personal Update",
    re.IGNORECASE,
)


def is_cold_excluded(row: dict) -> bool:
    subject = val(row, "outreach_subject")
    snippet = val(row, "outreach_snippet")

    if not subject and not snippet:
        return True

    if re.match(r"^(Re:|Fw:|Fwd:)", subject, re.IGNORECASE):
        return True

    if COLD_SUBJECT_RE.search(subject):
        return True

    if IMPORTANT_WORKSHOP_RE.search(subject):
        return True

    if RE_ENGAGEMENT_RE.search(subject):
        return True

    return False


# ---------------------------------------------------------------------------
# Step 3: Filter warm contacts
# ---------------------------------------------------------------------------

WARM_SUBJECT_PATTERNS = [
    r"meet you at", r"met you at", r"nice to meet", r"catch up at",
    r"meeting at", r"great to e-meet", r"nice meeting you", r"great meeting",
    r"Startup Village", r"ATx", r"MarTech", r"SXSW", r"Cannes",
    r"PI LIVE", r"conference", r"event", r"summit", r"huddle",
]

WARM_SNIPPET_PATTERNS = [
    r"meet you at", r"met you at", r"nice to meet", r"catch up at",
    r"great to e-meet", r"nice meeting you", r"great meeting",
    r"thanks to our friends", r"as discussed over", r"intro from",
    r"referred by", r"reference:", r"introduction from", r"Dentsu intro",
    r"leaving a request on our website",
    r"haven't logged in", r"haven't had a chance to log in",
    r"Your SOMONITOR Platform/account is Ready",
    r"Extending Your Trial", r"Setup Quick Intro", r"Complete Your Setup",
    r"Exploring Capabilities",
]

WARM_SUBJECT_RE = re.compile("|".join(WARM_SUBJECT_PATTERNS), re.IGNORECASE)
WARM_SNIPPET_RE = re.compile("|".join(WARM_SNIPPET_PATTERNS), re.IGNORECASE)


def is_warm_excluded(row: dict) -> bool:
    subject = val(row, "outreach_subject")
    snippet = val(row, "outreach_snippet")

    if WARM_SUBJECT_RE.search(subject):
        return True

    if WARM_SNIPPET_RE.search(snippet):
        return True

    return False


# ---------------------------------------------------------------------------
# Step 4: Filter autoreplies
# ---------------------------------------------------------------------------

EXPIRED_RE = re.compile(r"^\s*\?Expires=0\s*$")

BOUNCE_PATTERNS = [
    r"no longer with", r"left the company", r"delivery fail",
    r"Undeliverable", r"Mail delivery failed", r"did not reach",
    r"mailbox unavailable", r"address rejected", r"user unknown",
    r"does not exist", r"no such user", r"mailbox not found",
    r"account has been disabled", r"account is disabled",
    r"permanent failure", r"550 ", r"553 ", r"invalid recipient",
]
BOUNCE_RE = re.compile("|".join(BOUNCE_PATTERNS), re.IGNORECASE)

AUTOREPLY_PATTERNS = [
    r"out of office", r"\bOOO\b", r"on leave", r"on vacation",
    r"away from office", r"will be back", r"auto-reply", r"auto reply",
    r"automatic reply", r"autoreply", r"currently unavailable",
    r"limited access to email", r"away from my desk",
    r"out of the office", r"maternity leave", r"paternity leave",
    r"sabbatical", r"annual leave", r"I am away", r"I'm away",
    r"currently out", r"not in the office",
]
AUTOREPLY_RE = re.compile("|".join(AUTOREPLY_PATTERNS), re.IGNORECASE)

ENGAGEMENT_PATTERNS = [
    r"let's connect", r"interested", r"sounds good", r"love to",
    r"would like to", r"happy to", r"schedule a call", r"set up a meeting",
    r"tell me more", r"send me", r"can you share",
]
ENGAGEMENT_RE = re.compile("|".join(ENGAGEMENT_PATTERNS), re.IGNORECASE)


def classify_reply(row: dict) -> str | None:
    """Returns None to keep, or a reason string to exclude."""
    if val(row, "outcome") != "reply":
        return None

    reply_text = val(row, "reply_snippet") + " " + val(row, "reply_body_preview")
    reply_text = reply_text.strip()

    if not reply_text:
        return None

    if EXPIRED_RE.match(reply_text):
        return None

    if BOUNCE_RE.search(reply_text):
        return "bounce"

    if AUTOREPLY_RE.search(reply_text) and not ENGAGEMENT_RE.search(reply_text):
        return "autoreply"

    return None


# ---------------------------------------------------------------------------
# Step 5: Filter usable text
# ---------------------------------------------------------------------------

def has_usable_text(row: dict) -> bool:
    snippet = val(row, "outreach_snippet")
    if not snippet:
        return False
    if snippet == "?Expires=0":
        return False
    return True


# ---------------------------------------------------------------------------
# Step 6: Clean snippet text
# ---------------------------------------------------------------------------

URL_RE = re.compile(r"https?://\S+")

SIGNATURE_RE = re.compile(
    r"\b(Best Regards|Kind Regards|Cheers|Thanks,|Thank you,).*",
    re.IGNORECASE | re.DOTALL,
)

# Mojibake from Windows-1252 interpreted as UTF-8
SMART_REPLACEMENTS = [
    ("â", "'"),   # right single quote
    ("â", "'"),   # left single quote
    ("â", '"'),   # left double quote
    ("â", '"'),   # right double quote
    ("â", "-"),   # en dash
    ("â", "-"),   # em dash
    ("â¦", "..."), # ellipsis
    ("’", "'"),
    ("‘", "'"),
    ("“", '"'),
    ("”", '"'),
    ("–", "-"),
    ("—", "-"),
    ("…", "..."),
    # Pipedrive-specific mojibake seen in real data
    ("ï¿½", ""),
    ("�\x9c", ""),
    ("�\x9d", ""),
    ("�\x99", "'"),
]

NON_ASCII_RE = re.compile(r"[^\x00-\x7F]")


def clean_snippet(text: str) -> str:
    text = URL_RE.sub("", text)
    text = SIGNATURE_RE.sub("", text)

    for old, new in SMART_REPLACEMENTS:
        text = text.replace(old, new)

    text = NON_ASCII_RE.sub("", text)
    text = " ".join(text.split())
    text = text[:200]
    return text.strip()


# ---------------------------------------------------------------------------
# Step 7: Remove junk content
# ---------------------------------------------------------------------------

def is_junk(cleaned: str) -> bool:
    if cleaned.lower().startswith("join with google meet"):
        return True
    return False


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(
    n_tier1: int,
    n_tier2: int,
    n_combined: int,
    n_deduped: int,
    n_cold: int,
    n_warm: int,
    n_autoreply: int,
    n_usable: int,
    n_short: int,
    n_junk: int,
    final_rows: list[dict],
) -> None:
    from collections import Counter

    n_final = len(final_rows)

    print("=" * 60)
    print("  PREPARE PIPELINE REPORT")
    print("=" * 60)
    print(f"\n  Input:")
    print(f"    Tier 1 (replied):     {n_tier1:>6}")
    print(f"    Tier 2 (no reply):    {n_tier2:>6}")
    print(f"    Combined:             {n_combined:>6}")
    print(f"    After dedup:          {n_deduped:>6}  (removed {n_combined - n_deduped})")

    print(f"\n  Excluded:")
    print(f"    Cold filter:          {n_cold:>6}")
    print(f"    Warm filter:          {n_warm:>6}")
    print(f"    Autoreply filter:     {n_autoreply:>6}")
    print(f"    No usable text:       {n_usable:>6}")
    print(f"    Too short (<20ch):    {n_short:>6}")
    print(f"    Junk content:         {n_junk:>6}")
    total_excluded = n_cold + n_warm + n_autoreply + n_usable + n_short + n_junk
    print(f"    ──────────────────────────")
    print(f"    Total excluded:       {total_excluded:>6}")

    print(f"\n  Output:                 {n_final:>6}")

    outcome_counts = Counter(val(r, "outcome") for r in final_rows)
    print(f"\n  Outcome distribution:")
    for outcome, count in outcome_counts.most_common():
        pct = 100 * count / n_final if n_final else 0
        print(f"    {outcome:<20} {count:>6}  ({pct:.1f}%)")

    subject_counts = Counter(val(r, "outreach_subject") for r in final_rows)
    print(f"\n  Top 5 outreach subjects:")
    for subject, count in subject_counts.most_common(5):
        display = subject[:70] if len(subject) > 70 else subject
        print(f"    {count:>4}  {display}")

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 0: load tier1+tier2 CSVs, filter, clean, output clean.csv"
    )
    parser.add_argument("--tier1", type=Path, default=DEFAULT_TIER1)
    parser.add_argument("--tier2", type=Path, default=DEFAULT_TIER2)
    args = parser.parse_args()

    tier1_path: Path = args.tier1
    tier2_path: Path = args.tier2

    for label, path in [("tier1", tier1_path), ("tier2", tier2_path)]:
        if not path.exists():
            print(f"ERROR: {label} file not found: {path}", file=sys.stderr)
            sys.exit(1)

    tier1_rows = load_csv(tier1_path)
    tier2_rows = load_csv(tier2_path)
    n_tier1 = len(tier1_rows)
    n_tier2 = len(tier2_rows)
    n_combined = n_tier1 + n_tier2

    rows = combine_and_dedup(tier1_rows, tier2_rows)
    n_deduped = len(rows)

    # Step 2: cold outreach filter
    before = len(rows)
    rows = [r for r in rows if not is_cold_excluded(r)]
    n_cold = before - len(rows)

    # Step 3: warm contacts filter
    before = len(rows)
    rows = [r for r in rows if not is_warm_excluded(r)]
    n_warm = before - len(rows)

    # Step 4: autoreply filter
    before = len(rows)
    rows = [r for r in rows if classify_reply(r) is None]
    n_autoreply = before - len(rows)

    # Step 5: usable text filter
    before = len(rows)
    rows = [r for r in rows if has_usable_text(r)]
    n_usable = before - len(rows)

    # Step 6: clean snippet + length filter
    before = len(rows)
    for row in rows:
        row["clean_snippet"] = clean_snippet(val(row, "outreach_snippet"))
    rows = [r for r in rows if len(r["clean_snippet"]) >= 20]
    n_short = before - len(rows)

    # Step 7: junk content filter
    before = len(rows)
    rows = [r for r in rows if not is_junk(r["clean_snippet"])]
    n_junk = before - len(rows)

    print_report(
        n_tier1, n_tier2, n_combined, n_deduped,
        n_cold, n_warm, n_autoreply, n_usable, n_short, n_junk,
        rows,
    )

    output_fields = COLUMNS + ["clean_snippet"]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=output_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved {len(rows)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
