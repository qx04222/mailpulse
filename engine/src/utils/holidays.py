"""
Ontario (Canada) statutory holidays.
Work schedule: Mon-Sat (Sunday always off).
Holidays override normal work days — no push on holidays even if Mon-Sat.
"""
from __future__ import annotations
from datetime import date, timedelta
from functools import lru_cache
from typing import Optional, Set


def _easter(year: int) -> date:
    """Compute Easter Sunday using the Anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Return the nth occurrence of weekday (0=Mon) in the given month."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday_on_or_before(target: date, weekday: int) -> date:
    """Return the last occurrence of weekday on or before target date."""
    offset = (target.weekday() - weekday) % 7
    return target - timedelta(days=offset)


@lru_cache(maxsize=8)
def get_ontario_holidays(year: int) -> Set[date]:
    """
    Ontario statutory holidays for the given year.
    Includes: New Year, Family Day, Good Friday, Victoria Day,
    Canada Day, Civic Holiday, Labour Day, Thanksgiving, Christmas, Boxing Day.
    """
    holidays = set()

    # Fixed dates
    holidays.add(date(year, 1, 1))    # New Year's Day
    holidays.add(date(year, 7, 1))    # Canada Day
    holidays.add(date(year, 12, 25))  # Christmas Day
    holidays.add(date(year, 12, 26))  # Boxing Day

    # Floating holidays
    holidays.add(_nth_weekday(year, 2, 0, 3))   # Family Day: 3rd Monday of Feb
    holidays.add(_easter(year) - timedelta(days=2))  # Good Friday
    holidays.add(_last_weekday_on_or_before(date(year, 5, 24), 0))  # Victoria Day: last Mon on/before May 24
    holidays.add(_nth_weekday(year, 8, 0, 1))   # Civic Holiday: 1st Monday of Aug
    holidays.add(_nth_weekday(year, 9, 0, 1))   # Labour Day: 1st Monday of Sep
    holidays.add(_nth_weekday(year, 10, 0, 2))   # Thanksgiving: 2nd Monday of Oct

    return holidays


def is_business_day(d: Optional[date] = None) -> bool:
    """
    Check if the given date is a business day in Ontario.
    Business days: Mon-Sat, excluding statutory holidays.
    Sunday is always off.
    """
    if d is None:
        from zoneinfo import ZoneInfo
        from datetime import datetime, timezone
        d = datetime.now(ZoneInfo("America/Toronto")).date()

    # Sunday is always off
    if d.weekday() == 6:
        return False

    # Check statutory holidays
    if d in get_ontario_holidays(d.year):
        return False

    return True
