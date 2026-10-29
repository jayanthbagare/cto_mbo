from __future__ import annotations

import re
from pathlib import Path

import pytest

from cto_order_agent.datasource.protocol import DataSource

SRC = Path(__file__).resolve().parents[2] / "src" / "cto_order_agent"


@pytest.mark.unit
def test_mock_adapter_satisfies_the_port(ds: object) -> None:
    assert isinstance(ds, DataSource)


@pytest.mark.unit
def test_odata_adapter_satisfies_the_port(settings: object) -> None:
    from cto_order_agent.datasource.odata.client import ODataDataSource

    assert isinstance(ODataDataSource(settings), DataSource)  # type: ignore[arg-type]


@pytest.mark.unit
def test_agent_never_branches_on_provenance() -> None:
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        # The seam itself is allowed to know about provenance; nothing else is.
        if "datasource" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r'\.source\s*==|\["source"\]\s*==', text):
            offenders.append(str(path))
        if "SYNTHETIC" in text:
            offenders.append(str(path))
    assert offenders == []


@pytest.mark.unit
def test_mock_adapter_exposes_exactly_five_read_tools() -> None:
    tools = [name for name in dir(DataSource) if name.startswith("get_")]
    assert sorted(tools) == [
        "get_material_stock",
        "get_product_master",
        "get_production_order_confirmations",
        "get_production_orders",
        "get_sales_order",
    ]
