"""Closed-set recommendations (FR-018, FR-019, FR-020).

Actions come from templates, never from the model. A prompt-drifted model can
change wording; it cannot invent a write operation.
"""

from __future__ import annotations

from dataclasses import dataclass

from .enums import ExceptionCategory, OwnerRole, Severity
from .models import OrderException, Recommendation


@dataclass(frozen=True)
class Template:
    action: str
    owner: OwnerRole
    resolution: str


TEMPLATES: dict[ExceptionCategory, Template] = {
    ExceptionCategory.SCHEDULE_SLIP: Template(
        action=(
            "Review capacity and confirmation dates for production order {order}, then agree a "
            "revised delivery date with the customer"
        ),
        owner=OwnerRole.PRODUCTION_PLANNER,
        resolution="A confirmed end date on or before the requested delivery date",
    ),
    ExceptionCategory.MISSING_CONFIRMATION: Template(
        action=(
            "Contact the shop-floor supervisor to confirm progress on operation {operation} of "
            "production order {order} and post the confirmation"
        ),
        owner=OwnerRole.SHOP_FLOOR_SUPERVISOR,
        resolution="A posted confirmation with a confirmed quantity for the overdue operation",
    ),
    ExceptionCategory.QUANTITY_SHORTFALL: Template(
        action=(
            "Verify the unconfirmed quantity of production order {order} and either post the "
            "missing confirmation or create a follow-up order"
        ),
        owner=OwnerRole.PRODUCTION_PLANNER,
        resolution="Confirmed quantity equal to the ordered quantity",
    ),
    ExceptionCategory.MATERIAL_SHORTAGE: Template(
        action=(
            "Check procurement for the required material of production order {order} and raise a "
            "replenishment or expedite request"
        ),
        owner=OwnerRole.PROCUREMENT,
        resolution="Unrestricted stock at least equal to the open requirement at the start date",
    ),
    ExceptionCategory.STATUS_INCONSISTENCY: Template(
        action=(
            "Reconcile the status of production order {order} against its posted confirmations "
            "in the ERP"
        ),
        owner=OwnerRole.PRODUCTION_PLANNER,
        resolution="Order status and confirmed quantity consistent in the source system",
    ),
}


def _target(exception: OrderException) -> tuple[str, str]:
    parts = exception.exception_id.split(":")
    return exception.production_order, parts[-1]


def build_recommendations(exceptions: list[OrderException]) -> list[Recommendation]:
    ordered = sorted(exceptions, key=lambda e: (-e.score, e.production_order, e.exception_id))
    recommendations: list[Recommendation] = []
    for index, exception in enumerate(ordered, start=1):
        template = TEMPLATES[exception.category]
        order, discriminator = _target(exception)
        recommendations.append(
            Recommendation(
                recommendation_id=f"R-{index}",
                addresses=exception.exception_id,
                action=template.action.format(order=order, operation=discriminator),
                owner_role=template.owner,
                urgency=exception.severity,
                resolution_evidence=template.resolution,
            )
        )
    return recommendations


def urgency_counts(recommendations: list[Recommendation]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for rec in recommendations:
        counts[rec.urgency.value] = counts.get(rec.urgency.value, 0) + 1
    return counts


SEVERITY_ORDER = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]

__all__ = ["SEVERITY_ORDER", "TEMPLATES", "build_recommendations", "urgency_counts"]
