from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app

SESSION = "projects/test/agent/sessions/abc"
SEVERE_SYMPTOMS = [
    "convulsiones",
    "sangrado",
    "envenenamiento",
    "atropello",
    "no_respira",
    "desmayo",
    "abdomen_hinchado",
]
MILD_SYMPTOMS = ["vomito", "diarrea", "cojera", "picor", "estornudos", "falta_apetito"]


def build_payload(parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "responseId": "r1",
        "session": SESSION,
        "queryResult": {
            "queryText": "texto",
            "action": "cita.urgencia",
            "parameters": parameters,
            "allRequiredParamsPresent": True,
            "outputContexts": [],
            "intent": {"displayName": "cita_urgencias"},
        },
    }


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def triage(client: TestClient, symptom: str, animal: str = "perro") -> dict[str, Any]:
    parameters = {"dni": "12345678Z", "animal": animal, "sintoma": symptom}
    return client.post("/webhook", json=build_payload(parameters)).json()


@pytest.mark.parametrize("symptom", SEVERE_SYMPTOMS)
def test_should_mark_as_urgent_when_symptom_is_severe(client: TestClient, symptom: str) -> None:
    text = triage(client, symptom)["fulfillmentText"]

    assert "es urgente" in text.lower()
    assert "no parece grave" not in text.lower()
    assert "hueco inmediato" in text


@pytest.mark.parametrize("symptom", MILD_SYMPTOMS)
def test_should_say_it_is_not_severe_when_symptom_is_mild(client: TestClient, symptom: str) -> None:
    text = triage(client, symptom)["fulfillmentText"]

    assert "no parece grave" in text.lower()
    assert "es urgente" not in text.lower()
    assert "hueco inmediato" in text


def test_should_offer_a_slot_without_naming_the_symptom_when_it_is_unknown(
    client: TestClient,
) -> None:
    body = triage(client, "ratoncita")
    text = body["fulfillmentText"]

    assert "no he entendido" in text.lower()
    assert "hueco inmediato" in text
    assert "confirmamos la cita" in text.lower()
    assert "ratoncita" not in text
    assert body["outputContexts"] == []


@pytest.mark.parametrize(
    ("symptom", "spoken"),
    [("no_respira", "no respira"), ("falta_apetito", "falta de apetito"), ("vomito", "vómitos")],
)
def test_should_speak_a_readable_symptom_name(
    client: TestClient, symptom: str, spoken: str
) -> None:
    text = triage(client, symptom)["fulfillmentText"]

    assert spoken in text
    assert "_" not in text


def test_should_restore_accent_when_animal_is_huron(client: TestClient) -> None:
    text = triage(client, "diarrea", animal="huron")["fulfillmentText"]

    assert "hurón" in text


def test_should_not_touch_contexts(client: TestClient) -> None:
    assert triage(client, "convulsiones")["outputContexts"] == []


def triage_with_dni(client: TestClient, dni: str) -> dict[str, Any]:
    parameters = {"dni": dni, "animal": "perro", "sintoma": "convulsiones"}
    return client.post("/webhook", json=build_payload(parameters)).json()


@pytest.mark.parametrize("dni", ["1234567Z", "12345678", "ABCDEFGHZ"])
def test_should_state_the_error_and_stop_the_triage_when_dni_format_is_invalid(
    client: TestClient, dni: str
) -> None:
    text = triage_with_dni(client, dni)["fulfillmentText"]

    assert "dni no parece válido" in text.lower()
    assert "hueco inmediato" not in text


def test_should_close_emergency_contexts_when_dni_format_is_invalid(client: TestClient) -> None:
    body = triage_with_dni(client, "1234567Z")

    lifespans = {c["name"].rsplit("/", 1)[-1]: c["lifespanCount"] for c in body["outputContexts"]}
    assert lifespans == {"urgencia_en_curso": 0, "cita_urgencias-followup": 0}


def test_should_accept_dni_when_control_letter_does_not_match_the_number(
    client: TestClient,
) -> None:
    text = triage_with_dni(client, "12345678K")["fulfillmentText"]

    assert "es urgente" in text.lower()
