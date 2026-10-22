"""Helpers that build the Spanish spoken text (SSML) sent to the user."""

import re
from datetime import date, time
from xml.sax.saxutils import escape

_CLINIC_PHONE = re.compile(r"(?<!\d)900(?:\s?\d{3}){2}(?!\d)")
_WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_MONTHS = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
_ANIMAL_LABELS = {"huron": "hurón"}


def ssml(*parts: str) -> str:
    return f"<speak>{''.join(parts)}</speak>"


def pause() -> str:
    return '<break time="1s"/>'


def spell(code: str) -> str:
    return f'<say-as interpret-as="characters">{code}</say-as>'


def speak_text(text: str) -> str:
    """Make free text (such as a model answer) safe inside SSML and read phone numbers digit by digit."""
    return _CLINIC_PHONE.sub(
        lambda match: f'<say-as interpret-as="telephone">{match.group()}</say-as>',
        escape(text),
    )


def format_date(day: date) -> str:
    return f"{_WEEKDAYS[day.weekday()]} {day.day} de {_MONTHS[day.month - 1]}"


def format_time(slot: time) -> str:
    return f"{slot.hour:02d}:{slot.minute:02d}"


def animal_label(value: str) -> str:
    return _ANIMAL_LABELS.get(value, value)