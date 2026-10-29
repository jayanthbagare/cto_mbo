"""Answer-record persistence for replay (FR-027).

Persists the evidence bundle, not the prompt or completion: enough to
reconstruct every claim, without copying customer text into a second store.
"""

from __future__ import annotations

from typing import Any

import structlog

from ..domain.models import EvidenceBundle, RiskAssessment

log = structlog.get_logger("answer_record")


def record_answer(
    *,
    task_id: str,
    context_id: str,
    intent: str,
    message: str,
    bundle: EvidenceBundle | None = None,
    assessment: RiskAssessment | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "taskId": task_id,
        "contextId": context_id,
        "intent": intent,
        "answerLength": len(message),
        "asOf": bundle.as_of.isoformat() if bundle else None,
        "dataCompleteness": bundle.data_completeness.value if bundle else None,
        "sourcesConsulted": bundle.sources_consulted if bundle else [],
        "sourcesUnavailable": bundle.sources_unavailable if bundle else [],
        "facts": [fact.model_dump(mode="json") for fact in (bundle.facts if bundle else [])],
        "inferences": (
            [inf.model_dump(mode="json") for inf in bundle.inferences] if bundle else []
        ),
        "exceptions": (
            [exc.exception_id for exc in assessment.exceptions] if assessment else []
        ),
    }
    log.info("answer_record", **record)
    return record


def replay_facts(record: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """Recover (entity, key, field, value) tuples from a stored record."""
    return [
        (
            fact["source_entity"],
            fact["source_key"],
            fact["source_field"],
            fact["value"],
        )
        for fact in record.get("facts", [])
    ]


__all__ = ["record_answer", "replay_facts"]
