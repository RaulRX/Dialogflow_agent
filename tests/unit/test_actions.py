import pytest
from pydantic import ValidationError

from app.domain.actions import ActionNames
from app.domain.knowledge_base import Document, KnowledgeBase
from app.handlers import build_handlers
from app.handlers.documents import DocumentHandlers


class UnusedLLMClient:
    def answer(self, question: str, documents: str) -> str:
        raise AssertionError("The registry must not call the model")


def test_should_default_to_the_names_of_the_current_agent() -> None:
    actions = ActionNames()

    assert actions.booking_request == "cita.pedir"
    assert actions.fallback == "input.unknown"


def test_should_read_an_action_name_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ACTION_BOOKING_REQUEST", "appointment.request")

    assert ActionNames().booking_request == "appointment.request"


def test_should_reject_repeated_action_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ACTION_CARE", "prospecto.consultar")

    with pytest.raises(ValidationError, match="prospecto.consultar"):
        ActionNames()


def test_should_register_handlers_under_the_configured_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ACTION_BOOKING_REQUEST", "appointment.request")
    monkeypatch.setenv("ACTION_CLINIC", "clinic.info")
    documents = DocumentHandlers(
        UnusedLLMClient(), KnowledgeBase([Document("clinica_info", "clinica", "info", "texto")])
    )

    handlers = build_handlers(ActionNames(), documents)

    assert "appointment.request" in handlers
    assert "clinic.info" in handlers
    assert "cita.pedir" not in handlers
    assert "clinica.info" not in handlers
    assert len(handlers) == 10
