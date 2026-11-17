"""Name normalization for comparison only. Raw names are always stored alongside the result."""
from __future__ import annotations

import re
import unicodedata

# Letters that Unicode decomposition does not reduce to a base Latin letter.
SPECIAL_LETTERS = str.maketrans({
    "ø": "o", "Ø": "o", "ß": "ss", "æ": "ae", "Æ": "ae", "œ": "oe", "Œ": "oe", "ł": "l", "Ł": "l",
    "đ": "d", "Đ": "d", "ð": "d", "Ð": "d", "þ": "th", "Þ": "th", "ı": "i",
})
APOSTROPHES = "'’‘ʼ`´"


def normalize_name(raw: str | None) -> str | None:
    """Lowercase, strip diacritics and punctuation, and collapse whitespace.

    Keeps every name token and token order. Apostrophes join (O'Brien -> obrien); hyphens split
    (Smith-Rowe -> smith rowe). Returns None when nothing comparable remains.
    """
    if raw is None:
        return None
    text = raw.translate(SPECIAL_LETTERS)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    text = re.sub(f"[{APOSTROPHES}]", "", text)
    text = re.sub(r"[^\w\s]|_", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


# Common spelling convention for German-style umlauts: Müller is often written Mueller.
UMLAUT_SPELLING = str.maketrans({"ä": "ae", "Ä": "ae", "ö": "oe", "Ö": "oe", "ü": "ue", "Ü": "ue"})


def sorted_tokens(normalized: str | None) -> str | None:
    """Order-independent form, so "Son Heung-min" and "Heung-min Son" compare equal."""
    return " ".join(sorted(normalized.split())) if normalized else None


def name_keys(raw_names) -> set[str]:
    """Exact-comparison keys for all name forms of one player: order-free, with umlaut variants."""
    keys: set[str] = set()
    for raw in raw_names:
        if not raw:
            continue
        for form in (raw, raw.translate(UMLAUT_SPELLING)):
            key = sorted_tokens(normalize_name(form))
            if key:
                keys.add(key)
    return keys


def is_token_subset(left: str | None, right: str | None) -> bool:
    """True when every token of one name appears in the other. Identity support only."""
    if not left or not right:
        return False
    a, b = set(left.split()), set(right.split())
    return a <= b or b <= a
