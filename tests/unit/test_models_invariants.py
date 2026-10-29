from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cto_order_agent.domain.enums import DataCompleteness, Severity
from cto_order_agent.domain.errors import InvariantError
from cto_order_agent.domain.models import RiskAssessment

CLOCK = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)


@pytest.mark.unit
def test_at_risk_requires_exceptions() -> None:
    with pytest.raises(InvariantError):
        RiskAssessment(
            sales_order="0000012345",
            is_at_risk=True,
            exceptions=[],
            evaluated_at=CLOCK,
        )


@pytest.mark.unit
def test_at_risk_is_true_iff_exceptions_present() -> None:
    assessment = RiskAssessment(sales_order="0000012345", evaluated_at=CLOCK)
    assert assessment.is_at_risk is False
    assert assessment.exceptions == []


@pytest.mark.unit
def test_incomplete_assessment_must_name_missing_evidence() -> None:
    with pytest.raises(InvariantError):
        RiskAssessment(
            sales_order="0000012345",
            evaluated_at=CLOCK,
            data_completeness=DataCompleteness.PARTIAL,
            missing_evidence=[],
        )


@pytest.mark.unit
def test_severity_values_are_ordered_vocabulary() -> None:
    assert [s.value for s in Severity] == ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
