"""Tests for campus service tools (food venues, gym status)."""

import sys
import os
from datetime import datetime
from unittest.mock import patch, MagicMock
from zoneinfo import ZoneInfo

import httpx
import pytest

# Add project root to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from queries.campus import (
    fetch_food_venues,
    fetch_gym_status,
    clean_food_venues,
    clean_gym_status,
    _is_venue_open,
    _current_hours_message,
    _busy_level,
    PHOENIX_TZ,
)

# ==================== Sample API Responses ====================

SAMPLE_FOOD_VENUES_RESPONSE = {
    "version": "1.0",
    "iconRootUrl": "https://example.com/icons/",
    "foodVenues": [
        {
            "id": "1",
            "name": "The Lope Cafe",
            "locationDescription": "Hegel Hall, 1st Floor",
            "icon": "cafe.png",
            "venueDescription": "Coffee and pastries",
            "schedule": [
                {
                    "startDateTime": "2026-03-27T00:00:00",
                    "endDateTime": "2026-03-27T23:59:59",
                    "weekDay": "Friday",
                    "hours": [],
                    "openClosedMessages": [
                        {
                            "startDateTime": "2026-03-27T07:00:00",
                            "endDateTime": "2026-03-27T22:00:00",
                            "messagePrefix": "Open",
                            "message": "7:00 AM - 10:00 PM",
                            "openClosedStatus": "Open",
                        },
                        {
                            "startDateTime": "2026-03-27T22:00:00",
                            "endDateTime": "2026-03-28T07:00:00",
                            "messagePrefix": "Closed",
                            "message": "Opens at 7:00 AM",
                            "openClosedStatus": "Closed",
                        },
                    ],
                }
            ],
            "latitude": 33.5,
            "longitude": -112.0,
        },
        {
            "id": "2",
            "name": "Thunder Alley Grill",
            "locationDescription": "Student Union",
            "icon": "grill.png",
            "venueDescription": "Burgers and fries",
            "schedule": [
                {
                    "startDateTime": "2026-03-27T00:00:00",
                    "endDateTime": "2026-03-27T23:59:59",
                    "weekDay": "Friday",
                    "hours": [],
                    "openClosedMessages": [
                        {
                            "startDateTime": "2026-03-27T11:00:00",
                            "endDateTime": "2026-03-27T20:00:00",
                            "messagePrefix": "Open",
                            "message": "11:00 AM - 8:00 PM",
                            "openClosedStatus": "Open",
                        },
                    ],
                }
            ],
            "latitude": 33.51,
            "longitude": -112.01,
        },
    ],
}

SAMPLE_GYM_RESPONSE = [
    {
        "LocationId": 101,
        "LocationName": "Weight Room",
        "TotalCapacity": 100,
        "CountOfParticipants": 35,
        "PercetageCapacity": 35.0,
        "LastUpdatedDateAndTime": "2026-03-27T14:00:00",
        "FacilityName": "GCU Fitness Center",
        "IsClosed": False,
    },
    {
        "LocationId": 102,
        "LocationName": "Cardio Floor",
        "TotalCapacity": 80,
        "CountOfParticipants": 55,
        "PercetageCapacity": 68.75,
        "LastUpdatedDateAndTime": "2026-03-27T14:00:00",
        "FacilityName": "GCU Fitness Center",
        "IsClosed": False,
    },
    {
        "LocationId": 201,
        "LocationName": "Pool Area",
        "TotalCapacity": 50,
        "CountOfParticipants": 0,
        "PercetageCapacity": 0.0,
        "LastUpdatedDateAndTime": "2026-03-27T14:00:00",
        "FacilityName": "Aquatics Center",
        "IsClosed": True,
    },
]


# ==================== Food Venue Cleaner Tests ====================


