import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The webhook starts up with the real settings; the tests never call Gemini, so any key will do
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("KNOWLEDGE_BASE_PATH", str(ROOT / "ocr" / "data" / "knowledge_base.json"))

# The OCR scripts are plain modules (not a package), so expose them to the tests
sys.path.insert(0, str(ROOT / "ocr"))
# Lets the conversation tests import the voice package from the repo root
sys.path.insert(0, str(ROOT))


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "conversation: multi-turn script against the real Dialogflow agent (network, uses quota)",
    )
