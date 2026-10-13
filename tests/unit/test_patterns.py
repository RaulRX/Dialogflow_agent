from pathlib import Path

import pytest
from patterns import extract_fields, normalize_numeric_tokens

DOCUMENTS_DIR = Path(__file__).resolve().parents[2] / "ocr" / "documents"


class TestNormalizeNumericTokens:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1O mg", "10 mg"),
            ("L-6l540", "L-61540"),
            ("2O25", "2025"),
            ("0,O5 mg/kg", "0,05 mg/kg"),
            ("O3/2O28", "03/2028"),
        ],
    )
    def test_should_fix_lookalikes_when_token_contains_digits(self, raw, expected):
        assert normalize_numeric_tokens(raw) == expected

    @pytest.mark.parametrize(
        "text",
        ["dosis", "perro", "Oral, solo", "Indicaciones: otitis externa", "Lote: L"],
    )
    def test_should_leave_text_untouched_when_tokens_have_no_digits(self, text):
        assert normalize_numeric_tokens(text) == text

    def test_should_preserve_whitespace_and_line_breaks(self):
        text = "Dosis:  1O mg\nCaducidad: O3/2028"

        assert normalize_numeric_tokens(text) == "Dosis:  10 mg\nCaducidad: 03/2028"


class TestExtractFields:
    @pytest.mark.parametrize(
        ("field", "text", "expected"),
        [
            ("registration", "Registro: 1204 ESP", ["1204 ESP"]),
            ("registration", "Registro: 1204ESP", ["1204ESP"]),
            ("batch", "Lote: L-48213", ["L-48213"]),
            ("batch", "Lote: L483216", ["L483216"]),
            ("dose", "Dosis perro: 0,2 mg/kg el primer dia", ["0,2 mg/kg"]),
            (
                "dose",
                "5 mg/kg de praziquantel y 14 mg/kg de pirantel",
                ["5 mg/kg", "14 mg/kg"],
            ),
            ("weight", "Peso orientativo: de 5 a 40 kg segun la raza", ["40 kg"]),
            ("weight", "de 0,7 a 2 kg", ["2 kg"]),
            ("temperature", "Temperatura corporal normal: 38,5 C", ["38,5 C"]),
            ("temperature", "por debajo de 25 C", ["25 C"]),
            ("date", "proxima revision 15/01/2027", ["15/01/2027"]),
            ("expiry", "Caducidad: 03/2028", ["03/2028"]),
        ],
    )
    def test_should_extract_field_when_text_contains_it(self, field, text, expected):
        assert extract_fields(text)[field] == expected

    def test_should_not_treat_full_date_as_expiry(self):
        fields = extract_fields("proxima revision 15/01/2027")

        assert "expiry" not in fields
        assert fields["date"] == ["15/01/2027"]

    def test_should_not_match_dose_as_weight(self):
        assert "weight" not in extract_fields("Dosis perro: 7,5 mg/kg")

    @pytest.mark.parametrize(
        "text",
        [
            "Principio activo: meloxicam",
            "Lote: L-123",
            "Registro: 12 ESP",
            "",
            "perro y gato",
        ],
    )
    def test_should_return_empty_dict_when_nothing_matches(self, text):
        assert extract_fields(text) == {}

    def test_should_return_only_fields_that_matched(self):
        fields = extract_fields("Registro: 1204 ESP\nLote: L-48213")

        assert set(fields) == {"registration", "batch"}


class TestGroundTruthDocuments:
    """Every reference document must yield its expected fields (no OCR involved)."""

    @pytest.mark.parametrize(
        "path", sorted(DOCUMENTS_DIR.glob("prospecto_*.txt")), ids=lambda p: p.stem
    )
    def test_should_extract_registration_batch_dose_and_expiry_from_each_prospecto(
        self, path
    ):
        fields = extract_fields(path.read_text(encoding="utf-8"))

        assert {"registration", "batch", "dose", "expiry"} <= set(fields)

    @pytest.mark.parametrize(
        "path", sorted(DOCUMENTS_DIR.glob("cuidados_*.txt")), ids=lambda p: p.stem
    )
    def test_should_extract_date_and_temperature_from_each_cuidados_guide(self, path):
        fields = extract_fields(path.read_text(encoding="utf-8"))

        assert {"date", "temperature"} <= set(fields)

    def test_should_find_ten_reference_documents(self):
        assert len(list(DOCUMENTS_DIR.glob("*.txt"))) == 10
