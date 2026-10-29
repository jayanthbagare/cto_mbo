from __future__ import annotations

import pytest

from cto_order_agent.domain.enums import Intent
from cto_order_agent.nlu.order_ref import detect_intent, extract_order_ref, ordinal_position


@pytest.mark.unit
@pytest.mark.parametrize(
    "text, expected",
    [
        ("Status of sales order 0000012345", "0000012345"),
        ("what about 1234?", "1234"),
        ("show me order 0000012350 please", "0000012350"),
        ("no reference here", None),
    ],
)
def test_extract_order_ref(text: str, expected: str | None) -> None:
    assert extract_order_ref(text) == expected


@pytest.mark.unit
def test_extract_does_not_take_partial_digits() -> None:
    assert extract_order_ref("order 00000123456 exists") is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "text, intent",
    [
        ("Which orders are at risk?", Intent.PORTFOLIO),
        ("Why is order 0000012346 at risk?", Intent.RISK_EXPLANATION),
        ("What should I do about 0000012346?", Intent.RECOMMENDATION),
        ("Give me a customer-ready update for 0000012346", Intent.CUSTOMER_SUMMARY),
        ("Can you expedite order 0000012346?", Intent.WRITE_REQUEST),
        ("Status of 0000012345", Intent.ORDER_STATUS),
        ("hello", Intent.UNKNOWN),
    ],
)
def test_detect_intent(text: str, intent: Intent) -> None:
    assert detect_intent(text) is intent


@pytest.mark.unit
@pytest.mark.parametrize(
    "text, position",
    [("the second production order", 2), ("the 3rd one", 3), ("no ordinal", None)],
)
def test_ordinal_position(text: str, position: int | None) -> None:
    assert ordinal_position(text) == position
