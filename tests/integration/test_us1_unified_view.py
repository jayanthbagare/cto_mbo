from __future__ import annotations

import pytest
from tests.conftest import NO_ORDERS, ON_TRACK


@pytest.mark.integration
async def test_v1_complete_consolidated_view(executor) -> None:
    turn = await executor.handle_turn(
        f"Status of sales order {ON_TRACK}", "ctx-v1", "task-v1"
    )
    message = turn.message
    assert ON_TRACK in message
    assert "000010" in message and "000020" in message
    assert "1000001" in message and "1000002" in message and "1000003" in message
    assert "As of 2026-01-15" in message
    assert "Sources consulted" in message
    assert turn.assessment is not None and turn.assessment.is_at_risk is False


@pytest.mark.integration
async def test_v2_order_without_production_orders(executor) -> None:
    turn = await executor.handle_turn(f"Status of {NO_ORDERS}", "ctx-v2", "task-v2")
    assert "none linked to this sales order" in turn.message
    assert NO_ORDERS in turn.message
    assert "error" not in turn.message.lower()


@pytest.mark.integration
async def test_v3_order_not_found(executor) -> None:
    turn = await executor.handle_turn("Status of 0000099999", "ctx-v3", "task-v3")
    assert "No sales order matches 0000099999" in turn.message
    assert "will not guess" in turn.message


@pytest.mark.integration
async def test_v4_ambiguous_reference(executor) -> None:
    turn = await executor.handle_turn("Status of order 1234", "ctx-v4", "task-v4")
    assert "match 1234" in turn.message
    assert "Which one do you mean?" in turn.message


@pytest.mark.integration
async def test_v5_follow_up_uses_context(executor) -> None:
    await executor.handle_turn(f"Status of {ON_TRACK}", "ctx-v5", "task-v5a")
    turn = await executor.handle_turn(
        "What about the second production order?", "ctx-v5", "task-v5b"
    )
    assert "1000002" in turn.message
    assert "1000001" not in turn.message.split("1000002")[0]


@pytest.mark.integration
async def test_fixtures_are_read_only_across_turns(executor, dataclass_dir) -> None:
    before = {p.name: p.read_bytes() for p in dataclass_dir.glob("*.json")}
    await executor.handle_turn(f"Status of {ON_TRACK}", "ctx-ro", "task-ro")
    after = {p.name: p.read_bytes() for p in dataclass_dir.glob("*.json")}
    assert before == after
