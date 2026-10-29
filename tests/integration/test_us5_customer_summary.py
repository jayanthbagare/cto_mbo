from __future__ import annotations

import re

import pytest
from tests.conftest import DELAYED, ON_TRACK, SCHEDULE_SLIP

DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


@pytest.mark.integration
async def test_v11_summary_is_customer_safe(executor) -> None:
    turn = await executor.handle_turn(
        f"Give me a customer-ready update for {SCHEDULE_SLIP}", "ctx-v11", "task-v11"
    )
    message = turn.message
    assert SCHEDULE_SLIP in message
    for forbidden in ("1000030", "RELEASED", "1010", "MTO-1000-A", "SCHEDULE_SLIP"):
        assert forbidden not in message


@pytest.mark.integration
async def test_v11_summary_is_short(executor) -> None:
    turn = await executor.handle_turn(
        f"Give me a customer-ready update for {SCHEDULE_SLIP}", "ctx-v11b", "task-v11b"
    )
    assert len(turn.message.split()) < 120


@pytest.mark.integration
async def test_summary_separates_confirmed_from_estimated(executor) -> None:
    confirmed = await executor.handle_turn(
        f"Give me a customer-ready update for {ON_TRACK}", "ctx-v11c", "t1"
    )
    estimated = await executor.handle_turn(
        f"Give me a customer-ready update for {DELAYED}", "ctx-v11d", "t2"
    )
    assert "confirmed" in confirmed.message.lower()
    assert "estimate" in estimated.message.lower() or "unable to confirm" in (
        estimated.message.lower()
    )


@pytest.mark.integration
async def test_summary_dates_are_grounded(executor) -> None:
    turn = await executor.handle_turn(
        f"Give me a customer-ready update for {DELAYED}", "ctx-v11e", "t3"
    )
    dates = set(DATE.findall(turn.message))
    assert dates <= {turn.view.sales_order.requested_delivery_date.isoformat()} | {
        po.confirmed_end.date().isoformat()
        for po in turn.view.production_orders
        if po.confirmed_end
    }
