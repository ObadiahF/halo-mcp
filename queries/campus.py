"""
Campus service fetch functions and cleaners (unauthenticated APIs).

These endpoints are public and do not require Halo auth tokens,
so we use httpx directly instead of the HaloRequest builder.
"""

from datetime import datetime

import httpx
from zoneinfo import ZoneInfo

PHOENIX_TZ = ZoneInfo("America/Phoenix")

FOOD_VENUES_URL = "https://student-mobile-api.gcu.edu/v1/food-venues"
GYM_STATUS_URL = (
    "https://goboardapi.azurewebsites.net/api/FacilityCount/GetCountsByAccount"
    "?AccountAPIKey=49069907-7e82-4855-b98b-967471c0d779"
)


# ==================== Fetch Functions ====================


def fetch_food_venues() -> list[dict]:
    """Fetch food venue data from the GCU student mobile API."""
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(FOOD_VENUES_URL)
        resp.raise_for_status()
        return resp.json().get("foodVenues", [])


def fetch_gym_status() -> list[dict]:
    """Fetch gym facility counts from the GoBoard API."""
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(GYM_STATUS_URL)
        resp.raise_for_status()
        return resp.json()


# ==================== Cleaners ====================


def _is_venue_open(venue: dict, now: datetime | None = None) -> bool:
    """Determine if a food venue is currently open based on its schedule."""
    if now is None:
        now = datetime.now(PHOENIX_TZ)

    for entry in venue.get("schedule", []):
        for msg in entry.get("openClosedMessages", []):
            start = msg.get("startDateTime")
            end = msg.get("endDateTime")
            status = msg.get("openClosedStatus")
            if not start or not end:
                continue
            try:
                start_dt = datetime.fromisoformat(start).replace(tzinfo=PHOENIX_TZ)
                end_dt = datetime.fromisoformat(end).replace(tzinfo=PHOENIX_TZ)
            except (ValueError, TypeError):
                continue
            if start_dt <= now <= end_dt and status and status.lower() == "open":
                return True
    return False


def _current_hours_message(venue: dict, now: datetime | None = None) -> str | None:
    """Get the current hours message for a venue."""
    if now is None:
        now = datetime.now(PHOENIX_TZ)

    for entry in venue.get("schedule", []):
        for msg in entry.get("openClosedMessages", []):
            start = msg.get("startDateTime")
            end = msg.get("endDateTime")
            if not start or not end:
                continue
            try:
                start_dt = datetime.fromisoformat(start).replace(tzinfo=PHOENIX_TZ)
                end_dt = datetime.fromisoformat(end).replace(tzinfo=PHOENIX_TZ)
            except (ValueError, TypeError):
                continue
            if start_dt <= now <= end_dt:
                prefix = msg.get("messagePrefix", "")
                message = msg.get("message", "")
                return f"{prefix} {message}".strip() if prefix else message
    return None


def clean_food_venues(venues: list[dict], now: datetime | None = None) -> dict:
    """Clean food venues response for token efficiency."""
    cleaned = []
    for v in venues:
        cleaned.append({
            "name": v.get("name"),
            "location": v.get("locationDescription"),
            "description": v.get("venueDescription"),
            "open": _is_venue_open(v, now),
            "currentHours": _current_hours_message(v, now),
        })
    return {"venues": cleaned}


def _busy_level(percentage: float, is_closed: bool) -> str:
    """Categorize busyness from facility percentage."""
    if is_closed:
        return "closed"
    if percentage < 40:
        return "low"
    if percentage < 70:
        return "medium"
    return "high"


def clean_gym_status(facilities: list[dict]) -> dict:
    """Clean gym status response for token efficiency."""
    cleaned = []
    groups: dict[str, list[dict]] = {}

    for f in facilities:
        is_closed = bool(f.get("IsClosed", False))
        capacity = f.get("TotalCapacity", 0) or 0
        count = f.get("CountOfParticipants", 0) or 0
        # API has a typo: "PercetageCapacity"
        percentage = f.get("PercetageCapacity", 0) or 0

        entry = {
            "name": f.get("LocationName"),
            "count": count,
            "capacity": capacity,
            "percentage": percentage,
            "busyLevel": _busy_level(percentage, is_closed),
            "facility": f.get("FacilityName"),
        }
        cleaned.append(entry)

        # Group by facility
        facility_name = f.get("FacilityName", "Other")
        groups.setdefault(facility_name, []).append(entry)

    summaries = []
    for facility_name, locations in groups.items():
        total_count = sum(loc["count"] for loc in locations)
        total_capacity = sum(loc["capacity"] for loc in locations)
        summaries.append({
            "facility": facility_name,
            "locations": len(locations),
            "totalCount": total_count,
            "totalCapacity": total_capacity,
            "percentage": round(total_count / total_capacity * 100) if total_capacity else 0,
        })

    return {"facilities": cleaned, "summary": summaries}
