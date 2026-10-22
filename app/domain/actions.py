"""Names of the Dialogflow actions the webhook answers, so a renamed agent only needs the .env."""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ActionNames(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ACTION_", env_file=".env", extra="ignore", frozen=True
    )

    booking_request: str = "cita.pedir"
    booking_confirm: str = "cita.pedir.si"
    booking_lookup: str = "cita.consultar"
    emergency: str = "cita.urgencia"
    leaflet: str = "prospecto.consultar"
    leaflet_followup: str = "prospecto.seguimiento"
    care: str = "cuidados.consultar"
    care_followup: str = "cuidados.seguimiento"
    fallback: str = "input.unknown"
    clinic: str = "clinica.info"

    @model_validator(mode="after")
    def _names_must_be_unique(self) -> "ActionNames":
        names = list(self.model_dump().values())
        duplicated = sorted({name for name in names if names.count(name) > 1})
        if duplicated:
            raise ValueError(f"Action names must be unique, repeated: {duplicated}")
        return self


@lru_cache
def get_actions() -> ActionNames:
    return ActionNames()
