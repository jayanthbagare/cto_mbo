from __future__ import annotations

from decimal import Decimal

import pytest
from tests.conftest import MULTILEVEL, NO_ORDERS, ON_TRACK

from cto_order_agent.domain.consolidation import (
    AmbiguousOrder,
    OrderNotFound,
    build_view,
    resolve_order,
)


@pytest.mark.unit
async def test_links_items_to_production_orders(ds, ) -> None:
    view = await build_view(ds, ON_TRACK)
    assert view.sales_order.sales_order == ON_TRACK
    assert len(view.sales_order.items) == 2
    assert len(view.production_orders) == 3
    assert [po.production_order for po in view.orders_for_item("000010")] == ["1000001"]


@pytest.mark.unit
async def test_multilevel_hierarchy_is_preserved(ds) -> None:
    view = await build_view(ds, MULTILEVEL)
    assert len(view.production_orders) == 3
    by_id = {po.production_order: po for po in view.production_orders}
    assert by_id["1000011"].parent_production_order == "1000010"
    assert by_id["1000012"].hierarchy_level == 2


@pytest.mark.unit
async def test_materials_are_deduplicated(ds) -> None:
    view = await build_view(ds, ON_TRACK)
    names = [m.material for m in view.materials]
    assert len(names) == len(set(names))
    assert "MTO-1000-B" in names


@pytest.mark.unit
async def test_order_without_production_orders_is_a_finding(ds) -> None:
    view = await build_view(ds, NO_ORDERS)
    assert view.production_orders == []
    assert view.sales_order.sales_order == NO_ORDERS


@pytest.mark.unit
async def test_missing_order_raises(ds) -> None:
    with pytest.raises(OrderNotFound):
        await resolve_order(ds, "0000099999")


@pytest.mark.unit
async def test_ambiguous_prefix_lists_candidates(ds) -> None:
    with pytest.raises(AmbiguousOrder) as excinfo:
        await resolve_order(ds, "1234")
    assert len(excinfo.value.candidates) > 1


@pytest.mark.unit
async def test_available_stock_uses_unrestricted_only(ds) -> None:
    view = await build_view(ds, ON_TRACK)
    assert view.available_for("MTO-1000-A", "1010") == Decimal("1000")
