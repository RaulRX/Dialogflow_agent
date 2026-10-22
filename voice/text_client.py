import os
import uuid
from dataclasses import dataclass, field

from dotenv import load_dotenv
from google.cloud import dialogflow  # type: ignore[import-not-found]

from app.domain.validators import normalize_dni_in_text

load_dotenv()


@dataclass(frozen=True)
class Context:
    name: str
    lifespan: int
    parameters: dict


@dataclass(frozen=True)
class Turn:
    query_text: str
    intent: str
    action: str
    parameters: dict
    contexts: dict[str, Context] = field(default_factory=dict)
    fulfillment_text: str = ""
    confidence: float = 0.0
    webhook_source: str = ""


class TextClient:
    """One instance = one conversation: contexts live under the session id."""

    def __init__(self, project_id: str | None = None, language: str | None = None) -> None:
        self._project_id = project_id or os.environ["DIALOGFLOW_PROJECT_ID"]
        self._language = language or os.environ.get("DIALOGFLOW_LANGUAGE", "es")
        self._client = dialogflow.SessionsClient()
        self._session = self._client.session_path(self._project_id, str(uuid.uuid4()))

    def say(self, text: str) -> Turn:
        query_input = dialogflow.QueryInput(
            text=dialogflow.TextInput(
                text=normalize_dni_in_text(text), language_code=self._language
            )
        )
        response = self._client.detect_intent(
            request={"session": self._session, "query_input": query_input}
        )
        return self._to_turn(response.query_result)

    @staticmethod
    def _to_turn(result) -> Turn:
        data = dialogflow.QueryResult.to_dict(result)
        contexts = {
            raw["name"].rsplit("/", 1)[-1]: Context(
                name=raw["name"].rsplit("/", 1)[-1],
                lifespan=int(raw.get("lifespan_count", 0)),
                parameters=raw.get("parameters", {}),
            )
            for raw in data.get("output_contexts", [])
        }
        return Turn(
            query_text=data["query_text"],
            intent=data["intent"]["display_name"],
            action=data.get("action", ""),
            parameters=data.get("parameters", {}),
            contexts=contexts,
            fulfillment_text=data.get("fulfillment_text", ""),
            confidence=data.get("intent_detection_confidence", 0.0),
            webhook_source=data.get("webhook_source", ""),
        )


def print_turn(turn: Turn, response_text: str | None = None) -> None:
    """Print a turn; `response_text` overrides the fulfillment text (e.g. with SSML stripped)."""
    print(f"  Intencion  : {turn.intent} ({turn.confidence:.2f}) action={turn.action}")
    print(f"  Parametros : {turn.parameters}")
    print(f"  Contextos  : { {n: c.lifespan for n, c in turn.contexts.items()} }")
    print(f"  Responde   : {turn.fulfillment_text if response_text is None else response_text}")
    if turn.webhook_source:
        print(f"  Fuente     : {turn.webhook_source}")


def main() -> None:
    client = TextClient()
    print("Escribe una frase (q para salir).")
    while (text := input("\n> ").strip()) and text.lower() != "q":
        print_turn(client.say(text))


if __name__ == "__main__":
    main()