# Quickstart Validation Record

Executed 2026-10-29 against commit state `main` (pre-push), Python 3.11.5, `LLM_MODE=template`,
frozen clock `2026-01-15T08:00:00Z`. Each scenario was run both through the automated suite and, for
V1/V3/V12, manually against a live server on port 8099.

| # | Scenario | Method | Result |
|---|---|---|---|
| V1 | Unified order view | `curl` + `test_v1_complete_consolidated_view` | PASS — header, 2 items, 3 production orders at 2 levels, material availability, `As of` line |
| V2 | Order without production orders | `test_v2_order_without_production_orders` | PASS — states none linked, no error |
| V3 | Order not found | `curl` + `test_v3_order_not_found` | PASS — asks for correction, invents nothing |
| V4 | Ambiguous reference | `test_v4_ambiguous_reference` | PASS — lists candidates, asks which |
| V5 | Follow-up context | `test_v5_follow_up_uses_context` | PASS — second order resolved without repeating the number |
| V6 | Exception detection + negative case | `make eval` | PASS — 8/8 at risk, 0/6 false positives |
| V7 | Portfolio ranking | `test_v7_portfolio_is_ranked_and_scoped` | PASS — score order, scope and window disclosed, completed excluded |
| V8 | Fact/inference labelling | `test_v8_facts_and_inferences_are_labelled` | PASS — one label per claim, citations present |
| V9 | Insufficient evidence | `test_v9_insufficient_evidence_is_declared` | PASS — declares incompleteness, names missing source, no risk conclusion |
| V10 | Recommendations + read-only refusal | `test_v10_*` | PASS — ranked, owned, actionable; expedite refused; fixtures unchanged |
| V11 | Customer summary | `test_v11_*` | PASS — no internal ids, confirmed vs estimated separated, no invented date |
| V12 | Data-source swap | `make test-swap` + provenance gate | PASS (structural) — see limitation below |
| V13 | Performance | `make perf` | PASS — median 0.3 ms, p95 0.4 ms |

## Quality gates

| Gate | Command | Result |
|---|---|---|
| Suite green | `make check` | PASS (174 tests) |
| Lint | `ruff check` | PASS |
| Types | `mypy` strict | PASS (40 files) |
| Fixture law | `fixtures/generate.py --check` | PASS (12 scenarios) |
| Provenance | `make provenance` | PASS |
| Coverage | `make coverage` | PASS (100% on the three gated modules) |
| Scorecard | `make eval` | PASS (0 mismatches) |
| Performance | `make perf` | PASS |

## Limitations recorded

1. **V12 is structural, not end-to-end.** The full scenario suite has not been replayed against live
   SAP because no S/4HANA destination or credentials exist in this environment. The provenance gate
   proves no agent logic branches on the data source, and the adapter contract tests prove mapping
   shape parity, but a credentialed replay remains the first integration task.
2. **OData field names** are a documented subset and must be reconciled against the live `$metadata`
   before go-live.
3. **Single replica** — A2A task state is in-process.
4. **500-order projection** in `eval/RESULTS.md` is linear extrapolation, explicitly labelled.

## Manual smoke transcript (abridged)

```
GET /healthz               -> {"status":"ok","config":{...redacted...},"tasks":0}
GET /.well-known/agent-card.json -> "MTO/CTO Order Intelligence Agent", 5 skills
POST /a2a (status query)   -> TASK_STATE_COMPLETED, consolidated view with "As of 2026-01-15..."
```
