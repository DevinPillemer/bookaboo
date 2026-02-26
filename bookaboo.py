"""
Bookaboo orchestrator.

Flow:
  1. Parse the natural-language request with nlp_parser.
  2. Search for the venue via the Ontopo API.
  3. Check availability for the requested slot.
  4. Build the checkout URL for the best available slot.
  5. Generate a Google Calendar URL and save the event locally.
  6. Return a BookingResult.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from calendar_integration import build_event, generate_google_calendar_url, save_event
from nlp_parser import ParsedRequest, parse_reservation_request
from ontopo_client import BookingResult, OntopoClient
from user_profile import UserProfile, load_profile

logger = logging.getLogger(__name__)


async def reserve(
    text: str,
    profile: Optional[UserProfile] = None,
    now: Optional[datetime] = None,
) -> BookingResult:
    """
    End-to-end reservation flow.

    Args:
        text:    Free-form reservation request (e.g. "book 2 tonight 8pm at Prozdor").
        profile: Optional user profile override; loaded from disk if None.
        now:     Optional current datetime (for testing).

    Returns:
        A fully populated :class:`~ontopo_client.BookingResult`.
    """
    if profile is None:
        profile = load_profile()

    # 1. Parse request -------------------------------------------------------
    req: ParsedRequest = parse_reservation_request(text, now=now)

    if not req.restaurant_name:
        return BookingResult(
            success=False,
            error="Could not determine restaurant name from request.",
        )

    if req.date is None:
        return BookingResult(
            success=False,
            restaurant_name=req.restaurant_name,
            error="Could not determine date from request.",
        )

    date_yyyymmdd = req.date_yyyymmdd()
    time_hhmm_colon = req.time_str          # HH:MM
    time_hhmm_no_colon = req.time_hhmm()   # HHMM (for Ontopo API)
    party_size = req.party_size
    display_date = req.display_date()

    logger.info(
        "Parsed request: restaurant=%r date=%s time=%s party=%d",
        req.restaurant_name, date_yyyymmdd, time_hhmm_colon, party_size,
    )

    async with OntopoClient() as client:
        # 2. Search for the venue --------------------------------------------
        try:
            venues = await client.search_venues(req.restaurant_name)
        except Exception as exc:
            logger.exception("Venue search failed")
            return BookingResult(
                success=False,
                restaurant_name=req.restaurant_name,
                date=date_yyyymmdd,
                display_date=display_date,
                time=time_hhmm_colon,
                party_size=party_size,
                error=f"Venue search failed: {exc}",
            )

        if not venues:
            return BookingResult(
                success=False,
                restaurant_name=req.restaurant_name,
                date=date_yyyymmdd,
                display_date=display_date,
                time=time_hhmm_colon,
                party_size=party_size,
                error=f"No venues found for '{req.restaurant_name}'.",
            )

        venue = venues[0]
        venue_id = (
            venue.get("id")
            or venue.get("venue_id")
            or venue.get("venueId")
            or str(venue.get("_id", ""))
        )
        restaurant_name = (
            venue.get("name")
            or venue.get("title")
            or req.restaurant_name
        )
        restaurant_address = (
            venue.get("address")
            or venue.get("location", {}).get("address", "")
            or venue.get("fullAddress", "")
        )
        area = venue.get("area") or venue.get("neighborhood") or ""

        logger.info("Selected venue: id=%s name=%r", venue_id, restaurant_name)

        if not venue_id:
            return BookingResult(
                success=False,
                restaurant_name=restaurant_name,
                restaurant_address=restaurant_address,
                date=date_yyyymmdd,
                display_date=display_date,
                time=time_hhmm_colon,
                party_size=party_size,
                error="Could not determine venue ID from search results.",
            )

        # 3. Check availability ----------------------------------------------
        try:
            avail_raw = await client.check_availability(
                venue_id=venue_id,
                date=date_yyyymmdd,
                time=time_hhmm_no_colon,
                party_size=party_size,
            )
        except Exception as exc:
            logger.exception("Availability check failed")
            return BookingResult(
                success=False,
                restaurant_name=restaurant_name,
                restaurant_address=restaurant_address,
                date=date_yyyymmdd,
                display_date=display_date,
                time=time_hhmm_colon,
                party_size=party_size,
                error=f"Availability check failed: {exc}",
            )

        avail = client.parse_availability_response(avail_raw)

        # 4. Handle waiting-list / phone-needed scenarios --------------------
        if avail["phone_needed"]:
            checkout_url = client.build_checkout_url(
                venue_id=venue_id,
                date=date_yyyymmdd,
                time=time_hhmm_no_colon,
                party_size=party_size,
            )
            return BookingResult(
                success=True,
                restaurant_name=restaurant_name,
                restaurant_address=restaurant_address,
                date=date_yyyymmdd,
                display_date=display_date,
                time=time_hhmm_colon,
                party_size=party_size,
                checkout_url=checkout_url,
                area=area,
                available_slots=avail["slots"],
                waiting_list=False,
                phone_needed=True,
                phone_number=avail["phone_number"],
            )

        if avail["waiting_list"] and not avail["available"]:
            checkout_url = client.build_checkout_url(
                venue_id=venue_id,
                date=date_yyyymmdd,
                time=time_hhmm_no_colon,
                party_size=party_size,
            )
            return BookingResult(
                success=True,
                restaurant_name=restaurant_name,
                restaurant_address=restaurant_address,
                date=date_yyyymmdd,
                display_date=display_date,
                time=time_hhmm_colon,
                party_size=party_size,
                checkout_url=checkout_url,
                area=area,
                available_slots=[],
                waiting_list=True,
            )

        if not avail["available"] and not avail["slots"]:
            return BookingResult(
                success=False,
                restaurant_name=restaurant_name,
                restaurant_address=restaurant_address,
                date=date_yyyymmdd,
                display_date=display_date,
                time=time_hhmm_colon,
                party_size=party_size,
                error=f"No availability at {restaurant_name} on {display_date} at {time_hhmm_colon}.",
            )

        # 5. Pick best slot & build checkout URL -----------------------------
        best_slot = client.pick_best_slot(avail["slots"], time_hhmm_no_colon)
        slot_time = best_slot["time"] if best_slot else time_hhmm_no_colon
        slot_id = best_slot["slot_id"] if best_slot else ""

        # Normalise slot time to HH:MM for display
        slot_time_display = slot_time if ":" in slot_time else f"{slot_time[:2]}:{slot_time[2:]}"

        checkout_url = client.build_checkout_url(
            venue_id=venue_id,
            date=date_yyyymmdd,
            time=slot_time.replace(":", ""),
            party_size=party_size,
            slot_id=slot_id,
        )

        # 6. Calendar integration --------------------------------------------
        calendar_url = generate_google_calendar_url(
            restaurant_name=restaurant_name,
            restaurant_address=restaurant_address,
            date_yyyymmdd=date_yyyymmdd,
            time_hhmm=slot_time_display,
            party_size=party_size,
        )

        event = build_event(
            restaurant_name=restaurant_name,
            restaurant_address=restaurant_address,
            date_yyyymmdd=date_yyyymmdd,
            time_hhmm=slot_time_display,
            party_size=party_size,
            checkout_url=checkout_url,
        )
        try:
            save_event(event)
        except OSError:
            logger.warning("Could not save event to local calendar store")

        return BookingResult(
            success=True,
            restaurant_name=restaurant_name,
            restaurant_address=restaurant_address,
            date=date_yyyymmdd,
            display_date=display_date,
            time=slot_time_display,
            party_size=party_size,
            checkout_url=checkout_url,
            area=area,
            available_slots=avail["slots"],
            waiting_list=avail.get("waiting_list", False),
            phone_needed=False,
            calendar_url=calendar_url,
        )


async def search_restaurants(query: str) -> list[dict]:
    """Return a list of venue dicts matching *query*."""
    async with OntopoClient() as client:
        return await client.search_venues(query)


async def check_availability(
    venue_id: str,
    date_yyyymmdd: str,
    time_hhmm: str,
    party_size: int,
) -> dict:
    """Raw availability check, returns parsed availability dict."""
    async with OntopoClient() as client:
        raw = await client.check_availability(
            venue_id=venue_id,
            date=date_yyyymmdd,
            time=time_hhmm.replace(":", ""),
            party_size=party_size,
        )
        return client.parse_availability_response(raw)
