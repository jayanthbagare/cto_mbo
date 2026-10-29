from __future__ import annotations

import pytest

from cto_order_agent.observability.logging import MASK, redact


@pytest.mark.unit
@pytest.mark.parametrize(
    "key", ["secret", "client_secret", "token", "password", "authorization", "api_key"]
)
def test_sensitive_keys_are_masked(key: str) -> None:
    result = redact({key: "super-sensitive-value"})
    assert result[key] == MASK


@pytest.mark.unit
def test_inline_tokens_are_masked() -> None:
    result = redact({"note": "Bearer abcdef123456 and ghp_abcdefghijklmnop"})
    assert "abcdef123456" not in result["note"]
    assert "ghp_abcdefghijklmnop" not in result["note"]


@pytest.mark.unit
def test_nested_and_non_sensitive_values_survive() -> None:
    payload = {"sales_order": "0000012345", "nested": {"count": 3, "secret": "x"}}
    result = redact(payload)
    assert result["sales_order"] == "0000012345"
    assert result["nested"]["count"] == 3
    assert result["nested"]["secret"] == MASK


@pytest.mark.unit
def test_empty_secret_is_not_masked() -> None:
    assert redact({"secret": ""})["secret"] == ""
