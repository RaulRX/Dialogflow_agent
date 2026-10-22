"""Pydantic models for the Dialogflow ES webhook contract."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")


class OutputContext(_CamelModel):
    name: str
    lifespan_count: int = 0
    parameters: dict[str, Any] = Field(default_factory=dict)

    @property
    def short_name(self) -> str:
        return self.name.rsplit("/", 1)[-1]


class Intent(_CamelModel):
    display_name: str = ""


class QueryResult(_CamelModel):
    query_text: str = ""
    action: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    all_required_params_present: bool = False
    output_contexts: list[OutputContext] = Field(default_factory=list)
    intent: Intent = Field(default_factory=Intent)


class WebhookRequest(_CamelModel):
    response_id: str = ""
    session: str
    query_result: QueryResult

    def find_context(self, short_name: str) -> OutputContext | None:
        return next(
            (ctx for ctx in self.query_result.output_contexts if ctx.short_name == short_name),
            None,
        )

    def context_path(self, short_name: str) -> str:
        return f"{self.session}/contexts/{short_name}"


class WebhookResponse(_CamelModel):
    fulfillment_text: str
    output_contexts: list[OutputContext] = Field(default_factory=list)
    # Dialogflow returns it as `webhookSource`; it is traceability only and is never spoken.
    source: str | None = None