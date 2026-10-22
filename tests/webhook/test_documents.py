from typing import Any

import pytest

from app.domain.actions import ActionNames
from app.domain.knowledge_base import Document, KnowledgeBase
from app.domain.schemas import WebhookRequest
from app.handlers.documents import (
    DEFAULT_MISSING_DATA_QUESTION,
    LLM_FAILURE_MESSAGE,
    DocumentHandlers,
)
from app.llm.client import LLMError

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


KNOWLEDGE_BASE = KnowledgeBase(
    [
        Document("cuidados_gato", "cuidados", "gato", "GUIA GATO"),
        Document("cuidados_perro", "cuidados", "perro", "GUIA PERRO"),
        Document("prospecto_doloxan", "prospecto", "doloxan", "PROSPECTO DOLOXAN"),
        Document("prospecto_zenpet", "prospecto", "zenpet", "PROSPECTO ZENPET"),
        Document(
            "clinica_info",
            "clinica",
            "info",
            "INFORMACION DE LA CLINICA\nHorario de lunes a viernes: de 9 a 20 horas\n"
            "Telefono de urgencias: 900000000\nDocumento ficticio, solo para practica",
        ),
    ]
)
EVERY_DOCUMENT = KNOWLEDGE_BASE.select_all()


def build_request(
    action: str,
    query_text: str = "pregunta",
    parameters: dict[str, Any] | None = None,
    contexts: list[dict[str, Any]] | None = None,
) -> WebhookRequest:
    return WebhookRequest.model_validate(
        {
            "session": SESSION,
            "queryResult": {
                "queryText": query_text,
                "action": action,
                "parameters": parameters or {},
                "outputContexts": contexts or [],
            },
        }
    )


def topic_context(name: str, lifespan: int = 5, **parameters: str) -> dict[str, Any]:
    return {
        "name": f"{SESSION}/contexts/{name}",
        "lifespanCount": lifespan,
        "parameters": parameters,
    }


def handle(llm: FakeLLMClient, request: WebhookRequest):
    handlers = DocumentHandlers(llm, KNOWLEDGE_BASE).build_handlers(ActionNames())
    return handlers[request.query_result.action](request)


def test_should_register_every_document_action() -> None:
    handlers = DocumentHandlers(FakeLLMClient(), KNOWLEDGE_BASE).build_handlers(ActionNames())

    assert set(handlers) == {
        "prospecto.consultar",
        "prospecto.seguimiento",
        "cuidados.consultar",
        "cuidados.seguimiento",
        "input.unknown",
        "clinica.info",
    }


class TestDocumentSelection:
    def test_should_send_only_the_leaflet_of_the_medication(self) -> None:
        llm = FakeLLMClient()

        handle(llm, build_request("prospecto.consultar", parameters={"medicamento": "zenpet"}))

        assert llm.calls[0][1] == "PROSPECTO ZENPET"

    def test_should_send_only_the_care_guide_of_the_animal(self) -> None:
        llm = FakeLLMClient()

        handle(llm, build_request("cuidados.consultar", parameters={"animal": "gato"}))

        assert llm.calls[0][1] == "GUIA GATO"

    def test_should_send_every_guide_when_the_animal_is_unknown(self) -> None:
        llm = FakeLLMClient()

        handle(llm, build_request("cuidados.consultar"))

        assert llm.calls[0][1] == "GUIA GATO\n\nGUIA PERRO"


