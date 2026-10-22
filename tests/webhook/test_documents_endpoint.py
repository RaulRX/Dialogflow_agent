from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.llm.client import LLMError
from app.main import create_app

SESSION = "projects/test/agent/sessions/abc"


class FakeLLMClient:
    def __init__(self, answer: str = "Respuesta del modelo.", error: Exception | None = None):
        self._answer = answer
        self._error = error
        self.calls: list[tuple[str, str]] = []

    def answer(self, question: str, documents: str) -> str:
        self.calls.append((question, documents))
        if self._error is not None:
            raise self._error
        return self._answer


def build_payload(
    action: str, query_text: str = "pregunta", parameters: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "responseId": "r1",
        "session": SESSION,
        "queryResult": {
            "queryText": query_text,
            "action": action,
            "parameters": parameters or {},
            "allRequiredParamsPresent": True,
            "outputContexts": [],
            "intent": {"displayName": "intent"},
        },
    }


@pytest.fixture
def llm() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
def client(llm: FakeLLMClient) -> Iterator[TestClient]:
    with TestClient(create_app(llm=llm)) as test_client:
        yield test_client


def test_should_answer_a_clinic_question_with_the_real_knowledge_base(
    client: TestClient, llm: FakeLLMClient
) -> None:
    body = client.post(
        "/webhook", json=build_payload("clinica.info", query_text="¿dónde estáis?")
    ).json()

    assert body["fulfillmentText"] == "<speak>Respuesta del modelo.</speak>"
    question, documents = llm.calls[0]
    assert question == "¿dónde estáis?"
    assert "Calle Ficticia 12" in documents


def test_should_send_the_leaflet_of_the_medication_to_the_model(
    client: TestClient, llm: FakeLLMClient
) -> None:
    client.post(
        "/webhook",
        json=build_payload("prospecto.consultar", parameters={"medicamento": "doloxan"}),
    )

    documents = llm.calls[0][1]
    assert "DOLOXAN" in documents.upper()
    assert "ZENPET" not in documents.upper()


def test_should_use_the_fallback_handler_for_unmatched_questions(
    client: TestClient, llm: FakeLLMClient
) -> None:
    client.post("/webhook", json=build_payload("input.unknown", query_text="¿qué tiempo hace?"))

    assert llm.calls[0][0] == "¿qué tiempo hace?"


def test_should_fall_back_to_the_clinic_text_when_the_model_fails() -> None:
    failing = FakeLLMClient(error=LLMError("boom"))
    with TestClient(create_app(llm=failing)) as client:
        body = client.post("/webhook", json=build_payload("clinica.info")).json()

    assert "Calle Ficticia 12" in body["fulfillmentText"]


def test_should_still_serve_the_appointment_actions(client: TestClient) -> None:
    payload = build_payload("cita.consultar", parameters={"codigo_cita": "VET0001"})

    body = client.post("/webhook", json=payload).json()

    assert "Tu cita con código" in body["fulfillmentText"]
