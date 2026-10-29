from __future__ import annotations

from datetime import UTC, datetime

import pytest
from tests.conftest import SCHEDULE_SLIP

from cto_order_agent.domain.consolidation import build_view
from cto_order_agent.domain.risk import evaluate
from cto_order_agent.presentation.customer_summary import (
    SummaryLeak,
    assert_clean,
    render_customer_summary,
    sanitize,
)

CLOCK = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)


@pytest.mark.unit
def test_sanitize_removes_internal_identifiers() -> None:
    text = "Order 1000030 at plant 1010 with material MTO-1000-A is RELEASED"
    cleaned = sanitize(text, ["1000030", "1010", "MTO-1000-A"])
    assert "1000030" not in cleaned
    assert "1010" not in cleaned
    assert "MTO-1000-A" not in cleaned


@pytest.mark.unit
def test_assert_clean_fails_closed() -> None:
    with pytest.raises(SummaryLeak):
        assert_clean("production order 1000030 is late", ["1000030"])


@pytest.mark.unit
async def test_rendered_summary_has_no_internal_ids(ds) -> None:
    view = await build_view(ds, SCHEDULE_SLIP)
    assessment = evaluate(view, CLOCK, set(view.sources_unavailable))
    summary = render_customer_summary(view, assessment)
    for forbidden in ("1000030", "RELEASED", "1010", "MTO-1000-A", "SCHEDULE_SLIP"):
        assert forbidden not in summary
    assert "0000012346" in summary
