import pytest

from voice.text_client import TextClient, Turn

pytestmark = pytest.mark.conversation

DNI = "12345678Z"


def is_active(turn: Turn, context: str) -> bool:
    return context in turn.contexts and turn.contexts[context].lifespan > 0


class TestAppointmentFlow:
    def test_should_book_confirm_and_look_up_the_appointment_when_the_flow_is_completed(self):
        client = TextClient()

        turn = client.say("quiero pedir una cita")
        assert turn.action == "cita.pedir"

        turn = client.say(DNI)
        assert turn.action == "cita.pedir"
        assert turn.parameters["dni"] == DNI

        turn = client.say("mi perro")
        assert turn.action == "cita.pedir"
        assert turn.parameters["animal"] == "perro"

        turn = client.say("mañana")
        assert turn.action == "cita.pedir"
        assert turn.parameters["fecha"]

        summary = client.say("a las cinco de la tarde")
        assert summary.action == "cita.pedir"
        assert summary.parameters["hora"]
        assert is_active(summary, "cita_en_curso")
        cita_en_curso = summary.contexts["cita_en_curso"].parameters
        assert {"dni", "animal", "fecha", "hora"} <= set(cita_en_curso)

        confirmation = client.say("sí")
        assert confirmation.action == "cita.pedir.si"
        assert is_active(confirmation, "cita_confirmada")
        assert confirmation.contexts["cita_confirmada"].parameters["codigo_cita"]
        assert not is_active(confirmation, "cita_en_curso")

        lookup = client.say("quiero consultar mi cita")
        assert lookup.action == "cita.consultar"
        assert lookup.parameters["codigo_cita"] == (
            confirmation.contexts["cita_confirmada"].parameters["codigo_cita"]
        )