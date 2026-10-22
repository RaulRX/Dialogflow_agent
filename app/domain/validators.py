"""Input validation and sanitising helpers."""

import re
from datetime import date, datetime, time

VISIBLE_DNI_CHARS = 4

# A DNI (8 digits + letter) or NIE (X/Y/Z + 7 digits + letter) with optional spaces
# between every character, delimited so it never swallows neighbouring words.
_SPACED_DNI = re.compile(
    r"(?<!\w)(?:\d(?:\s?\d){7}|[XYZxyz]\s?\d(?:\s?\d){6})\s?[A-Za-z](?!\w)"
)

# Format only: the control letter is not checked against the number on purpose.
_DNI_FORMAT = re.compile(r"(?:\d{8}|[XYZ]\d{7})[A-Z]")
_SUNDAY = 6

_SATURDAY = 5

# Must match the schedule of the clinic document (ocr/documents/clinica_info.txt).
_WEEKDAY_HOURS = ((time(9, 0), time(20, 0)),)
_SATURDAY_HOURS = ((time(10, 0), time(14, 0)),)


def mask_dni(dni: str) -> str:
    """Hide a DNI/NIE for logging, keeping only its last characters."""
    compact = dni.replace(" ", "")
    if len(compact) <= VISIBLE_DNI_CHARS:
        return "*" * len(compact)
    return "*" * (len(compact) - VISIBLE_DNI_CHARS) + compact[-VISIBLE_DNI_CHARS:]


def normalize_dni_in_text(text: str) -> str:
    """Join a DNI/NIE typed with spaces ("1 2 3 4 5 6 7 8 z") into "12345678Z" inside a sentence."""
    return _SPACED_DNI.sub(lambda match: "".join(match.group().split()).upper(), text)


def is_valid_dni(dni: str) -> bool:
    """Check the DNI/NIE format (8 digits + letter, or X/Y/Z + 7 digits + letter).

    Spaces and case are ignored. The control letter is not verified against the number.
    """
    return _DNI_FORMAT.fullmatch(dni.replace(" ", "").upper()) is not None


def parse_date(raw: str) -> date | None:
    """Parse a Dialogflow @sys.date value (ISO date or datetime); None if malformed."""
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError:
        return None


def parse_time(raw: str) -> time | None:
    """Parse a Dialogflow @sys.time value (ISO datetime or bare HH:MM:SS); None if malformed."""
    try:
        return datetime.fromisoformat(raw).time().replace(tzinfo=None)
    except ValueError:
        pass
    try:
        return time.fromisoformat(raw)
    except ValueError:
        return None


def is_future_date(day: date, today: date) -> bool:
    return day > today


def is_sunday(day: date) -> bool:
    return day.weekday() == _SUNDAY


def is_within_opening_hours(day: date, slot: time) -> bool:
    """True if the slot starts inside the opening range of that day (closing time excluded)."""
    weekday = day.weekday()
    if weekday == _SUNDAY:
        return False
    ranges = _SATURDAY_HOURS if weekday == _SATURDAY else _WEEKDAY_HOURS
    return any(opens <= slot < closes for opens, closes in ranges)