"""Canonical, source-agnostic entities (data-model.md)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from .enums import (
    Confidence,
    DataCompleteness,
    ExceptionCategory,
    ItemStatus,
    Mode,
    OrderStatus,
    OwnerRole,
    ProductionOrderStatus,
    Severity,
    StockType,
)
from .errors import InvariantError, UngroundedFactError


class Entity(BaseModel):
    """Strict base: unknown fields are a defect, not a nicety."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )


# --------------------------------------------------------------------------- #
# Master data
# --------------------------------------------------------------------------- #


class Customer(Entity):
    customer_id: str = Field(pattern=r"^[0-9]{10}$")
    name: str = Field(min_length=1, max_length=80)
    country: str | None = Field(default=None, max_length=3)
    is_internal: bool = False


class Material(Entity):
    material: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=40)
    material_type: str = Field(default="FERT", max_length=4)
    base_unit: str = Field(min_length=1, max_length=3)
    product_group: str | None = Field(default=None, max_length=9)
    is_batch_managed: bool = False


class MaterialAvailability(Entity):
    material: str
    plant: str = Field(min_length=1, max_length=4)
    storage_location: str | None = Field(default=None, max_length=4)
    unrestricted_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    unit: str = Field(min_length=1, max_length=3)
    stock_type: StockType = StockType.UNRESTRICTED
    as_of: datetime

    @property
    def counted(self) -> bool:
        """Only unrestricted stock counts toward availability (data-model rule)."""
        return self.stock_type is StockType.UNRESTRICTED


# --------------------------------------------------------------------------- #
# Sales order
# --------------------------------------------------------------------------- #


class SalesOrderItem(Entity):
    sales_order: str = Field(pattern=r"^[0-9]{10}$")
    item_number: str = Field(pattern=r"^[0-9]{6}$")
    material: str = Field(min_length=1, max_length=40)
    requested_quantity: Decimal = Field(gt=0)
    quantity_unit: str = Field(min_length=1, max_length=3)
    plant: str = Field(min_length=1, max_length=4)
    item_status: ItemStatus = ItemStatus.OPEN
    confirmed_delivery_date: date | None = None


class SalesOrder(Entity):
    sales_order: str = Field(pattern=r"^[0-9]{10}$")
    sales_order_type: str = Field(default="OR", max_length=4)
    customer_id: str = Field(pattern=r"^[0-9]{10}$")
    customer_name: str = Field(min_length=1, max_length=80)
    purchase_order_ref: str | None = Field(default=None, max_length=35)
    requested_delivery_date: date
    overall_status: OrderStatus = OrderStatus.OPEN
    sales_organization: str = Field(default="1000", max_length=4)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    total_net_amount: Decimal | None = Field(default=None, ge=0)
    created_at: datetime
    items: list[SalesOrderItem] = Field(default_factory=list)

    def item(self, item_number: str) -> SalesOrderItem | None:
        return next((i for i in self.items if i.item_number == item_number), None)


# --------------------------------------------------------------------------- #
# Production order
# --------------------------------------------------------------------------- #


class ProductionOperation(Entity):
    production_order: str
    operation: str = Field(pattern=r"^[0-9]{1,6}$")
    description: str = Field(default="", max_length=40)
    work_center: str | None = Field(default=None, max_length=8)
    planned_start: datetime
    planned_end: datetime
    confirmed_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    is_released: bool = True

    @model_validator(mode="after")
    def _order_dates(self) -> ProductionOperation:
        if self.planned_end <= self.planned_start:
            raise InvariantError(
                f"operation {self.operation}: planned_end must be after planned_start"
            )
        return self

    @property
    def is_confirmed(self) -> bool:
        """Derived from confirmations only; never stored independently."""
        return self.confirmed_quantity > 0

    def overdue_days(self, clock: datetime) -> int:
        if self.is_confirmed or self.planned_end >= clock:
            return 0
        return (clock - self.planned_end).days