class TestQuestion:
    def test_should_send_the_user_words_unchanged_when_nothing_else_is_known(self) -> None:
        llm = FakeLLMClient()

        handle(llm, build_request("cuidados.consultar", query_text="¿qué come?"))

        assert llm.calls[0][0] == "¿qué come?"

    def test_should_append_the_parameters_of_the_turn(self) -> None:
        llm = FakeLLMClient()

        handle(
            llm,
            build_request(
                "prospecto.consultar",
                query_text="perro",
                parameters={"medicamento": "doloxan", "animal": "perro", "tema": "dosis"},
            ),
        )

        assert llm.calls[0][0] == "perro (medicamento: doloxan, animal: perro, tema: dosis)"

    def test_should_complete_a_follow_up_with_the_active_topic_context(self) -> None:
        llm = FakeLLMClient()
        request = build_request(
            "prospecto.seguimiento",
            query_text="¿y para un gato?",
            parameters={"animal": "gato"},
            contexts=[topic_context("prospecto_activo", medicamento="doloxan", animal="perro", tema="dosis")],
        )

        handle(llm, request)

        question, documents = llm.calls[0]
        assert question == "¿y para un gato? (medicamento: doloxan, animal: gato, tema: dosis)"
        assert documents == "PROSPECTO DOLOXAN"

    def test_should_ignore_an_expired_topic_context(self) -> None:
        llm = FakeLLMClient()
        request = build_request(
            "cuidados.consultar",
            query_text="¿qué come?",
            contexts=[topic_context("prospecto_activo", lifespan=0, medicamento="doloxan")],
        )

        handle(llm, request)

        assert llm.calls[0][0] == "¿qué come?"

    def test_should_ignore_empty_parameters(self) -> None:
        llm = FakeLLMClient()

        handle(
            llm,
            build_request("cuidados.consultar", query_text="hola", parameters={"animal": "", "tema": ""}),
        )

        assert llm.calls[0][0] == "hola"


class TestAnswer:
    def test_should_speak_the_model_answer(self) -> None:
        response = handle(
            FakeLLMClient("Dale una dosis al día."),
            build_request("cuidados.consultar"),
        )

        assert response.fulfillment_text == "<speak>Dale una dosis al día.</speak>"
        assert response.output_contexts == []

    def test_should_escape_markup_in_the_model_answer(self) -> None:
        response = handle(
            FakeLLMClient("Consultas & urgencias <b>24 horas</b>."),
            build_request("cuidados.consultar"),
        )

        assert "&amp;" in response.fulfillment_text
        assert "<b>" not in response.fulfillment_text

    def test_should_return_the_failure_message_when_the_model_fails(self) -> None:
        response = handle(
            FakeLLMClient(error=LLMError("boom")),
            build_request("prospecto.consultar"),
        )

        assert LLM_FAILURE_MESSAGE in response.fulfillment_text
        assert response.output_contexts == []


class TestMissingData:
    @staticmethod
    def ask_for_missing_data(answer: str = "MISSING_DATA: ¿Para qué animal?"):
        request = build_request(
            "cuidados.consultar",
            query_text="¿qué come?",
            contexts=[topic_context("cuidados_activo", animal="gato")],
        )
        return handle(FakeLLMClient(answer), request)

    def test_should_ask_the_follow_up_question_without_the_prefix(self) -> None:
        response = self.ask_for_missing_data()

        assert response.fulfillment_text == "<speak>¿Para qué animal?</speak>"

    def test_should_keep_the_original_question_in_the_pending_context(self) -> None:
        response = self.ask_for_missing_data()

        pending = next(c for c in response.output_contexts if c.short_name == "pregunta_pendiente")
        assert pending.lifespan_count == 2
        assert pending.parameters == {"pregunta": "¿qué come? (animal: gato)"}
        assert pending.name == f"{SESSION}/contexts/pregunta_pendiente"

    @pytest.mark.parametrize("name", ["prospecto_activo", "cuidados_activo"])
    def test_should_close_the_topic_contexts(self, name: str) -> None:
        response = self.ask_for_missing_data()

        context = next(c for c in response.output_contexts if c.short_name == name)
        assert context.lifespan_count == 0

    def test_should_use_a_default_question_when_the_model_gives_none(self) -> None:
        response = self.ask_for_missing_data("MISSING_DATA:")

        assert DEFAULT_MISSING_DATA_QUESTION in response.fulfillment_text


