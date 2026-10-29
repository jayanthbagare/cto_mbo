"""Tool contracts (contracts/mcp-tools.md) and their adapters.

Every tool is a thin wrapper over the DataSource. No tool writes, and no tool
reveals its provenance.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..datasource.protocol import DataSource
from ..domain.errors import ToolFailure

TOOL_NAMES = (
    "get_sales_order",
    "get_production_orders",
    "get_production_order_confirmations",
    "get_product_master",
    "get_material_stock",
)


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GetSalesOrderInput(ToolInput):
    salesOrder: str = Field(pattern=r"^[0-9]{10}$")
    includeItems: bool = True
    expandCustomer: bool = True


class GetProductionOrdersInput(ToolInput):
    salesOrder: str = Field(pattern=r"^[0-9]{10}$")
    salesOrderItem: str | None = Field(default=None, pattern=r"^[0-9]{6}$")
    includeOperations: bool = True
    includeHierarchy: bool = True
    top: int = Field(default=200, ge=1, le=500)


class GetConfirmationsInput(ToolInput):
    productionOrder: str = Field(pattern=r"^[0-9]{1,12}$")
    includeReversed: bool = False
    top: int = Field(default=500, ge=1, le=1000)


class GetProductMasterInput(ToolInput):
    materials: list[str] = Field(min_length=1, max_length=100)


class GetMaterialStockInput(ToolInput):
    material: str = Field(min_length=1, max_length=40)
    plant: str = Field(min_length=1, max_length=4)
    storageLocation: str | None = Field(default=None, max_length=4)
    stockType: str = Field(default="ALL", pattern=r"^(UNRESTRICTED|QUALITY|BLOCKED|ALL)$")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[ToolInput]
    handler: Callable[[Any], Awaitable[dict[str, Any]]]
    sap_api: str


def build_tool_specs(ds: DataSource) -> list[ToolSpec]:
    async def get_sales_order(payload: GetSalesOrderInput) -> dict[str, Any]:
        return await ds.get_sales_order(
            payload.salesOrder, payload.includeItems, payload.expandCustomer
        )

    async def get_production_orders(payload: GetProductionOrdersInput) -> dict[str, Any]:
        return await ds.get_production_orders(
            payload.salesOrder,
            payload.salesOrderItem,
            payload.includeOperations,
            payload.includeHierarchy,
            payload.top,
        )

    async def get_production_order_confirmations(
        payload: GetConfirmationsInput,
    ) -> dict[str, Any]:
        return await ds.get_production_order_confirmations(
            payload.productionOrder, payload.includeReversed, payload.top
        )

    async def get_product_master(payload: GetProductMasterInput) -> dict[str, Any]:
        return await ds.get_product_master(payload.materials)

    async def get_material_stock(payload: GetMaterialStockInput) -> dict[str, Any]:
        return await ds.get_material_stock(
            payload.material, payload.plant, payload.storageLocation, payload.stockType
        )

    return [
        ToolSpec(
            name="get_sales_order",
            description="Retrieve a sales order header and its items.",
            input_model=GetSalesOrderInput,
            handler=get_sales_order,
            sap_api="sap.s4:apiResource:CE_SALESORDER_0001:v1",
        ),
        ToolSpec(
            name="get_production_orders",
            description="Retrieve production orders linked to a sales order.",
            input_model=GetProductionOrdersInput,
            handler=get_production_orders,
            sap_api="sap.s4:apiResource:OP_API_PRODUCTION_ORDER_2_SRV_0001:v1",
        ),
        ToolSpec(
            name="get_production_order_confirmations",
            description="Retrieve confirmations for a production order.",
            input_model=GetConfirmationsInput,
            handler=get_production_order_confirmations,
            sap_api="sap.s4:apiResource:OP_API_PROD_ORDER_CONFIRMATIO_2_SRV_0001:v1",
        ),
        ToolSpec(
            name="get_product_master",
            description="Retrieve product master data for up to 100 materials.",
            input_model=GetProductMasterInput,
            handler=get_product_master,
            sap_api="sap.s4:apiResource:API_PRODUCT_SRV:v1",
        ),
        ToolSpec(
            name="get_material_stock",
            description="Retrieve stock levels for a material at a plant.",
            input_model=GetMaterialStockInput,
            handler=get_material_stock,
            sap_api="sap.s4:apiResource:OP_API_MATERIAL_STOCK_SRV:v1",
        ),
    ]


def error_payload(exc: ToolFailure) -> dict[str, Any]:
    return {
        "code": exc.code,
        "message": str(exc).split(": ", 1)[-1],
        "retryable": exc.retryable,
    }


__all__ = [
    "TOOL_NAMES",
    "GetConfirmationsInput",
    "GetMaterialStockInput",
    "GetProductMasterInput",
    "GetProductionOrdersInput",
    "GetSalesOrderInput",
    "ToolSpec",
    "build_tool_specs",
    "error_payload",
]
