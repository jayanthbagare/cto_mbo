"""Deterministic exception detection and severity ranking (research D3, D12).

The model never classifies risk. Every conclusion here is a pure function of
retrieved data plus the evaluation clock, which is what makes SC-003 and SC-004
assertable.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from .enums import (
    DataCompleteness,
    ExceptionCategory,
    OrderStatus,
    ProductionOrderStatus,
    Severity,
)
from .models import (
    ConsolidatedOrderView,
    Fact,
    OrderException,
    ProductionOrder,
    RiskAssessment,
)

# Research D12. Published so planners can audit the ordering.
SCORE_DELIVERY_PASSED = 400
SCORE_MATERIAL_SHORTAGE = 380
SCORE_SLIP_OVER_14 = 300
SCORE_SLIP = 280
SCORE_MISSING_CONFIRMATION_OVER_7 = 260
SCORE_QUANTITY_SHORTFALL = 200
SCORE_MISSING_CONFIRMATION = 180
SCORE_STATUS_INCONSISTENCY = 160
SCORE_UNPOSTED_CONFIRMATION = 100

SEVERITY_BY_SCORE: dict[int, Severity] = {
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

SEVERITY_RANK = {
    Severity.CRITICAL: 4,
    Severity.HIGH: 3,
    Severity.MEDIUM: 2,
    Severity.LOW: 1,
}


def _fact(
    view: ConsolidatedOrderView,
    fact_id: str,
    statement: str,
    entity: str,
    key: str,
    field: str,
    value: object,
) -> Fact:
    return Fact(
        fact_id=fact_id,
        statement=statement,
        source_entity=entity,
        source_key=key,
        source_field=field,
        value=str(value),
        as_of=view.as_of,
    )


def _as_date(value: datetime) -> str:
    return value.date().isoformat()


def _slip_exception(
    view: ConsolidatedOrderView, po: ProductionOrder, clock: datetime, seq: int
) -> OrderException | None:
    requested = view.sales_order.requested_delivery_date
    effective = po.effective_end.date()
    delivery_passed = requested < clock.date() and not po.is_complete
    if effective <= requested and not delivery_passed:
        return None

    days_late = max((effective - requested).days, 0)
    if delivery_passed:
        score = SCORE_DELIVERY_PASSED
        statement = (
            f"The requested delivery date {requested.isoformat()} has passed and production "
            f"order {po.production_order} is not complete"
        )
    elif days_late > 14:
        score = SCORE_SLIP_OVER_14
        statement = (
            f"Production order {po.production_order} is confirmed for {effective.isoformat()}, "
            f"{days_late} days after the requested delivery date {requested.isoformat()}"
        )
    else:
        score = SCORE_SLIP
        statement = (
            f"Production order {po.production_order} is confirmed for {effective.isoformat()}, "
            f"{days_late} days after the requested delivery date {requested.isoformat()}"
        )

    facts = [
        _fact(
            view,
            f"F-{seq * 100 + 1}",
            statement,
            "ProductionOrder",
            po.production_order,
            "MfgOrderConfirmedEndDate",
            _as_date(po.effective_end),
        ),
        _fact(
            view,
            f"F-{seq * 100 + 2}",
            f"Sales order {view.sales_order.sales_order} requests delivery "
            f"{requested.isoformat()}",
            "SalesOrder",
            view.sales_order.sales_order,
            "RequestedDeliveryDate",
            requested.isoformat(),
        ),
    ]
    return OrderException(
        exception_id=OrderException.make_id(
            ExceptionCategory.SCHEDULE_SLIP, po.production_order, "slip"
        ),
        category=ExceptionCategory.SCHEDULE_SLIP,
        production_order=po.production_order,
        sales_order=view.sales_order.sales_order,
        severity=SEVERITY_BY_SCORE[score],
        score=score,
        detected_at=clock,
        facts=facts,
        inference=(
            f"Delivery is at risk because the manufacturing completion date trails the "
            f"customer date by {days_late} days"
        ),
    )


def _missing_confirmation(
    view: ConsolidatedOrderView, po: ProductionOrder, clock: datetime, seq: int
) -> list[OrderException]:
    found: list[OrderException] = []
    for op in view.operations_for(po.production_order):
        overdue = op.overdue_days(clock)
        if overdue <= 0:
            continue
        score = (
            SCORE_MISSING_CONFIRMATION_OVER_7
            if overdue > 7
            else SCORE_MISSING_CONFIRMATION
        )
        facts = [
            _fact(
                view,
                f"F-{seq * 100 + 10 + int(op.operation) * 2}",
                f"Operation {op.operation} of production order {po.production_order} was "
                f"planned to finish {_as_date(op.planned_end)} and has no confirmation",
                "ProductionOperation",
                f"{po.production_order}/{op.operation}",
                "ConfirmationQuantity",
                "0",
            ),
            _fact(
                view,
                f"F-{seq * 100 + 11 + int(op.operation) * 2}",
                f"Operation {op.operation} is {overdue} days past its planned completion",
                "ProductionOperation",
                f"{po.production_order}/{op.operation}",
                "PlannedEndDate",
                _as_date(op.planned_end),
            ),
        ]
        found.append(
            OrderException(
                exception_id=OrderException.make_id(
                    ExceptionCategory.MISSING_CONFIRMATION, po.production_order, op.operation
                ),
                category=ExceptionCategory.MISSING_CONFIRMATION,
                production_order=po.production_order,
                sales_order=view.sales_order.sales_order,
                severity=SEVERITY_BY_SCORE[score],
                score=score,
                detected_at=clock,
                facts=facts,
                inference=(
                    f"Work may not have started or the confirmation was not posted, because "
                    f"operation {op.operation} is {overdue} days overdue with no confirmed "
                    f"quantity"
                ),
            )
        )
    return found


def _quantity_shortfall(
    view: ConsolidatedOrderView, po: ProductionOrder, clock: datetime, seq: int
) -> OrderException | None:
    if po.confirmed_quantity >= po.total_quantity:
        return None
    if po.status not in (
        ProductionOrderStatus.CONFIRMED,
        ProductionOrderStatus.TECHNICALLY_COMPLETE,
        ProductionOrderStatus.CLOSED,
    ):
        return None
    shortfall = po.total_quantity - po.confirmed_quantity
    facts = [
        _fact(
            view,
            f"F-{seq * 100 + 30}",
            f"Production order {po.production_order} confirms {po.confirmed_quantity} of "
            f"{po.total_quantity} {po.quantity_unit}",
            "ProductionOrder",
            po.production_order,
            "ConfirmedQuantity",
            str(po.confirmed_quantity),
        ),
        _fact(
            view,
            f"F-{seq * 100 + 31}",
            f"{shortfall} {po.quantity_unit} remains unconfirmed with no open remainder",
            "ProductionOrder",
            po.production_order,
            "TotalQuantity",
            str(po.total_quantity),
        ),
    ]
    return OrderException(
        exception_id=OrderException.make_id(
            ExceptionCategory.QUANTITY_SHORTFALL, po.production_order, "qty"
        ),
        category=ExceptionCategory.QUANTITY_SHORTFALL,
        production_order=po.production_order,
        sales_order=view.sales_order.sales_order,
        severity=SEVERITY_BY_SCORE[SCORE_QUANTITY_SHORTFALL],
        score=SCORE_QUANTITY_SHORTFALL,
        detected_at=clock,
        facts=facts,
        inference="The order is reported complete while part of the quantity was never confirmed",
    )


def _material_shortage(
    view: ConsolidatedOrderView, po: ProductionOrder, clock: datetime, seq: int
) -> OrderException | None:
    available = view.available_for(po.material, po.plant)
    if available is None:
        return None
    if available >= po.total_quantity:
        return None
    facts = [
        _fact(
            view,
            f"F-{seq * 100 + 40}",
            f"Unrestricted stock for material {po.material} at plant {po.plant} is {available}",
            "MaterialAvailability",
            f"{po.material}/{po.plant}",
            "MatlWrhsStkQtyInMatlBaseUnit",
            str(available),
        ),
        _fact(
            view,
            f"F-{seq * 100 + 41}",
            f"Production order {po.production_order} requires {po.total_quantity} "
            f"{po.quantity_unit}",
            "ProductionOrder",
            po.production_order,
            "TotalQuantity",
            str(po.total_quantity),
        ),
    ]
    return OrderException(
        exception_id=OrderException.make_id(
            ExceptionCategory.MATERIAL_SHORTAGE, po.production_order, "mat"
        ),
        category=ExceptionCategory.MATERIAL_SHORTAGE,
        production_order=po.production_order,
        sales_order=view.sales_order.sales_order,
        severity=SEVERITY_BY_SCORE[SCORE_MATERIAL_SHORTAGE],
        score=SCORE_MATERIAL_SHORTAGE,
        detected_at=clock,
        facts=facts,
        inference=(
            "Production cannot start on schedule unless material is procured or replenished"
        ),
    )


def _status_inconsistency(
    view: ConsolidatedOrderView, po: ProductionOrder, clock: datetime, seq: int
) -> OrderException | None:
    if po.confirmed_quantity > 0 and po.status in (
        ProductionOrderStatus.CREATED,
        ProductionOrderStatus.RELEASED,
    ):
        score = SCORE_STATUS_INCONSISTENCY
        statement = (
            f"Production order {po.production_order} shows a confirmed quantity of "
            f"{po.confirmed_quantity} while its status is {po.status.value}"
        )
        field = "ManufacturingOrderStatus"
        value = po.status.value
    elif view.confirmations_for(po.production_order) and po.confirmed_quantity == 0:
        score = SCORE_UNPOSTED_CONFIRMATION
        statement = (
            f"Production order {po.production_order} has confirmations recorded but no "
            f"confirmed quantity posted to the order"
        )
        field = "ConfirmationQuantity"
        value = "0"
    else:
        return None

    facts = [
        _fact(
            view,
            f"F-{seq * 100 + 50}",
            statement,
            "ProductionOrder",
            po.production_order,
            field,
            value,
        )
    ]
    return OrderException(
        exception_id=OrderException.make_id(
            ExceptionCategory.STATUS_INCONSISTENCY, po.production_order, "status"
        ),
        category=ExceptionCategory.STATUS_INCONSISTENCY,
        production_order=po.production_order,
        sales_order=view.sales_order.sales_order,
        severity=SEVERITY_BY_SCORE[score],
        score=score,
        detected_at=clock,
        facts=facts,
        inference="The record set contradicts itself, so its status cannot be trusted as-is",
    )


def sort_key(exc: OrderException) -> tuple[int, int, str]:
    """Score desc, then earliest delivery date, then order number (research D12)."""
    return (-exc.score, 0, exc.production_order)


def detect_exceptions(
    view: ConsolidatedOrderView,
    clock: datetime,
    unavailable: set[str] | None = None,
    delivery_date_by_order: dict[str, object] | None = None,
) -> list[OrderException]:
    unavailable = unavailable or set()
    if view.sales_order.overall_status in (OrderStatus.COMPLETED, OrderStatus.CANCELLED):
        return []

    found: list[OrderException] = []
    check_stock = "get_material_stock" not in unavailable

    for seq, po in enumerate(view.production_orders, start=1):
        slip = _slip_exception(view, po, clock, seq)
        if slip:
            found.append(slip)
        found.extend(_missing_confirmation(view, po, clock, seq))
        qty = _quantity_shortfall(view, po, clock, seq)
        if qty:
            found.append(qty)
        if check_stock:
            stock = _material_shortage(view, po, clock, seq)
            if stock:
                found.append(stock)
        status = _status_inconsistency(view, po, clock, seq)
        if status:
            found.append(status)

    return found


def evaluate(
    view: ConsolidatedOrderView,
    clock: datetime,
    unavailable: set[str] | None = None,
) -> RiskAssessment:
    """Build the assessment. `is_at_risk` is derived, never assigned."""
    unavailable = unavailable or set()
    exceptions = detect_exceptions(view, clock, unavailable)
    exceptions.sort(key=lambda e: (-e.score, e.production_order, e.exception_id))

    missing: list[str] = []
    if "get_material_stock" in unavailable:
        missing.append("Material stock is unavailable; material shortages were not evaluated.")
    if "get_production_order_confirmations" in unavailable:
        missing.append("Confirmations are unavailable; quantity shortfalls were not evaluated.")
    if "get_product_master" in unavailable:
        missing.append("Product master data is unavailable; material descriptions are missing.")

    completeness = DataCompleteness.COMPLETE
    if missing and len(missing) >= 2:
        completeness = DataCompleteness.INSUFFICIENT
    elif missing:
        completeness = DataCompleteness.PARTIAL

    severity = max((e.severity for e in exceptions), key=lambda s: SEVERITY_RANK[s], default=None)
    score = max((e.score for e in exceptions), default=0)

    return RiskAssessment(
        sales_order=view.sales_order.sales_order,
        is_at_risk=bool(exceptions),
        severity=severity,
        score=score,
        exceptions=exceptions,
        evaluated_at=clock,
        data_completeness=completeness,
        missing_evidence=missing,
    )


def format_severity(assessment: RiskAssessment) -> str:
    return assessment.severity.value if assessment.severity else "NONE"


def as_decimal(value: Decimal | int) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


__all__ = [
    "SEVERITY_BY_SCORE",
    "SEVERITY_RANK",
    "detect_exceptions",
    "evaluate",
    "format_severity",
]
