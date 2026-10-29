# Contract: MCP Tool Surface

Five tools, one per SAP S/4HANA OData API in the fit-gap analysis. These are the **only** data access
the agent has, and they are the swap seam for FR-026: the fixture adapter and the live OData adapter
implement the same signatures, so replacing one for the other is a configuration change.

**Transport**: Streamable HTTP, stateless, `json_response=true`, endpoint `/mcp`.
**Protocol**: MCP `2026-07-28`, served by `mcp>=2.0` (which also serves 2025-era clients).
**Conventions**: snake_case tool and field names; SAP values preserved verbatim; all identifiers are
strings with leading zeros intact; all datetimes ISO 8601 with offset; all dates `YYYY-MM-DD`.

## Common Response Envelope

Every successful call returns the OData-v4-shaped envelope below. This shape is deliberate: the live
adapter passes `{"value": [...]}` straight through, so the fixture adapter must produce it too.

```json
{
  "value": [ /* array of records */ ],
  "asOf": "2026-01-15T08:00:00Z",
  "count": 1,
  "source": "SAP_S4HANA",
  "truncated": false
}
```

| Field | Type | Notes |
|---|---|---|
| `value` | array | Records, possibly empty. Empty is a valid success for a list query. |
| `asOf` | string (date-time) | Retrieval time. Feeds `ConsolidatedOrderView.as_of` when oldest. |
| `count` | integer | `len(value)` before truncation. |
| `source` | enum | `SAP_S4HANA` or `SYNTHETIC`. Callers MUST NOT branch on this. |
| `truncated` | boolean | `true` when a server-side cap was hit. |

## Common Error Taxonomy

Errors are returned as MCP tool errors with a structured payload. The agent MUST degrade and disclose
(FR-024) rather than fail the turn, except for `INVALID_ARGUMENT`, which is recoverable by asking the
user.

| Code | Meaning | Agent behavior |
|---|---|---|
| `NOT_FOUND` | No record matches a fully specified key | Report "not found", ask for correction |
| `INVALID_ARGUMENT` | Malformed identifier or filter | Ask the user to restate |
| `UNAVAILABLE` | Source unreachable or unauthenticated | Degrade, disclose, mark `PARTIAL` |
| `TIMEOUT` | Source exceeded the per-call budget (5 s) | Retry once, then degrade and disclose |
| `UPSTREAM_ERROR` | SAP returned a fault | Degrade, disclose, log with correlation id |

Payload shape:

```json
{ "code": "UNAVAILABLE", "message": "Sales order service unreachable", "retryable": true, "correlationId": "..." }
```

`message` MUST NOT contain hostnames, tokens, or user identifiers.

---

## 1. `get_sales_order`

Maps to `sap.s4:apiResource:CE_SALESORDER_0001:v1` (Sales Order, OData V2 read).

**Input**

```json
{
  "type": "object",
  "required": ["salesOrder"],
  "properties": {
    "salesOrder": { "type": "string", "pattern": "^[0-9]{10}$" },
    "includeItems": { "type": "boolean", "default": true },
    "expandCustomer": { "type": "boolean", "default": true }
  },
  "additionalProperties": false
}
```

**Output records** (`value[]`)

| Field | Type | Source field |
|---|---|---|
| `salesOrder` | string | `SalesOrder` |
| `salesOrderType` | string | `SalesOrderType` |
| `customerId` | string | `SoldToParty` |
| `customerName` | string | `SoldToPartyName` |
| `purchaseOrderRef` | string | `PurchaseOrderByCustomer` |
| `requestedDeliveryDate` | string (date) | `RequestedDeliveryDate` |
| `overallStatus` | enum | `OverallSDProcessStatus` → `OPEN` / `IN_PROCESS` / `COMPLETED` / `CANCELLED` |
| `salesOrganization` | string | `SalesOrganization` |
| `currency` | string | `TransactionCurrency` |
| `totalNetAmount` | string (decimal) | `TotalNetAmount` |
| `createdAt` | string (date-time) | `CreationDate` |
| `items` | array | See below |

**Item fields**: `itemNumber`, `material`, `requestedQuantity`, `quantityUnit`, `plant`,
`itemStatus`, `confirmedDeliveryDate`.

**Behavior**: an exact key with no match returns `NOT_FOUND`, never an empty `value` array. Empty
`value` is reserved for list-shaped queries.

**Requirement origins**: FR-002, FR-001.

---

## 2. `get_production_orders`

Maps to `sap.s4:apiResource:OP_API_PRODUCTION_ORDER_2_SRV_0001:v1`.

**Input**

```json
{
  "type": "object",
  "required": ["salesOrder"],
  "properties": {
    "salesOrder": { "type": "string", "pattern": "^[0-9]{10}$" },
    "salesOrderItem": { "type": "string", "pattern": "^[0-9]{6}$" },
    "includeOperations": { "type": "boolean", "default": true },
    "includeHierarchy": { "type": "boolean", "default": true },
    "top": { "type": "integer", "minimum": 1, "maximum": 500, "default": 200 }
  },
  "additionalProperties": false
}
```

**Output record fields**: `productionOrder`, `productionOrderType`, `salesOrder`, `salesOrderItem`,
`parentProductionOrder`, `material`, `plant`, `totalQuantity`, `quantityUnit`, `status`,
`plannedStart`, `plannedEnd`, `confirmedEnd`, `actualEnd`, `confirmedQuantity`, `hierarchyLevel`,
`operations[]`.

