"""Handlers for booking confirmation and appointment lookup."""

import logging
import random
import re
from dataclasses import dataclass
from datetime import date, time
from typing import Any

from app.domain.schemas import OutputContext, WebhookRequest, WebhookResponse
from app.domain.speech import animal_label, format_date, format_time, pause, spell, ssml
from app.domain.validators import (
    is_future_date,
    is_sunday,
    is_valid_dni,
    is_within_opening_hours,
    parse_date,
    parse_time,
)

logger = logging.getLogger(__name__)

BOOKING_CONTEXT = "cita_en_curso"
CONFIRMED_CONTEXT = "cita_confirmada"
CONFIRMED_LIFESPAN = 10
CODE_PREFIX = "VET"
MAX_CODE_NUMBER = 9999
BOOKING_FOLLOWUP_CONTEXT = "pedir_cita-followup"
# Dialogflow overwrites a context parameter with any intent parameter of the same name, so the
# confirmed appointment is also kept under names that no intent uses.
CONFIRMED_FIELDS = ("codigo", "animal", "fecha", "hora")
CONFIRMED_PREFIX = "confirmada_"


@dataclass(frozen=True)
class Appointment:
    code: str
    animal: str
    day: date
    slot: time

    def describe(self) -> str:
        return (
            f"para tu {animal_label(self.animal)} el {format_date(self.day)} "
            f"a las {format_time(self.slot)}"
        )


FIXTURE_APPOINTMENTS: dict[str, Appointment] = {
    appointment.code: appointment
    for appointment in (
        Appointment("VET0001", "perro", date(2026, 11, 3), time(10, 0)),
        Appointment("VET0002", "gato", date(2026, 11, 5), time(17, 30)),
        Appointment("VET0003", "conejo", date(2026, 11, 10), time(9, 15)),
    )
}


def new_appointment_code() -> str:
    while True:
        code = f"{CODE_PREFIX}{random.randint(1, MAX_CODE_NUMBER):04d}"
        if code not in FIXTURE_APPOINTMENTS:
            return code


def normalize_code(raw: str) -> str:
    return re.sub(r"[\s-]", "", raw).upper()


def _appointment_from_parameters(code: str, parameters: dict[str, Any]) -> Appointment:
    day = parse_date(str(parameters.get("fecha", "")))
    slot = parse_time(str(parameters.get("hora", "")))
    if day is None or slot is None:
        raise ValueError("Context holds an unparsable date or time")
    return Appointment(code, str(parameters["animal"]), day, slot)


def _confirmed_parameters(code: str, parameters: dict[str, Any]) -> dict[str, Any]:
    values = {"codigo": code, **parameters}
    return {f"{CONFIRMED_PREFIX}{field}": values[field] for field in CONFIRMED_FIELDS}


def confirm_appointment(request: WebhookRequest) -> WebhookResponse:
    booking = request.find_context(BOOKING_CONTEXT)
    if booking is None:
        logger.info("Confirmation without a pending booking")
        return WebhookResponse(
            fulfillment_text=ssml(
                "No tengo ninguna cita pendiente de confirmar.", pause(),
                "Si quieres, empezamos una nueva.",
            )
        )

    code = new_appointment_code()
    appointment = _appointment_from_parameters(code, booking.parameters)
    confirmed_parameters = {
        **booking.parameters,
        "codigo_cita": code,
        **_confirmed_parameters(code, booking.parameters),
    }
    logger.info("Appointment confirmed: code=%s", code)
    return WebhookResponse(
        fulfillment_text=ssml(
            f"Hecho, tu cita {appointment.describe()} queda confirmada.", pause(),
            "Tu código es ", spell(code), ".", pause(),
            "Repito: ", spell(code), ".",
        ),
        output_contexts=[
            OutputContext(
                name=request.context_path(CONFIRMED_CONTEXT),
                lifespan_count=CONFIRMED_LIFESPAN,
                parameters=confirmed_parameters,
            ),
            OutputContext(name=request.context_path(BOOKING_CONTEXT), lifespan_count=0),
        ],
    )


def _find_appointment(request: WebhookRequest, code: str) -> Appointment | None:
    confirmed = request.find_context(CONFIRMED_CONTEXT)
    if confirmed is not None:
        stored = {
            field: confirmed.parameters.get(f"{CONFIRMED_PREFIX}{field}", "")
            for field in CONFIRMED_FIELDS
        }
        if stored["codigo"] and normalize_code(str(stored["codigo"])) == code:
            return _appointment_from_parameters(code, stored)
    return FIXTURE_APPOINTMENTS.get(code)


def lookup_appointment(request: WebhookRequest) -> WebhookResponse:
    code = normalize_code(str(request.query_result.parameters.get("codigo_cita", "")))
    appointment = _find_appointment(request, code)
    logger.info("Appointment lookup: code=%s found=%s", code, appointment is not None)
    if appointment is None:
        return WebhookResponse(
            fulfillment_text=ssml(
                "No encuentro ninguna cita con el código ", spell(code), ".", pause(),
                "Revisa el código e inténtalo de nuevo.",
            )
        )
    return WebhookResponse(
        fulfillment_text=ssml(
            "Tu cita con código ", spell(code), f" es {appointment.describe()}."
        )
    )


def today() -> date:
    return date.today()


def _validation_error(dni: str, day: date, slot: time) -> str | None:
    if not is_valid_dni(dni):
        return "Ese DNI no parece válido, tiene que llevar ocho cifras y una letra."
    if not is_future_date(day, today()):
        return "La fecha tiene que ser a partir de mañana."
    if is_sunday(day):
        return "Los domingos la clínica está cerrada."
    if not is_within_opening_hours(day, slot):
        return (
            "Atendemos de lunes a viernes de nueve de la mañana a ocho de la tarde "
            "y los sábados de diez a dos de la tarde."
        )
    return None


def request_appointment(request: WebhookRequest) -> WebhookResponse:
    parameters = request.query_result.parameters
    dni = str(parameters.get("dni", ""))
    day = parse_date(str(parameters.get("fecha", "")))
    slot = parse_time(str(parameters.get("hora", "")))
    if day is None or slot is None:
        raise ValueError("Dialogflow sent an unparsable date or time")

    error = _validation_error(dni, day, slot)
    if error is not None:
        logger.info("Appointment rejected: %s", error)
        return WebhookResponse(
            fulfillment_text=ssml(error, pause(), "Vuelve a pedirme la cita cuando quieras."),
            output_contexts=[
                OutputContext(name=request.context_path(BOOKING_CONTEXT), lifespan_count=0),
                OutputContext(
                    name=request.context_path(BOOKING_FOLLOWUP_CONTEXT), lifespan_count=0
                ),
            ],
        )

    animal = animal_label(str(parameters.get("animal", "")))
    return WebhookResponse(
        fulfillment_text=ssml(
            f"Resumo: cita para tu {animal}, el {format_date(day)} a las {format_time(slot)}, "
            "con DNI ", spell(dni), ".", pause(),
            "¿Quieres que la confirme?",
        )
    )