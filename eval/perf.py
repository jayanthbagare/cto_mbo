#!/usr/bin/env python3
"""Performance harness (SC-001, FR-024).

Measures single-order latency and portfolio scan time, then applies the
published budgets. Exits non-zero when a budget is exceeded.
"""

from __future__ import annotations

import asyncio
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cto_order_agent.a2a.executor import AgentExecutor  # noqa: E402
from cto_order_agent.config import Settings  # noqa: E402
from cto_order_agent.datasource.mock.adapter import MockDataSource  # noqa: E402
from cto_order_agent.domain.portfolio import scan  # noqa: E402

SINGLE_ORDER_BUDGET_MEDIAN = 60.0
SINGLE_ORDER_BUDGET_P95 = 300.0
PORTFOLIO_BUDGET = 90.0
SCALE_PROJECTION = 500


async def run() -> int:
    settings = Settings.from_env({"LLM_MODE": "template"})
    ds = MockDataSource.from_dir(ROOT / "fixtures" / "scenarios")
    executor = AgentExecutor(ds, settings, clock=settings.process_clock)

    latencies: list[float] = []
    for index in range(20):
        started = time.perf_counter()
        await executor.handle_turn(
            "Status of sales order 0000012345", f"perf-{index}", f"perf-task-{index}"
        )
        latencies.append(time.perf_counter() - started)

    latencies.sort()
    median = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95) - 1]

    started = time.perf_counter()
    result = await scan(ds, settings.process_clock, settings.portfolio_window_days)
    scan_seconds = time.perf_counter() - started
    per_order = scan_seconds / max(result.scanned, 1)
    projected = per_order * SCALE_PROJECTION

    print(f"single order median : {median * 1000:.1f} ms")
    print(f"single order p95    : {p95 * 1000:.1f} ms")
    print(f"portfolio scan      : {scan_seconds * 1000:.1f} ms for {result.scanned} orders")
    print(f"per-order cost      : {per_order * 1000:.1f} ms")
    print(f"{SCALE_PROJECTION}-order projection: {projected:.2f} s")

    failures: list[str] = []
    if median > SINGLE_ORDER_BUDGET_MEDIAN:
        failures.append(f"median {median:.1f}s exceeds {SINGLE_ORDER_BUDGET_MEDIAN}s")
    if p95 > SINGLE_ORDER_BUDGET_P95:
        failures.append(f"p95 {p95:.1f}s exceeds {SINGLE_ORDER_BUDGET_P95}s")
    if projected > PORTFOLIO_BUDGET:
        failures.append(f"projected scan {projected:.1f}s exceeds {PORTFOLIO_BUDGET}s")
    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
