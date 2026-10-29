from __future__ import annotations

from datetime import UTC, datetime

import pytest
from tests.conftest import DELAYED, MATERIAL, MISSING_CONF, QTY, SCHEDULE_SLIP

from cto_order_agent.domain.consolidation import build_view
from cto_order_agent.domain.enums import ExceptionCategory
from cto_order_agent.domain.recommendations import TEMPLATES, build_recommendations
from cto_order_agent.domain.risk import SEVERITY_RANK, evaluate

CLOCK = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)


async def _recs(ds, order: str):
    view = await build_view(ds, order)
    assessment = evaluate(view, CLOCK, set(view.sources_unavailable))
    return assessment, build_recommendations(assessment.exceptions)


@pytest.mark.unit
@pytest.mark.parametrize(
    "order", [SCHEDULE_SLIP, DELAYED, MISSING_CONF, MATERIAL, QTY]
)
async def test_one_action_per_exception(ds, order: str) -> None:
    assessment, recommendations = await _recs(ds, order)
    assert len(recommendations) == len(assessment.exceptions)
    assert {r.addresses for r in recommendations} == {
        e.exception_id for e in assessment.exceptions
    }


@pytest.mark.unit
async def test_actions_come_from_the_closed_set(ds) -> None:
    prefixes = [template.action.split("{")[0].strip() for template in TEMPLATES.values()]
    _, recommendations = await _recs(ds, DELAYED)
    for rec in recommendations:
        assert any(rec.action.startswith(prefix) for prefix in prefixes), rec.action


@pytest.mark.unit
async def test_owner_and_resolution_are_present(ds) -> None:
    _, recommendations = await _recs(ds, DELAYED)
    for rec in recommendations:
        assert rec.owner_role
        assert rec.resolution_evidence


@pytest.mark.unit
async def test_recommendations_are_ordered_by_urgency(ds) -> None:
    assessment, recommendations = await _recs(ds, DELAYED)
    ranks = [SEVERITY_RANK[r.urgency] for r in recommendations]
    assert ranks == sorted(ranks, reverse=True)


@pytest.mark.unit
def test_every_category_has_a_template() -> None:
    assert set(TEMPLATES) == set(ExceptionCategory)
