from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from tests.conftest import DELAYED

from cto_order_agent.domain.consolidation import build_view
from cto_order_agent.domain.enums import Mode
from cto_order_agent.domain.evidence import build_bundle
from cto_order_agent.domain.models import EvidenceBundle
from cto_order_agent.domain.recommendations import build_recommendations
from cto_order_agent.domain.risk import evaluate

CLOCK = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)


async def _bundle(ds, order: str = DELAYED):
    view = await build_view(ds, order)
    assessment = evaluate(view, CLOCK, set(view.sources_unavailable))
    return build_bundle(
        task_id="t1",
        context_id="c1",
        mode=Mode.RISK_EXPLANATION,
        view=view,
        assessment=assessment,
        recommendations=build_recommendations(assessment.exceptions),
        clock=CLOCK,
    )


@pytest.mark.unit
async def test_bundle_is_deterministic(ds) -> None:
    first = await _bundle(ds)
    second = await _bundle(ds)
    assert first.bundle_id == second.bundle_id
    assert [f.statement for f in first.facts] == [f.statement for f in second.facts]
    assert first.allowed_tokens == second.allowed_tokens


@pytest.mark.unit
async def test_allowed_tokens_come_from_facts(ds) -> None:
    bundle = await _bundle(ds)
    for fact in bundle.facts:
        assert fact.fact_id in bundle.allowed_tokens
        assert fact.value in bundle.allowed_tokens


@pytest.mark.unit
async def test_bundle_without_facts_is_impossible() -> None:
    with pytest.raises(ValidationError):
        EvidenceBundle(
            bundle_id="11111111-1111-1111-1111-111111111111",
            task_id="t",
            context_id="c",
            mode=Mode.PLANNER_VIEW,
            facts=[],
            as_of=CLOCK,
            data_completeness="COMPLETE",
        )


@pytest.mark.unit
async def test_fact_ids_are_dense_and_unique(ds) -> None:
    bundle = await _bundle(ds)
    ids = [fact.fact_id for fact in bundle.facts]
    assert len(ids) == len(set(ids))
    assert ids[0] == "F-1"


@pytest.mark.unit
async def test_inference_cites_facts(ds) -> None:
    bundle = await _bundle(ds)
    fact_ids = {fact.fact_id for fact in bundle.facts}
    for inference in bundle.inferences:
        assert set(inference.based_on) <= fact_ids
