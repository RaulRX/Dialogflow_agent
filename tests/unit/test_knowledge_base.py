import json
from pathlib import Path

import pytest

from app.domain.knowledge_base import Document, KnowledgeBase

REAL_KNOWLEDGE_BASE = Path(__file__).resolve().parents[2] / "ocr" / "data" / "knowledge_base.json"


@pytest.fixture
def knowledge_base() -> KnowledgeBase:
    return KnowledgeBase(
        [
            Document("cuidados_gato", "cuidados", "gato", "GUIA GATO"),
            Document("cuidados_perro", "cuidados", "perro", "GUIA PERRO"),
            Document("prospecto_doloxan", "prospecto", "doloxan", "PROSPECTO DOLOXAN"),
            Document("clinica_info", "clinica", "info", "INFO CLINICA"),
        ]
    )


def test_should_return_only_the_document_of_the_subject(knowledge_base: KnowledgeBase) -> None:
    assert knowledge_base.select("cuidados", "gato") == "GUIA GATO"


@pytest.mark.parametrize("subject", ["", "huron"])
def test_should_return_the_whole_category_when_subject_is_empty_or_unknown(
    knowledge_base: KnowledgeBase, subject: str
) -> None:
    assert knowledge_base.select("cuidados", subject) == "GUIA GATO\n\nGUIA PERRO"


def test_should_not_mix_categories(knowledge_base: KnowledgeBase) -> None:
    assert knowledge_base.select("clinica") == "INFO CLINICA"


def test_should_return_every_document(knowledge_base: KnowledgeBase) -> None:
    text = knowledge_base.select_all()

    assert text.count("\n\n") == 3
    assert "PROSPECTO DOLOXAN" in text


def test_should_fail_when_there_are_no_documents() -> None:
    with pytest.raises(ValueError):
        KnowledgeBase([])


def test_should_load_documents_from_file_ignoring_extra_fields(tmp_path: Path) -> None:
    path = tmp_path / "kb.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "cuidados_gato",
                    "category": "cuidados",
                    "subject": "gato",
                    "text": "GUIA GATO",
                    "extracted_fields": {"weight": ["3 kg"]},
                }
            ]
        ),
        encoding="utf-8",
    )

    assert KnowledgeBase.from_file(path).select("cuidados", "gato") == "GUIA GATO"


def test_should_load_the_generated_knowledge_base() -> None:
    knowledge_base = KnowledgeBase.from_file(REAL_KNOWLEDGE_BASE)

    assert "Calle Ficticia 12" in knowledge_base.select("clinica")
    assert "GATO" in knowledge_base.select("cuidados", "gato").upper()
    assert "DOLOXAN" in knowledge_base.select("prospecto", "doloxan").upper()


def test_should_select_documents_with_their_ids(knowledge_base: KnowledgeBase) -> None:
    documents = knowledge_base.select_documents("cuidados", "gato")

    assert [document.id for document in documents] == ["cuidados_gato"]


@pytest.mark.parametrize("subject", ["", "huron"])
def test_should_select_every_document_of_the_category_when_subject_is_empty_or_unknown(
    knowledge_base: KnowledgeBase, subject: str
) -> None:
    documents = knowledge_base.select_documents("cuidados", subject)

    assert [document.id for document in documents] == ["cuidados_gato", "cuidados_perro"]


def test_should_list_every_document_and_report_its_size(knowledge_base: KnowledgeBase) -> None:
    assert len(knowledge_base.all_documents()) == len(knowledge_base) == 4
