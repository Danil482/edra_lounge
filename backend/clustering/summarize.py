

def summarize_profile_from_json(profile_json: dict, posts_json: list) -> str:
    """Build a deterministic embedding-optimized text summary from raw LinkedIn API JSON."""
    parts = []

    if headline := profile_json.get("headline"):
        parts.append(headline)

    if city := (profile_json.get("location") or {}).get("city"):
        parts.append(city)

    if bio := profile_json.get("bio"):
        parts.append(bio)

    experiences = profile_json.get("experiences") or []
    if isinstance(experiences, dict):
        experiences = experiences.get("data") or []
    for exp in experiences[:3]:
        exp_parts = []
        if title := exp.get("title"):
            exp_parts.append(title)
        if company := (exp.get("company") or {}).get("name"):
            exp_parts.append(f"at {company}")
        if desc := exp.get("description"):
            exp_parts.append(desc[:300])
        skills = (exp.get("skills") or [])[:10]
        if skills:
            exp_parts.append(f"Skills: {', '.join(skills)}")
        if exp_parts:
            parts.append(" | ".join(exp_parts))

    for post in (posts_json or [])[:3]:
        if text := (post.get("text") or "").strip():
            parts.append(f"Post: {text[:500]}")

    return " /// ".join(parts)


def summarize_profile_from_archetype(profile) -> str:
    """
    Build a deterministic embedding-optimized text summary from a synthetic Profile object.
    """

    from backend.schemas import Profile  # noqa: F401 — lazy import to avoid circular deps

    parts = []

    for value in (profile.role, profile.domain, profile.headline, profile.archetype_summary):
        if value:
            parts.append(value)

    for signal in (profile.recent_signals or [])[:3]:
        if signal:
            parts.append(signal)

    return " /// ".join(parts)
