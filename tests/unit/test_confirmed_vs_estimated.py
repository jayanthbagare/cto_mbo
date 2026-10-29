from __future__ import annotations

from datetime import UTC, datetime

import pytest
from tests.conftest import NO_ORDERS, ON_TRACK, PARTIAL_ON_TIME

from cto_order_agent.domain.consolidation import build_view
from cto_order_agent.domain.risk import evaluate
from cto_order_agent.presentation.customer_summary import render_customer_summary

CLOCK = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)


async def _summary(ds, order: str) -> str:
    view = await build_view(ds, order)
    assessment = evaluate(view, CLOCK, set(view.sources_unavailable))
    return render_customer_summary(view, assessment)


@pytest.mark.unit
async def test_confirmed_date_is_commitment_language(ds) -> None:
    summary = await _summary(ds, ON_TRACK)
    assert "confirmed to finish" in summary
    assert "estimate and not" not in summary


@pytest.mark.unit
async def test_no_confirmed_date_is_estimate_language(ds) -> None:
    summary = await _summary(ds, NO_ORDERS)
    assert "estimate" in summary
    assert "confirmed to finish" not in summary


@pytest.mark.unit
async def test_partial_confirmation_never_reads_as_complete(ds) -> None:
    summary = await _summary(ds, PARTIAL_ON_TIME)
    assert "complete" not in summary.lower()
