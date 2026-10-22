"""Handlers that answer questions about the clinic documents through the language model."""

import logging
from collections.abc import Callable

from app.domain.actions import ActionNames
from app.domain.knowledge_base import Document, KnowledgeBase
from app.domain.schemas import OutputContext, WebhookRequest, WebhookResponse
from app.domain.speech import pause, speak_text, ssml
from app.llm.client import LLMClient, LLMError
from app.llm.prompts import MISSING_DATA_PREFIX

logger = logging.getLogger(__name__)

PENDING_CONTEXT = "pregunta_pendiente"
PENDING_LIFESPAN = 2
TOPIC_CONTEXTS = ("prospecto_activo", "cuidados_activo")
HINT_PARAMETERS = ("medicamento", "animal", "tema")
FICTIONAL_FOOTER = "Documento ficticio"

LLM_FAILURE_MESSAGE = (
    "Ahora mismo no puedo consultar la documentación. Inténtalo de nuevo en un momento."
)
DEFAULT_MISSING_DATA_QUESTION = "¿Sobre qué animal o medicamento quieres saber?"

DocumentSelector = Callable[[dict[str, str]], list[Document]]


def _as_text(value: object) -> str:
    """Dialogflow sends list-valued parameters (such as `tema`) as lists."""
    if isinstance(value, list):
        return ", ".join(text for item in value if (text := str(item).strip()))
    return str(value).strip()


def _parameter_hints(parameters: dict[str, object]) -> dict[str, str]:
    values = {name: _as_text(parameters.get(name, "")) for name in HINT_PARAMETERS}
    return {name: value for name, value in values.items() if value}


def _collect_hints(request: WebhookRequest) -> dict[str, str]:
    """What is known about the topic: the active topic context first, then this turn's
    parameters, which win because they are the most recent."""
    hints: dict[str, str] = {}
    for name in TOPIC_CONTEXTS:
        context = request.find_context(name)
        if context is not None and context.lifespan_count > 0:
            hints.update(_parameter_hints(context.parameters))
    hints.update(_parameter_hints(request.query_result.parameters))
    return hints


def _build_question(query_text: str, hints: dict[str, str]) -> str:
    """Short follow-ups ("¿y para un gato?") and slot-filling turns ("perro") do not carry
    the topic, so it is appended to the user's own words."""
    if not hints:
        return query_text
    details = ", ".join(f"{name}: {value}" for name, value in hints.items())
    return f"{query_text} ({details})"


def _pending_question(request: WebhookRequest) -> str | None:
    """The question the model could not answer yet, while the user is supplying the missing data."""
    context = request.find_context(PENDING_CONTEXT)
    if context is None or context.lifespan_count <= 0:
        return None
    return str(context.parameters.get("pregunta", "")).strip() or None


def _close_pending(request: WebhookRequest, response: WebhookResponse) -> WebhookResponse:
    if any(context.short_name == PENDING_CONTEXT for context in response.output_contexts):
        return response
    closing = OutputContext(name=request.context_path(PENDING_CONTEXT), lifespan_count=0)
    return response.model_copy(update={"output_contexts": [*response.output_contexts, closing]})


def _spoken_clinic_document(text: str) -> str:
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.startswith(FICTIONAL_FOOTER)
    ]
    return ssml(pause().join(speak_text(line) for line in lines))


