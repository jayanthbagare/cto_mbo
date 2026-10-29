"""Customer-ready summary (FR-022, FR-023).

Built from an allowlist of customer-facing fields, then sanitized. Internal
identifiers are never rendered, and the sanitizer fails closed if one survives.
"""

from __future__ import annotations

import re

from ..domain.models import ConsolidatedOrderView, RiskAssessment

_STATUS_CODE = re.compile(r"\b(OPEN|IN_PROCESS|COMPLETED|CANCELLED|CREATED|RELEASED|"
                          r"PARTIALLY_CONFIRMED|CONFIRMED|TECHNICALLY_COMPLETE|CLOSED)\b")
_WORK_CENTER = re.compile(r"\bWC[- ]?\d+\b")


class SummaryLeak(RuntimeError):
    """An internal identifier survived rendering. Fail closed."""


def _internal_identifiers(
    view: ConsolidatedOrderView, extra: list[str] | None = None
) -> list[str]:
    identifiers: set[str] = set()
    for po in view.production_orders:
        identifiers.add(po.production_order)
        identifiers.add(po.plant)
    for item in view.sales_order.items:
        identifiers.add(item.material)
        identifiers.add(item.plant)
    for op in view.operations:
        if op.work_center:
            identifiers.add(op.work_center)
    for name in extra or []:
        if name:
            identifiers.add(name)
    return sorted(identifiers, key=len, reverse=True)


def sanitize(text: str, internal: list[str] | None = None) -> str:
    cleaned = text
    for identifier in internal or []:
        if identifier and len(identifier) >= 3:
            cleaned = re.sub(rf"(?<![\w-]){re.escape(identifier)}(?![\w-])", "", cleaned)
    cleaned = _STATUS_CODE.sub("", cleaned)
    cleaned = _WORK_CENTER.sub("", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" +([.,;:])", r"\1", cleaned)
    return cleaned.strip()


def assert_clean(text: str, internal: list[str] | None = None) -> None:
    for identifier in internal or []:
        if identifier and len(identifier) >= 3 and re.search(
            rf"(?<![\w-]){re.escape(identifier)}(?![\w-])", text
        ):
            raise SummaryLeak(f"internal identifier leaked: {identifier}")
    if _STATUS_CODE.search(text) or _WORK_CENTER.search(text):
        raise SummaryLeak("internal status code or work center leaked")


def render_customer_summary(
    view: ConsolidatedOrderView,
    assessment: RiskAssessment,
) -> str:
    order = view.sales_order
    lines = [
        f"Update for order {order.sales_order}",
        "",
        f"Requested delivery date: {order.requested_delivery_date.isoformat()}.",
    ]

    committed = [po.confirmed_end for po in view.production_orders if po.confirmed_end]
    internal = _internal_identifiers(view)

    if assessment.exceptions:
        lines.append(
            "We are currently unable to confirm the requested date and are reviewing the "
            "plan to recover it."
        )
    elif committed:
        earliest = min(committed).date().isoformat()
        lines.append(
            f"Production is confirmed to finish by {earliest}, which supports the requested date."
        )
    else:
        lines.append(
            "Production has not yet been confirmed, so the date above is an estimate and not "
            "yet a commitment."
        )

    if order.overall_status.value in ("COMPLETED",):
        lines.append("This order is complete.")
    elif order.overall_status.value in ("CANCELLED",):
        lines.append("This order has been cancelled.")

    lines.append("")
    lines.append("We will confirm any change to this date as soon as it is known.")
    text = "\n".join(lines)
    cleaned = sanitize(text, internal)
    assert_clean(cleaned, internal)
    return cleaned


__all__ = ["SummaryLeak", "assert_clean", "render_customer_summary", "sanitize"]
