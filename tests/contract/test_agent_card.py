from __future__ import annotations

import json

import pytest
from tests.conftest import CONTRACTS

from cto_order_agent.a2a.agent_card import SKILLS, build_agent_card


@pytest.mark.contract
def test_served_card_matches_the_contract() -> None:
    committed = json.loads((CONTRACTS / "contracts" / "agent-card.json").read_text())
    assert build_agent_card() == committed


@pytest.mark.contract
def test_five_skills_are_advertised() -> None:
    card = build_agent_card()
    ids = [skill["id"] for skill in card["skills"]]
    assert ids == [
        "unified-order-view",
        "exception-detection",
        "risk-explanation",
        "planner-recommendations",
        "customer-status-summary",
    ]
    assert len(SKILLS) == 5


@pytest.mark.contract
def test_protocol_declarations() -> None:
    card = build_agent_card()
    assert card["supportedInterfaces"][0]["protocolVersion"] == "1.0.0"
    assert card["supportedInterfaces"][0]["protocolBinding"] == "JSONRPC"
    assert card["capabilities"]["pushNotifications"] is False
