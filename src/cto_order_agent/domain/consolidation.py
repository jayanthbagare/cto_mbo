"""Assemble the unified order view (FR-001 to FR-010)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from ..datasource.protocol import DataSource
from .errors import AgentError, ToolFailure
from .models import (
    ConsolidatedOrderView,
    Material,
    MaterialAvailability,
    ProductionConfirmation,
    ProductionOperation,
    ProductionOrder,
    SalesOrder,
)

MAX_IN_FLIGHT = 8


class OrderNotFound(AgentError):
    def __init__(self, reference: str) -> None:
        self.reference = reference
        super().__init__(f"sales order {reference} was not found")


class AmbiguousOrder(AgentError):
    def __init__(self, reference: str, candidates: list[str]) -> None:
        self.reference = reference
        self.candidates = candidates
        super().__init__(f"{len(candidates)} orders match {reference}")


def _iso(value: Any) -> datetime:

    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


async def resolve_order(ds: DataSource, reference: str) -> str:
    """Resolve a possibly partial reference to exactly one order number."""
    ref = reference.strip()
    if len(ref) == 10 and ref.isdigit():
        try:
            await ds.get_sales_order(ref, include_items=False)
            return ref
        except ToolFailure as exc:
            if exc.code != "NOT_FOUND":
                raise
    candidates = sorted(await ds.list_order_refs(3650))
    matches = [c for c in candidates if ref in c] if ref.isdigit() else []
    if not matches:
        raise OrderNotFound(reference)
    if len(matches) > 1:
        raise AmbiguousOrder(reference, matches)
    return matches[0]


async def build_view(ds: DataSource, sales_order: str) -> ConsolidatedOrderView:
    consulted: list[str] = ["get_sales_order"]
    unavailable: list[str] = []
    as_of_candidates: list[datetime] = []

    order_env = await ds.get_sales_order(sales_order)
    as_of_candidates.append(_iso(order_env["asOf"]))
    order = SalesOrder.model_validate(order_env["value"][0])

    tree = await _safe(
        ds,
        "get_production_orders",
        unavailable,
        lambda: ds.get_production_orders(sales_order),
    )
    production_orders: list[ProductionOrder] = []
    operations: list[ProductionOperation] = []
    if tree is not None:
        consulted.append("get_production_orders")
        as_of_candidates.append(_iso(tree["asOf"]))
        for raw in tree["value"]:
            record = dict(raw)
            raw_ops = record.pop("operations", []) or []
            production_orders.append(ProductionOrder.model_validate(record))
            operations.extend(ProductionOperation.model_validate(op) for op in raw_ops)

    confirmations = await _load_confirmations(
        ds, production_orders, consulted, unavailable, as_of_candidates
    )

    materials, availability = await _load_materials(
        ds, order, production_orders, sales_order, unavailable, as_of_candidates
    )
    if materials:
        consulted.append("get_product_master")
    if production_orders and (
        availability or "get_material_stock" not in unavailable
    ):
        consulted.append("get_material_stock")

    as_of = min(as_of_candidates) if as_of_candidates else _iso(order_env["asOf"])

    if "get_material_stock" in unavailable:
        consulted = [c for c in consulted if c != "get_material_stock"]

    return ConsolidatedOrderView(
        sales_order=order,
        production_orders=production_orders,
        operations=operations,
        confirmations=confirmations,
        materials=materials,
        availability=availability,
        as_of=as_of,
        sources_consulted=sorted(set(consulted)),
        sources_unavailable=sorted(set(unavailable)),
    )


async def _safe(
    ds: DataSource,
    tool: str,
    unavailable: list[str],
    call: Callable[[], Awaitable[dict[str, Any]]],
) -> dict[str, Any] | None:
    try:
        return await call()
    except ToolFailure as exc:
        if exc.code == "NOT_FOUND":
            raise
        unavailable.append(tool)
        return None


async def _load_confirmations(
    ds: DataSource,
    orders: list[ProductionOrder],
    consulted: list[str],
    unavailable: list[str],
    as_of_candidates: list[datetime],
) -> list[ProductionConfirmation]:
    if not orders:
        return []
    if "get_production_order_confirmations" in unavailable:
        return []

    semaphore = asyncio.Semaphore(MAX_IN_FLIGHT)

    async def one(po: ProductionOrder) -> dict[str, Any] | None:
        async with semaphore:
            return await _safe(
                ds,
                "get_production_order_confirmations",
                unavailable,
                lambda: ds.get_production_order_confirmations(po.production_order),
            )

    results = await asyncio.gather(*(one(po) for po in orders))
    collected: list[ProductionConfirmation] = []
    for env in results:
        if env is None:
            continue
        as_of_candidates.append(_iso(env["asOf"]))
        collected.extend(ProductionConfirmation.model_validate(r) for r in env["value"])
    if results and all(r is not None for r in results):
        consulted.append("get_production_order_confirmations")
    return collected


async def _load_materials(
    ds: DataSource,
    order: SalesOrder,
    orders: list[ProductionOrder],
    sales_order: str,
    unavailable: list[str],
    as_of_candidates: list[datetime],
) -> tuple[list[Material], list[MaterialAvailability]]:
    names = sorted({i.material for i in order.items} | {o.material for o in orders})
    if not names:
        return [], []

    master = await _safe(
        ds, "get_product_master", unavailable, lambda: ds.get_product_master(names)
    )
    materials: list[Material] = []
    if master is not None:
        as_of_candidates.append(_iso(master["asOf"]))
        materials = [Material.model_validate(r) for r in master["value"]]

    if "get_material_stock" in unavailable:
        return materials, []

    plants: dict[str, set[str]] = {}
    for item in order.items:
        plants.setdefault(item.material, set()).add(item.plant)
    for po in orders:
        plants.setdefault(po.material, set()).add(po.plant)

    pairs = sorted({(material, plant) for material, pl in plants.items() for plant in pl})
    semaphore = asyncio.Semaphore(MAX_IN_FLIGHT)

    async def one(material: str, plant: str) -> dict[str, Any] | None:
        async with semaphore:
            return await _safe(
                ds,
                "get_material_stock",
                unavailable,
                lambda: ds.get_material_stock(material, plant),
            )

    results = await asyncio.gather(*(one(m, p) for m, p in pairs)) if pairs else []
    availability: list[MaterialAvailability] = []
    for env in results:
        if env is None:
            continue
        as_of_candidates.append(_iso(env["asOf"]))
        availability.extend(MaterialAvailability.model_validate(r) for r in env["value"])
    return materials, availability


def total_open_quantity(order: SalesOrder, material: str) -> Decimal:
    return sum(
        (i.requested_quantity for i in order.items if i.material == material), Decimal("0")
    )


__all__ = ["AmbiguousOrder", "OrderNotFound", "build_view", "resolve_order"]
