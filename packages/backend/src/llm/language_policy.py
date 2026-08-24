import re

_HANGUL_RE = re.compile(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]")


def contains_korean_text(value: str) -> bool:
    """Return whether a natural-language value contains Korean text."""
    return bool(_HANGUL_RE.search(value))


def korean_text_or_fallback(value: str, *, fallback: str) -> str:
    """Keep empty/Korean text and replace non-Korean model text."""
    normalized = value.strip()
    if not normalized or contains_korean_text(normalized):
        return normalized
    return fallback
