"""Closed vocabularies. Values are the contract with the presentation layer."""

from __future__ import annotations

from enum import StrEnum


class OrderStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROCESS = "IN_PROCESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        return self in (OrderStatus.COMPLETED, OrderStatus.CANCELLED)


class ItemStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROCESS = "IN_PROCESS"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


class ProductionOrderStatus(StrEnum):
    CREATED = "CREATED"
    RELEASED = "RELEASED"
    PARTIALLY_CONFIRMED = "PARTIALLY_CONFIRMED"
    CONFIRMED = "CONFIRMED"
    TECHNICALLY_COMPLETE = "TECHNICALLY_COMPLETE"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        return self in (ProductionOrderStatus.CLOSED, ProductionOrderStatus.CANCELLED)


class StockType(StrEnum):
    UNRESTRICTED = "UNRESTRICTED"
    QUALITY = "QUALITY"
    BLOCKED = "BLOCKED"


class ExceptionCategory(StrEnum):
    SCHEDULE_SLIP = "SCHEDULE_SLIP"
    MISSING_CONFIRMATION = "MISSING_CONFIRMATION"
    QUANTITY_SHORTFALL = "QUANTITY_SHORTFALL"
    MATERIAL_SHORTAGE = "MATERIAL_SHORTAGE"
    STATUS_INCONSISTENCY = "STATUS_INCONSISTENCY"


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DataCompleteness(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"


class OwnerRole(StrEnum):
    PRODUCTION_PLANNER = "PRODUCTION_PLANNER"
    SHOP_FLOOR_SUPERVISOR = "SHOP_FLOOR_SUPERVISOR"
    PROCUREMENT = "PROCUREMENT"
    FULFILLMENT = "FULFILLMENT"


class Mode(StrEnum):
    PLANNER_VIEW = "PLANNER_VIEW"
    RISK_EXPLANATION = "RISK_EXPLANATION"
    CUSTOMER_SUMMARY = "CUSTOMER_SUMMARY"
    PORTFOLIO = "PORTFOLIO"


class Confidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Intent(StrEnum):
    ORDER_STATUS = "ORDER_STATUS"
    RISK_EXPLANATION = "RISK_EXPLANATION"
    PORTFOLIO = "PORTFOLIO"
    RECOMMENDATION = "RECOMMENDATION"
    CUSTOMER_SUMMARY = "CUSTOMER_SUMMARY"
    WRITE_REQUEST = "WRITE_REQUEST"
    UNKNOWN = "UNKNOWN"


__all__ = [
    "Confidence",
    "DataCompleteness",
    "ExceptionCategory",
    "Intent",
    "ItemStatus",
    "Mode",
    "OrderStatus",
    "OwnerRole",
    "ProductionOrderStatus",
    "Severity",
    "StockType",
]
