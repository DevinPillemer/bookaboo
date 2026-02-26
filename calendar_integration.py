"""
Calendar integration for Bookaboo.

Saves reservation events to ~/.config/restaurant-reservations/calendar_events.json
and generates Google Calendar deep-link URLs.
"""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, quote

CONFIG_DIR = Path.home() / ".config" / "restaurant-reservations"
EVENTS_FILE = CONFIG_DIR / "calendar_events.json"


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def load_events() -> list[dict]:
    """Load saved reservation events from disk."""
    if not EVENTS_FILE.exists():
        return []
    try:
        with EVENTS_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_event(event: dict) -> None:
    """Append a reservation event to the local JSON store."""
    _ensure_config_dir()
    events = load_events()
    events.append(event)
    with EVENTS_FILE.open("w", encoding="utf-8") as fh:
        json.dump(events, fh, ensure_ascii=False, indent=2)
    # Restrict permissions: owner read/write only
    EVENTS_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)


def build_event(
    restaurant_name: str,
    restaurant_address: str,
    date_yyyymmdd: str,
    time_hhmm: str,   # HH:MM 24h
    party_size: int,
    checkout_url: str = "",
    duration_hours: int = 2,
) -> dict[str, Any]:
    """
    Build a calendar event dict from reservation details.

    Args:
        restaurant_name:    Name of the restaurant.
        restaurant_address: Physical address.
        date_yyyymmdd:      Date string YYYYMMDD.
        time_hhmm:          Time string HH:MM.
        party_size:         Number of diners.
        checkout_url:       Ontopo checkout link.
        duration_hours:     Default reservation duration (2 hours).

    Returns:
        Dict representing the event (compatible with ``save_event``).
    """
    dt_str = f"{date_yyyymmdd[:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:]}"
    start_dt = datetime.fromisoformat(f"{dt_str}T{time_hhmm}:00")
    end_dt = start_dt + timedelta(hours=duration_hours)

    return {
        "id": f"{date_yyyymmdd}_{time_hhmm.replace(':', '')}_{restaurant_name.lower().replace(' ', '_')}",
        "title": f"Dinner at {restaurant_name}",
        "restaurant": restaurant_name,
        "address": restaurant_address,
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat(),
        "party_size": party_size,
        "checkout_url": checkout_url,
        "created_at": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# Google Calendar URL
# ---------------------------------------------------------------------------

def generate_google_calendar_url(
    restaurant_name: str,
    restaurant_address: str,
    date_yyyymmdd: str,
    time_hhmm: str,   # HH:MM 24h
    party_size: int,
    duration_hours: int = 2,
) -> str:
    """
    Generate a Google Calendar event creation URL.

    The resulting URL opens Google Calendar with all fields pre-filled so
    the user can add the reservation to their calendar with one click.
    """
    dt_str = f"{date_yyyymmdd[:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:]}"
    start_dt = datetime.fromisoformat(f"{dt_str}T{time_hhmm}:00")
    end_dt = start_dt + timedelta(hours=duration_hours)

    # Google Calendar uses UTC timestamps in format YYYYMMDDTHHmmSSZ
    # We treat the times as local (Israel) — Google will respect system TZ
    fmt = "%Y%m%dT%H%M%S"
    dates_param = f"{start_dt.strftime(fmt)}/{end_dt.strftime(fmt)}"

    details = f"Party of {party_size} — booked via Bookaboo"

    params = {
        "action": "TEMPLATE",
        "text": f"Dinner at {restaurant_name}",
        "dates": dates_param,
        "details": details,
        "location": restaurant_address,
    }
    return f"https://calendar.google.com/calendar/render?{urlencode(params)}"
