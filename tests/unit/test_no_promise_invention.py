from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest
from tests.conftest import DELAYED, SCHEDULE_SLIP

from cto_order_agent.domain.consolidation import build_view
from cto_order_agent.domain.risk import evaluate
from cto_order_agent.presentation.customer_summary import render_customer_summary

CLOCK = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


@pytest.mark.unit
@pytest.mark.parametrize("order", [SCHEDULE_SLIP, DELAYED])
async def test_summary_never_invents_a_date(ds, order: str) -> None:
    view = await build_view(ds, order)
    assessment = evaluate(view, CLOCK, set(view.sources_unavailable))
    summary = render_customer_summary(view, assessment)

    permitted = {view.sales_order.requested_delivery_date.isoformat()}
    permitted |= {
        po.confirmed_end.date().isoformat() for po in view.production_orders if po.confirmed_end
    }
    assert set(DATE.findall(summary)) <= permitted


@pytest.mark.unit
async def test_summary_does_not_promise_a_new_date(ds) -> None:
    view = await build_view(ds, DELAYED)
    assessment = evaluate(view, CLOCK, set(view.sources_unavailable))
    summary = render_customer_summary(view, assessment).lower()
    assert "we will deliver by" not in summary
    assert "guaranteed" not in summary