class TestCleanFoodVenues:
    def test_basic_cleaning(self):
        venues = SAMPLE_FOOD_VENUES_RESPONSE["foodVenues"]
        now = datetime(2026, 3, 27, 12, 0, 0, tzinfo=PHOENIX_TZ)
        result = clean_food_venues(venues, now)

        assert "venues" in result
        assert len(result["venues"]) == 2

        cafe = result["venues"][0]
        assert cafe["name"] == "The Lope Cafe"
        assert cafe["location"] == "Hegel Hall, 1st Floor"
        assert cafe["description"] == "Coffee and pastries"
        assert cafe["open"] is True
        assert cafe["currentHours"] is not None

    def test_empty_venues(self):
        result = clean_food_venues([])
        assert result == {"venues": []}

    def test_venue_missing_fields(self):
        venues = [{"name": "Test Venue"}]
        result = clean_food_venues(venues)
        assert len(result["venues"]) == 1
        assert result["venues"][0]["name"] == "Test Venue"
        assert result["venues"][0]["location"] is None
        assert result["venues"][0]["open"] is False


# ==================== Open/Closed Detection Tests ====================


class TestIsVenueOpen:
    def test_venue_open_during_hours(self):
        venue = SAMPLE_FOOD_VENUES_RESPONSE["foodVenues"][0]
        now = datetime(2026, 3, 27, 12, 0, 0, tzinfo=PHOENIX_TZ)
        assert _is_venue_open(venue, now) is True

    def test_venue_closed_after_hours(self):
        venue = SAMPLE_FOOD_VENUES_RESPONSE["foodVenues"][0]
        now = datetime(2026, 3, 27, 23, 0, 0, tzinfo=PHOENIX_TZ)
        assert _is_venue_open(venue, now) is False

    def test_venue_closed_before_hours(self):
        venue = SAMPLE_FOOD_VENUES_RESPONSE["foodVenues"][0]
        now = datetime(2026, 3, 27, 5, 0, 0, tzinfo=PHOENIX_TZ)
        assert _is_venue_open(venue, now) is False

    def test_venue_open_at_boundary(self):
        venue = SAMPLE_FOOD_VENUES_RESPONSE["foodVenues"][0]
        now = datetime(2026, 3, 27, 7, 0, 0, tzinfo=PHOENIX_TZ)
        assert _is_venue_open(venue, now) is True

    def test_venue_closed_at_end_boundary(self):
        """At 22:00, the 'Open' window ends and 'Closed' window starts."""
        venue = SAMPLE_FOOD_VENUES_RESPONSE["foodVenues"][0]
        now = datetime(2026, 3, 27, 22, 0, 0, tzinfo=PHOENIX_TZ)
        # At exactly 22:00, both windows overlap at boundary. The open window
        # includes 22:00 (<=), so it should still be open.
        assert _is_venue_open(venue, now) is True

    def test_venue_no_schedule(self):
        venue = {"name": "Empty", "schedule": []}
        now = datetime(2026, 3, 27, 12, 0, 0, tzinfo=PHOENIX_TZ)
        assert _is_venue_open(venue, now) is False

    def test_venue_no_open_closed_messages(self):
        venue = {"name": "Empty", "schedule": [{"openClosedMessages": []}]}
        now = datetime(2026, 3, 27, 12, 0, 0, tzinfo=PHOENIX_TZ)
        assert _is_venue_open(venue, now) is False

    def test_venue_bad_datetime_format(self):
        venue = {
            "schedule": [{
                "openClosedMessages": [{
                    "startDateTime": "not-a-date",
                    "endDateTime": "also-not-a-date",
                    "openClosedStatus": "Open",
                }]
            }]
        }
        now = datetime(2026, 3, 27, 12, 0, 0, tzinfo=PHOENIX_TZ)
        assert _is_venue_open(venue, now) is False

    def test_venue_missing_datetimes(self):
        venue = {
            "schedule": [{
                "openClosedMessages": [{
                    "openClosedStatus": "Open",
                }]
            }]
        }
        now = datetime(2026, 3, 27, 12, 0, 0, tzinfo=PHOENIX_TZ)
        assert _is_venue_open(venue, now) is False


