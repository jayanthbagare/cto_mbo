# Quickstart Validation Guide

Runnable scenarios that prove this feature satisfies
[spec.md](./spec.md). This is a validation and run guide — no implementation code, no test bodies, no
migrations. Implementation lives in `tasks.md` and the source tree.

Every scenario below maps to a user story, requirement, or success criterion. A release is not
acceptable unless every scenario in **Validation Scenarios** passes.

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.12 | 3.11 works; 3.12 is the deployment runtime |
| `uv` | latest | Dependency and virtualenv management |
| Docker (optional) | 24+ | Only for the container parity check |
| Network | off for tests | The full suite must pass with no egress |
| LLM endpoint | optional | Tests run recorded; live calls are needed only for V10 |

No SAP system, BTP account, or network access is required for any scenario except the optional live
adapter check.

## Setup

```bash
uv sync --frozen
uv run python fixtures/generate.py --seed 42 --check   # verify fixtures match the generator
```

`--check` must exit 0 and leave `git status --short fixtures/` empty. If it does not, the committed
corpus has drifted from its generator and the corpus must be regenerated, not hand-edited
(constitution: *Mock Data and Test Fixtures*).

### Configuration

All settings come from environment variables; there are no defaults for secrets and no secret may be
committed. Minimum set for local runs:

| Variable | Purpose |
|---|---|
| `DATA_SOURCE` | `mock` (default) or `odata` |
| `LLM_MODE` | `recorded` (default in tests), `live`, or `template` |
| `AI_CORE_BASE_URL` | OpenAI-compatible endpoint (`live` mode only) |
| `AI_CORE_CLIENT_ID` / `_SECRET` | Credentials, injected at runtime, never in `.env` committed to git |
| `PROCESS_CLOCK` | Fixed instant for deterministic runs; defaults to `2026-01-15T08:00:00Z` |

## Run Locally

```bash
make run          # starts the A2A server (:8080) and the MCP tool server (:8081) in one process
make check        # ruff + mypy + pytest: unit, contract, integration
make test-unit    # risk engine, validators, consolidation
make test-contract# MCP schemas, A2A agent card, evidence bundle schema
make test-int     # end-to-end conversational scenarios over A2A JSON-RPC
make eval         # runs the full scenario corpus and prints the SC scorecard
```

Expected first-run signal from `make check`: all green in under 2 minutes, with no network access. If
anything requires egress, the test is wrong, not the environment.

## Smoke Test

Discover the agent, then ask one question.

```bash
curl -s localhost:8080/.well-known/agent-card.json | jq '.skills[].id'
```

Expected: the five skill ids from [agent-card.json](./contracts/agent-card.json) —
`unified-order-view`, `exception-detection`, `risk-explanation`, `planner-recommendations`,
`customer-status-summary`.

```bash
curl -s localhost:8080/a2a \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"Status of sales order 0000012345"}]}}}' \
  | jq '.result.artifacts[0].parts[0].text'
```

Expected: a consolidated view naming the order, its items, all linked production orders with dates,
and an `As of` line. No exception dump, no placeholder text.

## Validation Scenarios

The corpus uses fictional, synthetic data only (`example.com`, `555-01xx`, seed 42).

### V1 — Unified order view (US1, FR-002/003/007/008, P1)

**Ask**: `Status of sales order 0000012345` (scenario `on-track`).

**Pass when**: response contains the header, every item, every linked production order at every
level, an `As of` timestamp, and the two link types (item → production order) are consistent.

### V2 — Order without production orders (US1 #2)

**Ask**: `Status of sales order 0000012350` (scenario `no-production-orders`).

**Pass when**: the response states that no production orders are linked, still reports the sales
order status, and does not imply an error or missing data.

### V3 — Order not found (US1 #3, FR-016)

**Ask**: `Status of sales order 0000099999`.

**Pass when**: the response says no such order exists and asks for a correction. It must contain no
invented order detail.

### V4 — Ambiguous reference (US1 #4)

**Ask**: `What about order 1234?` (prefix matching several orders).

**Pass when**: the agent lists the candidates with distinguishing detail and asks which is meant. It
must not pick one.

### V5 — Follow-up context (US1 #5, FR-009)

**Ask**: `Status of 0000012345`, then `What about the second production order?`

**Pass when**: the second answer refers to the same order and the second production order without
repeating the order number.

### V6 — Exception detection and negative case (US2, FR-011/012, SC-003)

```bash
make eval   # runs all 12 scenarios and prints per-scenario findings
```

**Pass when**: all 6 deliberately at-risk scenarios are flagged with the correct category, the 3
on-track scenarios are not flagged, and 3 closed/cancelled scenarios are excluded. Zero false
positives on `on-track`, `on-track-multilevel`, and `partially-confirmed-on-time`.

