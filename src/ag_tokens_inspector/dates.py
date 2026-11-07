"""Date parsing and day-level range filtering."""

import re
from datetime import date, datetime

_DATE_RE = re.compile(r"^(\d{4})([-/]?)(\d{2})\2(\d{2})$")


def parse_date(text: str) -> date:
    """Parse yyyyMMdd, yyyy-MM-dd or yyyy/MM/dd into a date; raise ValueError otherwise."""
    m = _DATE_RE.match(text.strip())
    if not m:
        raise ValueError(f"invalid date {text!r}; expected yyyyMMdd, yyyy-MM-dd or yyyy/MM/dd")
    return date(int(m.group(1)), int(m.group(3)), int(m.group(4)))


def timestamp_to_date(seconds: float) -> date:
    """Convert a Unix timestamp to a local calendar date."""
    return datetime.fromtimestamp(seconds).date()


def in_range(day: date | None, start: date | None, end: date | None) -> bool:
    """Return True when day lies within [start, end] (both inclusive, either optional).

    A missing day only matches when no bound is given.
    """
    if start is None and end is None:
        return True
    if day is None:
        return False
    return (start is None or day >= start) and (end is None or day <= end)
