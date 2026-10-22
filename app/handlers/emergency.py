"""Handler for the emergency triage."""

import logging

from app.domain.schemas import OutputContext, WebhookRequest, WebhookResponse
from app.domain.speech import animal_label, pause, ssml
from app.domain.validators import is_valid_dni

logger = logging.getLogger(__name__)

EMERGENCY_CONTEXT = "urgencia_en_curso"
EMERGENCY_FOLLOWUP_CONTEXT = "cita_urgencias-followup"

# Known symptoms that are not listed here are severe. A value outside SYMPTOM_LABELS is
# unknown: the triage cannot judge it, so it offers an immediate slot without naming it.
MILD_SYMPTOMS = frozenset(
    {"vomito", "diarrea", "cojera", "picor", "estornudos", "falta_apetito"}
)

SYMPTOM_LABELS = {
    "convulsiones": "convulsiones",
    "sangrado": "sangrado",
    "envenenamiento": "envenenamiento",
    "atropello": "atropello",
    "no_respira": "no respira",
    "desmayo": "desmayo",
    "abdomen_hinchado": "abdomen hinchado",
    "vomito": "vómitos",
    "diarrea": "diarrea",
    "cojera": "cojera",
    "picor": "picor",
    "estornudos": "estornudos",
    "falta_apetito": "falta de apetito",
}


def symptom_label(value: str) -> str:
    return SYMPTOM_LABELS.get(value, value.replace("_", " "))


def _invalid_dni_response(request: WebhookRequest) -> WebhookResponse:
    return WebhookResponse(
        fulfillment_text=ssml(
            "Ese DNI no parece válido, tiene que llevar ocho cifras y una letra.", pause(),
            "Vuelve a contarme la urgencia cuando quieras.",
        ),
        output_contexts=[
            OutputContext(name=request.context_path(EMERGENCY_CONTEXT), lifespan_count=0),
            OutputContext(name=request.context_path(EMERGENCY_FOLLOWUP_CONTEXT), lifespan_count=0),
        ],
    )


def triage_emergency(request: WebhookRequest) -> WebhookResponse:
    parameters = request.query_result.parameters
    if not is_valid_dni(str(parameters.get("dni", ""))):
        logger.info("Emergency rejected: invalid DNI")
        return _invalid_dni_response(request)

    animal = animal_label(str(parameters.get("animal", "")))
    symptom = str(parameters.get("sintoma", ""))
    label = symptom_label(symptom)
    severity = (
        "unknown"
        if symptom not in SYMPTOM_LABELS
        else "mild" if symptom in MILD_SYMPTOMS else "severe"
    )
    logger.info("Emergency triage: symptom=%s severity=%s", symptom or "-", severity)

    if symptom not in SYMPTOM_LABELS:
        return WebhookResponse(
            fulfillment_text=ssml(
                "No he entendido bien lo que le ocurre, pero puedo reservarte un hueco inmediato.",
                pause(),
                "¿Confirmamos la cita?",
            )
        )
    if symptom in MILD_SYMPTOMS:
        return WebhookResponse(
            fulfillment_text=ssml(
                f"Entendido, tu {animal}: {label}.", pause(),
                "Por lo que me cuentas no parece grave.", pause(),
                "¿Quieres que te reserve un hueco inmediato de todas formas?",
            )
        )
    return WebhookResponse(
        fulfillment_text=ssml(
            f"Entendido, tu {animal}: ", f'<prosody rate="slow">{label}</prosody>.', pause(),
            "Es urgente, no esperes.", pause(),
            "¿Quieres que te reserve un hueco inmediato?",
        )
    )
