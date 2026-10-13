import sys
from pathlib import Path

# The OCR scripts are plain modules (not a package), so expose them to the tests
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ocr"))
