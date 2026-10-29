from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from cto_order_agent.domain.enums import OrderStatus, ProductionOrderStatus
from cto_order_agent.domain.errors import InvariantError, UngroundedFactError
from cto_order_agent.domain.models import (
    Fact,
    ProductionOperation,
    ProductionOrder,
    SalesOrder,
)

CLOCK = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)


def _order(**overrides: object) -> SalesOrder:
    payload = {
        "sales_order": "0000012345",
        "customer_id": "0000100001",
        "customer_name": "ACME Example GmbH",
        "requested_delivery_date": date(2026, 1, 20),
        "created_at": datetime(2025, 12, 1, tzinfo=UTC),
    }
    payload.update(overrides)
    return SalesOrder(**payload)  # type: ignore[arg-type]


def _po(**overrides: object) -> ProductionOrder:
    payload = {
        "production_order": "1000001",
        "material": "MTO-1000-A",
        "plant": "1010",
        "total_quantity": "10",
        "quantity_unit": "EA",
        "planned_start": CLOCK,
        "planned_end": datetime(2026, 1, 18, tzinfo=UTC),
    }
    payload.update(overrides)
    return ProductionOrder(**payload)  # type: ignore[arg-type]


@pytest.mark.unit
def test_leading_zeros_are_preserved() -> None:
    order = _order()
    assert order.sales_order == "0000012345"
    assert len(order.sales_order) == 10


@pytest.mark.unit
def test_invalid_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _order(overall_status="WHATEVER")


@pytest.mark.unit
def test_planned_end_must_follow_start() -> None:
    with pytest.raises(InvariantError):
        _po(planned_end=CLOCK)


@pytest.mark.unit
def test_confirmed_quantity_cannot_exceed_total() -> None:
    with pytest.raises(InvariantError):
        _po(confirmed_quantity="11")


@pytest.mark.unit
def test_operation_is_confirmed_is_derived_only() -> None:
    operation = ProductionOperation(
        production_order="1000001",
        operation="0010",
        planned_start=CLOCK,
        planned_end=datetime(2026, 1, 16, tzinfo=UTC),
        confirmed_quantity="0",
    )
    assert operation.is_confirmed is False
    with pytest.raises(ValidationError):
        ProductionOperation(
            production_order="1000001",
            operation="0010",
            planned_start=CLOCK,
            planned_end=datetime(2026, 1, 16, tzinfo=UTC),
            is_confirmed=True,  # type: ignore[call-arg]
        )


@pytest.mark.unit
def test_fact_requires_a_source_record() -> None:
    with pytest.raises(UngroundedFactError):
        Fact(
            fact_id="F-1",
            statement="delivery is late",
            as_of=CLOCK,
        )


@pytest.mark.unit
def test_status_enum_values() -> None:
    assert OrderStatus.COMPLETED.is_terminal
    assert not OrderStatus.IN_PROCESS.is_terminal
    assert ProductionOrderStatus.CLOSED.is_terminal
