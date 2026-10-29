#!/usr/bin/env python3
"""Scenario scorecard (SC-002, SC-003, SC-004).

Reads every `*.expected.json` sidecar and compares the deterministic assessment
against it. Exits non-zero on any false positive or false negative.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cto_order_agent.config import Settings  # noqa: E402
from cto_order_agent.datasource.mock.adapter import MockDataSource  # noqa: E402
from cto_order_agent.domain.consolidation import build_view  # noqa: E402
from cto_order_agent.domain.risk import evaluate  # noqa: E402

FIXTURES = ROOT / "fixtures" / "scenarios"


async def run() -> int:
    settings = Settings.from_env({"LLM_MODE": "template"})
    ds = MockDataSource.from_dir(FIXTURES)
    clock = settings.process_clock

    rows: list[tuple[str, str, bool, bool, str]] = []
    failures = 0

    for path in sorted(FIXTURES.glob("*.expected.json")):
        expected = json.loads(path.read_text(encoding="utf-8"))
        for order, claim in expected["salesOrders"].items():
            view = await build_view(ds, order)
            assessment = evaluate(view, clock, set(view.sources_unavailable))
            actual_categories = {exc.category.value for exc in assessment.exceptions}
            expected_categories = set(claim["categories"])
            ok = (
                assessment.is_at_risk == claim["atRisk"]
                and actual_categories == expected_categories
            )
            if "dataCompleteness" in claim:
                ok = ok and assessment.data_completeness.value == claim["dataCompleteness"]
            if not ok:
                failures += 1
            rows.append(
                (
                    expected["scenario"],
                    order,
                    assessment.is_at_risk,
                    ok,
                    ",".join(sorted(actual_categories)) or "-",
                )
            )

    width = max(len(row[0]) for row in rows)
    print(f"{'scenario'.ljust(width)}  order       risk   result  categories")
    for scenario, order, at_risk, ok, categories in rows:
        flag = "PASS" if ok else "FAIL"
        print(
            f"{scenario.ljust(width)}  {order}  {str(at_risk).ljust(5)}  {flag}    {categories}"
        )

    at_risk = sum(1 for row in rows if row[2])
    print()
    print(f"orders evaluated : {len(rows)}")
    print(f"orders at risk   : {at_risk}")
    print(f"mismatches       : {failures}")
    print(f"SC-003 recall    : {at_risk - failures}/{at_risk}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
