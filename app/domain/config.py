"""Application settings, loaded from environment variables or the local .env file."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str
    gemini_model: str = "gemini-3.5-flash-lite"
    llm_timeout_seconds: float = 10
    llm_temperature: float = 0.0
    llm_thinking_level: Literal["minimal", "low", "medium", "high"] = "low"
    knowledge_base_path: str = "ocr/data/knowledge_base.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # required fields come from the environment