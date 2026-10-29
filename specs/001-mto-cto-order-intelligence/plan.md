# Implementation Plan: MTO/CTO Sales Order and Production Order Intelligence Agent

**Branch**: `001-mto-cto-order-intelligence` | **Date**: 2026-10-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-mto-cto-order-intelligence/spec.md`

## Summary

Deliver a read-only Python agent, reachable over A2A v1.0.0, that answers production-planner
questions about SAP S/4HANA sales orders. Five MCP tools mirror the S/4HANA OData APIs and read
from an on-disk synthetic scenario corpus; the same tool interfaces are backed by real OData later
with no change to agent logic.

The defining architectural choice: **risk classification, consolidation, and evidence assembly are
deterministic Python, not model output.** The model writes narrative over an immutable evidence
bundle, and a post-generation validator rejects any number, date, or status that is not present in
that bundle. This is what makes the fact-versus-inference requirement (FR-014 to FR-017) auditable
rather than aspirational, and it is what makes the acceptance suites in SC-002 to SC-004 stable
enough to assert on.

## Technical Context

**Language/Version**: Python 3.12 (3.11 minimum; 3.12 is the deployment runtime)

**Primary Dependencies**: `a2a-sdk>=1.0` (server + client), `mcp>=2.0` (MCP Python SDK, serves
both 2025-era and 2026-07-28 protocol clients), `pydantic>=2.7`, `starlette` + `uvicorn`,
`httpx`, `structlog`, `opentelemetry-sdk`; LLM via an OpenAI-compatible client pointed at SAP AI
Core generative AI hub. Dev: `pytest`, `pytest-asyncio`, `respx`, `ruff`, `mypy`, `uv`.

**Storage**: No database. Synthetic scenarios and fixtures are version-controlled JSON on disk,
loaded read-only at startup and validated against the Pydantic models. A2A task state is an
in-process TTL map (single replica; see research D7).

**Testing**: `pytest` with three layers — unit (risk engine, validators), contract (MCP tool
schemas, A2A agent card, evidence bundle schema), integration (end-to-end conversational
scenarios over the A2A JSON-RPC binding). `respx` for OData adapter tests. A recorded-provider
mode makes LLM-free assertions possible.

**Target Platform**: Linux container on SAP BTP — Cloud Foundry as the primary target, Kyma as an
alternative manifest. Outbound-only network egress; no inbound SAP connectivity required for v1.

**Project Type**: Single project — one deployable agent service plus a co-located MCP tool server.

**Performance Goals**: Median under 60 seconds and p95 under 5 minutes for a single-order question
(SC-001); tool calls under 20 ms against fixtures; portfolio scan of 500 orders under 90 seconds;
8 tool calls per single-order answer maximum via request-scoped deduplicated caching.

**Constraints**: Hard read-only (FR-020); zero fabricated values in output (SC-004); no secrets or
personal data in logs; deterministic fixtures with a frozen clock; fully offline-capable test suite;
single replica for task affinity.

**Scale/Scope**: ~50 concurrent planner sessions; corpora of 500 orders and 2,000 production
orders; 5 MCP tools; 12 synthetic scenarios; 28 functional requirements.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Specification Before Implementation | Every FR-001…FR-028 maps to at least one task; no task exists without an FR | PASS — traceability matrix is a task-generation obligation; `data-model.md` marks requirement origins per field |
| II. Human Authority and Approval Gates | No autonomous merge, deploy, or write; production deploy requires per-instance approval | PASS — read-only by construction (FR-020); CI gates G3/G4 are human-approved |
| III. Test-First, Verification-Gated | Failing test precedes each implementation step; contract tests precede adapters | PASS — plan sequences tests before code in every phase below |
| IV. Small, Reversible, Reviewable Changes | One logical change per PR; revertible without data loss | PASS — 6 independently shippable increments; no migrations exist to roll back |
| V. Least Privilege and Explicit Tool Boundaries | Minimal credentials, no secrets in context, untrusted content treated as data | PASS — with the explicit SAP-free-text injection control in research D9 |
| VI. Observability, Traceability, Reproducibility | Pinned dependencies, structured logs, reconstructable answers | PASS — provenance recorded per answer (FR-027); lockfile and digest-pinned base image |
| VII. Simplicity and Justified Complexity | Smallest design that satisfies the spec; no abstraction without a second caller | PASS — deterministic engine instead of an agentic planner; no vector store, no orchestration framework |

**Mock Data and Test Fixtures**: PASS. Fixtures are synthetic only, `example.com` reserved
identifiers, deterministic seed 42, frozen clock at `2026-01-15T08:00:00Z`, schema-validated at
load, labeled with a synthetic header, and version-controlled. The generator is a committed script,
not hand-edited JSON, so drift is detectable.

**Development Workflow and Quality Gates**: Gates G1 (spec, passed) and G2 (plan, this document)
apply. G3 to G5 apply per increment.

No gate violations. `Complexity Tracking` is therefore empty and omitted below.

## Project Structure

### Documentation (this feature)

```text
specs/001-mto-cto-order-intelligence/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── agent-card.json
│   ├── mcp-tools.md
│   └── evidence-bundle.schema.json
├── checklists/
│   └── requirements.md  # From /speckit.specify
└── tasks.md             # Phase 2 output (/speckit.tasks - NOT created here)
```

### Source Code (repository root)

```text
src/cto_order_agent/
├── main.py                    # Process entrypoint: mounts A2A app and MCP app
├── config.py                  # Settings from env; no secrets in code or logs
├── a2a/
│   ├── agent_card.py          # AgentCard built from typed SDK models, not hand-written JSON
│   ├── executor.py            # AgentExecutor: routes turns, owns conversation context
│   └── tasks.py               # In-process task store with TTL
├── domain/
│   ├── models.py              # Canonical order, item, production order, confirmation, material
│   ├── consolidation.py       # Assembles the consolidated order view (FR-001..FR-010)
│   ├── risk.py                # The five exception categories + severity ranking (FR-011..FR-013)
│   ├── evidence.py            # Evidence bundle construction; fact/inference labels (FR-014..FR-017)
│   └── recommendations.py     # Deterministic recommendation rules (FR-018, FR-019)
├── narrative/
│   ├── composer.py            # LLM narrative over the evidence bundle
│   ├── validator.py           # Rejects ungrounded numbers, dates, statuses (FR-016)
│   └── prompts/               # Versioned system prompts
├── datasource/
│   ├── protocol.py            # DataSource port — the single swap seam (FR-026)
│   ├── mock/                  # Fixture-backed adapter, the v1 default
│   └── odata/                 # Live S/4HANA adapter, stubbed behind a flag
├── mcp_server/
│   ├── server.py              # MCPServer with five tools (streamable-http, stateless)
│   └── tools.py               # Thin tool wrappers delegating to DataSource
└── observability/
    ├── logging.py             # structlog JSON, redaction filter
    └── tracing.py             # OpenTelemetry spans keyed by A2A context id

