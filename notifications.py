"""
Terminal notification formatting for Bookaboo.

Prints colour-coded, human-friendly messages for:
  • Successful reservation with checkout URL
  • Phone-required scenario (with call script for Devin Pillemer)
  • Waiting-list placement
  • Generic errors
"""

from __future__ import annotations

import sys

# ANSI colours ----------------------------------------------------------------
_RESET = "\033[0m"
_BOLD = "\033[1m"
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_CYAN = "\033[96m"
_BLUE = "\033[94m"
_MAGENTA = "\033[95m"

_SEP = "─" * 60


def _c(text: str, *codes: str) -> str:
    """Wrap *text* with ANSI codes if stdout is a TTY."""
    if not sys.stdout.isatty():
        return text
    return "".join(codes) + text + _RESET


def _header(icon: str, title: str, colour: str) -> None:
    print(_c(_SEP, colour))
    print(_c(f"{icon}  {title}", colour, _BOLD))
    print(_c(_SEP, colour))


def _field(label: str, value: str, label_colour: str = _CYAN) -> None:
    print(f"  {_c(label + ':', label_colour, _BOLD):<30} {value}")


# ---------------------------------------------------------------------------
# Public notification functions
# ---------------------------------------------------------------------------

def notify_success(
    restaurant_name: str,
    restaurant_address: str,
    display_date: str,
    time: str,
    party_size: int,
    checkout_url: str,
    calendar_url: str = "",
) -> None:
    """Print a success notification with checkout and calendar links."""
    _header("🎉", "Reservation Ready!", _GREEN)
    print()
    _field("Restaurant", restaurant_name)
    _field("Address", restaurant_address)
    _field("Date", display_date)
    _field("Time", time)
    _field("Party size", str(party_size))
    print()
    _field("Checkout URL", _c(checkout_url, _BLUE))
    if calendar_url:
        _field("Add to Calendar", _c(calendar_url, _BLUE))
    print()
    print(_c("  Complete your booking at the checkout URL above.", _GREEN))
    print(_c(_SEP, _GREEN))
    print()


def notify_phone_needed(
    restaurant_name: str,
    restaurant_address: str,
    display_date: str,
    time: str,
    party_size: int,
    phone_number: str,
    caller_name: str = "Devin Pillemer",
    caller_phone: str = "+972-50-724-2120",
) -> None:
    """
    Print a notification when a phone call is required to complete the booking.
    Includes a ready-to-use call script.
    """
    _header("📞", "Phone Call Required", _YELLOW)
    print()
    _field("Restaurant", restaurant_name)
    _field("Address", restaurant_address)
    _field("Date", display_date)
    _field("Time", time)
    _field("Party size", str(party_size))
    _field("Restaurant phone", _c(phone_number, _YELLOW, _BOLD))
    print()
    print(_c("  ── Call Script ──────────────────────────────────", _YELLOW))
    print()
    print(
        f'  "Hi, this is {caller_name}, I\'d like to make a reservation\n'
        f"   for {party_size} people on {display_date} at {time}.\n"
        f'   My phone number is {caller_phone}."'
    )
    print()
    print(_c(_SEP, _YELLOW))
    print()


def notify_waiting_list(
    restaurant_name: str,
    display_date: str,
    time: str,
    party_size: int,
    checkout_url: str = "",
) -> None:
    """Print a waiting-list notification."""
    _header("⏳", "Added to Waiting List", _MAGENTA)
    print()
    _field("Restaurant", restaurant_name)
    _field("Date", display_date)
    _field("Time", time)
    _field("Party size", str(party_size))
    if checkout_url:
        _field("Waiting list URL", _c(checkout_url, _BLUE))
    print()
    print(_c("  You've been added to the waiting list.", _MAGENTA))
    print(_c("  You'll be notified if a table becomes available.", _MAGENTA))
    print(_c(_SEP, _MAGENTA))
    print()


def notify_error(message: str, suggestion: str = "") -> None:
    """Print an error notification."""
    _header("❌", "Reservation Failed", _RED)
    print()
    print(f"  {_c(message, _RED)}")
    if suggestion:
        print()
        print(f"  {_c('Suggestion:', _YELLOW, _BOLD)} {suggestion}")
    print()
    print(_c(_SEP, _RED))
    print()


def notify_no_availability(
    restaurant_name: str,
    date: str,
    time: str,
    party_size: int,
) -> None:
    """Notify the user that no tables are available."""
    notify_error(
        f"No availability at {restaurant_name} on {date} at {time} for {party_size}.",
        suggestion="Try a different time or date, or check the waiting list.",
    )
