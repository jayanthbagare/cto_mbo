from __future__ import annotations

from datetime import UTC, datetime

import pytest
from tests.conftest import (
    DELAYED,
    INCONSISTENT,
    MATERIAL,
    MISSING_CONF,
    QTY,
    SCHEDULE_SLIP,
)

from cto_order_agent.domain.consolidation import build_view
from cto_order_agent.domain.enums import ExceptionCategory
from cto_order_agent.domain.risk import evaluate

CLOCK = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)


async def _categories(ds, order: str) -> set[ExceptionCategory]:
    view = await build_view(ds, order)
    assessment = evaluate(view, CLOCK, set(view.sources_unavailable))
    return {exc.category for exc in assessment.exceptions}


@pytest.mark.unit
async def test_schedule_slip(ds) -> None:
    assert ExceptionCategory.SCHEDULE_SLIP in await _categories(ds, SCHEDULE_SLIP)


@pytest.mark.unit
async def test_delivery_date_already_passed(ds) -> None:
    view = await build_view(ds, DELAYED)
    assessment = evaluate(view, CLOCK, set())
    assert ExceptionCategory.SCHEDULE_SLIP in {e.category for e in assessment.exceptions}
    assert assessment.severity.value == "CRITICAL"
    assert assessment.score == 400


@pytest.mark.unit
async def test_missing_confirmation(ds) -> None:
    assert ExceptionCategory.MISSING_CONFIRMATION in await _categories(ds, MISSING_CONF)


@pytest.mark.unit
async def test_material_shortage(ds) -> None:
    assert ExceptionCategory.MATERIAL_SHORTAGE in await _categories(ds, MATERIAL)


@pytest.mark.unit
async def test_quantity_shortfall(ds) -> None:
    assert ExceptionCategory.QUANTITY_SHORTFALL in await _categories(ds, QTY)


@pytest.mark.unit
async def test_status_inconsistency(ds) -> None:
    assert ExceptionCategory.STATUS_INCONSISTENCY in await _categories(ds, INCONSISTENT)


@pytest.mark.unit
async def test_every_exception_carries_facts(ds) -> None:
    view = await build_view(ds, DELAYED)
    assessment = evaluate(view, CLOCK, set())
    for exception in assessment.exceptions:
        assert exception.facts
        for fact in exception.facts:
            assert fact.source_field
            assert fact.source_key