class ProductionOrder(Entity):
    production_order: str = Field(pattern=r"^[0-9]{1,12}$")
    production_order_type: str = Field(default="ZP01", max_length=4)
    sales_order: str | None = Field(default=None, pattern=r"^[0-9]{10}$")
    sales_order_item: str | None = Field(default=None, pattern=r"^[0-9]{6}$")
    parent_production_order: str | None = Field(default=None, pattern=r"^[0-9]{1,12}$")
    material: str = Field(min_length=1, max_length=40)
    plant: str = Field(min_length=1, max_length=4)
    total_quantity: Decimal = Field(gt=0)
    quantity_unit: str = Field(min_length=1, max_length=3)
    status: ProductionOrderStatus = ProductionOrderStatus.CREATED
    planned_start: datetime
    planned_end: datetime
    confirmed_end: datetime | None = None
    actual_end: datetime | None = None
    confirmed_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    hierarchy_level: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _order_consistency(self) -> ProductionOrder:
        if self.planned_end <= self.planned_start:
            raise InvariantError(
                f"production order {self.production_order}: "
                "planned_end must be after planned_start"
            )
        if self.confirmed_quantity > self.total_quantity:
            raise InvariantError(
                f"production order {self.production_order}: "
                "confirmed quantity cannot exceed total quantity"
            )
        if (self.sales_order is None) != (self.sales_order_item is None):
            raise InvariantError(
                f"production order {self.production_order}: "
                "sales_order and sales_order_item must both be set or both be null"
            )
        return self

    @property
    def effective_end(self) -> datetime:
        """Confirmed end when it exists, otherwise the planned end."""
        return self.confirmed_end or self.planned_end

    @property
    def is_complete(self) -> bool:
        return self.status in (
            ProductionOrderStatus.CONFIRMED,
            ProductionOrderStatus.TECHNICALLY_COMPLETE,
            ProductionOrderStatus.CLOSED,
        )


class ProductionConfirmation(Entity):
    confirmation_group: str = Field(min_length=1, max_length=10)
    confirmation_count: str = Field(default="1", max_length=8)
    production_order: str
    operation: str = Field(pattern=r"^[0-9]{1,6}$")
    confirmed_quantity: Decimal = Field(gt=0)
    quantity_unit: str = Field(min_length=1, max_length=3)
    yield_quantity: Decimal | None = Field(default=None, ge=0)
    scrap_quantity: Decimal | None = Field(default=None, ge=0)
    posting_date: date
    is_reversed: bool = False


# --------------------------------------------------------------------------- #
# Risk and evidence
# --------------------------------------------------------------------------- #


class Fact(Entity):
    """An atomic provable statement. Unconstructible without a source record."""

    fact_id: str = Field(pattern=r"^F-[0-9]+$")
    statement: str = Field(min_length=1, max_length=500)
    source_system: Literal["SAP_S4HANA"] = "SAP_S4HANA"
    source_entity: str = Field(default="", max_length=40)
    source_key: str = Field(default="", max_length=40)
    source_field: str = Field(default="", max_length=60)
    value: str = Field(default="", max_length=200)
    as_of: datetime

    def model_post_init(self, __context: Any) -> None:
        missing = [
            name
            for name in ("source_entity", "source_key", "source_field", "value")
            if not getattr(self, name)
        ]
        if missing:
            raise UngroundedFactError(
                f"{self.fact_id}: fact has no source record ({', '.join(missing)})"
            )


class Inference(Entity):
    inference_id: str = Field(pattern=r"^I-[0-9]+$")
    statement: str = Field(min_length=1, max_length=500)
    based_on: list[str] = Field(min_length=1)
    confidence: Confidence = Confidence.MEDIUM

    @field_validator("based_on")
    @classmethod
    def _facts_only(cls, v: list[str]) -> list[str]:
        for fact_id in v:
            if not fact_id.startswith("F-"):
                raise InvariantError(f"inference must cite fact ids, got {fact_id!r}")
        return v


