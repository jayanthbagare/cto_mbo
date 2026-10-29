from __future__ import annotations

import json

import pytest
from tests.conftest import CLOCK, FIXTURES

from cto_order_agent.domain.consolidation import build_view
from cto_order_agent.domain.risk import evaluate

CLOCK_LINE = "as of 2026-01-15"


@pytest.mark.integration
@pytest.mark.eval
async def test_v6_scenario_corpus_matches_expected(ds) -> None:
    clock = CLOCK
    checked = 0
    for path in sorted(FIXTURES.glob("*.expected.json")):
        expected = json.loads(path.read_text())
        for order, claim in expected["salesOrders"].items():
            view = await build_view(ds, order)
            assessment = evaluate(view, clock, set(view.sources_unavailable))
            actual = {exc.category.value for exc in assessment.exceptions}
            assert assessment.is_at_risk is claim["atRisk"], (path.name, order)
            assert actual == set(claim["categories"]), (path.name, order, actual)
            checked += 1
    assert checked == 14


@pytest.mark.integration
async def test_v7_portfolio_is_ranked_and_scoped(executor) -> None:
    turn = await executor.handle_turn("Which orders are at risk?", "ctx-v7", "task-v7")
    message = turn.message
    assert "Orders at risk" in message
    assert "Scope: all open sales orders" in message
    assert CLOCK_LINE in message.lower()
    assert "0000012358" not in message  # completed orders are excluded
    lines = [line for line in message.splitlines() if line[:1].isdigit() and ". " in line]
    assert len(lines) >= 6


@pytest.mark.integration
async def test_exception_detail_names_the_triggering_category(executor) -> None:
    turn = await executor.handle_turn(
        "Does order 0000012346 have exceptions?", "ctx-v7b", "task-v7b"
    )
    assert "SCHEDULE_SLIP" in turn.message
