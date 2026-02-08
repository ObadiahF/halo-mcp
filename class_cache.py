"""
In-memory class cache with fuzzy ID resolution.

Populated automatically when list_classes runs. Allows tools to accept
course codes (e.g. "CST-323"), class names, slugs, or UUIDs — and
resolves them to the exact slug or UUID the Halo API expects.
"""

_classes: list[dict] = []


def populate(classes: list[dict]) -> None:
    """Replace cache with fresh class data from list_classes."""
    _classes.clear()
    _classes.extend(classes)


def resolve(ref: str) -> dict | None:
    """Fuzzy-match a class reference to a cached class.

    Matches against (in order): slug, UUID, courseCode, then substring of name.
    Returns the full class dict or None if no match.
    """
    ref_lower = ref.strip().lower()
    for c in _classes:
        if ref_lower in (c["slug"].lower(), c["id"].lower(), c["courseCode"].lower()):
            return c
    # Fallback: substring match on class name
    for c in _classes:
        if ref_lower in c["name"].lower():
            return c
    return None


def resolve_slug(ref: str) -> str:
    """Resolve ref to a slug. Returns ref unchanged if no match (passthrough)."""
    match = resolve(ref)
    return match["slug"] if match else ref


def resolve_id(ref: str) -> str:
    """Resolve ref to a UUID. Returns ref unchanged if no match (passthrough)."""
    match = resolve(ref)
    return match["id"] if match else ref
