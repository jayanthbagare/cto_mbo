"""Grounding gate (FR-016, SC-004).

Every numeric or date literal in the draft must appear in the bundle's
`allowed_tokens`. Anything else is a fabricated value and fails closed.
"""

from __future__ import annotations

import re

from ..domain.errors import ValidationFailure

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_ID = re.compile(r"\b[FIR]-\d+\b")

# Fragments that indicate untrusted free text was executed as instruction (research D9).
_INJECTION_MARKERS = (
    "ignore previous",
    "ignore all previous",
    "disregard the above",
    "system prompt",
    "you are now",
    "new instructions",
    "override the",
)


def extract_tokens(text: str) -> set[str]:
    """Dates stay atomic; bare numbers are extracted outside dates."""
    tokens = set(_DATE.findall(text))
    remainder = _DATE.sub(" ", _ID.sub(" ", text))
    tokens |= set(_NUMBER.findall(remainder))
    return tokens


def ungrounded(text: str, allowed: list[str] | set[str]) -> list[str]:
    allowed_set = {str(token) for token in allowed}
    found = extract_tokens(text)
    return sorted(token for token in found if token not in allowed_set)


def validate(text: str, allowed: list[str] | set[str]) -> str:
    """Return the text when grounded; raise ValidationFailure otherwise."""
    missing = ungrounded(text, allowed)
    if missing:
        raise ValidationFailure(missing)
    lowered = text.lower()
    for marker in _INJECTION_MARKERS:
        if marker in lowered:
            raise ValidationFailure([f"instruction-like text: {marker}"])
    return text


__all__ = ["extract_tokens", "ungrounded", "validate"]
