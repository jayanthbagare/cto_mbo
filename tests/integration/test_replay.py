from __future__ import annotations

import pytest
from tests.conftest import SCHEDULE_SLIP

from cto_order_agent.observability.answer_log import record_answer, replay_facts


@pytest.mark.integration
async def test_answer_record_reconstructs_every_fact(executor) -> None:
    turn = await executor.handle_turn(
        f"Why is order {SCHEDULE_SLIP} at risk?", "ctx-replay", "task-replay"
    )
    assert turn.bundle is not None

    record = record_answer(
        task_id=turn.task_id,
        context_id=turn.context_id,
        intent=turn.intent.value,
        message=turn.message,
        bundle=turn.bundle,
        assessment=turn.assessment,
    )
    recovered = replay_facts(record)
    assert len(recovered) == len(turn.bundle.facts)
    assert recovered == [
        (f.source_entity, f.source_key, f.source_field, f.value) for f in turn.bundle.facts
    ]
    assert record["contextId"] == "ctx-replay"
    assert record["exceptions"]


@pytest.mark.integration
async def test_record_does_not_contain_secrets(executor) -> None:
    turn = await executor.handle_turn(
        f"Status of {SCHEDULE_SLIP}", "ctx-replay-2", "task-replay-2"
    )
    record = record_answer(
        task_id=turn.task_id,
        context_id=turn.context_id,
        intent=turn.intent.value,
        message=turn.message,
    )
    serialized = str(record).lower()
    assert "secret" not in serialized
    assert "bearer" not in serialized
