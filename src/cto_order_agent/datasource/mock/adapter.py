"""Fixture adapter: the v1 default data source.

Loads the committed synthetic corpus, validates referential integrity at
startup (fail fast, not at question time), and serves tool-shaped reads.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from ...domain.errors import FixtureIntegrityError, ToolFailure
from ...domain.models import (
    Customer,
    Material,
    MaterialAvailability,
    ProductionConfirmation,
    ProductionOperation,
    ProductionOrder,
    SalesOrder,
)
from ..protocol import SOURCE_SYNTHETIC, envelope

SYNTHETIC_HEADER = "synthetic-fixture"

T = TypeVar("T")


class Dataset:
    """Merged, indexed corpus. All 12 scenarios live in one namespace."""

    def __init__(self) -> None:
        self.sales_orders: dict[str, SalesOrder] = {}
        self.production_orders: dict[str, ProductionOrder] = {}
        self.operations: dict[str, list[ProductionOperation]] = {}
        self.confirmations: dict[str, list[ProductionConfirmation]] = {}
        self.materials: dict[str, Material] = {}
        self.availability: dict[tuple[str, str], list[MaterialAvailability]] = {}
        self.customers: dict[str, Customer] = {}
        self.unavailable: dict[str, set[str]] = {}
        self.unavailable_materials: set[str] = set()
        self.unavailable_products: set[str] = set()
        self.as_of = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)

    def sales_orders_for(self, ref: str) -> list[SalesOrder]:
        return [o for key, o in self.sales_orders.items() if key.endswith(ref) and len(ref) >= 4]

    def children_of(self, parent: str) -> list[ProductionOrder]:
        return [p for p in self.production_orders.values() if p.parent_production_order == parent]

    def orders_for_sales_order(self, so: str, item: str | None = None) -> list[ProductionOrder]:
        roots = [
            p
            for p in self.production_orders.values()
            if p.sales_order == so and (item is None or p.sales_order_item == item)
        ]
        collected: dict[str, ProductionOrder] = {p.production_order: p for p in roots}
        frontier = list(collected)
        while frontier:
            current = frontier.pop()
            for child in self.children_of(current):
                if child.production_order not in collected:
                    collected[child.production_order] = child
                    frontier.append(child.production_order)
        return sorted(collected.values(), key=lambda p: (p.hierarchy_level, p.production_order))


def _read_documents(fixtures_dir: Path) -> Iterator[dict[str, Any]]:
    files = sorted(fixtures_dir.glob("*.json"))
    if not files:
        raise FixtureIntegrityError(f"no fixtures found in {fixtures_dir}")
    for path in files:
        if path.name.endswith(".expected.json"):
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        meta = doc.get("_meta", {})
        if meta.get("synthetic") is not True:
            raise FixtureIntegrityError(f"{path.name}: missing synthetic fixture header")
        yield doc


def load_dataset(fixtures_dir: str | Path) -> Dataset:
    ds = Dataset()
    directory = Path(fixtures_dir)
    for doc in _read_documents(directory):
        for rec in doc.get("customers", []):
            customer = Customer.model_validate(rec)
            ds.customers[customer.customer_id] = customer
        for rec in doc.get("materials", []):
            material = Material.model_validate(rec)
            ds.materials[material.material] = material
        for rec in doc.get("availability", []):
            avail = MaterialAvailability.model_validate(rec)
            ds.availability[(avail.material, avail.plant)] = [avail]
        for rec in doc.get("salesOrders", []):
            order = SalesOrder.model_validate(rec)
            if order.sales_order in ds.sales_orders:
                raise FixtureIntegrityError(f"duplicate sales order {order.sales_order}")
            ds.sales_orders[order.sales_order] = order
            if order.customer_id not in ds.customers:
                raise FixtureIntegrityError(
                    f"sales order {order.sales_order}: unknown customer {order.customer_id}"
                )
            for item in order.items:
                if item.material not in ds.materials:
                    raise FixtureIntegrityError(
                        f"sales order {order.sales_order} item {item.item_number}: "
                        f"unknown material {item.material}"
                    )
            ds.unavailable[order.sales_order] = set(doc.get("unavailableTools", []))
        ds.unavailable_materials.update(doc.get("unavailableMaterials", []))
        ds.unavailable_products.update(doc.get("unavailableProducts", []))
        for rec in doc.get("productionOrders", []):
            po = ProductionOrder.model_validate(rec)
            ds.production_orders[po.production_order] = po
        for rec in doc.get("operations", []):
            op = ProductionOperation.model_validate(rec)
            ds.operations.setdefault(op.production_order, []).append(op)
        for rec in doc.get("confirmations", []):
            conf = ProductionConfirmation.model_validate(rec)
            ds.confirmations.setdefault(conf.production_order, []).append(conf)

    _validate(ds)
    ds.as_of = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
    return ds


def _validate(ds: Dataset) -> None:
    for po in ds.production_orders.values():
        if po.parent_production_order and po.parent_production_order not in ds.production_orders:
            raise FixtureIntegrityError(
                f"production order {po.production_order}: unknown parent "
                f"{po.parent_production_order}"
            )
        if po.sales_order is not None:
            order = ds.sales_orders.get(po.sales_order)
            if order is None:
                raise FixtureIntegrityError(
                    f"production order {po.production_order}: orphan sales order {po.sales_order}"
                )
            if po.sales_order_item and order.item(po.sales_order_item) is None:
                raise FixtureIntegrityError(
                    f"production order {po.production_order}: orphan sales order item "
                    f"{po.sales_order}/{po.sales_order_item}"
                )
            item = order.item(po.sales_order_item or "")
            if item and item.quantity_unit != po.quantity_unit:
                raise FixtureIntegrityError(
                    f"production order {po.production_order}: unit {po.quantity_unit} "
                    f"does not match item unit {item.quantity_unit}"
                )
        if po.material not in ds.materials:
            raise FixtureIntegrityError(
                f"production order {po.production_order}: unknown material {po.material}"
            )
    for po_id in ds.operations:
        if po_id not in ds.production_orders:
            raise FixtureIntegrityError(f"operations reference unknown order {po_id}")
    for po_id, _confs in ds.confirmations.items():
        if po_id not in ds.production_orders:
            raise FixtureIntegrityError(f"confirmation references unknown order {po_id}")


class MockDataSource:
    """Read-only fixture adapter. Never mutates the dataset."""

    def __init__(self, dataset: Dataset) -> None:
        self._ds = dataset
        self._cache: dict[tuple[str, str], Any] = {}
        self._caching = False

    @classmethod
    def from_dir(cls, fixtures_dir: str | Path) -> MockDataSource:
        return cls(load_dataset(fixtures_dir))

    @contextlib.contextmanager
    def request_scope(self) -> Iterator[None]:
        """Request-scoped deduplicating cache (research D8)."""
        self._cache = {}
        self._caching = True
        try:
            yield
        finally:
            self._cache = {}
            self._caching = False

    def _memo(self, key: tuple[str, str], factory: Callable[[], T]) -> T:
        if not self._caching:
            return factory()
        if key not in self._cache:
            self._cache[key] = factory()
        return self._cache[key]  # type: ignore[no-any-return]

    def _guard(self, sales_order: str, tool: str) -> None:
        if tool in self._ds.unavailable.get(sales_order, set()):
            raise ToolFailure("UNAVAILABLE", f"{tool} is unavailable for this order", True)

    def _as_of(self) -> datetime:
        return self._ds.as_of

    async def get_sales_order(
        self,
        sales_order: str,
        include_items: bool = True,
        expand_customer: bool = True,
    ) -> dict[str, Any]:
        self._guard(sales_order, "get_sales_order")
        order = self._ds.sales_orders.get(sales_order)
        if order is None:
            raise ToolFailure("NOT_FOUND", f"sales order {sales_order} not found")
        record = order.model_dump(mode="json")
        if not include_items:
            record.pop("items", None)
        return envelope([record], self._as_of(), SOURCE_SYNTHETIC)

    async def get_production_orders(
        self,
        sales_order: str,
        sales_order_item: str | None = None,
        include_operations: bool = True,
        include_hierarchy: bool = True,
        top: int = 200,
    ) -> dict[str, Any]:
        self._guard(sales_order, "get_production_orders")
        if sales_order not in self._ds.sales_orders:
            raise ToolFailure("NOT_FOUND", f"sales order {sales_order} not found")

        def build() -> dict[str, Any]:
            orders = self._ds.orders_for_sales_order(sales_order, sales_order_item)
            if not include_hierarchy:
                orders = [o for o in orders if o.parent_production_order is None]
            truncated = len(orders) > top
            orders = orders[:top]
            records = []
            for po in orders:
                rec = po.model_dump(mode="json")
                if include_operations:
                    ops = self._ds.operations.get(po.production_order, [])
                    rec["operations"] = [op.model_dump(mode="json") for op in ops]
                records.append(rec)
            return envelope(records, self._as_of(), SOURCE_SYNTHETIC, truncated)

        return self._memo(("get_production_orders", f"{sales_order}|{sales_order_item}"), build)

    async def get_production_order_confirmations(
        self,
        production_order: str,
        include_reversed: bool = False,
        top: int = 500,
    ) -> dict[str, Any]:
        if production_order not in self._ds.production_orders:
            raise ToolFailure("NOT_FOUND", f"production order {production_order} not found")

        def build() -> dict[str, Any]:
            confs = self._ds.confirmations.get(production_order, [])
            if not include_reversed:
                confs = [c for c in confs if not c.is_reversed]
            records = [c.model_dump(mode="json") for c in confs[:top]]
            return envelope(records, self._as_of(), SOURCE_SYNTHETIC, len(confs) > top)

        return self._memo(("get_production_order_confirmations", production_order), build)

    async def get_product_master(self, materials: list[str]) -> dict[str, Any]:
        blocked = self._ds.unavailable_products.intersection(materials)
        if blocked:
            raise ToolFailure(
                "UNAVAILABLE",
                f"product master is unavailable for {sorted(blocked)[0]}",
                True,
            )

        def build() -> dict[str, Any]:
            found, missing = [], []
            for name in materials:
                material = self._ds.materials.get(name)
                if material is None:
                    missing.append(name)
                else:
                    found.append(material.model_dump(mode="json"))
            return envelope(found, self._as_of(), SOURCE_SYNTHETIC, missing=missing)

        return self._memo(("get_product_master", "|".join(sorted(materials))), build)

    async def get_material_stock(
        self,
        material: str,
        plant: str,
        storage_location: str | None = None,
        stock_type: str = "ALL",
    ) -> dict[str, Any]:
        if material in self._ds.unavailable_materials:
            raise ToolFailure(
                "UNAVAILABLE", f"material stock service is unavailable for {material}", True
            )

        def build() -> dict[str, Any]:
            rows = self._ds.availability.get((material, plant), [])
            if storage_location:
                rows = [r for r in rows if r.storage_location == storage_location]
            records = [r.model_dump(mode="json") for r in rows]
            return envelope(records, self._as_of(), SOURCE_SYNTHETIC)

        return self._memo(("get_material_stock", f"{material}|{plant}"), build)

    async def list_order_refs(self, window_days: int) -> list[str]:
        return sorted(self._ds.sales_orders)


__all__ = ["Dataset", "MockDataSource", "SYNTHETIC_HEADER", "load_dataset"]
