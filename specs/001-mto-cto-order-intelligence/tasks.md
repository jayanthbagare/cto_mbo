---

description: "Task list for MTO/CTO Sales Order and Production Order Intelligence Agent"
---

# Tasks: MTO/CTO Sales Order and Production Order Intelligence Agent

**Input**: Design documents from `/specs/001-mto-cto-order-intelligence/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: REQUIRED. Constitution Principle III (Test-First, Verification-Gated) is
NON-NEGOTIABLE, so every functional slice begins with a test that fails. Do not mark a task complete
until its test was observed failing first.

**Organization**: Tasks are grouped by user story so each story is independently implementable,
testable, and demonstrable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1 to US5)
- Every task names an exact file path

## Path Conventions

Single project. All paths are relative to the repository root:

- `src/cto_order_agent/` — agent and MCP tool server
- `fixtures/` — synthetic scenario corpus
- `tests/` — `unit/`, `contract/`, `integration/`
- `specs/001-mto-cto-order-intelligence/` — design artifacts

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and the guardrails every later task depends on.

- [X] T001 Create `pyproject.toml` with Python 3.12 requirement and pinned dependencies: `a2a-sdk>=1.0`, `mcp>=2.0`, `pydantic>=2.7`, `starlette`, `uvicorn`, `httpx`, `structlog`, `opentelemetry-sdk`, plus dev extras `pytest`, `pytest-asyncio`, `respx`, `ruff`, `mypy`, `pytest-cov`
- [X] T002 Create package skeleton with `src/cto_order_agent/__init__.py` and empty `__init__.py` files for `a2a/`, `domain/`, `narrative/`, `datasource/`, `mcp_server/`, `observability/`
- [X] T003 [P] Configure `ruff` (line length 100, target py312) and strict `mypy` for `src/` inside `pyproject.toml`
- [X] T004 [P] Configure `pytest` in `pyproject.toml` with `asyncio_mode=auto`, markers `unit`, `contract`, `integration`, `eval`; set `--cov=cto_order_agent` with a 100% gate scoped to `domain/risk.py`, `domain/evidence.py`, and `narrative/validator.py`
- [X] T005 [P] Create `Makefile` with targets `run`, `check`, `test-unit`, `test-contract`, `test-int`, `eval`, `perf`, `smoke`, matching `.specify/../specs/001-mto-cto-order-intelligence/quickstart.md`
- [X] T006 Implement settings loader in `src/cto_order_agent/config.py` reading `DATA_SOURCE`, `LLM_MODE`, `AI_CORE_BASE_URL`, `AI_CORE_CLIENT_ID`, `AI_CORE_CLIENT_SECRET`, `PROCESS_CLOCK` with no secret defaults and a frozen-clock parser defaulting to `2026-01-15T08:00:00Z`
- [X] T007 [P] Add `.gitignore` (env files, `__pycache__`, `.venv`, coverage) and `.env.example` documenting every variable from T006 without values
- [X] T008 [P] Implement `src/cto_order_agent/observability/logging.py` with `structlog` JSON output and a redaction processor that masks keys matching `secret|token|password|authorization|client_secret`
- [X] T009 [P] Add a unit test `tests/unit/test_logging_redaction.py` asserting the redaction processor masks each sensitive key and never emits a raw value

**Checkpoint**: `make check` runs and fails only on absent implementation, not on configuration.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared domain model, data boundary, and protocol surface. No user story can begin
until this phase is complete.

**⚠️ CRITICAL**: Every task here blocks all five user stories.

- [X] T010 Implement all canonical entities in `src/cto_order_agent/domain/models.py` per `data-model.md`: `SalesOrder`, `SalesOrderItem`, `ProductionOrder`, `ProductionOperation`, `ProductionConfirmation`, `Material`, `MaterialAvailability`, `Customer`, `Exception`, `Fact`, `RiskAssessment`, `Recommendation`, `ConsolidatedOrderView`; enforce every validation rule in the data-model tables in Pydantic validators
- [X] T011 [P] Add unit tests in `tests/unit/test_models.py` covering: leading-zero identifier preservation, enum conformance, `planned_end > planned_start`, `confirmed_quantity <= total_quantity`, and a `Fact` construction attempt without a source record raising `UngroundedFactError`
- [X] T012 [P] Add unit test `tests/unit/test_models_invariants.py` asserting `ProductionOperation.is_confirmed` cannot be set independently of confirmations and that `RiskAssessment.is_at_risk` is false iff `exceptions` is empty
- [X] T013 Define the data boundary port in `src/cto_order_agent/datasource/protocol.py`: a `DataSource` Protocol with the five async methods matching `contracts/mcp-tools.md` signatures, returning the common envelope, with no provenance-dependent parameters
- [X] T014 Implement the deterministic fixture generator in `fixtures/generate.py` (seed 42, frozen clock, `--check` flag that regenerates in memory and diffs against committed JSON, exit 1 on drift)
- [X] T015 Add unit test `tests/unit/test_fixture_generator.py` asserting two runs with seed 42 are byte-identical and that `--check` fails when a committed fixture is mutated
- [X] T016 Generate the 12 committed scenario bundles under `fixtures/scenarios/`: `on-track`, `on-track-multilevel`, `schedule-slip`, `already-delayed`, `missing-confirmation`, `material-shortage`, `quantity-shortfall`, `status-inconsistency`, `partially-confirmed-on-time`, `no-production-orders`, `data-gap`, plus a `not-found` case; every file opens with the synthetic-data header comment
- [X] T017 Generate the `expected_findings` sidecar per scenario at `fixtures/scenarios/<name>.expected.json` declaring exception categories and scores, so acceptance asserts against data rather than prose
- [X] T018 Implement `src/cto_order_agent/datasource/mock/adapter.py` loading fixtures at startup, validating referential integrity, and raising `FixtureIntegrityError` on any orphan production order, missing material, or unit mismatch
- [X] T019 Add integration-lite test `tests/unit/test_fixture_integrity.py` asserting startup fails fast on a mutated fixture with an orphan `salesOrderItem` and that all 12 scenarios load clean
- [X] T020 [P] Implement the A2A task store in `src/cto_order_agent/a2a/tasks.py`: TTL 30 minutes, max 1,000 tasks, thread-safe, `GetTask` returns the stored task, and an expired task returns not-found
- [X] T021 [P] Add unit test `tests/unit/test_task_store.py` covering TTL expiry, capacity eviction of the oldest task, and concurrent access from two coroutines
- [X] T022 Implement `src/cto_order_agent/a2a/agent_card.py` building the card from typed SDK models with the 5 skills from `contracts/agent-card.json`, `streaming=true`, `pushNotifications=false`
- [X] T023 Implement `src/cto_order_agent/a2a/executor.py` as an `AgentExecutor` skeleton: receives a message, creates or resumes a task by `contextId`, dispatches to a `handle_turn` seam that currently returns a typed `NotImplemented` message, and never calls a tool directly
- [X] T024 Implement the five MCP tools in `src/cto_order_agent/mcp_server/tools.py` as thin async wrappers delegating to the injected `DataSource`, translating adapter exceptions into structured `ToolError` payloads per the `mcp-tools.md` taxonomy
- [X] T025 Implement `src/cto_order_agent/mcp_server/server.py` using `MCPServer` with `run(transport="streamable-http", stateless_http=True, json_response=True)` on port 8081
- [X] T026 Implement `src/cto_order_agent/main.py` mounting the A2A JSON-RPC app, `/.well-known/agent-card.json`, the MCP app at `/mcp`, and `/healthz` in one process
- [X] T027 [P] Write contract test `tests/contract/test_mcp_schemas.py` asserting each generated tool input/output schema matches the JSON documented in `contracts/mcp-tools.md`, and that exactly 5 tools are registered
- [X] T028 [P] Write contract test `tests/contract/test_agent_card.py` asserting the served card equals `contracts/agent-card.json` field-for-field and declares exactly the 5 skill ids
- [X] T029 [P] Write contract test `tests/contract/test_evidence_bundle_schema.py` asserting a builder-produced bundle validates against `contracts/evidence-bundle.schema.json` (Draft 2020-12) in all four modes
- [X] T030 Add unit test `tests/unit/test_datasource_swap.py` asserting the `DataSource` protocol is satisfied by the mock adapter and that no module in `src/` references `SYNTHETIC` outside the adapter

**Checkpoint**: Foundation ready. `make test-contract` passes, the server boots, and all five tools
answer from fixtures. User stories can now proceed in parallel.

---

## Phase 3: User Story 1 - Unified Order View for a Single Order (Priority: P1) 🎯 MVP

**Goal**: A planner asks about an order number and receives the sales order, all linked production
orders at all levels, confirmations, and material availability as one consolidated answer with an
as-of timestamp.

**Independent Test**: Ask about scenario `on-track` and verify the response is internally consistent,
complete, and names the order's risk position — with no other story implemented.

### Tests for User Story 1 ⚠️

> Write these first and confirm they fail before T034 onward.

- [X] T031 [P] [US1] Write `tests/unit/test_consolidation.py`: item-to-production-order linkage on `(salesOrder, salesOrderItem)`, multi-level hierarchy flattening with `parentProductionOrder` preserved, deduplicated material union, and the `no-production-orders` case returning an explicit empty finding rather than an error
- [X] T032 [P] [US1] Write `tests/unit/test_order_ref.py`: accepts 10-digit order numbers with and without leading zeros, rejects malformed input, resolves an ambiguous prefix to multiple candidates, and returns not-found for an unmatched key
- [X] T033 [P] [US1] Write `tests/integration/test_us1_unified_view.py` mapping quickstart V1 through V5, asserting the consolidated view, the empty-production-order answer, not-found handling, disambiguation, and follow-up context reuse
- [X] T034 [P] [US1] Write `tests/unit/test_as_of.py` asserting `ConsolidatedOrderView.as_of` equals the oldest successful source read and is unaffected by the response time

### Implementation for User Story 1

- [X] T035 [US1] Implement `src/cto_order_agent/domain/consolidation.py`: breadth-first assembly from `SalesOrder` to items, to production orders by `(salesOrder, salesOrderItem)`, to operations, to confirmations, to the deduplicated material and availability union, producing a `ConsolidatedOrderView`
- [X] T036 [US1] Add request-scoped deduplicated caching to `src/cto_order_agent/datasource/mock/adapter.py`, keyed by `(tool, normalized arguments)`, with concurrent in-flight calls capped at 8 per research D8
- [X] T037 [US1] Implement order reference extraction in `src/cto_order_agent/nlu/order_ref.py` handling bare digits, zero-padded forms, prefixed text ("order 1234"), ambiguous prefixes, and non-numeric input
- [X] T038 [US1] Implement planner-view rendering in `src/cto_order_agent/presentation/planner_view.py` producing the consolidated layout with the `As of` line, hierarchy indentation, and the `Sources consulted` footer
- [X] T039 [US1] Handle the not-found and ambiguous outcomes in `src/cto_order_agent/presentation/planner_view.py`, rendering candidate lists with enough distinguishing detail to disambiguate
- [X] T040 [US1] Wire `handle_turn` in `src/cto_order_agent/a2a/executor.py` to store `(contextId → last order, last entity set)` in the task store and resolve follow-ups such as "what about the second production order?"
- [X] T041 [US1] Implement partial-source disclosure in `src/cto_order_agent/domain/consolidation.py`: failed tools populate `sources_unavailable`, set `data_completeness=PARTIAL`, and the rendered answer names the gap
- [X] T042 [US1] Guard against oversized output in `src/cto_order_agent/presentation/planner_view.py`: when more than 50 production orders are present, group by exception and state that the remainder is available on request
- [X] T043 [US1] Register the `unified-order-view` skill route in `src/cto_order_agent/a2a/executor.py` and confirm the card advertises it

**Checkpoint**: `make test-int` passes for V1–V5. US1 is demoable on its own.

---

## Phase 4: User Story 2 - Exception Detection Without Manual Triage (Priority: P2)

**Goal**: The agent flags schedule slip, missing confirmation, quantity shortfall, material shortage,
and status inconsistency, ranks orders by the D12 score, and never flags a healthy order.

**Independent Test**: Run `make eval` and verify all at-risk scenarios are flagged with the correct
category and zero on-track scenarios are flagged.

### Tests for User Story 2 ⚠️

- [X] T044 [P] [US2] Write `tests/unit/test_risk_rules.py` with one positive and one negative case per category: schedule slip needs confirmed-end after requested delivery date; missing confirmation needs an overdue unconfirmed operation; quantity shortfall needs confirmed below ordered with no open remainder; material shortage compares unrestricted stock only; status inconsistency needs two conflicting source values
- [X] T045 [P] [US2] Write `tests/unit/test_risk_negative.py` asserting `on-track`, `on-track-multilevel`, and `partially-confirmed-on-time` produce zero exceptions and `is_at_risk=false`
- [X] T046 [P] [US2] Write `tests/unit/test_severity.py` asserting the exact D12 scores for all nine rows and the tie-break order (highest score, then earliest requested delivery date, then order number)
- [X] T047 [P] [US2] Write `tests/unit/test_exception_ids.py` asserting byte-identical exception IDs across two runs with the same fixture and frozen clock
- [X] T048 [P] [US2] Write `tests/integration/test_us2_exceptions.py` mapping quickstart V6 and V7, including the portfolio scope and window disclosure
- [X] T049 [US2] Implement the five detection rules and `detect_exceptions()` in `src/cto_order_agent/domain/risk.py` returning `Exception` objects with templated facts and deterministic IDs
- [X] T050 [US2] Implement severity scoring and ordering in `src/cto_order_agent/domain/risk.py` using the published D12 table, and `RiskAssessment` assembly with `is_at_risk` derived solely from `len(exceptions) > 0`
- [X] T051 [US2] Implement `src/cto_order_agent/domain/portfolio.py` scanning open orders within the 12-month window, excluding terminal statuses, and returning a ranked list with the searched scope, window, and as-of time
- [X] T052 [US2] Render exception output in `src/cto_order_agent/presentation/planner_view.py`: category, both dates or values that triggered it, and the exception ID for cross-reference
- [X] T053 [US2] Route exception and portfolio questions in `src/cto_order_agent/a2a/executor.py`, including "which orders are at risk?" and "does this order have exceptions?"
- [X] T054 [US2] Implement the evaluation harness `eval/run_eval.py` reading every `expected_findings` sidecar, printing a per-scenario scorecard, and exiting non-zero on any false positive or false negative
- [X] T055 [US2] Verify the portfolio scan completes under 90 seconds against a generated 500-order corpus and record the measurement in `eval/RESULTS.md`

**Checkpoint**: US1 and US2 both pass independently. SC-003 assertions are green.

---

## Phase 5: User Story 3 - Risk Explanation That Separates Fact From Inference (Priority: P3)

**Goal**: Every substantive statement is labelled, every fact cites its source record and value, and
insufficient data is declared instead of papered over.

**Independent Test**: Ask why `schedule-slip` is at risk and verify label counts match substantive
sentences, every fact resolves to a source field, and `data-gap` produces an explicit insufficiency
statement.

### Tests for User Story 3 ⚠️

- [X] T056 [P] [US3] Write `tests/unit/test_evidence_bundle.py` asserting deterministic bundle IDs under a frozen clock, that `allowed_tokens` is derived only from facts and recommendations, and that a bundle with zero facts is impossible to construct
- [X] T057 [P] [US3] Write `tests/unit/test_narrative_validator.py`: accepts a narrative whose numbers all appear in `allowed_tokens`; rejects an invented date, an invented quantity, and an invented status code; asserts the retry path is invoked once before template fallback
- [X] T058 [P] [US3] Write `tests/unit/test_insufficient_evidence.py` asserting `data-gap` yields `data_completeness=INSUFFICIENT`, non-empty `missing_evidence`, and a narrative that contains no risk conclusion
- [X] T059 [P] [US3] Write `tests/unit/test_fact_labelling.py` asserting the composer emits exactly one label per substantive sentence and that no sentence is unlabelled
- [X] T060 [P] [US3] Write `tests/integration/test_us3_explanation.py` mapping quickstart V8 and V9
- [X] T061 [US3] Implement `src/cto_order_agent/domain/evidence.py` building the `EvidenceBundle`: templated `Fact` statements from records only, inferences linked to supporting fact IDs, and deterministic `allowed_tokens` generation
- [X] T062 [US3] Create versioned prompt files `src/cto_order_agent/narrative/prompts/risk_explanation.md` and `system.md` encoding the labelling contract and forbidding unsupported values
- [X] T063 [US3] Implement `src/cto_order_agent/narrative/composer.py` calling the OpenAI-compatible AI Core endpoint with `temperature=0`, `top_p=1`, fixed `max_tokens`, and a `recorded` mode that replays fixtures for tests
- [X] T064 [US3] Implement `src/cto_order_agent/narrative/validator.py`: extract every numeric, date, quantity, unit, and status token from the draft and reject any absent from `allowed_tokens`; return a structured failure, not an exception to the user
- [X] T065 [US3] Implement the deterministic template renderer fallback in `src/cto_order_agent/narrative/template_renderer.py` used when validation fails twice or `LLM_MODE=template`, producing the same fact/inference labels without a model call
- [X] T066 [US3] Wire the risk-explanation mode in `src/cto_order_agent/a2a/executor.py`: build bundle, compose, validate, fall back, and never emit an unvalidated draft
- [X] T067 [US3] Enforce research D9 in `src/cto_order_agent/narrative/composer.py`: SAP free text is passed only inside a delimited data block, truncated to 200 characters, never concatenated into system instructions, and imperative echoes are blocked

**Checkpoint**: SC-002 and SC-004 assertions pass. Unvalidated prose cannot reach a user.

---

## Phase 6: User Story 4 - Recommended Next Actions for Planners (Priority: P4)

**Goal**: Every exception yields at least one ranked, owned, verifiable action, and every request to
change data is refused with the manual alternative.

**Independent Test**: Ask for recommendations on `schedule-slip` and verify one action per exception
with owner and resolution evidence, then request an expedite and verify a read-only refusal.

### Tests for User Story 4 ⚠️

- [X] T068 [P] [US4] Write `tests/unit/test_recommendations.py` asserting one or more recommendations per exception, closed-set actions only, owner role present, urgency derived from parent severity, and ordering by urgency
- [X] T069 [P] [US4] Write `tests/unit/test_readonly_refusal.py` asserting every write-intent phrase (expedite, reschedule, release, cancel, change date, post confirmation) produces a refusal naming the read-only constraint plus the manual alternative
- [X] T070 [P] [US4] Write `tests/unit/test_tool_surface.py` asserting the registered MCP tool set contains no mutating tool and that the agent's allowed tool list equals exactly the five read tools
- [X] T071 [P] [US4] Write `tests/integration/test_us4_recommendations.py` mapping quickstart V10 and asserting the fixture corpus is byte-identical before and after the exchange
- [X] T072 [US4] Implement the closed recommendation template set in `src/cto_order_agent/domain/recommendations.py`, keyed by exception category, with owner roles and `resolution_evidence` strings
- [X] T073 [US4] Implement recommendation ranking and rendering in `src/cto_order_agent/presentation/planner_view.py`, grouping by severity and linking each action to its exception ID
- [X] T074 [US4] Implement write-intent detection and refusal in `src/cto_order_agent/a2a/executor.py`, ensuring the refusal precedes any tool call
- [X] T075 [US4] Register the `planner-recommendations` skill route and add the urgency-ordered summary line for "what is most urgent today"

**Checkpoint**: Recommendations are actionable and the read-only guarantee is test-enforced, not
prompt-enforced.

---

## Phase 7: User Story 5 - Customer-Ready Status Summary (Priority: P5)

**Goal**: A customer service representative gets a short, jargon-free summary that separates
confirmed from estimated dates and never over-promises.

**Independent Test**: Request a customer summary for `schedule-slip` and verify no internal codes or
production order numbers appear, dates are labelled confirmed or estimated, and no new date is
invented.

### Tests for User Story 5 ⚠️

- [X] T076 [P] [US5] Write `tests/unit/test_customer_summary_sanitizer.py`: strips internal status codes, production order numbers, plant codes, work centers, and material numbers; fails if any remain
- [X] T077 [P] [US5] Write `tests/unit/test_confirmed_vs_estimated.py` asserting confirmed dates carry commitment language, estimated dates carry estimate language, and an order with no confirmed date emits no commitment
- [X] T078 [P] [US5] Write `tests/unit/test_no_promise_invention.py` asserting the summary never contains a date absent from `allowed_tokens`, including the common "we will deliver by" pattern
- [X] T079 [P] [US5] Write `tests/integration/test_us5_customer_summary.py` mapping quickstart V11
- [X] T080 [US5] Implement `src/cto_order_agent/presentation/customer_summary.py` with a strict allowlist of customer-facing fields and a post-render sanitizer that fails closed on any residual internal identifier
- [X] T081 [US5] Add the customer-summary prompt at `src/cto_order_agent/narrative/prompts/customer_summary.md` and reuse the T064 validator with the same `allowed_tokens` gate
- [X] T082 [US5] Ensure customer summaries exclude internal customers and any record with `is_internal=true` in `src/cto_order_agent/presentation/customer_summary.py`
- [X] T083 [US5] Route the `customer-status-summary` intent in `src/cto_order_agent/a2a/executor.py`, defaulting ambiguous "summary" requests to the planner view and offering the customer version

**Checkpoint**: All five user stories pass independently. SC-006 is green.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Live-data seam, operations, and release hardening that no single story owns.

- [X] T084 [P] Implement the live adapter in `src/cto_order_agent/datasource/odata/client.py` mapping the canonical model to S/4HANA OData fields per `data-model.md`, with OAuth client-credentials auth and a 5-second per-call timeout
- [X] T085 [P] Implement `src/cto_order_agent/datasource/odata/mapping.py` converting OData status codes to canonical enums and raising `UPSTREAM_ERROR` on unit mismatch rather than coercing
- [X] T086 [P] Write `tests/contract/test_odata_mapping.py` using `respx` recorded responses for all five APIs, asserting field mapping, pagination, and the error taxonomy
- [X] T087 Add the SC-008 regression gate to the `Makefile`: run the full integration suite with `DATA_SOURCE=odata` against recorded responses and fail on any behavioral difference
- [X] T088 Add the provenance-blind static check to `Makefile` `check`: fail if `src/` contains `source ==`, `source==`, or a `SYNTHETIC` reference outside `datasource/mock/`
- [X] T089 [P] Implement answer-record persistence for FR-027 in `src/cto_order_agent/observability/answer_log.py`, writing the evidence bundle plus consulted sources as a structured log record keyed by task and context id
- [X] T090 [P] Add OpenTelemetry spans per A2A turn and per tool call in `src/cto_order_agent/observability/tracing.py`, keyed by `contextId`
- [X] T091 [P] Write `tests/integration/test_replay.py` asserting a logged answer record is sufficient to reconstruct every fact in a prior response
- [X] T092 [P] Create `manifest.yml` for BTP Cloud Foundry: 1 GiB, 1 instance, `/healthz` check, `DATA_SOURCE` and `LLM_MODE` env bindings, no secrets in the manifest
- [X] T093 [P] Create the Kyma alternative under `deploy/kyma/`: `Deployment`, `Service`, `APIRule`, and `ConfigMap` referencing the same image
- [X] T094 [P] Create `Dockerfile` with a digest-pinned Python 3.12 slim base, non-root user, and `uv sync --frozen --no-dev`
- [X] T095 Implement the performance harness `eval/perf.py`: 20 sequential single-order questions and one 500-order portfolio scan, printing median and p95, failing the build if median exceeds 60 s or p95 exceeds 5 min
- [X] T096 [P] Write `README.md` with the run, test, and deploy path, linking to `quickstart.md` rather than duplicating it
- [X] T097 [P] Write `AGENTS.md` recording the agent's boundaries: read-only, five tools only, provenance-blind, evidence-bundle-only narrative
- [X] T098 Execute every quickstart scenario V1–V13 manually against a clean clone and record results in `specs/001-mto-cto-order-intelligence/validation.md`
- [X] T099 Verify the 100% coverage gate on `domain/risk.py`, `domain/evidence.py`, and `narrative/validator.py` and fix any uncovered branch
- [X] T100 Run the constitution compliance gate in CI (`.github/workflows/ci.yml`): `make check`, `eval`, `fixtures/generate.py --check`, the provenance-blind check, and the secrets grep from `quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001–T009)**: No dependencies, starts immediately
- **Foundational (T010–T030)**: Depends on Setup; **BLOCKS all user stories**
- **User Stories (T031–T083)**: Each depends only on Foundational
- **Polish (T084–T100)**: Depends on the stories it hardens; T084–T088 need US1–US5 complete

