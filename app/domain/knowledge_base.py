"""Read-only access to the documents extracted by the OCR pipeline."""

import json
from dataclasses import dataclass
from pathlib import Path

_DOCUMENT_SEPARATOR = "\n\n"


@dataclass(frozen=True)
class Document:
    id: str
    category: str
    subject: str
    text: str


class KnowledgeBase:
    def __init__(self, documents: list[Document]) -> None:
        if not documents:
            raise ValueError("The knowledge base has no documents")
        self._documents = documents

    @classmethod
    def from_file(cls, path: str | Path) -> "KnowledgeBase":
        entries = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            [
                Document(
                    id=entry["id"],
                    category=entry["category"],
                    subject=entry["subject"],
                    text=entry["text"],
                )
                for entry in entries
            ]
        )

    def __len__(self) -> int:
        return len(self._documents)

    def select_documents(self, category: str, subject: str = "") -> list[Document]:
        """Document for `subject`, or the whole category if the subject is empty or unknown,
        so the model never receives less than it needs."""
        in_category = [doc for doc in self._documents if doc.category == category]
        exact = [doc for doc in in_category if doc.subject == subject]
        return exact or in_category

    def all_documents(self) -> list[Document]:
        return list(self._documents)

    def select(self, category: str, subject: str = "") -> str:
        return self.join_text(self.select_documents(category, subject))

    def select_all(self) -> str:
        return self.join_text(self._documents)

    @staticmethod
    def join_text(documents: list[Document]) -> str:
        return _DOCUMENT_SEPARATOR.join(doc.text for doc in documents)