### V7 — Portfolio ranking (US2 #4, FR-013, D12)

**Ask**: `Which orders are at risk this week?`

**Pass when**: orders are ordered by descending score exactly as the D12 table dictates, ties break
by earliest requested delivery date, and the response states the scope, window, and as-of time.

### V8 — Fact versus inference labelling (US3, FR-014/015, SC-002)

**Ask**: `Why is order 0000012346 at risk?`

**Pass when**: every substantive sentence carries a fact or inference label; every fact quotes a
source entity, field, and value; the count of labels equals the count of substantive sentences
(the eval asserts this, so a partially labelled answer fails).

### V9 — Insufficient evidence (US3 #3, FR-017)

**Ask**: `Why is order 0000012352 at risk?` (scenario `data-gap`, one source unavailable).

**Pass when**: the agent explicitly states that evidence is insufficient, names the missing source
and how stale the rest is, and does not assert a risk conclusion. A confident answer here is a
failure even if the conclusion happens to be right.

### V10 — Recommendations and read-only refusal (US4, FR-018/019/020)

**Ask**: `What should I do about 0000012346?` then `Can you expedite it for me?`

**Pass when**: each exception yields at least one recommendation with an owning role and a
resolution condition, ordered by urgency; the expedite request is declined with an explanation that
the agent is read-only, plus the manual alternative. The eval additionally asserts that no state
changed anywhere in the tool layer.

### V11 — Customer summary (US5, FR-022, FR-023, SC-006)

**Ask**: `Give me a customer-ready update for 0000012346`.

**Pass when**: the summary contains no internal status codes, no production order numbers, no plant
or work-center identifiers; confirms explicitly which dates are committed versus estimated; states
the shortfall plainly without inventing a date.

### V12 — Data source swap (FR-026, SC-008)

```bash
DATA_SOURCE=odata LLM_MODE=recorded uv run pytest tests/integration -q
```

Runs the identical scenario suite against the recorded OData adapter.

**Pass when**: 100% of behavioral assertions pass unchanged. Also verify the seams statically:

```bash
! grep -rn "source ==\|source==" src/          # no branching on data provenance
! grep -rn "SYNTHETIC" src/ --include=*.py | grep -v tests
```

### V13 — Performance (SC-001, FR-024)

```bash
make perf   # 20 sequential single-order questions against the fixture adapter
```

**Pass when**: median under 60 s and p95 under 5 min (fixture adapter should be well under 5 s;
the budget matters for the live adapter). Also confirm a 500-order portfolio scan completes under
90 s.

## Quality Gate Checklist

Run before requesting review. Each line is a command whose exit code is the verdict.

| Gate | Check |
|---|---|
| Tests first | Every FR has a test that failed before the implementation commit |
| Suite green | `make check` exits 0 |
| Coverage | Risk engine and validator modules at 100% line coverage |
| Grounding | `make eval` reports zero ungrounded tokens across all scenarios |
| Fact labelling | SC-002 assertion passes with zero unlabelled substantive sentences |
| Mock data law | `fixtures/generate.py --check` exits 0; every fixture carries the synthetic header |
| Secrets | `git grep -nIE '(secret\|token\|password)\s*=' -- src/ fixtures/` returns nothing sensitive |
| Provenance | No `source ==` branching in `src/` |
| Reproducibility | `uv sync --frozen` then `make check` on a clean clone |
| Container | `docker build` then `make smoke` passes with `DATA_SOURCE=mock` |
| Constitution | CI prints the compliance check result and it is green |

## Troubleshooting

| Symptom | Cause | Action |
|---|---|---|
| Every answer says "insufficient evidence" | Fixture load failed referential integrity | Read the startup `FixtureIntegrityError`; fix the generator, not the JSON |
| `V8` labelling count mismatch | A narrative template emits an unlabelled sentence | Fix the template renderer; the validator should have caught it — file the gap |
| `V9` returns a confident answer | `missingEvidence` empty while `dataCompleteness` is `PARTIAL` | Schema violation; the bundle builder is wrong |
| Fixture check reports a diff | Someone hand-edited fixtures | Regenerate with the committed generator and review the diff |
| `V12` differs from `V1` | Adapter leaked into agent logic | Find the branch; `src/` must be provenance-blind |
| Live mode times out | Missing egress or AI Core credentials | Set `LLM_MODE=template` to confirm the rest of the path, then fix connectivity |
| Agent card 404 | Server started without the well-known route | Check `make run` startup log for the mounted routes |

## Out of Scope for This Guide

Live SAP connectivity, BTP deployment verification, load testing beyond the 500-order scan, and
unattended push alerting. These are validated during integration and are tracked as deferred items
in the spec Assumptions.
