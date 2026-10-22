"""Gemini adapter for the LLMClient port."""

import logging
import time

from google import genai
from google.genai import types

from app.domain.config import Settings
from app.llm.client import LLMError
from app.llm.prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

_MILLISECONDS_PER_SECOND = 1000


class GeminiClient:
    def __init__(self, settings: Settings) -> None:
        self._model = settings.gemini_model
        self._client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(
                timeout=int(settings.llm_timeout_seconds * _MILLISECONDS_PER_SECOND)
            ),
        )
        self._config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=settings.llm_temperature,
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel(settings.llm_thinking_level.upper())
            ),
        )

    def answer(self, question: str, documents: str) -> str:
        started = time.perf_counter()
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=build_user_prompt(question, documents),
                config=self._config,
            )
        except Exception as error:  # SDK and transport raise many unrelated types
            logger.warning("Gemini request failed: %s, %s", type(error).__name__, error)
            raise LLMError("Gemini request failed") from error
        logger.info("Gemini answered in %.0f ms", (time.perf_counter() - started) * 1000)
        text = (response.text or "").strip()
        if not text:
            raise LLMError("Gemini returned an empty answer")
        return text
