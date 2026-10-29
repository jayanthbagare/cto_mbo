#!/usr/bin/env python3
"""Deterministic synthetic corpus generator.

Seed 42, frozen clock. `--check` regenerates in memory and diffs against the
committed JSON, so a hand-edited fixture fails CI (constitution: Mock Data).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SEED = 42
CLOCK = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
OUT = Path(__file__).resolve().parent / "scenarios"
NOTICE = "SYNTHETIC DATA - no production, customer, or personal data"

MATERIALS = {
    "MTO-1000-A": ("Frame Assembly A", "FERT", "EA"),
    "MTO-1000-B": ("Hydraulic Kit B", "HALB", "EA"),
    "MTO-1000-C": ("Steel Plate C", "ROH", "KG"),
    "MTO-2000-A": ("Pump Unit", "FERT", "EA"),
    "MTO-3000-A": ("Control Cabinet", "FERT", "EA"),
    "MTO-4000-A": ("Gearbox Housing", "FERT", "EA"),
    "MTO-5000-A": ("Sensor Module", "HALB", "EA"),
    "MTO-7000-A": ("Gap Test Part", "ROH", "EA"),
    "MTO-9000-A": ("Short Supply Part", "ROH", "EA"),
}

CUSTOMERS = {
    "0000100001": ("ACME Example GmbH", "DEU"),
    "0000100002": ("Northwind Example Ltd", "GBR"),
    "0000100003": ("Globex Example AG", "DEU"),
}


def dt(day: str, hour: int = 8) -> str:
    return f"{day}T{hour:02d}:00:00Z"


def customer(cid: str) -> dict[str, Any]:
    name, country = CUSTOMERS[cid]
    return {"customer_id": cid, "name": name, "country": country, "is_internal": False}


def item(
    so: str,
    number: str,
    material: str,
    qty: int,
    plant: str = "1010",
    status: str = "OPEN",
    confirmed: str | None = None,
) -> dict[str, Any]:
    return {
        "sales_order": so,
        "item_number": number,
        "material": material,
        "requested_quantity": str(qty),
        "quantity_unit": MATERIALS[material][2],
        "plant": plant,
        "item_status": status,
        "confirmed_delivery_date": confirmed,
    }


def order(
    so: str,
    cid: str,
    requested: str,
    items: list[dict[str, Any]],
    status: str = "IN_PROCESS",
    created: str = "2025-12-01",
) -> dict[str, Any]:
    return {
        "sales_order": so,
        "sales_order_type": "ZMTO",
        "customer_id": cid,
        "customer_name": CUSTOMERS[cid][0],
        "purchase_order_ref": f"PO-{so[-4:]}",
        "requested_delivery_date": requested,
        "overall_status": status,
        "sales_organization": "1000",
        "currency": "EUR",
        "total_net_amount": "50000.00",
        "created_at": dt(created),
        "items": items,
    }


def po(
    number: str,
    material: str,
    qty: int,
    status: str,
    start: str,
    end: str,
    confirmed_end: str | None,
    confirmed_qty: int,
    so: str | None = None,
    soi: str | None = None,
    parent: str | None = None,
    level: int = 0,
    plant: str = "1010",
) -> dict[str, Any]:
    return {
        "production_order": number,
        "production_order_type": "ZP01",
        "sales_order": so,
        "sales_order_item": soi,
        "parent_production_order": parent,
        "material": material,
        "plant": plant,
        "total_quantity": str(qty),
        "quantity_unit": MATERIALS[material][2],
        "status": status,
        "planned_start": dt(start),
        "planned_end": dt(end),
        "confirmed_end": dt(confirmed_end) if confirmed_end else None,
        "actual_end": dt(confirmed_end) if confirmed_end and status == "CLOSED" else None,
        "confirmed_quantity": str(confirmed_qty),
        "hierarchy_level": level,
    }


def op(
    po_number: str,
    number: str,
    start: str,
    end: str,
    confirmed_qty: int = 0,
    description: str = "Assembly step",
    work_center: str = "WC-01",
) -> dict[str, Any]:
    return {
        "production_order": po_number,
        "operation": number,
        "description": description,
        "work_center": work_center,
        "planned_start": dt(start),
        "planned_end": dt(end),
        "confirmed_quantity": str(confirmed_qty),
        "is_released": True,
    }


def conf(po_number: str, operation: str, qty: int, day: str, group: str) -> dict[str, Any]:
    return {
        "confirmation_group": group,
        "confirmation_count": "1",
        "production_order": po_number,
        "operation": operation,
        "confirmed_quantity": str(qty),
        "quantity_unit": "EA",
        "yield_quantity": str(qty),
        "scrap_quantity": "0",
        "posting_date": day,
        "is_reversed": False,
    }


def materials_block() -> list[dict[str, Any]]:
    return [
        {
            "material": name,
            "description": desc,
            "material_type": kind,
            "base_unit": unit,
            "product_group": "MTO",
            "is_batch_managed": False,
        }
        for name, (desc, kind, unit) in MATERIALS.items()
    ]


def availability_block(overrides: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pairs = [
        ("MTO-1000-A", "1010"),
        ("MTO-1000-B", "1010"),
        ("MTO-1000-C", "1010"),
        ("MTO-2000-A", "1010"),
        ("MTO-3000-A", "1010"),
        ("MTO-4000-A", "1010"),
        ("MTO-5000-A", "1010"),
        ("MTO-7000-A", "1010"),
        ("MTO-9000-A", "1010"),
    ]
    for material, plant in pairs:
        qty = overrides.get(material, {}).get(plant, 1000)
        rows.append(
            {
                "material": material,
                "plant": plant,
                "storage_location": "0001",
                "unrestricted_quantity": str(qty),
                "unit": MATERIALS[material][2],
                "stock_type": "UNRESTRICTED",
                "as_of": dt("2026-01-15"),
            }
        )
    return rows


def doc(name: str, **parts: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "_meta": {
            "synthetic": True,
            "notice": NOTICE,
            "schemaVersion": "1.0.0",
            "seed": SEED,
            "generatedBy": "fixtures/generate.py",
            "scenario": name,
        }
    }
    used = {
        i["material"] for o in parts.get("salesOrders", []) for i in o.get("items", [])
    } | {p["material"] for p in parts.get("productionOrders", [])}
    if "availability" in parts and used:
        parts["availability"] = [
            row for row in parts["availability"] if row["material"] in used
        ]
    base.update(parts)
    return base


def build_all() -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    customer_ids = sorted(CUSTOMERS)
    all_customers = [customer(c) for c in customer_ids]
    out: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}

    # 1. on-track ------------------------------------------------------------
    so = "0000012345"
    items = [item(so, "000010", "MTO-1000-A", 10), item(so, "000020", "MTO-2000-A", 5)]
    pos = [
        po("1000001", "MTO-1000-A", 10, "CONFIRMED", "2026-01-15", "2026-01-18",
           "2026-01-18", 10, so, "000010"),
        po("1000002", "MTO-2000-A", 5, "CONFIRMED", "2026-01-14", "2026-01-17",
           "2026-01-17", 5, so, "000020"),
        po("1000003", "MTO-1000-B", 10, "CONFIRMED", "2026-01-12", "2026-01-14",
           None, 10, parent="1000001", level=1),
    ]
    ops = [
        op("1000001", "0010", "2026-01-15", "2026-01-16", 10),
        op("1000001", "0020", "2026-01-16", "2026-01-18", 10),
        op("1000002", "0010", "2026-01-14", "2026-01-17", 5),
        op("1000003", "0010", "2026-01-12", "2026-01-14", 10),
    ]
    confs = [
        conf("1000001", "0010", 10, "2026-01-16", "CG-1"),
        conf("1000003", "0010", 10, "2026-01-14", "CG-2"),
    ]
    out["on-track"] = (
        doc("on-track", salesOrders=[order(so, "0000100001", "2026-01-20", items)],
            productionOrders=pos, operations=ops, confirmations=confs,
            materials=materials_block(), availability=availability_block({}),
            customers=all_customers),
        {"scenario": "on-track", "salesOrders": {so: {"atRisk": False, "categories": []}}},
    )

    # 2. on-track-multilevel ------------------------------------------------
    so = "0000012347"
    items = [item(so, "000010", "MTO-3000-A", 8)]
    pos = [
        po("1000010", "MTO-3000-A", 8, "CONFIRMED", "2026-01-15", "2026-01-19",
           "2026-01-19", 8, so, "000010"),
        po("1000011", "MTO-5000-A", 8, "CONFIRMED", "2026-01-15", "2026-01-16",
           None, 8, parent="1000010", level=1),
        po("1000012", "MTO-4000-A", 8, "CONFIRMED", "2026-01-12", "2026-01-15",
           None, 8, parent="1000011", level=2),
    ]
    ops = [
        op("1000010", "0010", "2026-01-15", "2026-01-19", 8),
        op("1000011", "0010", "2026-01-15", "2026-01-16", 8),
        op("1000012", "0010", "2026-01-12", "2026-01-15", 8),
    ]
    out["on-track-multilevel"] = (
        doc("on-track-multilevel",
            salesOrders=[order(so, "0000100002", "2026-01-25", items)],
            productionOrders=pos, operations=ops,
            confirmations=[conf("1000010", "0010", 8, "2026-01-19", "CG-10")],
            materials=materials_block(), availability=availability_block({}),
            customers=all_customers),
        {"scenario": "on-track-multilevel",
         "salesOrders": {so: {"atRisk": False, "categories": []}}},
    )

    # 3. partially-confirmed-on-time ----------------------------------------
    so = "0000012348"
    items = [item(so, "000010", "MTO-4000-A", 20)]
    pos = [
        po("1000020", "MTO-4000-A", 20, "PARTIALLY_CONFIRMED", "2026-01-14",
           "2026-01-18", "2026-01-18", 12, so, "000010"),
    ]
    ops = [
        op("1000020", "0010", "2026-01-14", "2026-01-16", 12),
        op("1000020", "0020", "2026-01-16", "2026-01-18", 0),
    ]
    out["partially-confirmed-on-time"] = (
        doc("partially-confirmed-on-time",
            salesOrders=[order(so, "0000100003", "2026-01-22", items)],
            productionOrders=pos, operations=ops,
            confirmations=[conf("1000020", "0010", 12, "2026-01-16", "CG-20")],
            materials=materials_block(), availability=availability_block({}),
            customers=all_customers),
        {"scenario": "partially-confirmed-on-time",
         "salesOrders": {so: {"atRisk": False, "categories": []}}},
    )

    # 4. schedule-slip ------------------------------------------------------
    so = "0000012346"
    items = [item(so, "000010", "MTO-1000-A", 10)]
    pos = [
        po("1000030", "MTO-1000-A", 10, "RELEASED", "2026-01-15", "2026-02-02",
           "2026-02-02", 0, so, "000010"),
    ]
    ops = [op("1000030", "0010", "2026-01-15", "2026-01-20", 0)]
    out["schedule-slip"] = (
        doc("schedule-slip", salesOrders=[order(so, "0000100001", "2026-01-20", items)],
            productionOrders=pos, operations=ops, confirmations=[],
            materials=materials_block(), availability=availability_block({}),
            customers=all_customers),
        {"scenario": "schedule-slip",
         "salesOrders": {so: {"atRisk": True, "categories": ["SCHEDULE_SLIP"]}}},
    )

    # 5. already-delayed ----------------------------------------------------
    so = "0000012349"
    items = [item(so, "000010", "MTO-2000-A", 4)]
    pos = [
        po("1000040", "MTO-2000-A", 4, "RELEASED", "2026-01-02", "2026-01-10",
           None, 0, so, "000010"),
    ]
    ops = [op("1000040", "0010", "2026-01-02", "2026-01-10", 0)]
    out["already-delayed"] = (
        doc("already-delayed", salesOrders=[order(so, "0000100002", "2026-01-08", items)],
            productionOrders=pos, operations=ops, confirmations=[],
            materials=materials_block(), availability=availability_block({}),
            customers=all_customers),
        {"scenario": "already-delayed",
         "salesOrders": {so: {"atRisk": True,
                              "categories": ["SCHEDULE_SLIP", "MISSING_CONFIRMATION"]}}},
    )

    # 6. missing-confirmation ----------------------------------------------
    so = "0000012351"
    items = [item(so, "000010", "MTO-3000-A", 6)]
    pos = [
        po("1000050", "MTO-3000-A", 6, "RELEASED", "2026-01-14", "2026-01-19",
           "2026-01-19", 0, so, "000010"),
    ]
    ops = [
        op("1000050", "0010", "2026-01-02", "2026-01-05", 0),
        op("1000050", "0020", "2026-01-15", "2026-01-19", 0),
    ]
    out["missing-confirmation"] = (
        doc("missing-confirmation",
            salesOrders=[order(so, "0000100003", "2026-01-24", items)],
            productionOrders=pos, operations=ops, confirmations=[],
            materials=materials_block(), availability=availability_block({}),
            customers=all_customers),
        {"scenario": "missing-confirmation",
         "salesOrders": {so: {"atRisk": True, "categories": ["MISSING_CONFIRMATION"]}}},
    )

    # 7. material-shortage --------------------------------------------------
    so = "0000012353"
    items = [item(so, "000010", "MTO-9000-A", 30)]
    pos = [
        po("1000060", "MTO-9000-A", 30, "RELEASED", "2026-01-16", "2026-01-19",
           "2026-01-19", 0, so, "000010"),
    ]
    ops = [op("1000060", "0010", "2026-01-16", "2026-01-19", 0)]
    out["material-shortage"] = (
        doc("material-shortage",
            salesOrders=[order(so, "0000100001", "2026-01-23", items)],
            productionOrders=pos, operations=ops, confirmations=[],
            materials=materials_block(),
            availability=availability_block({"MTO-9000-A": {"1010": 0}}),
            customers=all_customers),
        {"scenario": "material-shortage",
         "salesOrders": {so: {"atRisk": True, "categories": ["MATERIAL_SHORTAGE"]}}},
    )

    # 8. quantity-shortfall -------------------------------------------------
    so = "0000012354"
    items = [item(so, "000010", "MTO-4000-A", 20)]
    pos = [
        po("1000070", "MTO-4000-A", 20, "CLOSED", "2026-01-02", "2026-01-12",
           "2026-01-12", 15, so, "000010"),
    ]
    ops = [op("1000070", "0010", "2026-01-02", "2026-01-12", 15)]
    out["quantity-shortfall"] = (
        doc("quantity-shortfall",
            salesOrders=[order(so, "0000100002", "2026-01-20", items)],
            productionOrders=pos, operations=ops,
            confirmations=[conf("1000070", "0010", 15, "2026-01-12", "CG-70")],
            materials=materials_block(), availability=availability_block({}),
            customers=all_customers),
        {"scenario": "quantity-shortfall",
         "salesOrders": {so: {"atRisk": True, "categories": ["QUANTITY_SHORTFALL"]}}},
    )

    # 9. status-inconsistency ----------------------------------------------
    so = "0000012355"
    items = [item(so, "000010", "MTO-1000-A", 10)]
    pos = [
        po("1000080", "MTO-1000-A", 10, "RELEASED", "2026-01-14", "2026-01-18",
           "2026-01-18", 10, so, "000010"),
    ]
    ops = [op("1000080", "0010", "2026-01-14", "2026-01-18", 10)]
    out["status-inconsistency"] = (
        doc("status-inconsistency",
            salesOrders=[order(so, "0000100003", "2026-01-22", items)],
            productionOrders=pos, operations=ops,
            confirmations=[conf("1000080", "0010", 10, "2026-01-18", "CG-80")],
            materials=materials_block(), availability=availability_block({}),
            customers=all_customers),
        {"scenario": "status-inconsistency",
         "salesOrders": {so: {"atRisk": True, "categories": ["STATUS_INCONSISTENCY"]}}},
    )

    # 10. no-production-orders ---------------------------------------------
    so = "0000012350"
    items = [item(so, "000010", "MTO-2000-A", 3)]
    out["no-production-orders"] = (
        doc("no-production-orders",
            salesOrders=[order(so, "0000100001", "2026-01-28", items)],
            productionOrders=[], operations=[], confirmations=[],
            materials=materials_block(), availability=availability_block({}),
            customers=all_customers),
        {"scenario": "no-production-orders",
         "salesOrders": {so: {"atRisk": False, "categories": []}}},
    )

    # 11. data-gap ----------------------------------------------------------
    so = "0000012352"
    items = [item(so, "000010", "MTO-7000-A", 10)]
    pos = [
        po("1000090", "MTO-7000-A", 10, "RELEASED", "2026-01-15", "2026-01-18",
           "2026-01-18", 0, so, "000010"),
    ]
    ops = [op("1000090", "0010", "2026-01-10", "2026-01-14", 0)]
    out["data-gap"] = (
        doc("data-gap", salesOrders=[order(so, "0000100002", "2026-01-21", items)],
            productionOrders=pos, operations=ops, confirmations=[],
            materials=materials_block(), availability=[],
            unavailableTools=["get_material_stock"],
            unavailableMaterials=["MTO-7000-A"],
            unavailableProducts=["MTO-7000-A"],
            customers=all_customers),
        {"scenario": "data-gap",
         "salesOrders": {so: {"atRisk": True, "categories": ["MISSING_CONFIRMATION"],
                              "dataCompleteness": "INSUFFICIENT"}}},
    )

    # 12. portfolio-mixed ---------------------------------------------------
    critical = "0000012356"
    healthy = "0000012357"
    closed = "0000012358"
    orders = [
        order(critical, "0000100001", "2026-01-12",
              [item(critical, "000010", "MTO-2000-A", 5)]),
        order(healthy, "0000100002", "2026-01-26",
              [item(healthy, "000010", "MTO-3000-A", 4)]),
        order(closed, "0000100003", "2026-01-20",
              [item(closed, "000010", "MTO-4000-A", 2, status="COMPLETED")],
              status="COMPLETED"),
    ]
    pos = [
        po("1000100", "MTO-2000-A", 5, "RELEASED", "2026-01-02", "2026-01-09",
           None, 0, critical, "000010"),
        po("1000101", "MTO-3000-A", 4, "CONFIRMED", "2026-01-15", "2026-01-20",
           "2026-01-20", 4, healthy, "000010"),
        po("1000102", "MTO-4000-A", 2, "CLOSED", "2026-01-02", "2026-01-10",
           "2026-01-10", 2, closed, "000010"),
    ]
    ops = [
        op("1000100", "0010", "2026-01-02", "2026-01-09", 0),
        op("1000101", "0010", "2026-01-15", "2026-01-20", 4),
        op("1000102", "0010", "2026-01-02", "2026-01-10", 2),
    ]
    out["portfolio-mixed"] = (
        doc("portfolio-mixed", salesOrders=orders, productionOrders=pos,
            operations=ops,
            confirmations=[conf("1000102", "0010", 2, "2026-01-10", "CG-102")],
            materials=materials_block(), availability=availability_block({}),
            customers=all_customers),
        {"scenario": "portfolio-mixed",
         "salesOrders": {
             critical: {"atRisk": True,
                        "categories": ["SCHEDULE_SLIP", "MISSING_CONFIRMATION"]},
             healthy: {"atRisk": False, "categories": []},
             closed: {"atRisk": False, "categories": []},
         }},
    )
    return out


def serialize(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args(argv)

    if args.seed != SEED:
        print(f"unsupported seed {args.seed}: corpus is pinned to {SEED}", file=sys.stderr)
        return 2

    target = Path(args.out)
    built = build_all()
    failures: list[str] = []

    for name, (payload, expected) in sorted(built.items()):
        for suffix, data in ((".json", payload), (".expected.json", expected)):
            path = target / f"{name}{suffix}"
            text = serialize(data)
            if args.check:
                if not path.exists():
                    failures.append(f"missing {path.name}")
                elif path.read_text(encoding="utf-8") != text:
                    failures.append(f"drift in {path.name}")
            else:
                target.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")

    if args.check:
        expected_names = {
            f"{name}{suffix}" for name in built for suffix in (".json", ".expected.json")
        }
        if target.exists():
            for path in target.glob("*.json"):
                if path.name not in expected_names:
                    failures.append(f"unexpected {path.name}")
        if failures:
            for failure in failures:
                print(f"FAIL {failure}", file=sys.stderr)
            return 1
        print(f"OK {len(built)} scenarios match the generator")
    else:
        print(f"wrote {len(built)} scenarios to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
