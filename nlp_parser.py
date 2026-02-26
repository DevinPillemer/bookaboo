"""
Natural-language parser for restaurant reservation requests.

Parses phrases like:
  "reservation for 2 people tonight 8pm at Prozdor"
  "book a table tomorrow at 7:30 for 4 at Machneyuda"
  "dinner next Friday 9pm, 3 people, Taizu"

Only uses the standard library (re + datetime).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional


@dataclass
class ParsedRequest:
    restaurant_name: str = ""
    date: Optional[date] = None
    time_str: str = ""       # 24-hour HH:MM
    party_size: int = 2
    raw: str = ""

    def date_yyyymmdd(self) -> str:
        """Return date formatted as YYYYMMDD for the Ontopo API."""
        if self.date is None:
            return ""
        return self.date.strftime("%Y%m%d")

    def time_hhmm(self) -> str:
        """Return time formatted as HHMM (no colon) for the Ontopo API."""
        return self.time_str.replace(":", "")

    def display_date(self) -> str:
        """Return a human-readable date like 'Thursday, March 7'."""
        if self.date is None:
            return ""
        return self.date.strftime("%A, %B %-d")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_WEEKDAY_MAP = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

_MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

# Words that should be stripped out before extracting the restaurant name
_NOISE_WORDS = frozenset([
    "book", "reserve", "make", "a", "table", "reservation", "for", "at", "in",
    "the", "restaurant", "tonight", "today", "tomorrow", "next", "people",
    "person", "guests", "guest", "pax", "dinner", "lunch", "breakfast",
    "brunch", "seats", "seat", "please", "me", "us", "want", "need", "get",
    "find", "search", "check", "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday", "mon", "tue", "wed", "thu", "fri", "sat",
    "sun", "am", "pm",
])


def _today(now: Optional[datetime] = None) -> date:
    return (now or datetime.now()).date()


def _parse_date(text: str, now: Optional[datetime] = None) -> Optional[date]:
    """Extract a date from *text*.  Returns None if no date hint found."""
    today = _today(now)
    lower = text.lower()

    # "tonight" / "today"
    if re.search(r"\btonight\b|\btoday\b", lower):
        return today

    # "tomorrow"
    if re.search(r"\btomorrow\b", lower):
        return today + timedelta(days=1)

    # "next <weekday>" or just "<weekday>"
    for name, weekday_num in _WEEKDAY_MAP.items():
        if re.search(rf"\b{name}\b", lower):
            days_ahead = (weekday_num - today.weekday()) % 7
            # "next Friday" always means at least 7 days out if today IS Friday
            if re.search(rf"\bnext\s+{name}\b", lower):
                if days_ahead == 0:
                    days_ahead = 7
                elif days_ahead < 7:
                    pass  # already in the future this week — keep as-is for "next"
            else:
                if days_ahead == 0:
                    days_ahead = 7  # same weekday → next week
            return today + timedelta(days=days_ahead)

    # "March 15" / "15 March" / "15/3" / "3/15"
    for month_name, month_num in _MONTH_MAP.items():
        m = re.search(rf"\b{month_name}\s+(\d{{1,2}})\b", lower)
        if not m:
            m = re.search(rf"\b(\d{{1,2}})\s+{month_name}\b", lower)
        if m:
            day = int(m.group(1))
            year = today.year
            try:
                d = date(year, month_num, day)
                if d < today:
                    d = date(year + 1, month_num, day)
                return d
            except ValueError:
                pass

    # ISO / slash formats: 2025-03-15, 15/03, 03/15
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    m = re.search(r"\b(\d{1,2})[/\-](\d{1,2})\b", text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        # Guess DD/MM vs MM/DD based on plausibility
        for (month, day) in [(b, a), (a, b)]:
            if 1 <= month <= 12 and 1 <= day <= 31:
                try:
                    d = date(today.year, month, day)
                    if d < today:
                        d = date(today.year + 1, month, day)
                    return d
                except ValueError:
                    continue

    return None


def _parse_time(text: str) -> str:
    """
    Extract time from *text* and return it as HH:MM (24-hour).
    Returns "" if no time found.

    Strategy (in order of specificity):
      1. HH:MM [am/pm] – colon format, unambiguous.
      2. <hour> am|pm  – bare hour with explicit meridiem.
    Bare numbers without am/pm or colon are NOT treated as times to avoid
    matching date digits (e.g. "03" in "2025-03-10") or party-size numbers.
    """
    # Strip date-like patterns before matching to avoid false positives
    # e.g. "2025-03-10" contains "03" and "10" which look like times
    cleaned = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", text)
    cleaned = re.sub(r"\b\d{1,2}[/\-]\d{1,2}\b", "", cleaned)
    lower = cleaned.lower()

    # 1. Colon format: "20:30", "7:30pm", "12:00 am"
    m = re.search(
        r"\b(\d{1,2}):(\d{2})(?::\d{2})?\s*(am|pm)?\b",
        lower,
        re.IGNORECASE,
    )
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))
        meridiem = (m.group(3) or "").lower()
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    # 2. Bare hour with explicit am/pm: "8pm", "9 am", "8 PM"
    m = re.search(r"\b(\d{1,2})\s*(am|pm)\b", lower, re.IGNORECASE)
    if m:
        hour = int(m.group(1))
        meridiem = m.group(2).lower()
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23:
            return f"{hour:02d}:00"

    return ""


def _parse_party_size(text: str) -> int:
    """Extract party size.  Defaults to 2."""
    lower = text.lower()

    # "for 3", "3 people", "party of 4", "table for 2"
    patterns = [
        r"for\s+(\d+)\s*(?:people|person|guests?|pax|seats?)?",
        r"(\d+)\s+(?:people|persons?|guests?|pax|seats?|diners?)",
        r"party\s+of\s+(\d+)",
        r"table\s+for\s+(\d+)",
    ]
    for pat in patterns:
        m = re.search(pat, lower)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 20:
                return n

    # Single digit at word boundary that isn't clearly a time
    # e.g. "book 2 tonight" — must not match "8pm"
    # We strip known time patterns first
    stripped = re.sub(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", "", lower, flags=re.IGNORECASE)
    m = re.search(r"(?<![:\d])(\b[2-9]\b)(?![\d:])", stripped)
    if m:
        return int(m.group(1))

    return 2  # default


def _parse_restaurant_name(text: str) -> str:
    """
    Extract the restaurant name.

    Strategy: look for "at <Name>" or "in <Name>" phrase after stripping
    temporal / numeric tokens.  Falls back to capitalised words.
    """
    # Try "at <Name>" pattern
    m = re.search(
        r"\bat\s+([A-Za-z][A-Za-z '\-]+?)(?:\s*$|[,.\!?]|\s+(?:on|this|next|tonight|tomorrow|\d))",
        text,
        re.IGNORECASE,
    )
    if m:
        name = m.group(1).strip()
        if name.lower() not in _NOISE_WORDS:
            return _clean_restaurant_name(name)

    # Try "in <Name>" fallback
    m = re.search(r"\bin\s+([A-Za-z][A-Za-z '\-]+?)(?:\s*$|[,.\!?])", text, re.IGNORECASE)
    if m:
        name = m.group(1).strip()
        words = [w for w in name.split() if w.lower() not in _NOISE_WORDS]
        if words:
            return _clean_restaurant_name(" ".join(words))

    # Fall back: collect capitalised words that aren't noise
    words = []
    for word in re.findall(r"[A-Za-z''\-]+", text):
        if word[0].isupper() and word.lower() not in _NOISE_WORDS:
            words.append(word)
    if words:
        return " ".join(words)

    return ""


def _clean_restaurant_name(name: str) -> str:
    """Remove trailing noise words from a restaurant name candidate."""
    parts = name.split()
    while parts and parts[-1].lower() in _NOISE_WORDS:
        parts.pop()
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_reservation_request(
    text: str,
    now: Optional[datetime] = None,
) -> ParsedRequest:
    """
    Parse a natural-language reservation request.

    Args:
        text: Free-form request string.
        now:  Optional current datetime (used for relative date resolution;
              defaults to ``datetime.now()``).

    Returns:
        A :class:`ParsedRequest` with best-effort extracted fields.
    """
    req = ParsedRequest(raw=text)
    req.date = _parse_date(text, now)
    req.time_str = _parse_time(text)
    req.party_size = _parse_party_size(text)
    req.restaurant_name = _parse_restaurant_name(text)

    # Default time: 20:00 if none found
    if not req.time_str:
        req.time_str = "20:00"

    return req