class DocumentHandlers:
    def __init__(self, llm: LLMClient, knowledge_base: KnowledgeBase) -> None:
        self._llm = llm
        self._knowledge_base = knowledge_base

    def build_handlers(
        self, actions: ActionNames
    ) -> dict[str, Callable[[WebhookRequest], WebhookResponse]]:
        return {
            actions.leaflet: self.consult_leaflet,
            actions.leaflet_followup: self.consult_leaflet,
            actions.care: self.consult_care_guide,
            actions.care_followup: self.consult_care_guide,
            actions.fallback: self.answer_free_question,
            actions.clinic: self.answer_clinic_question,
        }

    def consult_leaflet(self, request: WebhookRequest) -> WebhookResponse:
        return self._answer(
            request,
            lambda hints: self._knowledge_base.select_documents(
                "prospecto", hints.get("medicamento", "")
            ),
        )

    def consult_care_guide(self, request: WebhookRequest) -> WebhookResponse:
        return self._answer(
            request,
            lambda hints: self._knowledge_base.select_documents(
                "cuidados", hints.get("animal", "")
            ),
        )

    def answer_free_question(self, request: WebhookRequest) -> WebhookResponse:
        return self._answer(request, lambda _: self._knowledge_base.all_documents())

    def answer_clinic_question(self, request: WebhookRequest) -> WebhookResponse:
        documents = self._knowledge_base.select_documents("clinica")
        source = self._source(documents)
        try:
            answer = self._call_model(request, request.query_result.query_text, documents, {})
        except LLMError:
            return self._clinic_document_response(documents, source)
        if answer.startswith(MISSING_DATA_PREFIX):
            logger.warning("The model asked for missing data on a clinic question")
            return self._clinic_document_response(documents, source)
        return WebhookResponse(fulfillment_text=ssml(speak_text(answer)), source=source)

    def _clinic_document_response(self, documents: list[Document], source: str) -> WebhookResponse:
        text = _spoken_clinic_document(self._knowledge_base.join_text(documents))
        return WebhookResponse(fulfillment_text=text, source=source)

    def _answer(self, request: WebhookRequest, select_documents: DocumentSelector) -> WebhookResponse:
        hints = _collect_hints(request)
        pending = _pending_question(request)
        query_text = request.query_result.query_text
        if pending is None:
            question = _build_question(query_text, hints)
            return self._ask(request, question, select_documents(hints), hints)

        # The original question may belong to any category, so the model gets every document.
        logger.info("Resuming the pending question with every document")
        question = _build_question(f"{pending} {query_text}", hints)
        response = self._ask(request, question, self._knowledge_base.all_documents(), hints)
        return _close_pending(request, response)

    def _ask(
        self,
        request: WebhookRequest,
        question: str,
        documents: list[Document],
        hints: dict[str, str],
    ) -> WebhookResponse:
        try:
            answer = self._call_model(request, question, documents, hints)
        except LLMError:
            return WebhookResponse(fulfillment_text=ssml(LLM_FAILURE_MESSAGE))
        return self._to_response(request, answer, question, self._source(documents))

    def _call_model(
        self,
        request: WebhookRequest,
        question: str,
        documents: list[Document],
        hints: dict[str, str],
    ) -> str:
        logger.info(
            "Model call: action=%s docs=[%s] hints=%s",
            request.query_result.action,
            self._source(documents),
            hints or "-",
        )
        return self._llm.answer(question, self._knowledge_base.join_text(documents))

    def _source(self, documents: list[Document]) -> str:
        """Documents the answer is based on; listing every id when all are sent adds nothing."""
        if len(documents) == len(self._knowledge_base):
            return f"todos ({len(documents)})"
        return ", ".join(document.id for document in documents)

    @staticmethod
    def _to_response(
        request: WebhookRequest, answer: str, question: str, source: str
    ) -> WebhookResponse:
        if not answer.startswith(MISSING_DATA_PREFIX):
            return WebhookResponse(fulfillment_text=ssml(speak_text(answer)), source=source)

        logger.info("The model asked for missing data")
        follow_up = answer[len(MISSING_DATA_PREFIX):].strip() or DEFAULT_MISSING_DATA_QUESTION
        return WebhookResponse(
            fulfillment_text=ssml(speak_text(follow_up)),
            output_contexts=[
                OutputContext(
                    name=request.context_path(PENDING_CONTEXT),
                    lifespan_count=PENDING_LIFESPAN,
                    parameters={"pregunta": question},
                ),
                *(
                    OutputContext(name=request.context_path(name), lifespan_count=0)
                    for name in TOPIC_CONTEXTS
                ),
            ],
            source=source,
        )
