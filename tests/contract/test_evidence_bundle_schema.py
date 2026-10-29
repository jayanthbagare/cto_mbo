from __future__ import annotations

import json
from datetime import UTC, datetime

import jsonschema
import pytest
from tests.conftest import (
    CONTRACTS,
    DATA_GAP,
    DELAYED,
    NO_ORDERS,
    ON_TRACK,
    SCHEDULE_SLIP,
)

from cto_order_agent.domain.consolidation import build_view
from cto_order_agent.domain.enums import Mode
from cto_order_agent.domain.evidence import build_bundle
from cto_order_agent.domain.recommendations import build_recommendations
from cto_order_agent.domain.risk import evaluate

CLOCK = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
SCHEMA = json.loads(
    (CONTRACTS / "contracts" / "evidence-bundle.schema.json").read_text()
)


async def _bundle(ds, order: str, mode: Mode):
    view = await build_view(ds, order)
    assessment = evaluate(view, CLOCK, set(view.sources_unavailable))
    return build_bundle(
        task_id="t",
        context_id="c",
        mode=mode,
        view=view,
        assessment=assessment,
        recommendations=build_recommendations(assessment.exceptions),
        clock=CLOCK,
    )


@pytest.mark.contract
@pytest.mark.parametrize(
    "order, mode",
    [
        (ON_TRACK, Mode.PLANNER_VIEW),
        (SCHEDULE_SLIP, Mode.RISK_EXPLANATION),
        (DELAYED, Mode.RISK_EXPLANATION),
        (DATA_GAP, Mode.RISK_EXPLANATION),
    ],
)
async def test_bundle_validates_against_schema(ds, order: str, mode: Mode) -> None:
    bundle = await _bundle(ds, order, mode)
    jsonschema.validate(instance=bundle.model_dump(mode="json", by_alias=True), schema=SCHEMA)


@pytest.mark.contract
async def test_incomplete_bundle_names_missing_evidence(ds) -> None:
    bundle = await _bundle(ds, DATA_GAP, Mode.RISK_EXPLANATION)
    payload = bundle.model_dump(mode="json", by_alias=True)
    assert payload["dataCompleteness"] == "INSUFFICIENT"
    assert payload["missingEvidence"]


@pytest.mark.contract
async def test_bundle_without_production_orders_is_valid(ds) -> None:
    bundle = await _bundle(ds, NO_ORDERS, Mode.PLANNER_VIEW)
    jsonschema.validate(instance=bundle.model_dump(mode="json", by_alias=True), schema=SCHEMA)
