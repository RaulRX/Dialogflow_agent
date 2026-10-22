"""FastAPI entrypoint for the Dialogflow ES fulfillment webhook."""

import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request

from app.domain.actions import get_actions
from app.domain.config import get_settings
from app.domain.knowledge_base import KnowledgeBase
from app.domain.schemas import WebhookRequest, WebhookResponse
from app.handlers import build_handlers
from app.handlers.documents import DocumentHandlers
from app.llm.client import LLMClient
from app.llm.gemini_client import GeminiClient

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
# These libraries log every HTTP call at INFO, which buries the webhook's own flow lines.
for noisy_logger in ("httpx", "google_genai"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

logger = logging.getLogger("webhook")

GENERIC_ERROR_MESSAGE = "Lo siento, ha ocurrido un problema. ¿Puedes repetirlo, por favor?"

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/webhook", response_model_exclude_none=True)
def webhook(request: WebhookRequest, http_request: Request) -> WebhookResponse:
    action = request.query_result.action
    handler = http_request.app.state.handlers.get(action)
    if handler is None:
        logger.info("No handler for action=%s, using static response", action)
        return WebhookResponse(fulfillment_text="")

    started = time.perf_counter()
    try:
        response = handler(request)
    except Exception:
        logger.exception("Handler failed for action=%s", action)
        return WebhookResponse(fulfillment_text=GENERIC_ERROR_MESSAGE)
    logger.info("Handled action=%s in %.0f ms", action, (time.perf_counter() - started) * 1000)
    return response


def create_app(llm: LLMClient | None = None) -> FastAPI:
    """Build the webhook. The model client is injectable so tests never reach the network."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        settings = get_settings()
        knowledge_base = KnowledgeBase.from_file(settings.knowledge_base_path)
        documents = DocumentHandlers(llm or GeminiClient(settings), knowledge_base)
        app.state.handlers = build_handlers(get_actions(), documents)
        yield

    app = FastAPI(title="Veterinaria webhook", lifespan=lifespan)
    app.include_router(router)
    return app


app = create_app()
