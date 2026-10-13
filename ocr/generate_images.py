"""Render each ocr/documents/*.txt to a clean PNG in ocr/source/."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "documents"
OUTPUT_DIR = ROOT / "source"

FONT_CANDIDATES = ("DejaVuSans.ttf", "arial.ttf")
FONT_SIZE = 30
IMAGE_WIDTH = 1800
MARGIN = 60
LINE_SPACING = 12


def load_font() -> ImageFont.FreeTypeFont:
    for name in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, FONT_SIZE)
        except OSError:
            continue
    # Pillow's bitmap fallback ignores the size and degrades OCR accuracy
    raise SystemExit(f"None of the fonts {FONT_CANDIDATES} could be loaded")


def wrap_line(line: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in line.split(" "):
        candidate = f"{current} {word}".strip()
        if not current or font.getlength(candidate) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def render_document(text: str, font: ImageFont.FreeTypeFont) -> Image.Image:
    max_width = IMAGE_WIDTH - 2 * MARGIN
    lines = [
        wrapped
        for raw_line in text.splitlines()
        for wrapped in wrap_line(raw_line, font, max_width)
    ]
    ascent, descent = font.getmetrics()
    line_height = ascent + descent + LINE_SPACING
    height = 2 * MARGIN + line_height * len(lines)

    image = Image.new("L", (IMAGE_WIDTH, height), color=255)
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines):
        draw.text((MARGIN, MARGIN + index * line_height), line, font=font, fill=0)
    return image


def main() -> None:
    sources = sorted(SOURCE_DIR.glob("*.txt"))
    if not sources:
        raise SystemExit(f"No .txt files found in {SOURCE_DIR}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    font = load_font()
    for source in sources:
        image = render_document(source.read_text(encoding="utf-8"), font)
        target = OUTPUT_DIR / f"{source.stem}.png"
        image.save(target)
        print(f"  {source.name} -> {target.name}")
    print(f"{len(sources)} images generated in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
