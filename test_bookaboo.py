"""
Bookaboo test suite.

Covers:
  - NLP parser: party size, date, time, restaurant name extraction
  - Date/time formatting helpers
  - Ontopo client: slot selection, availability parsing, checkout URL
  - Calendar integration: URL generation, event building
  - Notifications: smoke tests
  - Bookaboo orchestrator: mock API end-to-end
  - FastAPI server: /health, /reserve, /search, /availability, /reservations
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# NLP parser tests
# ---------------------------------------------------------------------------

from nlp_parser import parse_reservation_request


class TestNlpParser:
    """Tests for natural-language request parsing."""

    _NOW = datetime(2025, 3, 5, 12, 0, 0)  # Wednesday

    def _parse(self, text: str) -> Any:
        return parse_reservation_request(text, now=self._NOW)

    # --- party size ----------------------------------------------------------

    def test_party_size_explicit_people(self):
        req = self._parse("reservation for 4 people tonight 8pm at Prozdor")
        assert req.party_size == 4

    def test_party_size_default_two(self):
        req = self._parse("book tonight 8pm at Prozdor")
        assert req.party_size == 2

    def test_party_size_party_of(self):
        req = self._parse("party of 5 at Machneyuda tomorrow 7pm")
        assert req.party_size == 5

    def test_party_size_table_for(self):
        req = self._parse("table for 3 at Taizu next Friday 9pm")
        assert req.party_size == 3

    def test_party_size_inline_number(self):
        req = self._parse("book 2 tonight 8pm at Prozdor")
        assert req.party_size == 2

    def test_party_size_six_guests(self):
        req = self._parse("6 guests at HaBasta on Saturday")
        assert req.party_size == 6

    # --- date ----------------------------------------------------------------

    def test_date_tonight(self):
        req = self._parse("book tonight 8pm at Prozdor")
        assert req.date == date(2025, 3, 5)

    def test_date_today(self):
        req = self._parse("book today 8pm at Prozdor")
        assert req.date == date(2025, 3, 5)

    def test_date_tomorrow(self):
        req = self._parse("book tomorrow 7pm at Prozdor")
        assert req.date == date(2025, 3, 6)

    def test_date_next_friday(self):
        req = self._parse("next Friday 9pm at Taizu for 2")
        # From Wednesday 5 March → next Friday = 7 March
        assert req.date == date(2025, 3, 7)

    def test_date_next_saturday(self):
        req = self._parse("next Saturday 8pm at Prozdor")
        assert req.date == date(2025, 3, 8)

    def test_date_weekday_this_week(self):
        # Thursday is 2 days from Wednesday; should give this Thursday
        req = self._parse("Thursday 8pm at Prozdor")
        assert req.date == date(2025, 3, 6)

    def test_date_iso_format(self):
        req = self._parse("book on 2025-03-15 at 8pm at Prozdor for 2")
        assert req.date == date(2025, 3, 15)

    # --- time ----------------------------------------------------------------

    def test_time_8pm(self):
        req = self._parse("tonight 8pm at Prozdor")
        assert req.time_str == "20:00"

    def test_time_730pm(self):
        req = self._parse("tomorrow 7:30pm at Machneyuda")
        assert req.time_str == "19:30"

    def test_time_24h(self):
        req = self._parse("book on 2025-03-10 at 20:30 at Prozdor")
        assert req.time_str == "20:30"

    def test_time_default_when_missing(self):
        req = self._parse("book tomorrow at Prozdor for 2")
        assert req.time_str == "20:00"

    def test_time_noon(self):
        req = self._parse("lunch at 12pm at HaBasta")
        assert req.time_str == "12:00"

    # --- restaurant name -----------------------------------------------------

    def test_restaurant_at_prozdor(self):
        req = self._parse("book 2 tonight 8pm at Prozdor")
        assert req.restaurant_name.lower() == "prozdor"

    def test_restaurant_at_machneyuda(self):
        req = self._parse("reservation for 4 tomorrow 7:30pm at Machneyuda")
        assert req.restaurant_name.lower() == "machneyuda"

    def test_restaurant_multi_word(self):
        req = self._parse("dinner next Friday 9pm, 3 people, at Taizu Bar")
        assert "taizu" in req.restaurant_name.lower()

    def test_restaurant_at_end_of_sentence(self):
        req = self._parse("book table tonight 8pm for 2 at Catit")
        assert req.restaurant_name.lower() == "catit"

    # --- formatting helpers --------------------------------------------------

    def test_date_yyyymmdd(self):
        req = self._parse("tonight 8pm at Prozdor")
        assert req.date_yyyymmdd() == "20250305"

    def test_time_hhmm(self):
        req = self._parse("tonight 8pm at Prozdor")
        assert req.time_hhmm() == "2000"

    def test_display_date(self):
        req = self._parse("tonight 8pm at Prozdor")
        assert req.display_date() == "Wednesday, March 5"


# ---------------------------------------------------------------------------
# Ontopo client unit tests (no network)
# ---------------------------------------------------------------------------

from ontopo_client import OntopoClient


class TestOntopoClient:
    """Tests for OntopoClient helper methods (no I/O)."""

    def _client(self) -> OntopoClient:
        c = OntopoClient()
        c._token = "test_token"
        return c

    def test_build_checkout_url_contains_venue_id(self):
        c = self._client()
        url = c.build_checkout_url("venue123", "20250307", "2000", 2)
        assert "venue_id=venue123" in url

    def test_build_checkout_url_contains_date(self):
        c = self._client()
        url = c.build_checkout_url("venue123", "20250307", "2000", 2)
        assert "date=20250307" in url

    def test_build_checkout_url_contains_time(self):
        c = self._client()
        url = c.build_checkout_url("venue123", "20250307", "2000", 2)
        assert "time=2000" in url

    def test_build_checkout_url_contains_party_size(self):
        c = self._client()
        url = c.build_checkout_url("venue123", "20250307", "2000", 4)
        assert "party_size=4" in url

    def test_build_checkout_url_with_slot_id(self):
        c = self._client()
        url = c.build_checkout_url("venue123", "20250307", "2000", 2, slot_id="slot99")
        assert "slot_id=slot99" in url

    def test_parse_availability_slots(self):
        c = self._client()
        raw = {
            "slots": [
                {"time": "1930", "id": "s1"},
                {"time": "2000", "id": "s2"},
                {"time": "2030", "id": "s3"},
            ]
        }
        result = c.parse_availability_response(raw)
        assert result["available"] is True
        assert len(result["slots"]) == 3
        assert result["slots"][0]["time"] == "1930"

    def test_parse_availability_waiting_list(self):
        c = self._client()
        raw = {"slots": [], "waitingList": True}
        result = c.parse_availability_response(raw)
        assert result["waiting_list"] is True

    def test_parse_availability_phone_needed(self):
        c = self._client()
        raw = {"slots": [], "phoneNeeded": True, "phoneNumber": "+972-3-555-0000"}
        result = c.parse_availability_response(raw)
        assert result["phone_needed"] is True
        assert result["phone_number"] == "+972-3-555-0000"

    def test_pick_best_slot_closest(self):
        c = self._client()
        slots = [
            {"time": "1900", "slot_id": "a"},
            {"time": "2000", "slot_id": "b"},
            {"time": "2100", "slot_id": "c"},
        ]
        best = c.pick_best_slot(slots, "2015")
        assert best is not None
        assert best["slot_id"] == "b"

    def test_pick_best_slot_empty(self):
        c = self._client()
        assert c.pick_best_slot([], "2000") is None

    def test_pick_best_slot_single(self):
        c = self._client()
        slots = [{"time": "2000", "slot_id": "x"}]
        best = c.pick_best_slot(slots, "1900")
        assert best["slot_id"] == "x"


# ---------------------------------------------------------------------------
# Calendar integration tests
# ---------------------------------------------------------------------------

from calendar_integration import build_event, generate_google_calendar_url


class TestCalendarIntegration:
    """Tests for Google Calendar URL generation and event building."""

    def test_google_calendar_url_contains_restaurant(self):
        url = generate_google_calendar_url(
            restaurant_name="Prozdor",
            restaurant_address="Tel Aviv",
            date_yyyymmdd="20250307",
            time_hhmm="20:00",
            party_size=2,
        )
        assert "calendar.google.com" in url
        assert "Prozdor" in url

    def test_google_calendar_url_contains_date(self):
        url = generate_google_calendar_url(
            restaurant_name="Prozdor",
            restaurant_address="Tel Aviv",
            date_yyyymmdd="20250307",
            time_hhmm="20:00",
            party_size=2,
        )
        assert "20250307" in url

    def test_google_calendar_url_is_template_action(self):
        url = generate_google_calendar_url(
            restaurant_name="Prozdor",
            restaurant_address="Tel Aviv",
            date_yyyymmdd="20250307",
            time_hhmm="20:00",
            party_size=2,
        )
        assert "action=TEMPLATE" in url

    def test_build_event_structure(self):
        event = build_event(
            restaurant_name="Machneyuda",
            restaurant_address="Jerusalem",
            date_yyyymmdd="20250307",
            time_hhmm="19:30",
            party_size=4,
            checkout_url="https://example.com/checkout",
        )
        assert event["restaurant"] == "Machneyuda"
        assert event["party_size"] == 4
        assert "2025-03-07T19:30" in event["start"]
        assert "2025-03-07T21:30" in event["end"]

    def test_build_event_id_uniqueness(self):
        e1 = build_event("Prozdor", "TA", "20250307", "20:00", 2)
        e2 = build_event("Machneyuda", "JLM", "20250307", "20:00", 2)
        assert e1["id"] != e2["id"]


# ---------------------------------------------------------------------------
# Notifications smoke tests
# ---------------------------------------------------------------------------

from notifications import (
    notify_error,
    notify_no_availability,
    notify_phone_needed,
    notify_success,
    notify_waiting_list,
)


class TestNotifications:
    """Smoke tests – just ensure notification functions don't raise."""

    def test_notify_success(self, capsys):
        notify_success(
            restaurant_name="Prozdor",
            restaurant_address="Tel Aviv",
            display_date="Thursday, March 7",
            time="20:00",
            party_size=2,
            checkout_url="https://ontopo.co.il/reservation/checkout?venue_id=1",
            calendar_url="https://calendar.google.com/calendar/render?action=TEMPLATE",
        )
        captured = capsys.readouterr()
        assert "Prozdor" in captured.out
        assert "checkout" in captured.out.lower() or "https://" in captured.out

    def test_notify_phone_needed(self, capsys):
        notify_phone_needed(
            restaurant_name="Machneyuda",
            restaurant_address="Jerusalem",
            display_date="Friday, March 8",
            time="19:30",
            party_size=4,
            phone_number="+972-2-555-0000",
            caller_name="Devin Pillemer",
            caller_phone="+972-50-724-2120",
        )
        captured = capsys.readouterr()
        assert "Devin Pillemer" in captured.out
        assert "+972-50-724-2120" in captured.out

    def test_notify_waiting_list(self, capsys):
        notify_waiting_list(
            restaurant_name="Taizu",
            display_date="Saturday, March 9",
            time="21:00",
            party_size=2,
        )
        captured = capsys.readouterr()
        assert "Taizu" in captured.out

    def test_notify_error(self, capsys):
        notify_error("Something went wrong", suggestion="Try again.")
        captured = capsys.readouterr()
        assert "Something went wrong" in captured.out

    def test_notify_no_availability(self, capsys):
        notify_no_availability("Prozdor", "Thursday, March 7", "20:00", 2)
        captured = capsys.readouterr()
        assert "Prozdor" in captured.out


