from __future__ import annotations

import pytest

from cto_order_agent.mcp_server.tools import TOOL_NAMES, build_tool_specs

FORBIDDEN = ("create", "update", "delete", "set_", "post_", "cancel", "expedite", "write")


@pytest.mark.unit
def test_exactly_five_tools(ds) -> None:
    specs = build_tool_specs(ds)
    assert tuple(spec.name for spec in specs) == TOOL_NAMES
    assert len(TOOL_NAMES) == 5


@pytest.mark.unit
def test_no_mutating_tool_is_registered(ds) -> None:
    for spec in build_tool_specs(ds):
        assert not any(verb in spec.name.lower() for verb in FORBIDDEN)


@pytest.mark.unit
def test_tool_inputs_forbid_extra_fields(ds) -> None:
    for spec in build_tool_specs(ds):
        assert spec.input_model.model_config.get("extra") == "forbid"


@pytest.mark.unit
def test_tools_map_to_the_documented_sap_apis(ds) -> None:
    apis = {spec.name: spec.sap_api for spec in build_tool_specs(ds)}
    assert apis["get_sales_order"].endswith("CE_SALESORDER_0001:v1")
    assert apis["get_production_orders"].endswith("OP_API_PRODUCTION_ORDER_2_SRV_0001:v1")
    assert apis["get_material_stock"].endswith("OP_API_MATERIAL_STOCK_SRV:v1")
