"""Veterinary regex patterns and numeric OCR normalization."""

import re

PATTERNS: dict[str, str] = {
    "registration": r"\b\d{4}\s?ESP\b",
    "batch": r"\bL-?\d{5,6}\b",
    "dose": r"\b\d+(?:,\d+)?\s?mg/kg\b",
    "weight": r"\b\d+(?:,\d+)?\s?kg\b",
    "temperature": r"\b\d{2}(?:,\d)?\s?C\b",
    "date": r"\b\d{2}/\d{2}/\d{4}\b",
    # MM/YYYY not preceded or followed by a digit or slash, so it does not match inside a full date
    "expiry": r"(?<![\d/])\d{2}/\d{4}(?![\d/])",
}

# Typical Tesseract confusions inside numbers
_DIGIT_LOOKALIKES = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1"})


def normalize_numeric_tokens(text: str) -> str:
    """Fix O/0 and l/1 confusions only inside tokens that already contain a digit."""

    def fix_token(token: str) -> str:
        if any(char.isdigit() for char in token):
            return token.translate(_DIGIT_LOOKALIKES)
        return token

    return re.sub(r"\S+", lambda match: fix_token(match.group()), text)


def extract_fields(text: str) -> dict[str, list[str]]:
    """Return only the patterns that matched, each with all its matches."""
    fields = {name: re.findall(pattern, text) for name, pattern in PATTERNS.items()}
    return {name: values for name, values in fields.items() if values}
