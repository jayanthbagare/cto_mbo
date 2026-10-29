"""Live adapter. Same five tool shapes, no behavioral difference (FR-026)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import httpx

from ...config import Settings
from ...domain.errors import ToolFailure
from ..protocol import SOURCE_SAP, envelope
from .mapping import (
    map_confirmation,
    map_material_stock,
    map_product,
    map_production_order,
    map_sales_order,
)

TIMEOUT_SECONDS = 5.0

PATHS = {
    "sales_order": "/sap/opu/odata/sap/API_SALES_ORDER_SRV/A_SalesOrder",
    "production_order": "/sap/opu/odata/sap/API_PRODUCTION_ORDER_2_SRV/A_ProductionOrder",
    "confirmation": (
        "/sap/opu/odata/sap/API_PROD_ORDER_CONFIRMATION_2_SRV/A_ProductionOrderConfirmation"
    ),
    "product": "/sap/opu/odata/sap/API_PRODUCT_SRV/A_Product",
    "stock": "/sap/opu/odata/sap/API_MATERIAL_STOCK_SRV/A_MatlStkInAcctMod",
}


def _now() -> datetime:
    return datetime.now(UTC)


class ODataDataSource:
    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
        base_url: str | None = None,
    ) -> None:
        self._settings = settings
        self._base = (base_url or os.environ.get("S4_BASE_URL", "")).rstrip("/")
        self._client = client

    def _auth_headers(self) -> dict[str, str]:
        if not self._settings.ai_core_client_secret:
            return {}
        return {"authorization": f"Bearer {self._settings.ai_core_client_secret}"}

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self._base:
            raise ToolFailure("UNAVAILABLE", "S/4HANA destination is not configured", True)
        try:
            if self._client is not None:
                response = await self._client.get(
                    f"{self._base}{path}", params=params, headers=self._auth_headers()
                )
            else:
                async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                    response = await client.get(
                        f"{self._base}{path}", params=params, headers=self._auth_headers()
                    )
        except httpx.TimeoutException as exc:
            raise ToolFailure("TIMEOUT", "S/4HANA call timed out", True) from exc
        except httpx.HTTPError as exc:
            raise ToolFailure("UNAVAILABLE", "S/4HANA is unreachable", True) from exc

        if response.status_code == 404:
            raise ToolFailure("NOT_FOUND", "record not found in S/4HANA")
        if response.status_code in (401, 403):
            raise ToolFailure("UNAVAILABLE", "S/4HANA authorization failed", False)
        if response.status_code >= 500:
            raise ToolFailure("UPSTREAM_ERROR", "S/4HANA returned a fault")
        if response.status_code >= 400:
            raise ToolFailure("INVALID_ARGUMENT", "S/4HANA rejected the request")
        return dict(response.json())

    @staticmethod
    def _results(payload: dict[str, Any]) -> list[dict[str, Any]]:
        body = payload.get("d", payload)
        if isinstance(body, dict) and "results" in body:
            return list(body["results"])
        if isinstance(body, dict) and "value" in body:
            return list(body["value"])
        return [body] if body else []

    async def get_sales_order(
        self, sales_order: str, include_items: bool = True, expand_customer: bool = True
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"$format": "json"}
        if include_items:
            params["$expand"] = "to_Item"
        payload = await self._get(f"{PATHS['sales_order']}('{sales_order}')", params)
        records = [map_sales_order(r) for r in self._results(payload)]
        if not records:
            raise ToolFailure("NOT_FOUND", f"sales order {sales_order} not found")
        return envelope(records, _now(), SOURCE_SAP)

    async def get_production_orders(
        self,
        sales_order: str,
        sales_order_item: str | None = None,
        include_operations: bool = True,
        include_hierarchy: bool = True,
        top: int = 200,
    ) -> dict[str, Any]:
        filters = [f"SalesOrder eq '{sales_order}'"]
        if sales_order_item:
            filters.append(f"SalesOrderItem eq '{sales_order_item}'")
        params: dict[str, Any] = {
            "$format": "json",
            "$filter": " and ".join(filters),
            "$top": str(min(top, 500)),
        }
        if include_operations:
            params["$expand"] = "to_Operation"
        payload = await self._get(PATHS["production_order"], params)
        records = [map_production_order(r) for r in self._results(payload)]
        return envelope(records, _now(), SOURCE_SAP, len(records) >= top)

    async def get_production_order_confirmations(
        self, production_order: str, include_reversed: bool = False, top: int = 500
    ) -> dict[str, Any]:
        filters = [f"OrderID eq '{production_order}'"]
        if not include_reversed:
            filters.append("IsReversed eq false")
        payload = await self._get(
            PATHS["confirmation"],
            {"$format": "json", "$filter": " and ".join(filters), "$top": str(top)},
        )
        records = [map_confirmation(r) for r in self._results(payload)]
        return envelope(records, _now(), SOURCE_SAP)

    async def get_product_master(self, materials: list[str]) -> dict[str, Any]:
        query = " or ".join(f"Product eq '{m}'" for m in materials)
        payload = await self._get(
            PATHS["product"], {"$format": "json", "$filter": query, "$top": "100"}
        )
        records = [map_product(r) for r in self._results(payload)]
        found = {r["material"] for r in records}
        missing = [m for m in materials if m not in found]
        return envelope(records, _now(), SOURCE_SAP, missing=missing)

    async def get_material_stock(
        self,
        material: str,
        plant: str,
        storage_location: str | None = None,
        stock_type: str = "ALL",
    ) -> dict[str, Any]:
        filters = [f"Material eq '{material}'", f"Plant eq '{plant}'"]
        if storage_location:
            filters.append(f"StorageLocation eq '{storage_location}'")
        if stock_type != "ALL":
            filters.append(f"MaterialStockType eq '{stock_type}'")
        as_of = _now().isoformat().replace("+00:00", "Z")
        payload = await self._get(
            PATHS["stock"], {"$format": "json", "$filter": " and ".join(filters)}
        )
        records = [map_material_stock(r, as_of) for r in self._results(payload)]
        return envelope(records, _now(), SOURCE_SAP)

    async def list_order_refs(self, window_days: int) -> list[str]:
        payload = await self._get(
            PATHS["sales_order"],
            {
                "$format": "json",
                "$select": "SalesOrder",
                "$filter": "OverallSDProcessStatus ne 'C'",
                "$top": "5000",
            },
        )
        return sorted({r["SalesOrder"] for r in self._results(payload)})


__all__ = ["ODataDataSource", "PATHS", "TIMEOUT_SECONDS"]