class OrderException(Entity):
    """The 'Exception' entity: one detected deviation."""

    exception_id: str
    category: ExceptionCategory
    production_order: str
    sales_order: str
    severity: Severity
    score: int = Field(ge=0)
    detected_at: datetime
    facts: list[Fact] = Field(min_length=1)
    inference: str | None = Field(default=None, max_length=500)

    @staticmethod
    def make_id(category: ExceptionCategory, production_order: str, discriminator: str) -> str:
        return f"{category.value}:{production_order}:{discriminator}"


class RiskAssessment(Entity):
    sales_order: str
    is_at_risk: bool = False
    severity: Severity | None = None
    score: int = 0
    exceptions: list[OrderException] = Field(default_factory=list)
    evaluated_at: datetime
    data_completeness: DataCompleteness = DataCompleteness.COMPLETE
    missing_evidence: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _invariants(self) -> RiskAssessment:
        if self.is_at_risk != bool(self.exceptions):
            raise InvariantError("is_at_risk must be true if and only if exceptions are present")
        if self.data_completeness is not DataCompleteness.COMPLETE and not self.missing_evidence:
            raise InvariantError("an incomplete assessment must name its missing evidence")
        return self


class Recommendation(Entity):
    recommendation_id: str = Field(pattern=r"^R-[0-9]+$")
    addresses: str
    action: str = Field(min_length=1, max_length=300)
    owner_role: OwnerRole
    urgency: Severity
    resolution_evidence: str = Field(min_length=1, max_length=200)


# --------------------------------------------------------------------------- #
# Aggregates
# --------------------------------------------------------------------------- #


class ConsolidatedOrderView(Entity):
    sales_order: SalesOrder
    production_orders: list[ProductionOrder] = Field(default_factory=list)
    operations: list[ProductionOperation] = Field(default_factory=list)
    confirmations: list[ProductionConfirmation] = Field(default_factory=list)
    materials: list[Material] = Field(default_factory=list)
    availability: list[MaterialAvailability] = Field(default_factory=list)
    as_of: datetime
    sources_consulted: list[str] = Field(default_factory=list)
    sources_unavailable: list[str] = Field(default_factory=list)

    def orders_for_item(self, item_number: str) -> list[ProductionOrder]:
        return [o for o in self.production_orders if o.sales_order_item == item_number]

    def operations_for(self, production_order: str) -> list[ProductionOperation]:
        return [o for o in self.operations if o.production_order == production_order]

    def confirmations_for(self, production_order: str) -> list[ProductionConfirmation]:
        return [c for c in self.confirmations if c.production_order == production_order]

    def material(self, material: str) -> Material | None:
        return next((m for m in self.materials if m.material == material), None)

    def available_for(self, material: str, plant: str) -> Decimal | None:
        rows = [
            a
            for a in self.availability
            if a.material == material and a.plant == plant and a.counted
        ]
        if not rows:
            return None
        return sum((a.unrestricted_quantity for a in rows), Decimal("0"))


class EvidenceBundle(Entity):
    bundle_id: UUID
    task_id: str
    context_id: str
    mode: Mode
    facts: list[Fact] = Field(min_length=1)
    inferences: list[Inference] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    as_of: datetime
    data_completeness: DataCompleteness
    allowed_tokens: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    sources_consulted: list[str] = Field(default_factory=list)
    sources_unavailable: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _completeness(self) -> EvidenceBundle:
        if self.data_completeness is not DataCompleteness.COMPLETE and not self.missing_evidence:
            raise InvariantError("incomplete bundle must name missing evidence")
        if self.data_completeness is DataCompleteness.COMPLETE and self.sources_unavailable:
            raise InvariantError("complete bundle cannot have unavailable sources")
        return self


__all__ = [
    "ConsolidatedOrderView",
    "Customer",
    "EvidenceBundle",
    "Fact",
    "Inference",
    "Material",
    "MaterialAvailability",
    "OrderException",
    "ProductionConfirmation",
    "ProductionOperation",
    "ProductionOrder",
    "Recommendation",
    "RiskAssessment",
    "SalesOrder",
    "SalesOrderItem",
]
