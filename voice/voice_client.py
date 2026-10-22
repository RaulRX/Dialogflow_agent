"""Voice conversation with Dialogflow: microphone in, spoken answer out."""

import html
import io
import msvcrt  # Windows-only: non-blocking keyboard reads
import re
import time
import wave

import numpy as np
import sounddevice as sd  # type: ignore[import-untyped]
from google.cloud import dialogflow  # type: ignore[import-not-found]

from voice.text_client import TextClient, Turn, print_turn

SAMPLE_RATE = 16000  # Dialogflow expects 16 kHz for LINEAR_16
DEFAULT_MAX_RECORD_SECONDS = 15
STOP_RECORDING_KEY = "q"
ENTER_KEY = "\r"
ESCAPE_KEY = "\x1b"
_KEY_POLL_SECONDS = 0.05
_SSML_TAG = re.compile(r"<[^>]+>")


def strip_ssml(text: str) -> str:
    """Remove SSML tags and XML escapes so the answer can be printed as plain text."""
    return html.unescape(_SSML_TAG.sub("", text)).strip()


def wait_for_start() -> bool:
    """Block until Enter (True: start listening) or Esc (False: quit)."""
    while True:
        key = msvcrt.getwch()
        if key == ENTER_KEY:
            return True
        if key == ESCAPE_KEY:
            return False


def record(max_seconds: int = DEFAULT_MAX_RECORD_SECONDS) -> bytes:
    """Record from the microphone until the stop key is pressed (or max_seconds elapse)."""
    chunks: list[np.ndarray] = []

    def on_audio(indata: np.ndarray, frames: int, time_info: object, status: object) -> None:
        chunks.append(indata.copy())

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=on_audio):
        deadline = time.monotonic() + max_seconds
        while time.monotonic() < deadline:
            if msvcrt.kbhit() and msvcrt.getwch().lower() == STOP_RECORDING_KEY:
                break
            time.sleep(_KEY_POLL_SECONDS)
    return np.concatenate(chunks).tobytes() if chunks else b""


def play(wav_bytes: bytes) -> None:
    """Dialogflow returns LINEAR_16 output as a complete WAV file (RIFF header included)."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
        frames = wav.readframes(wav.getnframes())
        rate = wav.getframerate()
    sd.play(np.frombuffer(frames, dtype=np.int16), rate)
    sd.wait()


class VoiceClient(TextClient):
    """Same conversation session as TextClient, but the input is audio and the answer is spoken."""

    def say_audio(self, audio: bytes) -> tuple[Turn, bytes]:
        query_input = dialogflow.QueryInput(
            audio_config=dialogflow.InputAudioConfig(
                audio_encoding=dialogflow.AudioEncoding.AUDIO_ENCODING_LINEAR_16,
                language_code=self._language,
                sample_rate_hertz=SAMPLE_RATE,
            )
        )
        output_config = dialogflow.OutputAudioConfig(
            audio_encoding=dialogflow.OutputAudioEncoding.OUTPUT_AUDIO_ENCODING_LINEAR_16
        )
        response = self._client.detect_intent(
            request={
                "session": self._session,
                "query_input": query_input,
                "input_audio": audio,
                "output_audio_config": output_config,
            }
        )
        return self._to_turn(response.query_result), response.output_audio


def main() -> None:
    client = VoiceClient()
    print("Enter: hablar | q: dejar de grabar | Esc: salir")
    while wait_for_start():
        print("Grabando...")
        audio = record()
        if not audio:
            print("  No se ha grabado audio.")
            continue
        started = time.perf_counter()
        turn, wav_bytes = client.say_audio(audio)
        latency = time.perf_counter() - started
        print(f"  Entendido  : {turn.query_text}")
        print_turn(turn, strip_ssml(turn.fulfillment_text))
        print(f"  Latencia   : {latency:.2f} s")
        if wav_bytes:
            play(wav_bytes)


if __name__ == "__main__":
    main()
