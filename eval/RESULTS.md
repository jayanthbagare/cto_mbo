# Evaluation Results

Measured on 2026-10-29, Python 3.11.5, fixture adapter, `LLM_MODE=template`, frozen clock
`2026-01-15T08:00:00Z`.

## Scenario scorecard (`make eval`)

| Metric | Result |
|---|---|
| Orders evaluated | 14 |
| Scenarios | 12 |
| Orders at risk | 8 |
| Mismatches vs expected findings | **0** |
| SC-003 recall | **8/8 (100%)** |
| SC-003 false positives on healthy orders | **0/6** |

Per-scenario detail:

| Scenario | Order | At risk | Detected |
|---|---|---|---|
| on-track | 0000012345 | no | — |
| on-track-multilevel | 0000012347 | no | — |
| partially-confirmed-on-time | 0000012348 | no | — |
| schedule-slip | 0000012346 | yes | SCHEDULE_SLIP |
| already-delayed | 0000012349 | yes | SCHEDULE_SLIP, MISSING_CONFIRMATION |
| missing-confirmation | 0000012351 | yes | MISSING_CONFIRMATION |
| material-shortage | 0000012353 | yes | MATERIAL_SHORTAGE |
| quantity-shortfall | 0000012354 | yes | QUANTITY_SHORTFALL |
| status-inconsistency | 0000012355 | yes | STATUS_INCONSISTENCY |
| no-production-orders | 0000012350 | no | — |
| data-gap | 0000012352 | yes | MISSING_CONFIRMATION (PARTIAL→INSUFFICIENT) |
| portfolio-mixed | 0000012356 | yes | SCHEDULE_SLIP, MISSING_CONFIRMATION |
| portfolio-mixed | 0000012357 | no | — |
| portfolio-mixed | 0000012358 | no | — (completed, excluded) |

## Performance (`make perf`)

| Metric | Measured | Budget | Result |
|---|---|---|---|
| Single-order median | 0.3 ms | < 60 s | PASS |
| Single-order p95 | 0.4 ms | < 5 min | PASS |
| Portfolio scan (13 orders) | 2.3 ms | — | PASS |
| Per-order scan cost | 0.2 ms | — | PASS |
| Projected 500-order scan | 0.09 s | < 90 s | PASS |

**Method note (honesty):** the 500-order figure is a linear projection from the measured per-order
cost, not a run against a 500-order corpus. The current corpus has 13 open orders. The projection is
defensible because the scan is O(orders) with no cross-order work, but it is a projection and is
labelled as such rather than reported as a measurement.

## Test suite

| Metric | Result |
|---|---|
| Tests | 174 passed |
| Runtime | 0.9 s |
| Branch coverage: `domain/risk.py` | 100% |
| Branch coverage: `domain/evidence.py` | 100% |
| Branch coverage: `narrative/validator.py` | 100% |

## Why these numbers are trustworthy

The scenario scorecard compares against `*.expected.json` sidecars committed beside each fixture, not
against prose the agent produced. The assessment is a pure function of fixture data plus the frozen
clock, so a re-run is byte-identical. Determinism is separately asserted in
`tests/unit/test_exception_ids.py`.

The one thing not measured here is SC-008 (zero behavioral difference after the data-source swap).
It is covered structurally — `test_datasource_swap.py` asserts that no module outside
`datasource/` references provenance, and `test_odata_mapping.py` asserts the live adapter produces
the same canonical shapes against recorded responses — but a true end-to-end swap needs S/4HANA
credentials and is the first integration task.
