"""The single swap seam (FR-026).

Nothing above this module may inspect the provenance of the data. A static gate
in CI rejects any `source ==` comparison under `src/`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

SOURCE_SAP = "SAP_S4HANA"
SOURCE_SYNTHETIC = "SYNTHETIC"


def envelope(
    records: list[dict[str, Any]],
    as_of: datetime,
    source: str,
    truncated: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    """OData-v4-shaped result. The live adapter passes `{"value": [...]}` through."""
    payload: dict[str, Any] = {
        "value": records,
        "asOf": as_of.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "count": len(records),
        "source": source,
        "truncated": truncated,
    }
    payload.update(extra)
    return payload


@runtime_checkable
class DataSource(Protocol):
    """Five tool-shaped reads plus one internal enumeration used for portfolios."""

    async def get_sales_order(
        self,
        sales_order: str,
        include_items: bool = True,
        expand_customer: bool = True,
    ) -> dict[str, Any]: ...

    async def get_production_orders(
        self,
        sales_order: str,
        sales_order_item: str | None = None,
        include_operations: bool = True,
        include_hierarchy: bool = True,
        top: int = 200,
    ) -> dict[str, Any]: ...

    async def get_production_order_confirmations(
        self,
        production_order: str,
        include_reversed: bool = False,
        top: int = 500,
    ) -> dict[str, Any]: ...

    async def get_product_master(self, materials: list[str]) -> dict[str, Any]: ...

    async def get_material_stock(
        self,
        material: str,
        plant: str,
        storage_location: str | None = None,
        stock_type: str = "ALL",
    ) -> dict[str, Any]: ...

    async def list_order_refs(self, window_days: int) -> list[str]:
        """Open order numbers inside the portfolio window.

        Not an MCP tool: it is the enumeration every ERP provides for a list
        query, kept on the port so the live adapter can implement it with the
        same filter semantics.
        """
        ...


__all__ = ["SOURCE_SAP", "SOURCE_SYNTHETIC", "DataSource", "envelope"]
