from __future__ import annotations

from datetime import UTC, datetime

import pytest
from tests.conftest import ON_TRACK

from cto_order_agent.domain.consolidation import build_view

FROZEN = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)


@pytest.mark.unit
async def test_as_of_is_the_oldest_source_read(ds) -> None:
    view = await build_view(ds, ON_TRACK)
    assert view.as_of == FROZEN


@pytest.mark.unit
async def test_sources_consulted_are_disclosed(ds) -> None:
    view = await build_view(ds, ON_TRACK)
    assert "get_sales_order" in view.sources_consulted
    assert "get_production_order_confirmations" in view.sources_consulted
    assert view.sources_unavailable == []


@pytest.mark.unit
async def test_partial_source_is_disclosed(ds) -> None:
    from tests.conftest import DATA_GAP

    view = await build_view(ds, DATA_GAP)
    assert "get_material_stock" in view.sources_unavailable