### User Story Dependencies

| Story | Depends on | Notes |
|---|---|---|
| US1 (P1) | Foundational | True MVP; no cross-story dependency |
| US2 (P2) | Foundational | Consumes the US1 consolidation output but is testable standalone against fixtures |
| US3 (P3) | Foundational | Builds an evidence bundle from consolidation plus exceptions; standalone-testable on a pre-built bundle |
| US4 (P4) | Foundational | Rules key off `Exception` objects; standalone-testable with synthesized exceptions |
| US5 (P5) | Foundational | Renders from the bundle; standalone-testable with a fixture bundle |

US3, US4, and US5 each have a test seam that lets them be verified before their upstream story is
complete — build the input object directly rather than waiting. This preserves independent
testability, which is the point of the split.

### Within Each Story

1. Tests first, observed failing
2. Models and rules before rendering
3. Rendering before routing
4. Routing before the integration test turns green

### Parallel Opportunities

- Phase 1: T003, T004, T005, T007, T008, T009 in parallel
- Phase 2: T011, T012, T020, T021, T027, T028, T029 in parallel; T016 and T017 after T014
- Phase 3: T031–T034 in parallel; then T035–T037 in parallel, T038/T039 together, T040 last
- Phase 4: T044–T048 in parallel; T049/T050 share `risk.py` and must be sequential
- Phase 5: T056–T060 in parallel; T061 before T063; T064 before T066
- Phase 6: T068–T071 in parallel; T072 before T073
- Phase 7: T076–T079 in parallel; T080 before T081
- Phase 8: T084, T089, T090, T092, T093, T094, T096, T097 in parallel

