"""Portfolio scan (FR-013)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ..datasource.protocol import DataSource
from .consolidation import build_view
from .enums import OrderStatus
from .models import RiskAssessment
from .risk import evaluate


@dataclass(frozen=True)
class PortfolioRow:
    sales_order: str
    severity: str
    score: int
    exception_count: int
    requested_delivery_date: str


@dataclass(frozen=True)
class PortfolioResult:
    rows: list[PortfolioRow]
    scope: str
    window_days: int
    as_of: datetime
    scanned: int


async def scan(
    ds: DataSource, clock: datetime, window_days: int = 365
) -> PortfolioResult:
    refs = sorted(await ds.list_order_refs(window_days))
    horizon = timedelta(days=window_days)
    rows: list[PortfolioRow] = []
    scanned = 0

    for reference in refs:
        view = await build_view(ds, reference)
        order = view.sales_order
        if order.overall_status is OrderStatus.CANCELLED:
            continue
        if order.overall_status is OrderStatus.COMPLETED:
            continue
        delta = order.requested_delivery_date - clock.date()
        if abs(delta) > horizon:
            continue
        scanned += 1
        assessment: RiskAssessment = evaluate(
            view, clock, set(view.sources_unavailable)
        )
        if not assessment.exceptions:
            continue
        rows.append(
            PortfolioRow(
                sales_order=order.sales_order,
                severity=assessment.severity.value if assessment.severity else "NONE",
                score=assessment.score,
                exception_count=len(assessment.exceptions),
                requested_delivery_date=order.requested_delivery_date.isoformat(),
            )
        )

    rows.sort(key=lambda r: (-r.score, r.requested_delivery_date, r.sales_order))
    return PortfolioResult(
        rows=rows,
        scope="all open sales orders",
        window_days=window_days,
        as_of=clock,
        scanned=scanned,
    )


__all__ = ["PortfolioResult", "PortfolioRow", "scan"]