class TestFreeQuestion:
    def test_should_send_every_document_to_the_model(self) -> None:
        llm = FakeLLMClient()

        response = handle(llm, build_request("input.unknown", query_text="¿cuánto pesa un gato?"))

        assert llm.calls == [("¿cuánto pesa un gato?", EVERY_DOCUMENT)]
        assert "Respuesta del modelo." in response.fulfillment_text

    def test_should_return_the_failure_message_when_the_model_fails(self) -> None:
        response = handle(
            FakeLLMClient(error=LLMError("boom")), build_request("input.unknown")
        )

        assert LLM_FAILURE_MESSAGE in response.fulfillment_text


class TestPendingQuestion:
    @staticmethod
    def pending_context(lifespan: int = 2) -> dict[str, Any]:
        return {
            "name": f"{SESSION}/contexts/pregunta_pendiente",
            "lifespanCount": lifespan,
            "parameters": {"pregunta": "¿qué come?"},
        }

    @pytest.mark.parametrize("action", ["input.unknown", "cuidados.consultar", "prospecto.consultar"])
    def test_should_join_the_original_question_with_the_answer(self, action: str) -> None:
        llm = FakeLLMClient()
        request = build_request(
            action,
            query_text="perro",
            parameters={"animal": "perro"},
            contexts=[self.pending_context()],
        )

        handle(llm, request)

        assert llm.calls == [("¿qué come? perro (animal: perro)", EVERY_DOCUMENT)]

    def test_should_close_the_pending_context_after_answering(self) -> None:
        request = build_request("cuidados.consultar", query_text="perro", contexts=[self.pending_context()])

        response = handle(FakeLLMClient(), request)

        pending = next(c for c in response.output_contexts if c.short_name == "pregunta_pendiente")
        assert pending.lifespan_count == 0

    def test_should_close_the_pending_context_when_the_model_fails(self) -> None:
        request = build_request("input.unknown", query_text="perro", contexts=[self.pending_context()])

        response = handle(FakeLLMClient(error=LLMError("boom")), request)

        pending = next(c for c in response.output_contexts if c.short_name == "pregunta_pendiente")
        assert pending.lifespan_count == 0

    def test_should_renew_the_pending_context_when_data_is_still_missing(self) -> None:
        request = build_request("input.unknown", query_text="el mío", contexts=[self.pending_context()])

        response = handle(FakeLLMClient("MISSING_DATA: ¿Qué animal?"), request)

        pendings = [c for c in response.output_contexts if c.short_name == "pregunta_pendiente"]
        assert len(pendings) == 1
        assert pendings[0].lifespan_count == 2
        assert pendings[0].parameters == {"pregunta": "¿qué come? el mío"}

    def test_should_ignore_an_expired_pending_context(self) -> None:
        llm = FakeLLMClient()
        request = build_request(
            "cuidados.consultar", query_text="perro", contexts=[self.pending_context(lifespan=0)]
        )

        handle(llm, request)

        assert llm.calls[0][0] == "perro"


