"""MCP server: streamable HTTP, stateless (research D2)."""

from __future__ import annotations

import json
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from ..datasource.protocol import DataSource
from ..domain.errors import ToolFailure

INSTRUCTIONS = (
    "Read-only access to SAP S/4HANA sales order and production order data. "
    "All identifiers are strings with leading zeros preserved. "
    "An empty value array is a valid answer, not an error."
)


def _raise(exc: ToolFailure) -> None:
    raise ToolError(json.dumps(error_payload(exc)))


def error_payload(exc: ToolFailure) -> dict[str, Any]:
    return {
        "code": exc.code,
        "message": str(exc).split(": ", 1)[-1],
        "retryable": exc.retryable,
    }


def create_mcp_server(ds: DataSource) -> MCPServer:
    mcp: MCPServer = MCPServer(
        name="cto-order-tools",
        version="0.1.0",
        instructions=INSTRUCTIONS,
    )

    @mcp.tool()
    async def get_sales_order(
        salesOrder: str, includeItems: bool = True, expandCustomer: bool = True
    ) -> dict[str, Any]:
        """Retrieve a sales order header and its items."""
        try:
            return await ds.get_sales_order(salesOrder, includeItems, expandCustomer)
        except ToolFailure as exc:
            _raise(exc)
            raise

    @mcp.tool()
    async def get_production_orders(
        salesOrder: str,
        salesOrderItem: str | None = None,
        includeOperations: bool = True,
        includeHierarchy: bool = True,
        top: int = 200,
    ) -> dict[str, Any]:
        """Retrieve production orders linked to a sales order."""
        try:
            return await ds.get_production_orders(
                salesOrder, salesOrderItem, includeOperations, includeHierarchy, top
            )
        except ToolFailure as exc:
            _raise(exc)
            raise

    @mcp.tool()
    async def get_production_order_confirmations(
        productionOrder: str, includeReversed: bool = False, top: int = 500
    ) -> dict[str, Any]:
        """Retrieve confirmations for a production order."""
        try:
            return await ds.get_production_order_confirmations(
                productionOrder, includeReversed, top
            )
        except ToolFailure as exc:
            _raise(exc)
            raise

    @mcp.tool()
    async def get_product_master(materials: list[str]) -> dict[str, Any]:
        """Retrieve product master data for up to 100 materials."""
        try:
            return await ds.get_product_master(materials)
        except ToolFailure as exc:
            _raise(exc)
            raise

    @mcp.tool()
    async def get_material_stock(
        material: str,
        plant: str,
        storageLocation: str | None = None,
        stockType: str = "ALL",
    ) -> dict[str, Any]:
        """Retrieve stock levels for a material at a plant."""
        try:
            return await ds.get_material_stock(material, plant, storageLocation, stockType)
        except ToolFailure as exc:
            _raise(exc)
            raise

    return mcp


__all__ = ["INSTRUCTIONS", "create_mcp_server", "error_payload"]
