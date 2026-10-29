from __future__ import annotations

from datetime import UTC, datetime

import pytest
from tests.conftest import DELAYED

from cto_order_agent.domain.consolidation import build_view
from cto_order_agent.domain.enums import Severity
from cto_order_agent.domain.portfolio import scan
from cto_order_agent.domain.risk import (
    SCORE_DELIVERY_PASSED,
    SCORE_MATERIAL_SHORTAGE,
    SCORE_MISSING_CONFIRMATION,
    SCORE_MISSING_CONFIRMATION_OVER_7,
    SCORE_QUANTITY_SHORTFALL,
    SCORE_SLIP,
    SCORE_SLIP_OVER_14,
    SCORE_STATUS_INCONSISTENCY,
    SCORE_UNPOSTED_CONFIRMATION,
    SEVERITY_BY_SCORE,
    evaluate,
)

CLOCK = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)

EXPECTED = {
    SCORE_DELIVERY_PASSED: Severity.CRITICAL,
    SCORE_MATERIAL_SHORTAGE: Severity.CRITICAL,
    SCORE_SLIP_OVER_14: Severity.HIGH,
    SCORE_SLIP: Severity.HIGH,
    SCORE_MISSING_CONFIRMATION_OVER_7: Severity.HIGH,
    SCORE_QUANTITY_SHORTFALL: Severity.MEDIUM,
    SCORE_MISSING_CONFIRMATION: Severity.MEDIUM,
    SCORE_STATUS_INCONSISTENCY: Severity.MEDIUM,
    SCORE_UNPOSTED_CONFIRMATION: Severity.LOW,
}


@pytest.mark.unit
def test_published_score_table() -> None:
    assert SEVERITY_BY_SCORE == EXPECTED
    assert SCORE_DELIVERY_PASSED == 400
    assert SCORE_MATERIAL_SHORTAGE == 380
    assert SCORE_SLIP_OVER_14 == 300
    assert SCORE_SLIP == 280
    assert SCORE_MISSING_CONFIRMATION_OVER_7 == 260
    assert SCORE_QUANTITY_SHORTFALL == 200
    assert SCORE_MISSING_CONFIRMATION == 180
    assert SCORE_STATUS_INCONSISTENCY == 160
    assert SCORE_UNPOSTED_CONFIRMATION == 100


@pytest.mark.unit
async def test_exceptions_are_ordered_by_score(ds) -> None:
    view = await build_view(ds, DELAYED)
    assessment = evaluate(view, CLOCK, set())
    scores = [exc.score for exc in assessment.exceptions]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.unit
async def test_portfolio_is_ranked(ds) -> None:
    result = await scan(ds, CLOCK, 365)
    scores = [row.score for row in result.rows]
    assert scores == sorted(scores, reverse=True)
    assert result.rows[0].score == 400


@pytest.mark.unit
async def test_portfolio_tie_breaks_by_delivery_date(ds) -> None:
    result = await scan(ds, CLOCK, 365)
    for left, right in zip(result.rows, result.rows[1:], strict=False):
        if left.score == right.score:
            assert left.requested_delivery_date <= right.requested_delivery_date
