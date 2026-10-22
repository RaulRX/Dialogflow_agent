import re
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.handlers import appointment
from app.main import app

SESSION = "projects/test/agent/sessions/abc"
BOOKING_PARAMETERS = {
    "dni": "12345678Z",
    "animal": "perro",
    "fecha": "2026-10-20T12:00:00+02:00",
    "hora": "2026-10-15T17:30:00+02:00",
}
CONFIRMED_PARAMETERS = {
    "confirmada_codigo": "VET0777",
    "confirmada_animal": "perro",
    "confirmada_fecha": "2026-10-20T12:00:00+02:00",
    "confirmada_hora": "2026-10-15T17:30:00+02:00",
}


def context(name: str, parameters: dict[str, Any], lifespan: int = 5) -> dict[str, Any]:
    return {
        "name": f"{SESSION}/contexts/{name}",
        "lifespanCount": lifespan,
        "parameters": parameters,
    }


def build_payload(
    action: str,
    parameters: dict[str, Any] | None = None,
    contexts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "responseId": "r1",
        "session": SESSION,
        "queryResult": {
            "queryText": "texto",
            "action": action,
            "parameters": parameters or {},
            "allRequiredParamsPresent": True,
            "outputContexts": contexts or [],
            "intent": {"displayName": "intent"},
        },
    }


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def contexts_by_name(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {ctx["name"].rsplit("/", 1)[-1]: ctx for ctx in body["outputContexts"]}


class TestConfirmAppointment:
    def test_should_confirm_with_a_code_and_open_confirmed_context(self, client: TestClient) -> None:
        payload = build_payload(
            "cita.pedir.si", contexts=[context("cita_en_curso", BOOKING_PARAMETERS)]
        )

        body = client.post("/webhook", json=payload).json()

        spoken_code = re.search(r">(VET\d{4})</say-as>", body["fulfillmentText"])
        assert spoken_code
        confirmed = contexts_by_name(body)["cita_confirmada"]
        assert confirmed["lifespanCount"] == 10
        assert confirmed["parameters"]["codigo_cita"] == spoken_code.group(1)
        assert confirmed["parameters"]["animal"] == "perro"
        assert confirmed["parameters"]["confirmada_codigo"] == spoken_code.group(1)
        assert confirmed["parameters"]["confirmada_animal"] == "perro"

    def test_should_close_the_booking_context(self, client: TestClient) -> None:
        payload = build_payload(
            "cita.pedir.si", contexts=[context("cita_en_curso", BOOKING_PARAMETERS)]
        )

        body = client.post("/webhook", json=payload).json()

        assert contexts_by_name(body)["cita_en_curso"]["lifespanCount"] == 0

    def test_should_mention_spoken_date_and_time(self, client: TestClient) -> None:
        payload = build_payload(
            "cita.pedir.si", contexts=[context("cita_en_curso", BOOKING_PARAMETERS)]
        )

        text = client.post("/webhook", json=payload).json()["fulfillmentText"]

        assert "martes 20 de octubre" in text
        assert "17:30" in text

    def test_should_explain_there_is_nothing_to_confirm_when_booking_context_is_missing(
        self, client: TestClient
    ) -> None:
        body = client.post("/webhook", json=build_payload("cita.pedir.si")).json()

        assert "no tengo ninguna cita pendiente" in body["fulfillmentText"].lower()
        assert "outputContexts" not in body or not contexts_by_name(body)

    def test_should_skip_codes_that_belong_to_example_appointments(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        numbers = iter([1, 2, 42])
        monkeypatch.setattr(appointment.random, "randint", lambda low, high: next(numbers))

        assert appointment.new_appointment_code() == "VET0042"


class TestLookupAppointment:
    def test_should_use_confirmed_context_when_code_matches(self, client: TestClient) -> None:
        confirmed = {**CONFIRMED_PARAMETERS, "codigo_cita": "VET0777"}
        payload = build_payload(
            "cita.consultar",
            {"codigo_cita": "VET0777"},
            [context("cita_confirmada", confirmed, lifespan=10)],
        )

        text = client.post("/webhook", json=payload).json()["fulfillmentText"]

        assert "martes 20 de octubre" in text
        assert "17:30" in text
        assert "perro" in text

    def test_should_find_example_appointment_when_code_has_spaces_and_lowercase(
        self, client: TestClient
    ) -> None:
        payload = build_payload("cita.consultar", {"codigo_cita": "vet 0001"})

        text = client.post("/webhook", json=payload).json()["fulfillmentText"]

        assert "martes 3 de noviembre" in text
        assert "10:00" in text
        assert "perro" in text

    def test_should_say_not_found_when_code_is_unknown(self, client: TestClient) -> None:
        payload = build_payload("cita.consultar", {"codigo_cita": "VET9999"})

        text = client.post("/webhook", json=payload).json()["fulfillmentText"]

        assert "no encuentro ninguna cita" in text.lower()

    def test_should_not_use_confirmed_context_when_code_differs(self, client: TestClient) -> None:
        confirmed = {**CONFIRMED_PARAMETERS, "codigo_cita": "VET0777"}
        payload = build_payload(
            "cita.consultar",
            {"codigo_cita": "VET9999"},
            [context("cita_confirmada", confirmed, lifespan=10)],
        )

        text = client.post("/webhook", json=payload).json()["fulfillmentText"]

        assert "no encuentro ninguna cita" in text.lower()


    def test_should_ignore_the_values_dialogflow_overwrote_in_the_confirmed_context(
        self, client: TestClient
    ) -> None:
        # A later request (or a lookup) makes Dialogflow replace codigo_cita, animal, fecha and hora.
        overwritten = {
            **CONFIRMED_PARAMETERS,
            "codigo_cita": "VET1234",
            "animal": "gato",
            "fecha": "2026-10-23T12:00:00+02:00",
            "hora": "2026-10-22T22:00:00+02:00",
        }
        payload = build_payload(
            "cita.consultar",
            {"codigo_cita": "VET1234"},
            [context("cita_confirmada", overwritten, lifespan=10)],
        )

        text = client.post("/webhook", json=payload).json()["fulfillmentText"]

        assert "no encuentro ninguna cita" in text.lower()

    def test_should_describe_the_confirmed_appointment_not_the_overwritten_values(
        self, client: TestClient
    ) -> None:
        overwritten = {**CONFIRMED_PARAMETERS, "codigo_cita": "VET0777", "animal": "gato"}
        payload = build_payload(
            "cita.consultar",
            {"codigo_cita": "VET0777"},
            [context("cita_confirmada", overwritten, lifespan=10)],
        )

        text = client.post("/webhook", json=payload).json()["fulfillmentText"]

        assert "perro" in text
        assert "martes 20 de octubre" in text


class TestRequestAppointment:
    @pytest.fixture(autouse=True)
    def fixed_today(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(appointment, "today", lambda: date(2026, 10, 15))

    @staticmethod
    def request_booking(client: TestClient, **overrides: str) -> dict[str, Any]:
        parameters = {**BOOKING_PARAMETERS, **overrides}
        return client.post("/webhook", json=build_payload("cita.pedir", parameters)).json()

    def test_should_summarize_the_booking_when_data_is_valid(self, client: TestClient) -> None:
        body = self.request_booking(client)

        assert "martes 20 de octubre" in body["fulfillmentText"]
        assert "17:30" in body["fulfillmentText"]
        assert "perro" in body["fulfillmentText"]
        assert "confirme" in body["fulfillmentText"]
        assert body["outputContexts"] == []

    @pytest.mark.parametrize(
        ("overrides", "expected_error"),
        [
            ({"dni": "1234567Z"}, "dni"),
            ({"fecha": "2026-10-15T12:00:00+02:00"}, "fecha"),
            ({"fecha": "2026-10-14T12:00:00+02:00"}, "fecha"),
            ({"fecha": "2026-10-18T12:00:00+02:00"}, "domingos"),
            ({"hora": "2026-10-15T20:00:00+02:00"}, "atendemos"),
            ({"fecha": "2026-10-17T12:00:00+02:00", "hora": "2026-10-15T15:00:00+02:00"}, "atendemos"),
        ],
    )
    def test_should_state_the_error_when_data_is_invalid(
        self, client: TestClient, overrides: dict[str, str], expected_error: str
    ) -> None:
        body = self.request_booking(client, **overrides)

        assert expected_error in body["fulfillmentText"].lower()
        assert "vuelve a pedirme la cita" in body["fulfillmentText"].lower()

    def test_should_close_booking_contexts_when_data_is_invalid(self, client: TestClient) -> None:
        body = self.request_booking(client, dni="1234567Z")

        contexts = contexts_by_name(body)
        assert contexts["cita_en_curso"]["lifespanCount"] == 0
        assert contexts["pedir_cita-followup"]["lifespanCount"] == 0

    def test_should_accept_appointment_when_date_is_tomorrow_and_time_is_first_slot(
        self, client: TestClient
    ) -> None:
        body = self.request_booking(
            client, fecha="2026-10-16T12:00:00+02:00", hora="2026-10-15T09:00:00+02:00"
        )

        assert "confirme" in body["fulfillmentText"]
