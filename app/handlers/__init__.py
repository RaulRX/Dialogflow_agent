"""Registry that maps a Dialogflow action to its webhook handler."""

from collections.abc import Callable

from app.domain.actions import ActionNames
from app.domain.schemas import WebhookRequest, WebhookResponse
from app.handlers import appointment, emergency
from app.handlers.documents import DocumentHandlers

Handler = Callable[[WebhookRequest], WebhookResponse]


def build_handlers(actions: ActionNames, documents: DocumentHandlers) -> dict[str, Handler]:
    handlers: dict[str, Handler] = {
        actions.booking_request: appointment.request_appointment,
        actions.booking_confirm: appointment.confirm_appointment,
        actions.booking_lookup: appointment.lookup_appointment,
        actions.emergency: emergency.triage_emergency,
    }
    handlers.update(documents.build_handlers(actions))
    return handlers
