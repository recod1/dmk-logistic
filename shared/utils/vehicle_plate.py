"""Normalize and validate RU vehicle / trailer plates (bot-compatible)."""

from __future__ import annotations

import re

LATIN_TO_CYR = str.maketrans(
    {
        "A": "А",
        "B": "В",
        "E": "Е",
        "K": "К",
        "M": "М",
        "H": "Н",
        "O": "О",
        "P": "Р",
        "C": "С",
        "T": "Т",
        "Y": "У",
        "X": "Х",
    }
)

# Bot create-route ТС: А111АА222 / А111АА22 / ЕН068477
PATTERN_STD = re.compile(r"^[А-ЯA-Z]\d{3}[А-ЯA-Z]{2}\d{2,3}$")
PATTERN_SPEC = re.compile(r"^[А-ЯA-Z]{2}\d{6}$")

PLATE_HINT = (
    "Номер должен быть в одном из форматов:\n"
    "• А111АА222 или А111АА22\n"
    "• ЕН068477 (2 буквы + 6 цифр)"
)


def normalize_plate(raw: str | None) -> str:
    text = (raw or "").strip().upper().replace(" ", "").replace("-", "")
    return text.translate(LATIN_TO_CYR)


def is_valid_plate(raw: str | None) -> bool:
    plate = normalize_plate(raw)
    if not plate:
        return False
    return bool(PATTERN_STD.match(plate) or PATTERN_SPEC.match(plate))


def require_plate(raw: str | None) -> str:
    plate = normalize_plate(raw)
    if not is_valid_plate(plate):
        raise ValueError(PLATE_HINT)
    return plate
