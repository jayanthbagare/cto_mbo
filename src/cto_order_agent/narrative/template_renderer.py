"""Deterministic narrative. The guaranteed fallback when grounding fails.

This renderer must satisfy the same acceptance tests as the model path, so a
model outage degrades tone, never correctness (FR-024).
"""

from __future__ import annotations

from ..domain.enums import Mode
from ..domain.models import EvidenceBundle


def _facts_block(bundle: EvidenceBundle) -> list[str]:
    if not bundle.facts:
        return []
    lines = ["Confirmed facts:"]
    for fact in bundle.facts:
        lines.append(f"- {fact.fact_id} (confirmed fact): {fact.statement}")
    return lines


def _inference_block(bundle: EvidenceBundle) -> list[str]:
    if not bundle.inferences:
        return []
    lines = ["Inferred risks:"]
    for inference in bundle.inferences:
        lines.append(
            f"- {inference.inference_id} (inferred risk, confidence "
            f"{inference.confidence.value.lower()}): {inference.statement}"
        )
    return lines


def _recommendation_block(bundle: EvidenceBundle) -> list[str]:
    if not bundle.recommendations:
        return []
    lines = ["Recommended actions:"]
    for rec in bundle.recommendations:
        lines.append(
            f"- {rec.recommendation_id} [{rec.urgency.value}] ({rec.owner_role.value}): "
            f"{rec.action}. Resolved when: {rec.resolution_evidence}."
        )
    return lines


def render(bundle: EvidenceBundle) -> str:
    lines: list[str] = []

    if bundle.mode is Mode.CUSTOMER_SUMMARY:
        lines.append("Order status update")
    elif bundle.mode is Mode.PORTFOLIO:
        lines.append("Orders needing attention")
    else:
        lines.append("Order assessment")

    if bundle.data_completeness.value != "COMPLETE":
        lines.append(
            "Data is incomplete. Missing evidence: " + "; ".join(bundle.missing_evidence)
        )

    lines.extend(_facts_block(bundle))
    lines.extend(_inference_block(bundle))
    lines.extend(_recommendation_block(bundle))

    lines.append(f"As of {bundle.as_of.isoformat()}.")
    if bundle.sources_consulted:
        lines.append("Sources consulted: " + ", ".join(bundle.sources_consulted) + ".")
    if bundle.sources_unavailable:
        lines.append("Sources unavailable: " + ", ".join(bundle.sources_unavailable) + ".")
    return "\n".join(lines)


__all__ = ["render"]