fixtures/
├── scenarios/                 # 12 synthetic scenario bundles (labeled synthetic)
└── generate.py                # Deterministic generator, seed 42

tests/
├── contract/
├── integration/
└── unit/
```

**Structure Decision**: Single project. The agent and the MCP tool server ship as one container
because the tool server is the agent's private data boundary, not a shared service — splitting them
would add a network hop and a deployment surface without a second consumer. The `datasource`
package is the only place that knows whether data is synthetic or live, which is what makes FR-026
enforceable by a contract test that runs the whole scenario suite against both adapters.

## Phase Sequencing

Each increment is independently shippable and independently revertible.

1. **Skeleton and contracts** — A2A agent card, MCP tool schemas, evidence bundle schema,
   fixture generator. Delivers a discoverable agent that answers "not implemented".
2. **Fixture data layer** — 12 scenarios, `datasource/mock`, schema validation at load.
3. **Consolidation (US1, P1)** — unified order view, disambiguation, follow-ups. This is the MVP.
4. **Risk and evidence (US2, US3, P2/P3)** — the five categories, severity ranking, fact/inference
   labels, grounding validator.
5. **Recommendations and customer summary (US4, US5, P4/P5)** — deterministic rules plus the two
   narrative modes.
6. **Live adapter seam and hardening (P6)** — OData adapter behind the same port, regression suite
   proving zero behavioral change (SC-008), observability, deployment manifests.

## Phase 0: Outline & Research

Unknowns extracted from Technical Context and resolved in [research.md](./research.md):

| # | Topic | Resolution |
|---|---|---|
| D1 | A2A version and binding | v1.0.0, JSON-RPC binding, streaming enabled |
| D2 | MCP transport and SDK | `mcp>=2.0`, Streamable HTTP, stateless |
| D3 | Where risk logic lives | Deterministic Python engine, not model output |
| D4 | LLM provider and grounding | SAP AI Core via OpenAI-compatible client, temperature 0, validator gate |
| D5 | Date/quantity authority and clocks | Plant calendar from source; frozen clock in tests |
| D6 | Fixture strategy | Generated, seeded, schema-validated, labeled synthetic |
| D7 | A2A task state | In-process TTL store; single replica, documented limit |
| D8 | Navigation across entities | N+1 batching and request-scoped dedup |
| D9 | Prompt injection via SAP free text | Free text never enters the instruction channel |
| D10 | Deployment target | BTP Cloud Foundry primary, Kyma optional |
| D11 | Observability and replay | OpenTelemetry + evidence bundle persistence per answer |
| D12 | Severity ranking definition | Deterministic score, defined in research D12 |

## Phase 1: Design & Contracts

- [data-model.md](./data-model.md) — 11 entities, canonical field names, SAP field mapping,
  validation rules, state transitions, and the severity scale.
- [contracts/agent-card.json](./contracts/agent-card.json) — A2A v1.0.0 discovery document.
- [contracts/mcp-tools.md](./contracts/mcp-tools.md) — the five tool contracts with input/output
  schemas and error semantics.
- [contracts/evidence-bundle.schema.json](./contracts/evidence-bundle.schema.json) — the immutable
  artifact the narrative layer is allowed to describe, and the basis of the grounding check.
- [quickstart.md](./quickstart.md) — runnable validation scenarios mapped to acceptance criteria.

## Post-Design Constitution Re-Evaluation

Re-checked after Phase 1 design. All gates still pass, with two design-level mitigations worth
recording:

- **Reproducibility vs. model nondeterminism (VI).** The narrative layer is the only
  nondeterministic component. Mitigation: the evidence bundle is deterministic and fully tested;
  golden-snapshot tests assert on the bundle, not the prose; the validator makes prose divergence
  fail closed rather than silently vary. Narrative snapshots are advisory, evidence snapshots are
  binding.
- **Least privilege vs. untrusted SAP content (V).** SAP free-text fields (material descriptions,
  customer names) are attacker-influenced in a compromised or multi-tenant system. Mitigation
  D9: free text is carried only in a data channel, structurally delimited, never concatenated into
  system instructions, and the validator blocks imperative content from being echoed as agent
  instruction.

No new gate violations. `Complexity Tracking` remains empty: the design uses no orchestration
framework, no database, and no queue, and the one abstraction introduced (`DataSource`) has two
concrete callers from day one — the fixture adapter and the fixture-backed contract test — which
satisfies Principle VII rather than violating it.
