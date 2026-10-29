"""Evidence bundle construction (FR-014 to FR-017).

The bundle is the only thing the narrative layer is allowed to describe, and
`allowed_tokens` is the whitelist the grounding validator enforces.
"""

from __future__ import annotations

import re
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from .enums import Confidence, DataCompleteness, Mode
from .models import (
    ConsolidatedOrderView,
    EvidenceBundle,
    Fact,
    Inference,
    OrderException,
    Recommendation,
    RiskAssessment,
)

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _iso(value: datetime) -> str:
    return value.isoformat()


def _date(value: datetime) -> str:
    return value.date().isoformat()


def _renumber(facts: list[Fact]) -> list[Fact]:
    renumbered: list[Fact] = []
    seen: set[tuple[str, str, str, str]] = set()
    for fact in facts:
        key = (fact.source_entity, fact.source_key, fact.source_field, fact.value)
        if key in seen:
            continue
        seen.add(key)
        renumbered.append(
            fact.model_copy(update={"fact_id": f"F-{len(renumbered) + 1}"})
        )
    return renumbered


def _base_facts(view: ConsolidatedOrderView) -> list[Fact]:
    order = view.sales_order
    as_of = view.as_of
    facts = [
        Fact(
            fact_id="F-0",
            statement=(
                f"Sales order {order.sales_order} requests delivery on "
                f"{order.requested_delivery_date.isoformat()}"
            ),
            source_entity="SalesOrder",
            source_key=order.sales_order,
            source_field="RequestedDeliveryDate",
            value=order.requested_delivery_date.isoformat(),
            as_of=as_of,
        ),
        Fact(
            fact_id="F-0",
            statement=f"Sales order {order.sales_order} has status {order.overall_status.value}",
            source_entity="SalesOrder",
            source_key=order.sales_order,
            source_field="OverallSDProcessStatus",
            value=order.overall_status.value,
            as_of=as_of,
        ),
    ]
    for item in order.items:
        facts.append(
            Fact(
                fact_id="F-0",
                statement=(
                    f"Item {item.item_number} requests {item.requested_quantity} "
                    f"{item.quantity_unit} of material {item.material}"
                ),
                source_entity="SalesOrderItem",
                source_key=f"{order.sales_order}/{item.item_number}",
                source_field="RequestedQuantity",
                value=str(item.requested_quantity),
                as_of=as_of,
            )
        )
    for po in view.production_orders:
        facts.append(
            Fact(
                fact_id="F-0",
                statement=(
                    f"Production order {po.production_order} has status {po.status.value} and "
                    f"is planned to finish {_date(po.planned_end)}"
                ),
                source_entity="ProductionOrder",
                source_key=po.production_order,
                source_field="ManufacturingOrderStatus",
                value=po.status.value,
                as_of=as_of,
            )
        )
        facts.append(
            Fact(
                fact_id="F-0",
                statement=(
                    f"Production order {po.production_order} confirms "
                    f"{po.confirmed_quantity} of {po.total_quantity} {po.quantity_unit}"
                ),
                source_entity="ProductionOrder",
                source_key=po.production_order,
                source_field="ConfirmedQuantity",
                value=str(po.confirmed_quantity),
                as_of=as_of,
            )
        )
    return facts


def _exception_facts(exceptions: list[OrderException]) -> list[Fact]:
    facts: list[Fact] = []
    for exception in exceptions:
        facts.extend(exception.facts)
    return facts


def _tokens(
    view: ConsolidatedOrderView,
    assessment: RiskAssessment,
    facts: list[Fact],
    inferences: list[Inference],
    recommendations: list[Recommendation],
    as_of: datetime,
) -> list[str]:
    tokens: set[str] = set()

    def harvest(text: str) -> None:
        tokens.update(_NUMBER.findall(text))
        tokens.update(_DATE.findall(text))

    harvest(_iso(as_of))
    harvest(_date(as_of))

    for fact in facts:
        harvest(fact.value)
        harvest(fact.statement)
        tokens.add(fact.fact_id)
    for inference in inferences:
        harvest(inference.statement)
        tokens.add(inference.inference_id)
    for rec in recommendations:
        harvest(rec.action)
        harvest(rec.resolution_evidence)
        tokens.add(rec.recommendation_id)
    for exception in assessment.exceptions:
        tokens.add(exception.exception_id)
        tokens.add(exception.score.__str__())
        harvest(exception.exception_id)
        if exception.inference:
            harvest(exception.inference)

    order = view.sales_order
    tokens.update(
        {
            order.sales_order,
            order.customer_id,
            order.requested_delivery_date.isoformat(),
            order.overall_status.value,
            _date(as_of),
            _iso(as_of),
            str(len(order.items)),
            str(len(view.production_orders)),
            str(len(view.materials)),
            str(len(assessment.exceptions)),
            str(len(recommendations)),
            str(len(view.sales_order.items)),
        }
    )
    for item in order.items:
        tokens.add(item.item_number)
        tokens.add(str(item.requested_quantity))
    for po in view.production_orders:
        tokens.add(po.production_order)
        tokens.add(str(po.total_quantity))
        tokens.add(str(po.confirmed_quantity))
        tokens.add(po.status.value)
        tokens.add(_date(po.planned_end))
        if po.confirmed_end:
            tokens.add(_date(po.confirmed_end))
    for material in view.materials:
        tokens.add(material.material)
        tokens.add(material.base_unit)
    for avail in view.availability:
        tokens.add(str(avail.unrestricted_quantity))
    if assessment.severity:
        tokens.add(assessment.severity.value)

    return sorted(tokens)


def build_bundle(
    *,
    task_id: str,
    context_id: str,
    mode: Mode,
    view: ConsolidatedOrderView,
    assessment: RiskAssessment,
    recommendations: list[Recommendation],
    clock: datetime,
) -> EvidenceBundle:
    raw_facts = _base_facts(view) + _exception_facts(assessment.exceptions)
    facts = _renumber(raw_facts)

    inferences: list[Inference] = []
    fact_ids = [f.fact_id for f in facts]
    for index, exception in enumerate(assessment.exceptions, start=1):
        if not exception.inference:
            continue
        inferences.append(
            Inference(
                inference_id=f"I-{index}",
                statement=exception.inference,
                based_on=fact_ids or ["F-1"],
                confidence=Confidence.MEDIUM,
            )
        )

    bundle_id = uuid5(
        NAMESPACE_URL,
        f"{task_id}|{context_id}|{mode.value}|{view.sales_order.sales_order}|{clock.isoformat()}",
    )

    tokens = _tokens(view, assessment, facts, inferences, recommendations, view.as_of)

    return EvidenceBundle(
        bundle_id=bundle_id,
        task_id=task_id,
        context_id=context_id,
        mode=mode,
        facts=facts,
        inferences=inferences,
        recommendations=recommendations,
        as_of=view.as_of,
        data_completeness=assessment.data_completeness
        if assessment.data_completeness is not DataCompleteness.COMPLETE
        else DataCompleteness.COMPLETE,
        allowed_tokens=tokens,
        missing_evidence=list(assessment.missing_evidence),
        sources_consulted=list(view.sources_consulted),
        sources_unavailable=list(view.sources_unavailable),
    )


__all__ = ["build_bundle"]