# ---------------------------------------------------------------------------
# Bookaboo orchestrator tests (mocked Ontopo API)
# ---------------------------------------------------------------------------

from bookaboo import reserve as bookaboo_reserve


@pytest.mark.asyncio
class TestBookabooOrchestrator:
    """End-to-end orchestrator tests with mocked Ontopo API."""

    _NOW = datetime(2025, 3, 5, 12, 0, 0)

    def _mock_client(self):
        """Return a configured mock OntopoClient."""
        mock = AsyncMock()
        mock.__aenter__ = AsyncMock(return_value=mock)
        mock.__aexit__ = AsyncMock(return_value=None)

        mock.search_venues = AsyncMock(return_value=[
            {
                "id": "venue_prozdor",
                "name": "Prozdor",
                "address": "Ibn Gabirol 71, Tel Aviv",
                "area": "Tel Aviv",
            }
        ])
        mock.check_availability = AsyncMock(return_value={
            "slots": [
                {"time": "1930", "id": "s1"},
                {"time": "2000", "id": "s2"},
                {"time": "2030", "id": "s3"},
            ]
        })
        mock.parse_availability_response = OntopoClient().parse_availability_response.__func__
        mock.pick_best_slot = OntopoClient().pick_best_slot.__func__
        mock.build_checkout_url = MagicMock(return_value="https://ontopo.co.il/reservation/checkout?venue_id=venue_prozdor")
        return mock

    async def test_successful_reservation(self):
        with patch("bookaboo.OntopoClient") as MockClient, \
             patch("bookaboo.save_event"):
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.search_venues = AsyncMock(return_value=[
                {"id": "v1", "name": "Prozdor", "address": "Tel Aviv", "area": "TA"}
            ])
            mock_instance.check_availability = AsyncMock(return_value={
                "slots": [{"time": "2000", "id": "s1"}]
            })
            mock_instance.parse_availability_response = MagicMock(return_value={
                "available": True,
                "slots": [{"time": "2000", "slot_id": "s1", "label": "20:00", "available": True}],
                "waiting_list": False,
                "phone_needed": False,
                "phone_number": "",
            })
            mock_instance.pick_best_slot = MagicMock(return_value={
                "time": "2000", "slot_id": "s1"
            })
            mock_instance.build_checkout_url = MagicMock(
                return_value="https://ontopo.co.il/reservation/checkout?venue_id=v1"
            )
            MockClient.return_value = mock_instance

            result = await bookaboo_reserve(
                "book 2 tonight 8pm at Prozdor", now=self._NOW
            )

        assert result.success is True
        assert result.restaurant_name == "Prozdor"
        assert result.checkout_url != ""

    async def test_no_venues_found(self):
        with patch("bookaboo.OntopoClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.search_venues = AsyncMock(return_value=[])
            MockClient.return_value = mock_instance

            result = await bookaboo_reserve(
                "book 2 tonight 8pm at Prozdor", now=self._NOW
            )

        assert result.success is False
        assert "No venues found" in result.error

    async def test_missing_restaurant_name(self):
        result = await bookaboo_reserve("book 2 tonight 8pm", now=self._NOW)
        assert result.success is False
        assert "restaurant name" in result.error.lower()

    async def test_phone_needed(self):
        with patch("bookaboo.OntopoClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.search_venues = AsyncMock(return_value=[
                {"id": "v2", "name": "Machneyuda", "address": "Jerusalem"}
            ])
            mock_instance.check_availability = AsyncMock(return_value={
                "phoneNeeded": True, "phoneNumber": "+972-2-555-0000"
            })
            mock_instance.parse_availability_response = MagicMock(return_value={
                "available": False,
                "slots": [],
                "waiting_list": False,
                "phone_needed": True,
                "phone_number": "+972-2-555-0000",
            })
            mock_instance.build_checkout_url = MagicMock(return_value="https://ontopo.co.il/checkout")
            MockClient.return_value = mock_instance

            result = await bookaboo_reserve(
                "book 2 tomorrow 7pm at Machneyuda", now=self._NOW
            )

        assert result.phone_needed is True
        assert result.phone_number == "+972-2-555-0000"

    async def test_waiting_list(self):
        with patch("bookaboo.OntopoClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.search_venues = AsyncMock(return_value=[
                {"id": "v3", "name": "Taizu", "address": "Tel Aviv"}
            ])
            mock_instance.check_availability = AsyncMock(return_value={
                "waitingList": True
            })
            mock_instance.parse_availability_response = MagicMock(return_value={
                "available": False,
                "slots": [],
                "waiting_list": True,
                "phone_needed": False,
                "phone_number": "",
            })
            mock_instance.build_checkout_url = MagicMock(return_value="https://ontopo.co.il/checkout")
            MockClient.return_value = mock_instance

            result = await bookaboo_reserve(
                "book 2 next Friday 9pm at Taizu", now=self._NOW
            )

        assert result.waiting_list is True


