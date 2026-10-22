"""Port for the language model used to answer questions about the documents."""

from typing import Protocol


class LLMError(Exception):
    """The model could not produce an answer (timeout, API failure or empty response)."""


class LLMClient(Protocol):
    def answer(self, question: str, documents: str) -> str:
        """Return the raw model answer to `question`, based only on `documents`.

        Raises LLMError if no usable answer could be obtained.
        """
        ...