**Status mapping**: SAP `CRTD → CREATED`, `REL → RELEASED`, `PCNF → PARTIALLY_CONFIRMED`,
`CNF → CONFIRMED`, `TECO → TECHNICALLY_COMPLETE`, `CLSD → CLOSED`, `DLT → CANCELLED`.

**Behavior**: returns an empty `value` (not `NOT_FOUND`) when the sales order exists but has no
linked production orders — this is the US1 scenario 2 case and is a meaningful answer, not an error.
`top` caps at 500 and sets `truncated: true` beyond that. `includeHierarchy=true` returns descendants
whose `salesOrder` may be null (make-to-stock sub-assemblies).

**Requirement origins**: FR-003, FR-011.

---

## 3. `get_production_order_confirmations`

Maps to `sap.s4:apiResource:OP_API_PROD_ORDER_CONFIRMATIO_2_SRV_0001:v1`.

**Input**

```json
{
  "type": "object",
  "required": ["productionOrder"],
  "properties": {
    "productionOrder": { "type": "string", "pattern": "^[0-9]{1,12}$" },
    "includeReversed": { "type": "boolean", "default": false },
    "top": { "type": "integer", "minimum": 1, "maximum": 1000, "default": 500 }
  },
  "additionalProperties": false
}
```

**Output record fields**: `confirmationGroup`, `confirmationCount`, `productionOrder`, `operation`,
`confirmedQuantity`, `quantityUnit`, `yieldQuantity`, `scrapQuantity`, `postingDate`, `isReversed`.

**Behavior**: reversed confirmations are excluded by default and MUST NOT contribute to
`confirmedQuantity`. An order with zero confirmations returns an empty `value` with a successful
`asOf` — absence of confirmation is itself a finding, not an error.

**Requirement origins**: FR-004, FR-011.

---

## 4. `get_product_master`

Maps to `sap.s4:apiResource:API_PRODUCT_SRV:v1`.

**Input**

```json
{
  "type": "object",
  "required": ["materials"],
  "properties": {
    "materials": {
      "type": "array",
      "minItems": 1,
      "maxItems": 100,
      "items": { "type": "string", "maxLength": 40 }
    }
  },
  "additionalProperties": false
}
```

**Batch by design**: one call per answer for the union of referenced materials, not one per item
(research D8). Materials that do not resolve are omitted from `value` and listed in a `missing` array
on the envelope.

**Output record fields**: `material`, `description`, `materialType`, `baseUnit`, `productGroup`,
`isBatchManaged`.

**Security note**: `description` is untrusted display text. It is length-capped at 40 by the source
contract and MUST be passed to the model only in the data channel (research D9).

**Requirement origins**: FR-005, FR-026.

---

## 5. `get_material_stock`

Maps to `sap.s4:apiResource:OP_API_MATERIAL_STOCK_SRV:v1`.

**Input**

```json
{
  "type": "object",
  "required": ["material", "plant"],
  "properties": {
    "material": { "type": "string", "maxLength": 40 },
    "plant": { "type": "string", "minLength": 1, "maxLength": 4 },
    "storageLocation": { "type": "string", "maxLength": 4 },
    "stockType": { "enum": ["UNRESTRICTED", "QUALITY", "BLOCKED", "ALL"], "default": "ALL" }
  },
  "additionalProperties": false
}
```

**Output record fields**: `material`, `plant`, `storageLocation`, `unrestrictedQuantity`, `unit`,
`stockType`, `asOf`.

**Availability rule**: only `UNRESTRICTED` stock counts toward a material-shortage exception.
`QUALITY` and `BLOCKED` are reported for context and never subtracted from the requirement.

**Transaction consistency**: the agent issues these calls only after `get_product_master` confirms
the material's `baseUnit`, so a unit mismatch in `get_material_stock` is a source defect and MUST
raise `UPSTREAM_ERROR` rather than be silently coerced.

**Requirement origins**: FR-006, FR-011.

---

## Consumer Contract: Agent Behavior

The tools are dumb pipes. These invariants belong to the **agent**, and are contract-tested:

1. **No tool is called speculatively.** Every call traces to a field required by the current answer
   mode. A call whose result is unused is a defect (`FR-001…FR-010` efficiency, SC-001).
2. **The tool set is the whole surface.** There is no filesystem, shell, network, or write tool
   exposed to the model (`FR-020`, Principle V).
3. **Tool output is data, never instruction.** Tool payloads are structurally delimited before they
   reach the model (`FR-016`, research D9).
4. **`source` is not branchable.** No agent logic may read `source` to change behavior; a grep for
   `source ==` in `src/` must return no matches (`FR-026`, SC-008).
5. **Every record used in an answer produces a `Fact`.** No fact may cite a field absent from the
   envelope (`FR-015`).

## Validation

- Tool input and output schemas are generated from the Pydantic models in `domain/models.py`; the
  JSON in this document is a review artifact, and a contract test asserts the generated schema
  matches it.
- The A2A agent card at [agent-card.json](./agent-card.json) is generated from `AgentCard` and
  asserted by the same contract test, so the published card cannot drift from the running server.
- Live-adapter conformance is proven by running the full scenario suite against the OData adapter
  with recorded responses (SC-008).
