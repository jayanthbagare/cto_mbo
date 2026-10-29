from __future__ import annotations

import pytest
from tests.conftest import DATA_GAP

from cto_order_agent.domain.enums import DataCompleteness


@pytest.mark.unit
async def test_data_gap_is_declared_not_guessed(executor) -> None:
    turn = await executor.handle_turn(
        f"Why is order {DATA_GAP} at risk?", "ctx-gap", "task-gap"
    )
    assert turn.assessment is not None
    assert turn.assessment.data_completeness is DataCompleteness.INSUFFICIENT
    assert turn.assessment.missing_evidence
    assert "incomplete" in turn.message.lower()
    assert "inferred risk" not in turn.message.lower()
    assert turn.bundle is not None
    assert turn.bundle.inferences == []


@pytest.mark.unit
async def test_missing_evidence_names_the_source(executor) -> None:
    turn = await executor.handle_turn(
        f"Status of {DATA_GAP}", "ctx-gap-2", "task-gap-2"
    )
    assert "get_material_stock" in turn.message
