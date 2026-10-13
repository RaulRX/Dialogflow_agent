"""Run Tesseract over ocr/documents/*.png and write icr/data/knowledge_base.json."""

import json
import shutil
import sys
from pathlib import Path

import pytesseract  # type: ignore[import-untyped]
from patterns import extract_fields, normalize_numeric_tokens
from PIL import Image

ROOT = Path(__file__).resolve().parent
IMAGES_DIR = ROOT / "source"
DOCUMENTS_DIR = ROOT / "documents"
OUTPUT_PATH = ROOT / "data" / "knowledge_base.json"

TESSERACT_WINDOWS_PATH = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
TESSERACT_CONFIG = "--psm 6"
MAX_CER = 0.05


def configure_tesseract() -> None:
    if shutil.which("tesseract") is None and TESSERACT_WINDOWS_PATH.is_file():
        pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_WINDOWS_PATH)


def read_document(path: Path) -> str:
    image = Image.open(path).convert("L")
    return pytesseract.image_to_string(image, lang="spa", config=TESSERACT_CONFIG)


def levenshtein(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            cost = 0 if char_a == char_b else 1
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost)
            )
        previous = current
    return previous[-1]


def character_error_rate(reference: str, hypothesis: str) -> float:
    reference = " ".join(reference.split())
    hypothesis = " ".join(hypothesis.split())
    return levenshtein(reference, hypothesis) / max(len(reference), 1)


def build_entry(image_path: Path) -> tuple[dict, float | None]:
    text = normalize_numeric_tokens(read_document(image_path)).strip()
    category, _, subject = image_path.stem.partition("_")

    source_path = DOCUMENTS_DIR / f"{image_path.stem}.txt"
    cer = None
    if source_path.is_file():
        cer = character_error_rate(source_path.read_text(encoding="utf-8"), text)

    entry = {
        "id": image_path.stem,
        "category": category,
        "subject": subject,
        "text": text,
        "extracted_fields": extract_fields(text),
    }
    return entry, cer


def main() -> int:
    configure_tesseract()
    images = sorted(IMAGES_DIR.glob("*.png"))
    if not images:
        print(f"No images in {IMAGES_DIR}. Run generate_images.py first.")
        return 1

    entries = []
    failed = False
    for image_path in images:
        entry, cer = build_entry(image_path)
        entries.append(entry)
        cer_label = "n/a" if cer is None else f"{cer:.1%}"
        print(
            f"  {entry['id']}: CER {cer_label}, fields {sorted(entry['extracted_fields'])}"
        )
        if cer is not None and cer > MAX_CER:
            failed = True

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{len(entries)} documents written to {OUTPUT_PATH}")

    if failed:
        print(f"WARNING: some documents exceed the CER threshold ({MAX_CER:.0%}).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())