class TestClinicQuestion:
    def test_should_answer_with_the_clinic_document_only(self) -> None:
        llm = FakeLLMClient("Abrimos a las 9.")

        response = handle(llm, build_request("clinica.info", query_text="¿a qué hora abrís?"))

        assert llm.calls == [("¿a qué hora abrís?", KNOWLEDGE_BASE.select("clinica"))]
        assert response.fulfillment_text == "<speak>Abrimos a las 9.</speak>"

    def test_should_read_the_phone_digit_by_digit(self) -> None:
        response = handle(FakeLLMClient("Llama al 900000000."), build_request("clinica.info"))

        assert '<say-as interpret-as="telephone">900000000</say-as>' in response.fulfillment_text

    @pytest.mark.parametrize(
        "llm",
        [FakeLLMClient(error=LLMError("boom")), FakeLLMClient("MISSING_DATA: ¿Qué animal?")],
    )
    def test_should_fall_back_to_the_document_text(self, llm: FakeLLMClient) -> None:
        response = handle(llm, build_request("clinica.info"))

        text = response.fulfillment_text
        assert "Horario de lunes a viernes: de 9 a 20 horas" in text
        assert '<say-as interpret-as="telephone">900000000</say-as>' in text
        assert "ficticio" not in text
        assert "MISSING_DATA" not in text

    def test_should_not_touch_the_pending_context(self) -> None:
        request = build_request(
            "clinica.info",
            query_text="¿dónde estáis?",
            contexts=[
                {
                    "name": f"{SESSION}/contexts/pregunta_pendiente",
                    "lifespanCount": 2,
                    "parameters": {"pregunta": "¿qué come?"},
                }
            ],
        )
        llm = FakeLLMClient()

        response = handle(llm, request)

        assert llm.calls[0][0] == "¿dónde estáis?"
        assert response.output_contexts == []


class TestSourceAndLogging:
    def test_should_report_the_leaflet_used_as_source(self) -> None:
        response = handle(
            FakeLLMClient(), build_request("prospecto.consultar", parameters={"medicamento": "zenpet"})
        )

        assert response.source == "prospecto_zenpet"

    def test_should_report_every_document_of_the_category_when_the_subject_is_unknown(self) -> None:
        response = handle(FakeLLMClient(), build_request("cuidados.consultar"))

        assert response.source == "cuidados_gato, cuidados_perro"

    def test_should_summarize_the_source_when_every_document_is_sent(self) -> None:
        response = handle(FakeLLMClient(), build_request("input.unknown"))

        assert response.source == "todos (5)"

    def test_should_report_the_clinic_document_as_source(self) -> None:
        response = handle(FakeLLMClient(), build_request("clinica.info"))

        assert response.source == "clinica_info"

    def test_should_keep_the_source_when_the_clinic_model_fails(self) -> None:
        response = handle(FakeLLMClient(error=LLMError("boom")), build_request("clinica.info"))

        assert response.source == "clinica_info"

    def test_should_not_report_a_source_when_the_model_fails(self) -> None:
        response = handle(
            FakeLLMClient(error=LLMError("boom")),
            build_request("prospecto.consultar", parameters={"medicamento": "zenpet"}),
        )

        assert response.source is None

    def test_should_report_every_document_when_resuming_a_pending_question(self) -> None:
        request = build_request(
            "cuidados.consultar",
            query_text="perro",
            contexts=[topic_context("pregunta_pendiente", lifespan=2, pregunta="¿qué come?")],
        )

        assert handle(FakeLLMClient(), request).source == "todos (5)"

    def test_should_log_the_documents_without_the_user_question(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("INFO")
        request = build_request(
            "prospecto.consultar",
            query_text="pregunta privada",
            parameters={"medicamento": "zenpet"},
        )

        handle(FakeLLMClient(), request)

        assert "docs=[prospecto_zenpet]" in caplog.text
        assert "pregunta privada" not in caplog.text


class TestListParameters:
    def test_should_send_a_list_parameter_as_plain_text(self) -> None:
        llm = FakeLLMClient()

        handle(
            llm,
            build_request(
                "prospecto.seguimiento",
                query_text="¿y para un gato?",
                parameters={"medicamento": "doloxan", "tema": ["dosis", "modo_aplicacion"]},
            ),
        )

        assert llm.calls[0][0] == "¿y para un gato? (medicamento: doloxan, tema: dosis, modo_aplicacion)"

    def test_should_ignore_an_empty_list_parameter(self) -> None:
        llm = FakeLLMClient()

        handle(llm, build_request("cuidados.consultar", query_text="¿qué come?", parameters={"tema": []}))

        assert llm.calls[0][0] == "¿qué come?"
