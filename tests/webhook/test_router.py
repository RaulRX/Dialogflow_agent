from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.domain.schemas import OutputContext, WebhookRequest, WebhookResponse
from app.main import GENERIC_ERROR_MESSAGE, app

SESSION = "projects/test/agent/sessions/abc"


def build_payload(action: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "responseId": "r1",
        "session": SESSION,
        "queryResult": {
            "queryText": "texto",
            "action": action,
            "parameters": parameters or {},
            "allRequiredParamsPresent": True,
            "outputContexts": [],
            "intent": {"displayName": "intent"},
        },
    }


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_should_report_ok_when_health_is_called(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_should_return_empty_text_when_action_has_no_handler(client: TestClient) -> None:
    response = client.post("/webhook", json=build_payload("accion.inexistente"))

    assert response.status_code == 200
    assert response.json()["fulfillmentText"] == ""


def test_should_call_registered_handler_and_serialize_with_camel_case(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def handler(request: WebhookRequest) -> WebhookResponse:
        return WebhookResponse(
            fulfillment_text=f"hola {request.query_result.parameters['animal']}",
            output_contexts=[
                OutputContext(name=request.context_path("demo"), lifespan_count=3)
            ],
        )

    monkeypatch.setitem(app.state.handlers, "demo.action", handler)

    response = client.post("/webhook", json=build_payload("demo.action", {"animal": "perro"}))

    body = response.json()
    assert body["fulfillmentText"] == "hola perro"
    assert body["outputContexts"][0]["name"] == f"{SESSION}/contexts/demo"
    assert body["outputContexts"][0]["lifespanCount"] == 3


def test_should_return_generic_message_without_leaking_error_when_handler_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing_handler(request: WebhookRequest) -> WebhookResponse:
        raise RuntimeError("secret internal detail")

    monkeypatch.setitem(app.state.handlers, "demo.fail", failing_handler)

    response = client.post("/webhook", json=build_payload("demo.fail"))

    assert response.status_code == 200
    assert response.json()["fulfillmentText"] == GENERIC_ERROR_MESSAGE
    assert "secret internal detail" not in response.text


def test_should_serialize_the_source_only_when_the_handler_sets_it(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(
        app.state.handlers, "demo.plain", lambda request: WebhookResponse(fulfillment_text="a")
    )
    monkeypatch.setitem(
        app.state.handlers,
        "demo.sourced",
        lambda request: WebhookResponse(fulfillment_text="b", source="prospecto_doloxan"),
    )

    plain = client.post("/webhook", json=build_payload("demo.plain")).json()
    sourced = client.post("/webhook", json=build_payload("demo.sourced")).json()

    assert "source" not in plain
    assert sourced["source"] == "prospecto_doloxan"
