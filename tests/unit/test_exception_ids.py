from __future__ import annotations

from datetime import UTC, datetime

import pytest
from tests.conftest import DELAYED, INCONSISTENT

from cto_order_agent.domain.consolidation import build_view
from cto_order_agent.domain.risk import evaluate


@pytest.mark.unit
@pytest.mark.parametrize("order", [DELAYED, INCONSISTENT])
async def test_exception_ids_are_deterministic(ds, order: str) -> None:
    clock = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
    first = await build_view(ds, order)
    second = await build_view(ds, order)
    ids_first = [e.exception_id for e in evaluate(first, clock, set()).exceptions]
    ids_second = [e.exception_id for e in evaluate(second, clock, set()).exceptions]
    assert ids_first == ids_second
    assert ids_first


@pytest.mark.unit
async def test_exception_id_shape(ds) -> None:
    clock = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
    view = await build_view(ds, DELAYED)
    for exception in evaluate(view, clock, set()).exceptions:
        category, production_order, discriminator = exception.exception_id.split(":")
        assert category == exception.category.value
        assert production_order == exception.production_order
        assert discriminator
