from __future__ import annotations

import pytest

WRITE_REQUESTS = [
    "Can you expedite order 0000012346?",
    "Reschedule 0000012346 to next week",
    "Release the production order",
    "Cancel order 0000012346",
    "Change the date for 0000012346",
    "Post the confirmation for 0000012346",
    "Delete the production order",
]


@pytest.mark.unit
@pytest.mark.parametrize("text", WRITE_REQUESTS)
async def test_write_requests_are_refused(executor, text: str) -> None:
    turn = await executor.handle_turn(text, "ctx-write", "task-write")
    assert turn.message.startswith("I am read-only")
    assert "SAP S/4HANA" in turn.message
    assert turn.assessment is None
    assert turn.records == {}


@pytest.mark.unit
async def test_refusal_precedes_any_tool_call(executor) -> None:
    before = dict(executor._ds._cache)
    turn = await executor.handle_turn(
        "Expedite 0000012346 immediately", "ctx-write-2", "task-write-2"
    )
    assert turn.view is None
    assert executor._ds._cache == before
