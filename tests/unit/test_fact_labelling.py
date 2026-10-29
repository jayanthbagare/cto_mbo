from __future__ import annotations

import pytest
from tests.conftest import SCHEDULE_SLIP

LABELS = ("(confirmed fact)", "(inferred risk")


@pytest.mark.unit
async def test_every_claim_is_labelled(executor) -> None:
    turn = await executor.handle_turn(
        f"Why is order {SCHEDULE_SLIP} at risk?", "ctx-label", "task-label"
    )
    claims = [
        line
        for line in turn.message.splitlines()
        if line.startswith("- F-") or line.startswith("- I-")
    ]
    assert claims
    for line in claims:
        assert any(label in line for label in LABELS), line


@pytest.mark.unit
async def test_labelled_claims_match_the_bundle(executor) -> None:
    turn = await executor.handle_turn(
        f"Why is order {SCHEDULE_SLIP} at risk?", "ctx-label-2", "task-label-2"
    )
    assert turn.bundle is not None
    facts = [line for line in turn.message.splitlines() if line.startswith("- F-")]
    inferences = [line for line in turn.message.splitlines() if line.startswith("- I-")]
    assert len(facts) == len(turn.bundle.facts)
    assert len(inferences) == len(turn.bundle.inferences)
