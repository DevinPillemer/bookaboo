"""
Ontopo API client for restaurant reservations in Israel.
Handles anonymous auth, venue search, availability checking, and checkout URL generation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

ONTOPO_BASE_URL = "https://ontopo.co.il"
DISTRIBUTOR_ID = "15171493"
DISTRIBUTOR_VERSION = "7738"


@dataclass
class BookingResult:
    success: bool
    restaurant_name: str = ""
    restaurant_address: str = ""
    date: str = ""           # YYYYMMDD
    display_date: str = ""   # e.g. "Thursday, March 7"
    time: str = ""           # HH:MM 24h
    party_size: int = 2
    checkout_url: str = ""
    area: str = ""
    available_slots: list[dict] = field(default_factory=list)
    waiting_list: bool = False
    phone_needed: bool = False
    phone_number: str = ""
    calendar_url: str = ""
    error: str = ""


class OntopoClient:
    """Async Ontopo API client."""

    def __init__(self, base_url: str = ONTOPO_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self._token: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "OntopoClient":
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": f"Bookaboo/1.0 distributor/{DISTRIBUTOR_ID}",
            },
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Client not initialised – use 'async with OntopoClient()'")
        return self._client

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    async def login_anonymously(self) -> str:
        """Authenticate anonymously and return the session token."""
        client = self._ensure_client()
        payload = {
            "distributor": DISTRIBUTOR_ID,
            "version": DISTRIBUTOR_VERSION,
        }
        resp = await client.post(f"{self.base_url}/api/loginAnonymously", json=payload)
        resp.raise_for_status()
        data = resp.json()
        token = (
            data.get("token")
            or data.get("access_token")
            or data.get("sessionToken")
            or data.get("data", {}).get("token")
        )
        if not token:
            raise ValueError(f"No token in loginAnonymously response: {data}")
        self._token = token
        logger.debug("Logged in anonymously, token acquired")
        return token

    async def _auth_headers(self) -> dict[str, str]:
        if not self._token:
            await self.login_anonymously()
        return {"Authorization": f"Bearer {self._token}"}

    # ------------------------------------------------------------------
    # Venue search
    # ------------------------------------------------------------------

    async def search_venues(
        self,
        query: str,
        area: str = "",
        limit: int = 10,
    ) -> list[dict]:
        """Search for venues by name / query string."""
        client = self._ensure_client()
        headers = await self._auth_headers()
        params: dict[str, Any] = {
            "query": query,
            "distributor": DISTRIBUTOR_ID,
            "limit": limit,
        }
        if area:
            params["area"] = area

        resp = await client.get(
            f"{self.base_url}/api/venue_search",
            params=params,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

        # Normalise various response shapes
        venues = (
            data.get("venues")
            or data.get("results")
            or data.get("data")
            or (data if isinstance(data, list) else [])
        )
        logger.debug("venue_search returned %d results for %r", len(venues), query)
        return venues

    # ------------------------------------------------------------------
    # Venue profile
    # ------------------------------------------------------------------

    async def get_venue_profile(self, venue_id: str) -> dict:
        """Fetch full profile for a specific venue."""
        client = self._ensure_client()
        headers = await self._auth_headers()
        resp = await client.get(
            f"{self.base_url}/api/venue/{venue_id}",
            headers=headers,
            params={"distributor": DISTRIBUTOR_ID},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("venue") or data.get("data") or data

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    async def check_availability(
        self,
        venue_id: str,
        date: str,   # YYYYMMDD
        time: str,   # HHMM
        party_size: int,
    ) -> dict:
        """
        Check table availability for a venue.

        Args:
            venue_id:   Ontopo venue identifier.
            date:       Date in YYYYMMDD format.
            time:       Time in HHMM format (24-hour, no colon).
            party_size: Number of diners.

        Returns:
            Raw availability response dict.
        """
        client = self._ensure_client()
        headers = await self._auth_headers()
        payload = {
            "venue_id": venue_id,
            "date": date,
            "time": time,
            "party_size": party_size,
            "distributor": DISTRIBUTOR_ID,
        }
        resp = await client.post(
            f"{self.base_url}/api/availability_search",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Checkout URL
    # ------------------------------------------------------------------

    def build_checkout_url(
        self,
        venue_id: str,
        date: str,    # YYYYMMDD
        time: str,    # HHMM
        party_size: int,
        slot_id: str = "",
    ) -> str:
        """
        Build a deep-link checkout URL for the Ontopo booking flow.

        Args:
            venue_id:   Venue identifier.
            date:       YYYYMMDD.
            time:       HHMM.
            party_size: Number of diners.
            slot_id:    Optional specific slot/offer ID from availability response.

        Returns:
            Fully qualified checkout URL.
        """
        params: dict[str, Any] = {
            "venue_id": venue_id,
            "date": date,
            "time": time,
            "party_size": party_size,
            "distributor": DISTRIBUTOR_ID,
        }
        if slot_id:
            params["slot_id"] = slot_id
        if self._token:
            params["token"] = self._token
        return f"{self.base_url}/reservation/checkout?{urlencode(params)}"

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------

    def parse_availability_response(self, data: dict) -> dict:
        """
        Normalise the availability response into a standard shape::

            {
                "available": bool,
                "slots": [{"time": "HHMM", "slot_id": "...", ...}],
                "waiting_list": bool,
                "phone_needed": bool,
                "phone_number": str,
            }
        """
        # Try common response key names
        slots_raw = (
            data.get("slots")
            or data.get("availableSlots")
            or data.get("available_slots")
            or data.get("times")
            or data.get("data", {}).get("slots")
            or []
        )

        slots = []
        for s in slots_raw:
            t = s.get("time") or s.get("hour") or s.get("start_time") or ""
            slots.append({
                "time": t,
                "slot_id": s.get("id") or s.get("slot_id") or s.get("offerId") or "",
                "label": s.get("label") or s.get("display") or t,
                "available": s.get("available", True),
            })

        waiting = (
            data.get("waitingList")
            or data.get("waiting_list")
            or data.get("data", {}).get("waitingList")
            or False
        )
        phone_needed = (
            data.get("phoneNeeded")
            or data.get("phone_needed")
            or data.get("callRequired")
            or False
        )
        phone_number = (
            data.get("phoneNumber")
            or data.get("phone_number")
            or data.get("phone")
            or ""
        )

        return {
            "available": bool(slots) or bool(data.get("available")),
            "slots": slots,
            "waiting_list": bool(waiting),
            "phone_needed": bool(phone_needed),
            "phone_number": phone_number,
        }

    def pick_best_slot(
        self, slots: list[dict], preferred_time: str
    ) -> Optional[dict]:
        """
        Choose the slot closest to *preferred_time* (HHMM string).

        Returns None when *slots* is empty.
        """
        if not slots:
            return None
        if len(slots) == 1:
            return slots[0]

        def time_distance(slot: dict) -> int:
            t = slot.get("time", "0000").replace(":", "")
            try:
                slot_mins = int(t[:2]) * 60 + int(t[2:])
                pref_mins = int(preferred_time[:2]) * 60 + int(preferred_time[2:])
                return abs(slot_mins - pref_mins)
            except (ValueError, IndexError):
                return 9999

        return min(slots, key=time_distance)
