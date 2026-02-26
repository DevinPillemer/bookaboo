#!/usr/bin/env python3
"""
Bookaboo CLI entry point.

Usage:
    python3 reserve.py "book 2 tonight 8pm at Prozdor"
    python3 reserve.py "reservation for 4 tomorrow 7:30pm at Machneyuda"
"""

from __future__ import annotations

import asyncio
import logging
import sys

from bookaboo import reserve
from notifications import (
    notify_error,
    notify_no_availability,
    notify_phone_needed,
    notify_success,
    notify_waiting_list,
)
from user_profile import load_profile


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )


async def _run(text: str) -> int:
    """Run the reservation flow and return an exit code."""
    profile = load_profile()
    result = await reserve(text, profile=profile)

    if not result.success:
        notify_error(
            result.error or "Reservation failed.",
            suggestion="Check the restaurant name, date, and time and try again.",
        )
        return 1

    if result.phone_needed:
        notify_phone_needed(
            restaurant_name=result.restaurant_name,
            restaurant_address=result.restaurant_address,
            display_date=result.display_date,
            time=result.time,
            party_size=result.party_size,
            phone_number=result.phone_number,
            caller_name=profile.full_name,
            caller_phone=profile.phone,
        )
        return 0

    if result.waiting_list:
        notify_waiting_list(
            restaurant_name=result.restaurant_name,
            display_date=result.display_date,
            time=result.time,
            party_size=result.party_size,
            checkout_url=result.checkout_url,
        )
        return 0

    if not result.checkout_url:
        notify_no_availability(
            restaurant_name=result.restaurant_name,
            date=result.display_date,
            time=result.time,
            party_size=result.party_size,
        )
        return 1

    notify_success(
        restaurant_name=result.restaurant_name,
        restaurant_address=result.restaurant_address,
        display_date=result.display_date,
        time=result.time,
        party_size=result.party_size,
        checkout_url=result.checkout_url,
        calendar_url=result.calendar_url,
    )
    return 0


def main() -> None:
    _setup_logging()

    if len(sys.argv) < 2:
        print("Usage: reserve.py \"<reservation request>\"")
        print()
        print("Examples:")
        print('  reserve.py "book 2 tonight 8pm at Prozdor"')
        print('  reserve.py "reservation for 4 tomorrow 7:30pm at Machneyuda"')
        print('  reserve.py "dinner next Friday 9pm, 3 people, Taizu"')
        sys.exit(1)

    text = " ".join(sys.argv[1:])
    exit_code = asyncio.run(_run(text))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
