from __future__ import annotations

from datetime import UTC, datetime

import pytest
from tests.conftest import MULTILEVEL, NO_ORDERS, ON_TRACK, PARTIAL_ON_TIME

from cto_order_agent.domain.consolidation import build_view
from cto_order_agent.domain.risk import evaluate

CLOCK = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)


@pytest.mark.unit
@pytest.mark.parametrize("order", [ON_TRACK, MULTILEVEL, PARTIAL_ON_TIME, NO_ORDERS])
async def test_healthy_orders_are_not_flagged(ds, order: str) -> None:
    view = await build_view(ds, order)
    assessment = evaluate(view, CLOCK, set(view.sources_unavailable))
    assert assessment.exceptions == []
    assert assessment.is_at_risk is False
    assert assessment.severity is None


@pytest.mark.unit
async def test_partial_confirmation_on_time_is_not_a_shortfall(ds) -> None:
    view = await build_view(ds, PARTIAL_ON_TIME)
    assessment = evaluate(view, CLOCK, set())
    assert assessment.is_at_risk is False
