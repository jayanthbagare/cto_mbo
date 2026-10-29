"""S/4HANA OData field mapping (canonical model <- SAP field names).

Field names follow the documented subset in data-model.md and MUST be
reconciled against the live `$metadata` during integration.
"""

from __future__ import annotations

from typing import Any

from ...domain.errors import ToolFailure

ORDER_STATUS = {
    "": "OPEN",
    "A": "OPEN",
    "B": "IN_PROCESS",
    "C": "COMPLETED",
    " ": "OPEN",
}

PRODUCTION_STATUS = {
    "CRTD": "CREATED",
    "REL": "RELEASED",
    "PCNF": "PARTIALLY_CONFIRMED",
    "CNF": "CONFIRMED",
    "TECO": "TECHNICALLY_COMPLETE",
    "CLSD": "CLOSED",
    "DLT": "CANCELLED",
}


def _require(record: dict[str, Any], field: str) -> Any:
    if field not in record:
        raise ToolFailure("UPSTREAM_ERROR", f"missing field {field} in upstream payload")
    return record[field]


def map_sales_order(record: dict[str, Any]) -> dict[str, Any]:
    items = [
        {
            "sales_order": record["SalesOrder"],
            "item_number": item["SalesOrderItem"],
            "material": item["Material"],
            "requested_quantity": str(item["RequestedQuantity"]),
            "quantity_unit": item["RequestedQuantityUnit"],
            "plant": item["Plant"],
            "item_status": ORDER_STATUS.get(item.get("SDProcessStatus", ""), "OPEN"),
            "confirmed_delivery_date": item.get("ConfirmedDeliveryDate") or None,
        }
        for item in record.get("to_Item", {}).get("results", [])
    ]
    return {
        "sales_order": record["SalesOrder"],
        "sales_order_type": record.get("SalesOrderType", "OR"),
        "customer_id": record["SoldToParty"],
        "customer_name": record.get("SoldToPartyName", "Unknown customer"),
        "purchase_order_ref": record.get("PurchaseOrderByCustomer"),
        "requested_delivery_date": record["RequestedDeliveryDate"],
        "overall_status": ORDER_STATUS.get(record.get("OverallSDProcessStatus", ""), "OPEN"),
        "sales_organization": record.get("SalesOrganization", "1000"),
        "currency": record.get("TransactionCurrency", "EUR"),
        "total_net_amount": str(record["TotalNetAmount"])
        if record.get("TotalNetAmount") is not None
        else None,
        "created_at": record["CreationDate"],
        "items": items,
    }


def map_production_order(record: dict[str, Any]) -> dict[str, Any]:
    raw_status = record.get("ManufacturingOrderStatus", "")
    if raw_status not in PRODUCTION_STATUS:
        raise ToolFailure("UPSTREAM_ERROR", f"unknown production order status {raw_status!r}")
    operations = [
        {
            "production_order": record["ManufacturingOrder"],
            "operation": op["OperationID"],
            "description": op.get("OperationText", ""),
            "work_center": op.get("WorkCenter"),
            "planned_start": op["PlannedStartDate"],
            "planned_end": op["PlannedEndDate"],
            "confirmed_quantity": "0",
            "is_released": bool(op.get("OperationIsReleased", True)),
        }
        for op in record.get("to_Operation", {}).get("results", [])
    ]
    return {
        "production_order": record["ManufacturingOrder"],
        "production_order_type": record.get("ManufacturingOrderType", "ZP01"),
        "sales_order": record.get("SalesOrder") or None,
        "sales_order_item": record.get("SalesOrderItem") or None,
        "parent_production_order": record.get("ParentManufacturingOrder") or None,
        "material": record["Material"],
        "plant": record["ProductionPlant"],
        "total_quantity": str(record["TotalQuantity"]),
        "quantity_unit": record.get("ProductionUnit", "EA"),
        "status": PRODUCTION_STATUS[raw_status],
        "planned_start": record["MfgOrderPlannedStartDate"],
        "planned_end": record["MfgOrderPlannedEndDate"],
        "confirmed_end": record.get("MfgOrderConfirmedEndDate") or None,
        "actual_end": record.get("MfgOrderActualEndDate") or None,
        "confirmed_quantity": str(record.get("ConfirmedQuantity", "0")),
        "hierarchy_level": 0,
        "operations": operations,
    }


def map_confirmation(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "confirmation_group": record["ConfirmationGroup"],
        "confirmation_count": str(record.get("ConfirmationCount", "1")),
        "production_order": record["OrderID"],
        "operation": record["OperationID"],
        "confirmed_quantity": str(record["ConfirmationQuantity"]),
        "quantity_unit": record["ConfirmationUnit"],
        "yield_quantity": str(record["YieldQuantity"])
        if record.get("YieldQuantity") is not None
        else None,
        "scrap_quantity": str(record["ScrapQuantity"])
        if record.get("ScrapQuantity") is not None
        else None,
        "posting_date": record["PostingDate"],
        "is_reversed": bool(record.get("IsReversed", False)),
    }


def map_product(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "material": record["Product"],
        "description": record.get("ProductDescription", record["Product"]),
        "material_type": record.get("ProductType", "FERT"),
        "base_unit": record["BaseUnit"],
        "product_group": record.get("ProductGroup"),
        "is_batch_managed": bool(record.get("IsBatchManaged", False)),
    }


def map_material_stock(record: dict[str, Any], as_of: str) -> dict[str, Any]:
    quantity = _require(record, "MatlWrhsStkQtyInMatlBaseUnit")
    unit = record.get("MaterialBaseUnit")
    if not unit:
        raise ToolFailure("UPSTREAM_ERROR", "stock payload has no base unit")
    return {
        "material": record["Material"],
        "plant": record["Plant"],
        "storage_location": record.get("StorageLocation"),
        "unrestricted_quantity": str(quantity),
        "unit": unit,
        "stock_type": record.get("MaterialStockType", "UNRESTRICTED"),
        "as_of": as_of,
    }


__all__ = [
    "ORDER_STATUS",
    "PRODUCTION_STATUS",
    "map_confirmation",
    "map_material_stock",
    "map_product",
    "map_production_order",
    "map_sales_order",
]
