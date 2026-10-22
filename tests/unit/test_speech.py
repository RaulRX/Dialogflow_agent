from datetime import date, time

import pytest

from app.domain.speech import animal_label, format_date, format_time, speak_text, spell, ssml


def test_should_format_date_with_spanish_weekday_and_month() -> None:
    assert format_date(date(2026, 10, 20)) == "martes 20 de octubre"


def test_should_format_date_when_day_is_sunday_and_month_is_december() -> None:
    assert format_date(date(2026, 12, 6)) == "domingo 6 de diciembre"


def test_should_format_time_with_two_digit_minutes() -> None:
    assert format_time(time(17, 5)) == "17:05"


def test_should_restore_accent_when_animal_is_huron() -> None:
    assert animal_label("huron") == "hurón"


def test_should_return_value_unchanged_when_animal_has_no_label() -> None:
    assert animal_label("perro") == "perro"


def test_should_wrap_parts_in_speak_tag() -> None:
    assert ssml("a", "b") == "<speak>ab</speak>"


def test_should_spell_code_character_by_character() -> None:
    assert spell("VET0001") == '<say-as interpret-as="characters">VET0001</say-as>'


def test_should_escape_markup_characters_in_free_text() -> None:
    assert speak_text("Consultas & <urgencias>") == "Consultas &amp; &lt;urgencias&gt;"


@pytest.mark.parametrize("phone", ["900000000", "900 000 000"])
def test_should_read_the_clinic_phone_digit_by_digit(phone: str) -> None:
    assert speak_text(f"Llama al {phone}.") == (
        f'Llama al <say-as interpret-as="telephone">{phone}</say-as>.'
    )


def test_should_not_treat_a_longer_number_as_a_phone() -> None:
    assert speak_text("Lote 9000000001") == "Lote 9000000001"
