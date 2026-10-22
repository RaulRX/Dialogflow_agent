import pytest

from voice.text_client import TextClient, Turn

pytestmark = pytest.mark.conversation

DNI = "12345678Z"


def is_active(turn: Turn, context: str) -> bool:
    return context in turn.contexts and turn.contexts[context].lifespan > 0


class TestEmergencyToAppointment:
    def test_should_reuse_dni_and_animal_when_a_mild_emergency_becomes_a_regular_appointment(self):
        client = TextClient()

        turn = client.say("tengo una urgencia")
        assert turn.action == "cita.urgencia"

        turn = client.say(DNI)
        assert turn.action == "cita.urgencia"
        assert turn.parameters["dni"] == DNI

        turn = client.say("es un gato")
        assert turn.action == "cita.urgencia"
        assert turn.parameters["animal"] == "gato"

        triage = client.say("tiene diarrea")
        assert triage.action == "cita.urgencia"
        assert triage.parameters["sintoma"] == "diarrea"
        assert is_active(triage, "urgencia_en_curso")

        declined = client.say("no")
        assert declined.action == "cita.urgencia.no"
        assert is_active(declined, "urgencia_en_curso")

        appointment = client.say("quiero pedir una cita")
        assert appointment.action == "cita.pedir"
        assert appointment.parameters["dni"] == DNI
        assert appointment.parameters["animal"] == "gato"
        assert not appointment.parameters.get("fecha")