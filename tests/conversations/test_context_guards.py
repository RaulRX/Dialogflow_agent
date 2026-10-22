import pytest

from voice.text_client import TextClient

pytestmark = pytest.mark.conversation

CONFIRMATION_ACTIONS = {"cita.pedir.si", "cita.urgencia.si"}


class TestBareYes:
    def test_should_fall_back_when_yes_arrives_in_a_fresh_session(self):
        client = TextClient()

        turn = client.say("sí")

        assert turn.action not in CONFIRMATION_ACTIONS
        assert turn.action == "input.unknown"
        assert "cita_confirmada" not in turn.contexts

    def test_should_confirm_only_after_an_appointment_is_in_progress(self):
        client = TextClient()
        client.say("quiero pedir una cita")
        client.say("12345678Z")
        client.say("mi perro")
        client.say("mañana")
        summary = client.say("a las cinco de la tarde")

        turn = client.say("sí")

        assert "cita_en_curso" in summary.contexts
        assert turn.action == "cita.pedir.si"
        assert "cita_confirmada" in turn.contexts
