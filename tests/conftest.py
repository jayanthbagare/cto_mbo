from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from cto_order_agent.a2a.executor import AgentExecutor
from cto_order_agent.config import Settings
from cto_order_agent.datasource.mock.adapter import MockDataSource

CLOCK = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "scenarios"
CONTRACTS = Path(__file__).resolve().parents[1] / "specs" / "001-mto-cto-order-intelligence"

ON_TRACK = "0000012345"
MULTILEVEL = "0000012347"
PARTIAL_ON_TIME = "0000012348"
SCHEDULE_SLIP = "0000012346"
DELAYED = "0000012349"
MISSING_CONF = "0000012351"
MATERIAL = "0000012353"
QTY = "0000012354"
INCONSISTENT = "0000012355"
NO_ORDERS = "0000012350"
DATA_GAP = "0000012352"


@pytest.fixture
def settings() -> Settings:
    return Settings.from_env({"LLM_MODE": "template", "PROCESS_CLOCK": CLOCK.isoformat()})


@pytest.fixture
def ds() -> MockDataSource:
    return MockDataSource.from_dir(FIXTURES)


@pytest.fixture
def executor(ds: MockDataSource, settings: Settings) -> AgentExecutor:
    return AgentExecutor(ds, settings, clock=CLOCK)


@pytest.fixture
def dataclass_dir() -> Path:
    return FIXTURES