### Parallel Example: User Story 2

```bash
# Five independent test files, no shared state:
Task: "Risk rule unit tests in tests/unit/test_risk_rules.py"
Task: "Negative-case tests in tests/unit/test_risk_negative.py"
Task: "Severity table tests in tests/unit/test_severity.py"
Task: "Exception ID determinism in tests/unit/test_exception_ids.py"
Task: "Integration V6/V7 in tests/integration/test_us2_exceptions.py"
```

### Parallel Example: Foundational Layer

```bash
# After T010 (models) lands, these are file-independent:
Task: "Model invariant tests in tests/unit/test_models_invariants.py"
Task: "A2A task store in src/cto_order_agent/a2a/tasks.py"
Task: "MCP schema contract test in tests/contract/test_mcp_schemas.py"
Task: "Agent card contract test in tests/contract/test_agent_card.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup
2. Phase 2 Foundational — non-negotiable, blocks everything
3. Phase 3 US1
4. **STOP and validate**: run V1–V5, demo the consolidated view
5. Ship if the timeline demands it — this alone addresses the 30-minute-to-under-5-minute goal

### Incremental Delivery

| Increment | Adds | Business value |
|---|---|---|
| 1 (US1) | Unified order view | Replaces the manual consolidation; the core 30→5 minute win |
| 2 (US2) | Exception detection | Proactive triage replaces hunting for problems |
| 3 (US3) | Grounded risk explanation | Findings become defensible in a planning meeting |
| 4 (US4) | Recommendations | Insight becomes an action |
| 5 (US5) | Customer summary | Escalation response improves |
| 6 (Polish) | Live adapter, ops | Mock-to-live swap with zero behavioral change |

Each increment is independently revertible: no migrations, no persistent schema, no write path.

### Parallel Team Strategy

1. Team completes Setup + Foundational together — this is the critical path
2. Then split: Developer A takes US1, Developer B takes US2, Developer C takes US3
3. US4 and US5 start once US1's presentation module is stable, to avoid file conflicts in `planner_view.py`
4. Polish is owned by whoever finishes last

### Critical Path

`T010 (models)` → `T016 (fixtures)` → `T018 (mock adapter)` → `T026 (main.py)` → `T031 (US1 tests)`
→ `T035 (consolidation)` → `T040 (executor wiring)` → US2 → US3.

---

## Notes

- `[P]` marks different files with no incomplete dependency — verify before parallelizing; `risk.py`
  and `planner_view.py` are shared-file hotspots that serialize their own tasks
- Tests must fail before implementation, per constitution Principle III
- Every task ends with a runnable state; commit per task or logical group
- Fixtures are generated, never hand-edited; `--check` is the gate
- Do not introduce a sixth MCP tool, a database, a queue, or an orchestration framework — all were
  rejected in research for stated reasons, and adding one requires a constitution amendment
- Stop at each checkpoint and validate the story independently before starting the next
