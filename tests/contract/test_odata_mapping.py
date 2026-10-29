from __future__ import annotations

import httpx
import pytest
import respx

from cto_order_agent.datasource.odata.client import ODataDataSource
from cto_order_agent.datasource.odata.mapping import (
    map_material_stock,
    map_production_order,
    map_sales_order,
)
from cto_order_agent.domain.errors import ToolFailure

BASE = "https://s4.example.com"

SALES_ORDER_RECORD = {
    "SalesOrder": "0000012345",
    "SalesOrderType": "ZMTO",
    "SoldToParty": "0000100001",
    "SoldToPartyName": "ACME Example GmbH",
    "RequestedDeliveryDate": "2026-01-20",
    "OverallSDProcessStatus": "B",
    "CreationDate": "2025-12-01T00:00:00Z",
    "TransactionCurrency": "EUR",
    "TotalNetAmount": "50000.00",
    "to_Item": {
        "results": [
            {
                "SalesOrderItem": "000010",
                "Material": "MTO-1000-A",
                "RequestedQuantity": "10",
                "RequestedQuantityUnit": "EA",
                "Plant": "1010",
                "SDProcessStatus": "A",
            }
        ]
    },
}

PRODUCTION_RECORD = {
    "ManufacturingOrder": "1000001",
    "ManufacturingOrderType": "ZP01",
    "Material": "MTO-1000-A",
    "ProductionPlant": "1010",
    "TotalQuantity": "10",
    "ProductionUnit": "EA",
    "ManufacturingOrderStatus": "REL",
    "MfgOrderPlannedStartDate": "2026-01-15T08:00:00Z",
    "MfgOrderPlannedEndDate": "2026-01-18T08:00:00Z",
    "SalesOrder": "0000012345",
    "SalesOrderItem": "000010",
    "to_Operation": {"results": []},
}


@pytest.mark.contract
def test_sales_order_mapping() -> None:
    mapped = map_sales_order(SALES_ORDER_RECORD)
    assert mapped["sales_order"] == "0000012345"
    assert mapped["overall_status"] == "IN_PROCESS"
    assert mapped["items"][0]["item_status"] == "OPEN"
    assert mapped["items"][0]["quantity_unit"] == "EA"


@pytest.mark.contract
def test_production_status_mapping() -> None:
    assert map_production_order(PRODUCTION_RECORD)["status"] == "RELEASED"


@pytest.mark.contract
def test_unknown_status_raises_upstream_error() -> None:
    broken = dict(PRODUCTION_RECORD, ManufacturingOrderStatus="WAT")
    with pytest.raises(ToolFailure) as excinfo:
        map_production_order(broken)
    assert excinfo.value.code == "UPSTREAM_ERROR"


@pytest.mark.contract
def test_stock_mapping_preserves_unit_and_rejects_missing_unit() -> None:
    record = {
        "Material": "MTO-1000-A",
        "Plant": "1010",
        "MatlWrhsStkQtyInMatlBaseUnit": "1000",
        "MaterialBaseUnit": "EA",
    }
    assert map_material_stock(record, "2026-01-15T08:00:00Z")["unrestricted_quantity"] == "1000"
    with pytest.raises(ToolFailure):
        map_material_stock(
            {"Material": "X", "Plant": "1010", "MatlWrhsStkQtyInMatlBaseUnit": "1"},
            "2026-01-15T08:00:00Z",
        )


@pytest.mark.contract
@respx.mock
async def test_client_reads_and_maps(settings) -> None:
    respx.get(
        f"{BASE}/sap/opu/odata/sap/API_SALES_ORDER_SRV/A_SalesOrder('0000012345')"
    ).mock(return_value=httpx.Response(200, json=SALES_ORDER_RECORD))

    client = ODataDataSource(settings, base_url=BASE)
    envelope = await client.get_sales_order("0000012345")
    assert envelope["value"][0]["sales_order"] == "0000012345"
    assert envelope["asOf"].endswith("Z")


@pytest.mark.contract
@respx.mock
async def test_client_maps_404_to_not_found(settings) -> None:
    respx.get(
        f"{BASE}/sap/opu/odata/sap/API_SALES_ORDER_SRV/A_SalesOrder('0000099999')"
    ).mock(return_value=httpx.Response(404, json={}))

    client = ODataDataSource(settings, base_url=BASE)
    with pytest.raises(ToolFailure) as excinfo:
        await client.get_sales_order("0000099999")
    assert excinfo.value.code == "NOT_FOUND"
