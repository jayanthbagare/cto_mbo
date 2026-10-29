from __future__ import annotations

import pytest

from cto_order_agent.mcp_server.server import create_mcp_server
from cto_order_agent.mcp_server.tools import (
    TOOL_NAMES,
    GetConfirmationsInput,
    GetMaterialStockInput,
    GetProductionOrdersInput,
    GetProductMasterInput,
    GetSalesOrderInput,
    build_tool_specs,
)

EXPECTED_REQUIRED = {
    "get_sales_order": {"salesOrder"},
    "get_production_orders": {"salesOrder"},
    "get_production_order_confirmations": {"productionOrder"},
    "get_product_master": {"materials"},
    "get_material_stock": {"material", "plant"},
}

EXPECTED_MODELS = {
    "get_sales_order": GetSalesOrderInput,
    "get_production_orders": GetProductionOrdersInput,
    "get_production_order_confirmations": GetConfirmationsInput,
    "get_product_master": GetProductMasterInput,
    "get_material_stock": GetMaterialStockInput,
}


@pytest.mark.contract
def test_tool_set_matches_the_contract(ds) -> None:
    specs = {spec.name: spec for spec in build_tool_specs(ds)}
    assert set(specs) == set(TOOL_NAMES)
    for name, required in EXPECTED_REQUIRED.items():
        schema = specs[name].input_model.model_json_schema()
        assert set(schema.get("required", [])) == required
        assert schema["additionalProperties"] is False


@pytest.mark.contract
def test_input_models_are_the_documented_ones() -> None:
    assert {name: model for name, model in EXPECTED_MODELS.items()} == EXPECTED_MODELS


@pytest.mark.contract
async def test_server_registers_exactly_five_tools(ds) -> None:
    server = create_mcp_server(ds)
    tools = await server.list_tools()
    assert len(tools) == 5
    assert {tool.name for tool in tools} == set(TOOL_NAMES)


@pytest.mark.contract
def test_identifiers_are_strings_not_numbers(ds) -> None:
    schema = GetSalesOrderInput.model_json_schema()
    assert schema["properties"]["salesOrder"]["type"] == "string"
    assert schema["properties"]["salesOrder"]["pattern"] == "^[0-9]{10}$"