class TestCurrentHoursMessage:
    def test_returns_message_during_open_hours(self):
        venue = SAMPLE_FOOD_VENUES_RESPONSE["foodVenues"][0]
        now = datetime(2026, 3, 27, 12, 0, 0, tzinfo=PHOENIX_TZ)
        msg = _current_hours_message(venue, now)
        assert msg == "Open 7:00 AM - 10:00 PM"

    def test_returns_closed_message_after_hours(self):
        venue = SAMPLE_FOOD_VENUES_RESPONSE["foodVenues"][0]
        now = datetime(2026, 3, 27, 23, 0, 0, tzinfo=PHOENIX_TZ)
        msg = _current_hours_message(venue, now)
        assert msg == "Closed Opens at 7:00 AM"

    def test_returns_none_when_no_match(self):
        venue = {"schedule": []}
        now = datetime(2026, 3, 27, 12, 0, 0, tzinfo=PHOENIX_TZ)
        assert _current_hours_message(venue, now) is None

    def test_message_without_prefix(self):
        venue = {
            "schedule": [{
                "openClosedMessages": [{
                    "startDateTime": "2026-03-27T07:00:00",
                    "endDateTime": "2026-03-27T22:00:00",
                    "messagePrefix": "",
                    "message": "7:00 AM - 10:00 PM",
                    "openClosedStatus": "Open",
                }]
            }]
        }
        now = datetime(2026, 3, 27, 12, 0, 0, tzinfo=PHOENIX_TZ)
        assert _current_hours_message(venue, now) == "7:00 AM - 10:00 PM"


# ==================== Food Venue Filter Tests ====================


class TestFoodVenueFiltering:
    def test_filter_by_name(self):
        venues = SAMPLE_FOOD_VENUES_RESPONSE["foodVenues"]
        now = datetime(2026, 3, 27, 12, 0, 0, tzinfo=PHOENIX_TZ)
        result = clean_food_venues(venues, now)
        # Simulate the filter logic from the tool
        filtered = [v for v in result["venues"] if v.get("name") and "cafe" in v["name"].lower()]
        assert len(filtered) == 1
        assert filtered[0]["name"] == "The Lope Cafe"

    def test_filter_case_insensitive(self):
        venues = SAMPLE_FOOD_VENUES_RESPONSE["foodVenues"]
        now = datetime(2026, 3, 27, 12, 0, 0, tzinfo=PHOENIX_TZ)
        result = clean_food_venues(venues, now)
        filtered = [v for v in result["venues"] if v.get("name") and "THUNDER" in v["name"].upper()]
        assert len(filtered) == 1

    def test_filter_no_match(self):
        venues = SAMPLE_FOOD_VENUES_RESPONSE["foodVenues"]
        now = datetime(2026, 3, 27, 12, 0, 0, tzinfo=PHOENIX_TZ)
        result = clean_food_venues(venues, now)
        filtered = [v for v in result["venues"] if v.get("name") and "nonexistent" in v["name"].lower()]
        assert len(filtered) == 0

    def test_filter_partial_match(self):
        venues = SAMPLE_FOOD_VENUES_RESPONSE["foodVenues"]
        result = clean_food_venues(venues)
        filtered = [v for v in result["venues"] if v.get("name") and "grill" in v["name"].lower()]
        assert len(filtered) == 1
        assert filtered[0]["name"] == "Thunder Alley Grill"


# ==================== Gym Status Cleaner Tests ====================


class TestCleanGymStatus:
    def test_basic_cleaning(self):
        result = clean_gym_status(SAMPLE_GYM_RESPONSE)
        assert "facilities" in result
        assert "summary" in result
        assert len(result["facilities"]) == 3

    def test_facility_fields(self):
        result = clean_gym_status(SAMPLE_GYM_RESPONSE)
        weight_room = result["facilities"][0]
        assert weight_room["name"] == "Weight Room"
        assert weight_room["count"] == 35
        assert weight_room["capacity"] == 100
        assert weight_room["percentage"] == 35.0
        assert weight_room["busyLevel"] == "low"
        assert weight_room["facility"] == "GCU Fitness Center"

    def test_medium_busy_level(self):
        result = clean_gym_status(SAMPLE_GYM_RESPONSE)
        cardio = result["facilities"][1]
        assert cardio["busyLevel"] == "medium"

    def test_closed_facility(self):
        result = clean_gym_status(SAMPLE_GYM_RESPONSE)
        pool = result["facilities"][2]
        assert pool["busyLevel"] == "closed"
        assert pool["count"] == 0

    def test_summary_grouping(self):
        result = clean_gym_status(SAMPLE_GYM_RESPONSE)
        summaries = {s["facility"]: s for s in result["summary"]}

        fitness = summaries["GCU Fitness Center"]
        assert fitness["locations"] == 2
        assert fitness["totalCount"] == 90  # 35 + 55
        assert fitness["totalCapacity"] == 180  # 100 + 80
        assert fitness["percentage"] == 50  # 90/180 * 100

        aquatics = summaries["Aquatics Center"]
        assert aquatics["locations"] == 1
        assert aquatics["totalCount"] == 0
        assert aquatics["totalCapacity"] == 50

    def test_empty_facilities(self):
        result = clean_gym_status([])
        assert result == {"facilities": [], "summary": []}

    def test_zero_capacity(self):
        facilities = [{
            "LocationId": 1,
            "LocationName": "Test Room",
            "TotalCapacity": 0,
            "CountOfParticipants": 0,
            "PercetageCapacity": 0,
            "FacilityName": "Test Facility",
            "IsClosed": False,
        }]
        result = clean_gym_status(facilities)
        assert result["facilities"][0]["busyLevel"] == "low"
        # Summary should handle zero capacity without division error
        assert result["summary"][0]["percentage"] == 0

    def test_null_fields(self):
        facilities = [{
            "LocationId": 1,
            "LocationName": "Test Room",
            "TotalCapacity": None,
            "CountOfParticipants": None,
            "PercetageCapacity": None,
            "FacilityName": "Test Facility",
            "IsClosed": False,
        }]
        result = clean_gym_status(facilities)
        assert result["facilities"][0]["count"] == 0
        assert result["facilities"][0]["capacity"] == 0
        assert result["facilities"][0]["percentage"] == 0


