"""Mapping between evaluation strategy archetypes and EDRA 5-slot rules."""

from __future__ import annotations

import io
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

STRATEGY_TO_RULE = {
    "personalized_opener": {
        "framing": "applied-curiosity",
        "tone": "direct",
        "opener_type": "reference-to-signal",
        "word_target": "medium",
        "ask_size": "trial",
        "reply_rate": 0.68,
        "description": "Bold ROI claim addressing their performance directly",
        "example": "Your digital marketing performance will increase by 20%...",
    },
    "tech_demo": {
        "framing": "applied-curiosity",
        "tone": "formal",
        "opener_type": "cold",
        "word_target": "long",
        "ask_size": "trial",
        "reply_rate": 0.64,
        "description": "Technology benefits pitch with AI/automation angle",
        "example": "AI brings many advantages to marketing, including the ability to...",
    },
    "company_pitch": {
        "framing": "knowledge-share",
        "tone": "warm",
        "opener_type": "cold",
        "word_target": "medium",
        "ask_size": "trial",
        "reply_rate": 0.62,
        "description": "Company intro emphasizing brand success stories",
        "example": "I'm Asya from SoMin.ai — a company that helps brands improve...",
    },
    "general_intro": {
        "framing": "knowledge-share",
        "tone": "warm",
        "opener_type": "reference-to-signal",
        "word_target": "medium",
        "ask_size": "trial",
        "reply_rate": 0.60,
        "description": "Team member intro referencing their prior interest/form fill",
        "example": "Hi, I'm Filipp from the SOMONITOR team! Thank you for your interest...",
    },
    "event_followup": {
        "framing": "follow-up-comment",
        "tone": "warm",
        "opener_type": "shared-context",
        "word_target": "medium",
        "ask_size": "intro",
        "reply_rate": 0.43,
        "description": "References prior interaction (event, LinkedIn, WhatsApp)",
        "example": "As discussed on LinkedIn, please find attached our deck...",
    },
    "vc_fundraising": {
        "framing": "strategic-alignment",
        "tone": "formal",
        "opener_type": "credential-anchor",
        "word_target": "long",
        "ask_size": "intro",
        "reply_rate": 0.23,
        "description": "VC/investment framing with academic credentials",
        "example": "Prof. Aleks Farseev here. I'm representing an Investible VC-backed startup...",
    },
    "mass_newsletter": {
        "framing": "peer-collaboration",
        "tone": "playful",
        "opener_type": "credential-anchor",
        "word_target": "long",
        "ask_size": "chat",
        "reply_rate": 0.09,
        "description": "Mass event invitation, no personalization",
        "example": "Prof. Aleks Farseev here! We organized a catch-up for Performance Marketers...",
    },
}

SLOT_NAMES = ["framing", "tone", "opener_type", "word_target", "ask_size"]


def print_mapping():
    print("=" * 90)
    print("  STRATEGY -> EDRA RULE MAPPING")
    print("=" * 90)

    sorted_strategies = sorted(STRATEGY_TO_RULE.items(), key=lambda x: -x[1]["reply_rate"])

    header = f"  {'Strategy':<22} {'Reply':>6}  {'framing':<20} {'tone':<10} {'opener':<20} {'length':<8} {'ask':<8}"
    print(f"\n{header}")
    print(f"  {'-'*22} {'-'*6}  {'-'*20} {'-'*10} {'-'*20} {'-'*8} {'-'*8}")

    for name, rule in sorted_strategies:
        print(
            f"  {name:<22} {rule['reply_rate']:>5.0%}  "
            f"{rule['framing']:<20} {rule['tone']:<10} "
            f"{rule['opener_type']:<20} {rule['word_target']:<8} {rule['ask_size']:<8}"
        )

    print(f"\n  Key insight from per-cluster best strategy (DR estimator):")
    print(f"  - Marketing Sales → personalized_opener (applied-curiosity + direct + reference-to-signal)")
    print(f"  - Investor Angel  → company_pitch (knowledge-share + warm + cold)")
    print(f"  - Founder         → general_intro (knowledge-share + warm + reference-to-signal)")
    print(f"  - Partner Venture → general_intro (knowledge-share + warm + reference-to-signal)")
    print(f"  - Marketing Mgr   → personalized_opener (applied-curiosity + direct + reference-to-signal)")
    print(f"  - Director CEO    → vc_fundraising (strategic-alignment + formal + credential-anchor)")
    print(f"  - Marketing Dir   → company_pitch (knowledge-share + warm + cold)")


if __name__ == "__main__":
    print_mapping()
