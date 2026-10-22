from voice.voice_client import strip_ssml


def test_should_remove_ssml_tags_and_keep_the_text() -> None:
    text = '<speak>Tu código es <say-as interpret-as="characters">VET0001</say-as>.</speak>'

    assert strip_ssml(text) == "Tu código es VET0001."


def test_should_return_plain_text_unchanged() -> None:
    assert strip_ssml("Hola, ¿qué tal?") == "Hola, ¿qué tal?"


def test_should_unescape_xml_entities() -> None:
    assert strip_ssml("<speak>Perros &amp; gatos</speak>") == "Perros & gatos"


def test_should_trim_the_surrounding_whitespace() -> None:
    assert strip_ssml("<speak>  uno  </speak>") == "uno"
