"""Planner-facing rendering (FR-007, FR-008, FR-024)."""

from __future__ import annotations

from ..domain.enums import DataCompleteness
from ..domain.models import (
    ConsolidatedOrderView,
    ProductionOrder,
    Recommendation,
    RiskAssessment,
)

MAX_TREE_ORDERS = 50


def _indent(level: int) -> str:
    return "  " * level


def render_consolidated_view(view: ConsolidatedOrderView, assessment: RiskAssessment) -> str:
    order = view.sales_order
    lines = [
        f"Sales order {order.sales_order} — {order.customer_name}",
        (
            f"Status: {order.overall_status.value} | Requested delivery: "
            f"{order.requested_delivery_date.isoformat()} | "
            f"Currency: {order.currency}"
        ),
        "",
        "Items:",
    ]
    for item in order.items:
        lines.append(
            f"  {item.item_number}  {item.material}  "
            f"{item.requested_quantity} {item.quantity_unit}  plant {item.plant}  "
            f"[{item.item_status.value}]"
        )

    lines.append("")
    if not view.production_orders:
        lines.append("Production orders: none linked to this sales order.")
    else:
        lines.append(f"Production orders ({len(view.production_orders)}):")
        by_parent: dict[str | None, list[ProductionOrder]] = {}
        for candidate in view.production_orders:
            by_parent.setdefault(candidate.parent_production_order, []).append(candidate)

        def render_node(node: ProductionOrder, depth: int) -> None:
            confirmed = (
                node.confirmed_end.date().isoformat() if node.confirmed_end else "not confirmed"
            )
            lines.append(
                f"{_indent(depth)}- {node.production_order}  {node.material}  "
                f"{node.total_quantity} {node.quantity_unit}  status {node.status.value}  "
                f"planned end {node.planned_end.date().isoformat()}  confirmed {confirmed}"
            )
            for operation in view.operations_for(node.production_order):
                marker = "confirmed" if operation.is_confirmed else "no confirmation"
                lines.append(
                    f"{_indent(depth + 1)}operation {operation.operation}: "
                    f"{marker}, planned end {operation.planned_end.date().isoformat()}"
                )
            for child in by_parent.get(node.production_order, []):
                render_node(child, depth + 1)

        for root in by_parent.get(None, []):
            render_node(root, 0)
        if len(view.production_orders) > MAX_TREE_ORDERS:
            lines.append(
                f"  (output truncated: more than {MAX_TREE_ORDERS} production orders — "
                "grouped by exception, ask for the full list if needed)"
            )

    if view.materials:
        lines.append("")
        lines.append("Material availability:")
        for material in view.materials:
            plant = next(
                (i.plant for i in order.items if i.material == material.material),
                next(
                    (p.plant for p in view.production_orders if p.material == material.material),
                    None,
                ),
            )
            available = view.available_for(material.material, plant) if plant else None
            shown = "unknown" if available is None else f"{available} {material.base_unit}"
            lines.append(f"  {material.material}  {material.description}: {shown} unrestricted")

    lines.append("")
    if assessment.exceptions:
        lines.append(
            f"Risk: {assessment.severity.value if assessment.severity else 'NONE'} "
            f"(score {assessment.score}) — {len(assessment.exceptions)} exception(s)"
        )
        for exception in assessment.exceptions:
            lines.append(
                f"  - {exception.category.value} on production order "
                f"{exception.production_order} [{exception.severity.value}] "
                f"({exception.exception_id})"
            )
    else:
        lines.append("Risk: none detected for this order.")

    if assessment.data_completeness is not DataCompleteness.COMPLETE:
        lines.append("")
        lines.append(
            f"Data completeness: {assessment.data_completeness.value}. "
            + " ".join(assessment.missing_evidence)
        )

    lines.append("")
    lines.append(f"As of {view.as_of.isoformat()}.")
    lines.append("Sources consulted: " + ", ".join(view.sources_consulted) + ".")
    if view.sources_unavailable:
        lines.append("Sources unavailable: " + ", ".join(view.sources_unavailable) + ".")
    return "\n".join(lines)


def render_exception_list(
    rows: list[tuple[str, str, int, int]],
    scope: str,
    window_days: int,
    as_of: str,
) -> str:
    """Rows are (sales_order, severity, score, exception_count), already ranked."""
    if not rows:
        return (
            f"No orders are at risk in the searched scope.\n"
            f"Scope: {scope} | window: {window_days} days | as of {as_of}."
        )
    lines = [f"Orders at risk ({len(rows)}), most severe first:"]
    for index, (sales_order, severity, score, count) in enumerate(rows, start=1):
        lines.append(
            f"{index}. {sales_order}  {severity}  score {score}  ({count} exception(s))"
        )
    lines.append("")
    lines.append(f"Scope: {scope} | window: {window_days} days | as of {as_of}.")
    return "\n".join(lines)


def render_recommendations(
    assessment: RiskAssessment, recommendations: list[Recommendation]
) -> str:
    if not recommendations:
        return (
            "No exceptions were detected for this order, so no corrective action is required. "
            "I am read-only and cannot change order data."
        )
    lines = [f"Recommended actions ({len(recommendations)}), most urgent first:"]
    for index, rec in enumerate(recommendations, start=1):
        lines.append(
            f"{index}. [{rec.urgency.value}] {rec.action} "
            f"(owner: {rec.owner_role.value}). "
            f"Resolved when: {rec.resolution_evidence}."
        )
    lines.append("")
    lines.append(
        "I am read-only: these actions must be carried out in SAP S/4HANA by the named owner."
    )
    return "\n".join(lines)


def render_not_found(reference: str) -> str:
    return (
        f"No sales order matches {reference}. Please check the number and send it again; "
        "I will not guess an order."
    )


def render_ambiguous(reference: str, candidates: list[str]) -> str:
    lines = [f"{len(candidates)} sales orders match {reference}:"]
    for candidate in candidates:
        lines.append(f"  - {candidate}")
    lines.append("Which one do you mean?")
    return "\n".join(lines)


def render_refusal() -> str:
    return (
        "I am read-only and cannot change order data. I can show the consolidated status, "
        "flag exceptions, and recommend the manual step. To change this order, use the change "
        "order transaction in SAP S/4HANA or ask a planner with write access."
    )


def render_unknown() -> str:
    return (
        "I can help with a sales order number, an at-risk portfolio question, a risk "
        "explanation, recommendations, or a customer summary. Which order should I look at?"
    )


__all__ = [
    "MAX_TREE_ORDERS",
    "render_ambiguous",
    "render_consolidated_view",
    "render_exception_list",
    "render_not_found",
    "render_recommendations",
    "render_refusal",
    "render_unknown",
]
