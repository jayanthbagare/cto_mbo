# MTO/CTO Order Intelligence Agent

A read-only agent for production planners and fulfillment teams. Ask about a sales order in plain
language and get one consolidated view of the sales order, its linked production orders,
confirmations, and material availability — plus detected exceptions, evidence-backed risk
explanations, and ranked next actions.

Built to the specification in
[`specs/001-mto-cto-order-intelligence/`](specs/001-mto-cto-order-intelligence/spec.md).

## What makes it trustworthy

Risk classification, consolidation, and evidence assembly are **deterministic Python**, not model
output. The model writes prose over an immutable evidence bundle, and a validator rejects any
number, date, or status that is not present in the retrieved data. If validation fails twice, the
agent falls back to a deterministic template rather than shipping an unsupported claim.

## Quick start

```bash
uv sync --all-extras
uv run python fixtures/generate.py --check   # corpus integrity
uv run python -m cto_order_agent.main         # http://localhost:8080
```

```bash
curl -s localhost:8080/.well-known/agent-card.json | jq '.skills[].id'
```

Ask a question:

```bash
curl -s localhost:8080/a2a \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{
       "message":{"role":"user","parts":[{"kind":"text",
       "text":"Status of sales order 0000012345"}]}}}' \
  | jq -r '.result.task.artifacts[0].parts[0].text'
```

## Validate

```bash
make check        # lint + type check + fixtures + full test suite
make eval         # scenario scorecard (14 orders, 12 scenarios)
make perf         # latency budgets
```

See [quickstart.md](specs/001-mto-cto-order-intelligence/quickstart.md) for the full validation
guide (V1–V13), including the data-source swap check.

## Architecture

```text
A2A (JSON-RPC 1.0.0)  ──►  AgentExecutor
                              ├── nlu/           intent + order reference (no model)
                              ├── domain/        consolidation → risk rules → evidence
                              ├── narrative/     model prose + grounding gate
                              └── presentation/  planner view, customer summary
                                        │
                              DataSource port (the swap seam)
                                        ├── mock/   synthetic fixtures (v1)
                                        └── odata/  live S/4HANA (same shapes)
                                        │
                              MCP (5 read-only tools, streamable HTTP)
```

## Layout

| Path | Purpose |
|---|---|
| `src/cto_order_agent/domain/` | Canonical models, consolidation, risk rules, evidence, recommendations |
| `src/cto_order_agent/narrative/` | Model composition and the grounding validator |
| `src/cto_order_agent/datasource/` | The only code that knows mock from live |
| `src/cto_order_agent/mcp_server/` | Five tool contracts |
| `fixtures/` | Generated synthetic corpus (seed 42, frozen clock) |
| `eval/` | Scenario scorecard and performance harness |
| `deploy/kyma/` | Kyma alternative to the Cloud Foundry manifest |

## Read-only guarantee

The agent has no write tool, no filesystem or shell access, and no path that mutates order data. The
tool surface is contract-tested to stay at exactly five read tools.

## Known limitations

- **Single replica.** A2A task state is in-process with a 30-minute TTL. Horizontal scaling requires
  externalizing the task store.
- **Portfolio enumeration.** `list_order_refs` is a data-port capability, not one of the five MCP
  tools; the live adapter implements it as an OData list query.
- **OData field names** must be reconciled against the live `$metadata` at integration time.
- **Streaming** is a single terminal event, not incremental token streaming.