# ---------------------------------------------------------------------------
# FastAPI server tests
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient

from api_server import app


class TestApiServer:
    """FastAPI endpoint tests."""

    @pytest.fixture(autouse=True)
    def client(self):
        self.client = TestClient(app)

    def test_health(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_reserve_empty_text(self):
        resp = self.client.post("/reserve", json={"text": ""})
        assert resp.status_code == 400

    def test_search_empty_query(self):
        resp = self.client.post("/search", json={"query": ""})
        assert resp.status_code == 400

    def test_reserve_returns_json(self):
        with patch("bookaboo.OntopoClient") as MockClient, \
             patch("bookaboo.save_event"):
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.search_venues = AsyncMock(return_value=[
                {"id": "v1", "name": "Prozdor", "address": "Tel Aviv", "area": "TA"}
            ])
            mock_instance.check_availability = AsyncMock(return_value={"slots": []})
            mock_instance.parse_availability_response = MagicMock(return_value={
                "available": False, "slots": [], "waiting_list": False,
                "phone_needed": False, "phone_number": "",
            })
            mock_instance.build_checkout_url = MagicMock(return_value="")
            MockClient.return_value = mock_instance

            resp = self.client.post(
                "/reserve",
                json={"text": "book 2 tonight 8pm at Prozdor"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data

    def test_reservations_returns_list(self):
        with patch("api_server.load_events", return_value=[]):
            resp = self.client.get("/reservations")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_api_key_auth_rejected(self, monkeypatch):
        monkeypatch.setenv("BOOKABOO_API_KEY", "secret123")
        # Reload the env var in the module
        import importlib
        import api_server as _srv
        _srv._BOOKABOO_API_KEY = "secret123"

        resp = self.client.get("/reservations", headers={"X-API-Key": "wrongkey"})
        assert resp.status_code == 401

        # Clean up
        _srv._BOOKABOO_API_KEY = None

    def test_api_key_auth_accepted(self, monkeypatch):
        import api_server as _srv
        _srv._BOOKABOO_API_KEY = "secret123"

        with patch("api_server.load_events", return_value=[]):
            resp = self.client.get(
                "/reservations", headers={"X-API-Key": "secret123"}
            )
        assert resp.status_code == 200

        _srv._BOOKABOO_API_KEY = None


# ---------------------------------------------------------------------------
# User profile tests
# ---------------------------------------------------------------------------

from user_profile import UserProfile, load_profile, save_profile


class TestUserProfile:
    def test_default_profile_values(self):
        p = UserProfile()
        assert p.first_name == "Devin"
        assert p.last_name == "Pillemer"
        assert p.email == "devin.pillemer@gmail.com"
        assert p.phone == "+972-50-724-2120"
        assert p.party_size == 2
        assert p.preferred_time == "20:00"

    def test_full_name(self):
        p = UserProfile()
        assert p.full_name == "Devin Pillemer"

    def test_save_load_roundtrip(self, tmp_path):
        import user_profile as up
        original_dir = up.CONFIG_DIR
        original_file = up.PROFILE_FILE
        try:
            up.CONFIG_DIR = tmp_path / "config"
            up.PROFILE_FILE = up.CONFIG_DIR / "user_profile.json"
            profile = UserProfile(first_name="Test", last_name="User")
            save_profile(profile)
            loaded = load_profile()
            assert loaded.first_name == "Test"
            assert loaded.last_name == "User"
        finally:
            up.CONFIG_DIR = original_dir
            up.PROFILE_FILE = original_file
