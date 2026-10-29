"""Deterministic intent and order-reference detection (FR-001, FR-009)."""

from __future__ import annotations

import re

from ..domain.enums import Intent

_ORDER = re.compile(r"(?<![\d])(\d{4,10})(?![\d])")

_WRITE_VERBS = (
    "expedite",
    "reschedule",
    "release the",
    "release order",
    "cancel",
    "delete",
    "change the date",
    "change delivery",
    "post the confirmation",
    "post confirmation",
    "update the order",
    "modify",
    "create a production order",
    "set the status",
)

_PORTFOLIO = ("which orders", "at risk", "at-risk", "portfolio", "all orders", "any orders")
_CUSTOMER = ("customer-ready", "customer ready", "customer summary", "send to the customer")
_RECOMMEND = (
    "what should i do",
    "what do i do",
    "recommend",
    "next action",
    "most urgent",
    "priorit",
)
_EXPLAIN = ("why", "explain", "evidence", "where does that come from", "how do you know")
_STATUS = ("status", "show me", "what about", "consolidat", "linked", "details", "view")


def extract_order_refs(text: str) -> list[str]:
    """All digit runs that could be order references, in order, deduplicated."""
    seen: list[str] = []
    for match in _ORDER.findall(text):
        if match not in seen:
            seen.append(match)
    return seen


def extract_order_ref(text: str) -> str | None:
    refs = extract_order_refs(text)
    return refs[0] if refs else None


def detect_intent(text: str) -> Intent:
    lowered = text.lower().strip()
    if not lowered:
        return Intent.UNKNOWN
    if any(verb in lowered for verb in _WRITE_VERBS):
        return Intent.WRITE_REQUEST
    if any(phrase in lowered for phrase in _EXPLAIN):
        return Intent.RISK_EXPLANATION
    if any(phrase in lowered for phrase in _PORTFOLIO):
        return Intent.PORTFOLIO
    if any(phrase in lowered for phrase in _CUSTOMER):
        return Intent.CUSTOMER_SUMMARY
    if any(phrase in lowered for phrase in _RECOMMEND):
        return Intent.RECOMMENDATION
    if any(phrase in lowered for phrase in _STATUS) or extract_order_ref(lowered):
        return Intent.ORDER_STATUS
    return Intent.UNKNOWN


def ordinal_position(text: str) -> int | None:
    """Resolve 'the second production order' to a 1-based index."""
    words = {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
        "sixth": 6,
        "seventh": 7,
        "eighth": 8,
        "ninth": 9,
        "tenth": 10,
    }
    lowered = text.lower()
    for word, value in words.items():
        if word in lowered:
            return value
    match = re.search(r"\b(\d)(?:st|nd|rd|th)\b", lowered)
    return int(match.group(1)) if match else None


__all__ = ["detect_intent", "extract_order_ref", "extract_order_refs", "ordinal_position"]
