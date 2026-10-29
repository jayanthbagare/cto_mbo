from __future__ import annotations

import pytest
from tests.conftest import DELAYED, SCHEDULE_SLIP


@pytest.mark.integration
async def test_v10_recommendations_are_ranked_and_owned(executor) -> None:
    turn = await executor.handle_turn(
        f"What should I do about {SCHEDULE_SLIP}?", "ctx-v10", "task-v10"
    )
    message = turn.message
    assert "Recommended actions" in message
    assert "PRODUCTION_PLANNER" in message
    assert "Resolved when" in message
    assert "I am read-only" in message


@pytest.mark.integration
async def test_v10_expedite_is_refused(executor) -> None:
    turn = await executor.handle_turn(
        f"Can you expedite {SCHEDULE_SLIP} for me?", "ctx-v10b", "task-v10b"
    )
    assert turn.message.startswith("I am read-only")
    assert "cannot change order data" in turn.message


@pytest.mark.integration
async def test_multiple_exceptions_get_multiple_actions(executor) -> None:
    turn = await executor.handle_turn(
        f"What should I do about {DELAYED}?", "ctx-v10c", "task-v10c"
    )
    assert turn.assessment is not None
    assert turn.assessment.exceptions
    actions = [line for line in turn.message.splitlines() if line[:1].isdigit() and ". [" in line]
    assert len(actions) == len(turn.assessment.exceptions)


@pytest.mark.integration
async def test_no_data_changes_after_recommendations(executor, dataclass_dir) -> None:
    before = {p.name: p.read_bytes() for p in dataclass_dir.glob("*.json")}
    await executor.handle_turn(f"What should I do about {DELAYED}?", "ctx-v10d", "t")
    await executor.handle_turn("Release the production order", "ctx-v10d", "t2")
    after = {p.name: p.read_bytes() for p in dataclass_dir.glob("*.json")}
    assert before == after