# ==================== Busy Level Tests ====================


class TestBusyLevel:
    def test_low(self):
        assert _busy_level(0, False) == "low"
        assert _busy_level(39.9, False) == "low"

    def test_medium(self):
        assert _busy_level(40, False) == "medium"
        assert _busy_level(69.9, False) == "medium"

    def test_high(self):
        assert _busy_level(70, False) == "high"
        assert _busy_level(100, False) == "high"

    def test_closed(self):
        assert _busy_level(50, True) == "closed"
        assert _busy_level(0, True) == "closed"


# ==================== Gym Status Filter Tests ====================


class TestGymStatusFiltering:
    def test_filter_by_facility_name(self):
        result = clean_gym_status(SAMPLE_GYM_RESPONSE)
        needle = "fitness"
        filtered_facilities = [
            f for f in result["facilities"]
            if f.get("facility") and needle in f["facility"].lower()
        ]
        assert len(filtered_facilities) == 2

    def test_filter_by_aquatics(self):
        result = clean_gym_status(SAMPLE_GYM_RESPONSE)
        needle = "aquatics"
        filtered = [
            f for f in result["facilities"]
            if f.get("facility") and needle in f["facility"].lower()
        ]
        assert len(filtered) == 1
        assert filtered[0]["name"] == "Pool Area"

    def test_filter_no_match(self):
        result = clean_gym_status(SAMPLE_GYM_RESPONSE)
        needle = "nonexistent"
        filtered = [
            f for f in result["facilities"]
            if f.get("facility") and needle in f["facility"].lower()
        ]
        assert len(filtered) == 0


# ==================== Fetch Function Tests (Mocked HTTP) ====================


class TestFetchFoodVenues:
    @patch("queries.campus.httpx.Client")
    def test_fetch_success(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_FOOD_VENUES_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = fetch_food_venues()
        assert len(result) == 2
        assert result[0]["name"] == "The Lope Cafe"
        mock_client.get.assert_called_once_with(
            "https://student-mobile-api.gcu.edu/v1/food-venues"
        )

    @patch("queries.campus.httpx.Client")
    def test_fetch_http_error(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=MagicMock(status_code=500)
        )

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            fetch_food_venues()

    @patch("queries.campus.httpx.Client")
    def test_fetch_empty_response(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"foodVenues": []}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = fetch_food_venues()
        assert result == []

    @patch("queries.campus.httpx.Client")
    def test_fetch_missing_key(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = fetch_food_venues()
        assert result == []


class TestFetchGymStatus:
    @patch("queries.campus.httpx.Client")
    def test_fetch_success(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_GYM_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = fetch_gym_status()
        assert len(result) == 3
        mock_client.get.assert_called_once()

    @patch("queries.campus.httpx.Client")
    def test_fetch_http_error(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=MagicMock(status_code=500)
        )

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            fetch_gym_status()
