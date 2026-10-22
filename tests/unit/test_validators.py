from datetime import date, time

import pytest

from app.domain.validators import (
    is_future_date,
    is_sunday,
    is_valid_dni,
    is_within_opening_hours,
    mask_dni,
    normalize_dni_in_text,
    parse_date,
    parse_time,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1 2 3 4 5 6 7 8 Z", "12345678Z"),
        ("1 2 3 4 5 6 7 8 z", "12345678Z"),
        ("12 34 56 78 Z", "12345678Z"),
        ("12345678 z", "12345678Z"),
        ("x 1 2 3 4 5 6 7 l", "X1234567L"),
        ("mi dni es 1 2 3 4 5 6 7 8 z y mi gato", "mi dni es 12345678Z y mi gato"),
        ("12345678Z", "12345678Z"),
        ("quiero una cita", "quiero una cita"),
        ("tiene 12345678 años", "tiene 12345678 años"),
        ("tiene 1 2 3 4 5 6 7 8 años", "tiene 1 2 3 4 5 6 7 8 años"),
        ("1 2 3 4 5 6 7 Z", "1 2 3 4 5 6 7 Z"),
    ],
)
def test_should_join_dni_digits_only_when_a_full_dni_is_spelled_with_spaces(
    text: str, expected: str
) -> None:
    assert normalize_dni_in_text(text) == expected


def test_should_keep_only_last_four_chars_when_masking_dni() -> None:
    assert mask_dni("12345678Z") == "*****678Z"


def test_should_mask_everything_when_dni_is_too_short() -> None:
    assert mask_dni("12") == "**"


@pytest.mark.parametrize(
    "dni",
    ["12345678Z", "12345678z", "12345678 Z", "12345678A", "X1234567L", "x1234567l", "Y1234567A"],
)
def test_should_accept_dni_when_format_is_valid_regardless_of_control_letter(dni: str) -> None:
    assert is_valid_dni(dni)


@pytest.mark.parametrize(
    "dni", ["1234567Z", "123456789", "12345678", "ABCDEFGHZ", "X123456LL", "W1234567L", ""]
)
def test_should_reject_dni_when_format_is_wrong(dni: str) -> None:
    assert not is_valid_dni(dni)


def test_should_parse_date_when_value_is_iso_datetime() -> None:
    assert parse_date("2026-10-20T12:00:00+02:00") == date(2026, 10, 20)


def test_should_return_none_when_date_is_malformed() -> None:
    assert parse_date("mañana") is None


@pytest.mark.parametrize("raw", ["2026-10-15T10:30:00+02:00", "10:30:00"])
def test_should_parse_time_when_value_is_iso_or_bare(raw: str) -> None:
    assert parse_time(raw) == time(10, 30)


def test_should_return_none_when_time_is_malformed() -> None:
    assert parse_time("a las diez") is None


def test_should_require_strictly_future_date() -> None:
    today = date(2026, 10, 15)
    assert is_future_date(date(2026, 10, 16), today)
    assert not is_future_date(today, today)
    assert not is_future_date(date(2026, 10, 14), today)


def test_should_detect_sunday() -> None:
    assert is_sunday(date(2026, 10, 18))
    assert not is_sunday(date(2026, 10, 19))


@pytest.mark.parametrize(
    ("day", "slot", "expected"),
    [
        (date(2026, 10, 16), time(8, 59), False),  # Friday
        (date(2026, 10, 16), time(9, 0), True),
        (date(2026, 10, 16), time(15, 30), True),
        (date(2026, 10, 16), time(19, 59), True),
        (date(2026, 10, 16), time(20, 0), False),
        (date(2026, 10, 17), time(9, 59), False),  # Saturday
        (date(2026, 10, 17), time(10, 0), True),
        (date(2026, 10, 17), time(13, 59), True),
        (date(2026, 10, 17), time(14, 0), False),
        (date(2026, 10, 18), time(12, 0), False),  # Sunday
    ],
)
def test_should_check_opening_hours_per_weekday_with_closing_excluded(
    day: date, slot: time, expected: bool
) -> None:
    assert is_within_opening_hours(day, slot) is expected
