from __future__ import annotations

import pytest
from tests.conftest import DATA_GAP, SCHEDULE_SLIP


@pytest.mark.integration
async def test_v8_facts_and_inferences_are_labelled(executor) -> None:
    turn = await executor.handle_turn(
        f"Why is order {SCHEDULE_SLIP} at risk?", "ctx-v8", "task-v8"
    )
    facts = [line for line in turn.message.splitlines() if line.startswith("- F-")]
    inferences = [line for line in turn.message.splitlines() if line.startswith("- I-")]
    assert facts and inferences
    assert all("(confirmed fact)" in line for line in facts)
    assert all("(inferred risk" in line for line in inferences)
    assert turn.bundle is not None
    assert "2026-02-02" in turn.message


@pytest.mark.integration
async def test_v9_insufficient_evidence_is_declared(executor) -> None:
    turn = await executor.handle_turn(
        f"Why is order {DATA_GAP} at risk?", "ctx-v9", "task-v9"
    )
    lowered = turn.message.lower()
    assert "incomplete" in lowered
    assert "missing evidence" in lowered
    assert "inferred risk" not in lowered
    assert "get_material_stock" in turn.message


@pytest.mark.integration
async def test_grounding_gate_holds_for_every_explanation_mode(executor) -> None:
    for index, order in enumerate([SCHEDULE_SLIP, "0000012349", "0000012353"]):
        turn = await executor.handle_turn(
            f"Why is order {order} at risk?", f"ctx-g{index}", f"task-g{index}"
        )
        assert turn.bundle is not None
        # every numeric token in the answer exists in the bundle's whitelist
        from cto_order_agent.narrative.validator import ungrounded

        assert ungrounded(turn.message, turn.bundle.allowed_tokens) == []
