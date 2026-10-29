"""Turn handling: intent routing, consolidation, gated narrative."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog

from ..config import Settings
from ..datasource.protocol import DataSource
from ..domain.consolidation import AmbiguousOrder, OrderNotFound, build_view, resolve_order
from ..domain.enums import DataCompleteness, Intent, Mode
from ..domain.evidence import build_bundle
from ..domain.models import ConsolidatedOrderView, EvidenceBundle, RiskAssessment
from ..domain.portfolio import scan
from ..domain.recommendations import build_recommendations
from ..domain.risk import evaluate
from ..narrative.composer import Composer
from ..nlu.order_ref import detect_intent, extract_order_ref, ordinal_position
from ..presentation.customer_summary import render_customer_summary
from ..presentation.planner_view import (
    render_ambiguous,
    render_consolidated_view,
    render_exception_list,
    render_not_found,
    render_recommendations,
    render_refusal,
    render_unknown,
)
from .tasks import TaskStore

log = structlog.get_logger(__name__)

ORDER_SCOPED = {
    Intent.ORDER_STATUS,
    Intent.RISK_EXPLANATION,
    Intent.RECOMMENDATION,
    Intent.CUSTOMER_SUMMARY,
}


@dataclass
class AgentTurn:
    message: str
    task_id: str
    context_id: str
    state: str = "TASK_STATE_COMPLETED"
    intent: Intent = Intent.UNKNOWN
    view: ConsolidatedOrderView | None = None
    assessment: RiskAssessment | None = None
    bundle: EvidenceBundle | None = None
    records: dict[str, Any] = field(default_factory=dict)


class AgentExecutor:
    """One turn in, one answer out. No tool call happens outside this class."""

    def __init__(
        self,
        data_source: DataSource,
        settings: Settings,
        composer: Composer | None = None,
        store: TaskStore | None = None,
        clock: datetime | None = None,
    ) -> None:
        self._ds = data_source
        self._settings = settings
        self._composer = composer or Composer(settings)
        self._store = store or TaskStore(
            ttl_seconds=settings.task_ttl_seconds, max_tasks=settings.max_tasks
        )
        self._clock = clock or settings.process_clock

    @property
    def store(self) -> TaskStore:
        return self._store

    def _scope(self) -> Any:
        scope = getattr(self._ds, "request_scope", None)
        return scope() if callable(scope) else contextlib.nullcontext()

    async def handle_turn(self, text: str, context_id: str, task_id: str) -> AgentTurn:
        intent = detect_intent(text)
        ctx = self._store.get_context(context_id)
        reference = extract_order_ref(text)

        if intent is Intent.WRITE_REQUEST:
            return AgentTurn(
                message=render_refusal(),
                task_id=task_id,
                context_id=context_id,
                intent=intent,
            )

        if intent is Intent.PORTFOLIO:
            result = await scan(self._ds, self._clock, self._settings.portfolio_window_days)
            rows = [
                (row.sales_order, row.severity, row.score, row.exception_count)
                for row in result.rows
            ]
            return AgentTurn(
                message=render_exception_list(
                    rows, result.scope, result.window_days, result.as_of.isoformat()
                ),
                task_id=task_id,
                context_id=context_id,
                intent=intent,
                records={"scanned": result.scanned, "at_risk": len(rows)},
            )

        if reference is None:
            reference = ctx.get("order")
        if reference is None:
            return AgentTurn(
                message=render_unknown(),
                task_id=task_id,
                context_id=context_id,
                intent=Intent.UNKNOWN,
            )

        try:
            with self._scope():
                resolved = await resolve_order(self._ds, reference)
                view = await build_view(self._ds, resolved)
        except OrderNotFound:
            return AgentTurn(
                message=render_not_found(reference),
                task_id=task_id,
                context_id=context_id,
                intent=intent,
            )
        except AmbiguousOrder as exc:
            return AgentTurn(
                message=render_ambiguous(reference, exc.candidates),
                task_id=task_id,
                context_id=context_id,
                intent=intent,
            )

        assessment = evaluate(view, self._clock, set(view.sources_unavailable))
        self._store.set_context(
            context_id,
            order=view.sales_order.sales_order,
            orders=[po.production_order for po in view.production_orders],
            at_risk=assessment.is_at_risk,
        )

        position = ordinal_position(text)
        if position and "production order" in text.lower() and view.production_orders:
            subset = view.model_copy(
                update={"production_orders": [view.production_orders[position - 1]]
                        if 0 < position <= len(view.production_orders) else view.production_orders}
            )
            message = render_consolidated_view(subset, evaluation_for(subset, assessment))
            return AgentTurn(
                message=message,
                task_id=task_id,
                context_id=context_id,
                intent=Intent.ORDER_STATUS,
                view=view,
                assessment=assessment,
            )

        if intent is Intent.CUSTOMER_SUMMARY:
            message = render_customer_summary(view, assessment)
        elif intent is Intent.RECOMMENDATION:
            recommendations = build_recommendations(assessment.exceptions)
            message = render_recommendations(assessment, recommendations)
        elif intent is Intent.RISK_EXPLANATION:
            bundle = build_bundle(
                task_id=task_id,
                context_id=context_id,
                mode=Mode.RISK_EXPLANATION,
                view=view,
                assessment=assessment,
                recommendations=build_recommendations(assessment.exceptions),
                clock=self._clock,
            )
            if assessment.data_completeness is DataCompleteness.INSUFFICIENT:
                bundle = bundle.model_copy(update={"inferences": [], "recommendations": []})
            message = await self._composer.compose(bundle)
            return AgentTurn(
                message=message,
                task_id=task_id,
                context_id=context_id,
                intent=Intent.RISK_EXPLANATION,
                view=view,
                assessment=assessment,
                bundle=bundle,
            )
        else:
            message = render_consolidated_view(view, assessment)

        return AgentTurn(
            message=message,
            task_id=task_id,
            context_id=context_id,
            intent=intent,
            view=view,
            assessment=assessment,
        )


def evaluation_for(view: ConsolidatedOrderView, parent: RiskAssessment) -> RiskAssessment:
    """Keep the order-level assessment but restrict display to the selected subtree."""
    selected = [
        e
        for e in parent.exceptions
        if any(po.production_order == e.production_order for po in view.production_orders)
    ]
    return parent.model_copy(
        update={
            "exceptions": selected,
            "is_at_risk": bool(selected),
            "severity": parent.severity if selected else None,
            "score": parent.score if selected else 0,
        }
    )


__all__ = ["AgentExecutor", "AgentTurn"]
