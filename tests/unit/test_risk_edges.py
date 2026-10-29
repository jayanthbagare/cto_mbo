from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from tests.conftest import ON_TRACK, SCHEDULE_SLIP

from cto_order_agent.domain.consolidation import build_view
from cto_order_agent.domain.enums import DataCompleteness, Mode
from cto_order_agent.domain.evidence import build_bundle
from cto_order_agent.domain.recommendations import build_recommendations
from cto_order_agent.domain.risk import (
    SCORE_SLIP_OVER_14,
    SCORE_UNPOSTED_CONFIRMATION,
    as_decimal,
    evaluate,
    format_severity,
    sort_key,
)

CLOCK = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)


@pytest.mark.unit
async def test_slip_longer_than_two_weeks_is_high(ds) -> None:
    view = await build_view(ds, SCHEDULE_SLIP)
    po = view.production_orders[0]
    far = view.sales_order.requested_delivery_date + timedelta(days=20)
    late_po = po.model_copy(update={"confirmed_end": datetime.combine(
        far, datetime.min.time(), tzinfo=UTC)})
    view = view.model_copy(update={"production_orders": [late_po]})
    assessment = evaluate(view, CLOCK, set())
    slip = [e for e in assessment.exceptions if e.category.value == "SCHEDULE_SLIP"][0]
    assert slip.score == SCORE_SLIP_OVER_14


@pytest.mark.unit
async def test_missing_stock_data_skips_the_rule(ds) -> None:
    view = await build_view(ds, ON_TRACK)
    stripped = view.model_copy(update={"availability": []})
    assessment = evaluate(stripped, CLOCK, set())
    assert not any(e.category.value == "MATERIAL_SHORTAGE" for e in assessment.exceptions)


@pytest.mark.unit
async def test_unposted_confirmation_is_low_severity(ds) -> None:
    view = await build_view(ds, ON_TRACK)
    po = view.production_orders[0]
    inconsistent = po.model_copy(update={"confirmed_quantity": Decimal("0")})
    view = view.model_copy(update={"production_orders": [inconsistent]})
    assessment = evaluate(view, CLOCK, set())
    unposted = [
        e
        for e in assessment.exceptions
        if e.category.value == "STATUS_INCONSISTENCY" and e.score == SCORE_UNPOSTED_CONFIRMATION
    ]
    assert unposted, [e.score for e in assessment.exceptions]


@pytest.mark.unit
async def test_two_unavailable_sources_means_insufficient(ds) -> None:
    view = await build_view(ds, ON_TRACK)
    assessment = evaluate(
        view, CLOCK, {"get_material_stock", "get_product_master"}
    )
    assert assessment.data_completeness is DataCompleteness.INSUFFICIENT
    assert len(assessment.missing_evidence) >= 2


@pytest.mark.unit
async def test_single_unavailable_source_means_partial(ds) -> None:
    view = await build_view(ds, ON_TRACK)
    assessment = evaluate(view, CLOCK, {"get_material_stock"})
    assert assessment.data_completeness is DataCompleteness.PARTIAL


@pytest.mark.unit
async def test_unavailable_confirmations_are_named(ds) -> None:
    view = await build_view(ds, ON_TRACK)
    assessment = evaluate(view, CLOCK, {"get_production_order_confirmations"})
    assert any("Confirmations" in item for item in assessment.missing_evidence)


@pytest.mark.unit
async def test_exception_without_inference_is_still_reportable(ds) -> None:
    view = await build_view(ds, "0000012349")
    assessment = evaluate(view, CLOCK, set())
    stripped = assessment.model_copy(
        update={
            "exceptions": [
                exc.model_copy(update={"inference": None}) for exc in assessment.exceptions
            ]
        }
    )
    bundle = build_bundle(
        task_id="t",
        context_id="c",
        mode=Mode.RISK_EXPLANATION,
        view=view,
        assessment=stripped,
        recommendations=build_recommendations(stripped.exceptions),
        clock=CLOCK,
    )
    assert bundle.inferences == []
    assert bundle.facts


@pytest.mark.unit
async def test_helpers(ds) -> None:
    view = await build_view(ds, SCHEDULE_SLIP)
    assessment = evaluate(view, CLOCK, set())
    assert format_severity(assessment) == "HIGH"
    assert as_decimal(3) == Decimal("3")
    assert as_decimal(Decimal("3")) == Decimal("3")
    ordered = sorted(assessment.exceptions, key=sort_key)
    assert ordered == sorted(ordered, key=lambda e: -e.score)
    healthy = await build_view(ds, ON_TRACK)
    assert format_severity(evaluate(healthy, CLOCK, set())) == "NONE"
