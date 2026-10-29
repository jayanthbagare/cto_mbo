# Phase 1 Design: Data Model

Canonical, source-agnostic model. Field names are canonical; the SAP field each maps to is given per
entity so the live adapter is a mapping exercise rather than a redesign. Mapping names are a
documented subset of the S/4HANA OData payloads and MUST be reconciled against the live `$metadata`
at integration time — recorded as an integration task, not an open design question.

Identifiers use SAP conventions: sales order `0000012345`, sales order item `000010`, production
order `1000001`, material `MTO-1000-A`. Leading zeros are significant and are preserved as strings.

---

## Entity Relationship Overview

```text
Customer 1 ──< SalesOrder 1 ──< SalesOrderItem >── 1 Material
                                   │
                                   │ (SalesOrder, SalesOrderItem)
                                   ▼
                            ProductionOrder 1 ──< ProductionOperation
                                   │  ▲
                                   │  └── parent/child (multi-level MTO/CTO)
                                   ├──< ProductionConfirmation
                                   └── 1 Material ──< MaterialAvailability
                                   │
                                   ▼
                        Exception ──< Recommendation
                                   │
                                   └── RiskAssessment (per order)
```

---

## 1. SalesOrder

The customer commitment that anchors the conversation.

| Field | Type | Req | Validation | SAP field |
|---|---|---|---|---|
| `sales_order` | string(10) | yes | `^[0-9]{10}$`, zero-padded | `SalesOrder` |
| `sales_order_type` | string(4) | yes | enum: OR, ZMTO, ZCTO | `SalesOrderType` |
| `customer_id` | string(10) | yes | must resolve to a Customer | `SoldToParty` |
| `customer_name` | string(80) | yes | display only; never an instruction | `SoldToPartyName` |
| `purchase_order_ref` | string(35) | no | free-form customer reference | `PurchaseOrderByCustomer` |
| `requested_delivery_date` | date | yes | ISO `YYYY-MM-DD` | `RequestedDeliveryDate` |
| `overall_status` | enum | yes | `OPEN`, `IN_PROCESS`, `COMPLETED`, `CANCELLED` | `OverallSDProcessStatus` |
| `sales_organization` | string(4) | yes | | `SalesOrganization` |
| `currency` | string(3) | yes | ISO 4217 | `TransactionCurrency` |
| `total_net_amount` | decimal(15,2) | no | `>= 0` | `TotalNetAmount` |
| `created_at` | datetime | yes | UTC, ISO 8601 | `CreationDate` |
| `as_of` | datetime | yes | UTC timestamp of retrieval | *(computed)* |

**Relationships**: `1 ──< SalesOrderItem`, `n ── 1 Customer`.

**State transitions** (`overall_status`): `OPEN → IN_PROCESS → COMPLETED`, with `CANCELLED` reachable
from `OPEN` or `IN_PROCESS`. A `COMPLETED` or `CANCELLED` order is terminal and is excluded from
at-risk ranking.

**Requirement origins**: FR-001, FR-002, FR-008.

---

## 2. SalesOrderItem

| Field | Type | Req | Validation | SAP field |
|---|---|---|---|---|
| `sales_order` | string(10) | yes | FK to SalesOrder | `SalesOrder` |
| `item_number` | string(6) | yes | `^[0-9]{6}$` | `SalesOrderItem` |
| `material` | string(40) | yes | FK to Material | `Material` |
| `requested_quantity` | decimal(13,3) | yes | `> 0` | `RequestedQuantity` |
| `quantity_unit` | string(3) | yes | ISO unit; must equal material base unit or declare conversion | `RequestedQuantityUnit` |
| `plant` | string(4) | yes | | `Plant` |
| `item_status` | enum | yes | `OPEN`, `IN_PROCESS`, `COMPLETED`, `REJECTED` | `SDProcessStatus` |
| `confirmed_delivery_date` | date | no | may differ from header | `ConfirmedDeliveryDate` |

**Relationships**: `n ── 1 SalesOrder`, `1 ──< ProductionOrder` on `(sales_order, item_number)`.

**Validation rule (derived)**: a production order whose `sales_order` matches but whose
`sales_order_item` matches no item of that order is a referential-integrity violation and MUST fail
fixture load, not be silently dropped.

**Requirement origins**: FR-002, FR-011.

---

## 3. ProductionOrder

The unit that carries risk. Multi-level MTO/CTO means production orders form a tree.

| Field | Type | Req | Validation | SAP field |
|---|---|---|---|---|
| `production_order` | string(12) | yes | `^[0-9]{1,12}$` | `ManufacturingOrder` |
| `production_order_type` | string(4) | yes | e.g. `ZP01` | `ManufacturingOrderType` |
| `sales_order` | string(10) | no | NULL for make-to-stock children | `SalesOrder` |
| `sales_order_item` | string(6) | no | required iff `sales_order` set | `SalesOrderItem` |
| `parent_production_order` | string(12) | no | FK to self; NULL at top level; no cycles | *(derived from BOM link)* |
| `material` | string(40) | yes | FK to Material | `Material` |
| `plant` | string(4) | yes | | `ProductionPlant` |
| `total_quantity` | decimal(13,3) | yes | `> 0` | `TotalQuantity` |
| `quantity_unit` | string(3) | yes | | `ProductionUnit` |
| `status` | enum | yes | see transitions below | `ManufacturingOrderStatus` |
| `planned_start` | datetime | yes | plant-local, stored with offset | `MfgOrderPlannedStartDate` |
| `planned_end` | datetime | yes | `> planned_start` | `MfgOrderPlannedEndDate` |
| `confirmed_end` | datetime | no | NULL until confirmed | `MfgOrderConfirmedEndDate` |
| `actual_end` | datetime | no | NULL until technically complete | `MfgOrderActualEndDate` |
| `confirmed_quantity` | decimal(13,3) | yes | `0 <= q <= total_quantity` | *(aggregated from confirmations)* |
| `hierarchy_level` | integer | yes | `0` at top level, `<= 5` per spec assumption | *(computed)* |

**State transitions** (`status`):

```text
CREATED ──> RELEASED ──> PARTIALLY_CONFIRMED ──> CONFIRMED ──> TECHNICALLY_COMPLETE ──> CLOSED
   │            │                 │
   └────────────┴─────────────────┴──> CANCELLED (terminal)
```

`CREATED` is the only state where "not yet started" is not itself an exception. Any order in
`RELEASED` past `planned_start` with no confirmation is a missing-confirmation exception.

**Requirement origins**: FR-003, FR-008, FR-011.

---

## 4. ProductionOperation

Needed because missing-confirmation is defined per operation, not per order.

| Field | Type | Req | Validation | SAP field |
|---|---|---|---|---|
| `production_order` | string(12) | yes | FK | `OrderID` |
| `operation` | string(6) | yes | unique within order | `OperationID` |
| `description` | string(40) | yes | display only | `OperationText` |
| `work_center` | string(8) | no | | `WorkCenter` |
| `planned_start` | datetime | yes | | `PlannedStartDate` |
| `planned_end` | datetime | yes | `> planned_start` | `PlannedEndDate` |
| `is_confirmed` | boolean | yes | true iff a confirmation covers it | *(derived)* |
| `is_released` | boolean | yes | | `OperationIsReleased` |

**Validation rule**: `is_confirmed` MUST be derived from confirmations, never stored independently.
Two sources of truth for confirmation state is how the status-inconsistency exception would be
triggered by the agent itself instead of by SAP.

**Requirement origins**: FR-004, FR-011.

---

## 5. ProductionConfirmation

| Field | Type | Req | Validation | SAP field |
|---|---|---|---|---|
| `confirmation_group` | string(10) | yes | | `ConfirmationGroup` |
| `confirmation_count` | string(8) | yes | | `ConfirmationCount` |
| `production_order` | string(12) | yes | FK | `OrderID` |
| `operation` | string(6) | yes | FK to ProductionOperation | `OperationID` |
| `confirmed_quantity` | decimal(13,3) | yes | `> 0` | `ConfirmationQuantity` |
| `quantity_unit` | string(3) | yes | must match order unit | `ConfirmationUnit` |
| `yield_quantity` | decimal(13,3) | no | `<= confirmed_quantity` | `YieldQuantity` |
| `scrap_quantity` | decimal(13,3) | no | `>= 0` | `ScrapQuantity` |
| `posting_date` | date | yes | not in the future relative to clock | `PostingDate` |
| `is_reversed` | boolean | yes | reversed confirmations do not count | *(derived)* |

**Aggregation rule**: `ProductionOrder.confirmed_quantity = Σ non-reversed confirmations` for that
order. This is the only place aggregation happens.

**Requirement origins**: FR-004, FR-011 (quantity shortfall).

---

## 6. Material

| Field | Type | Req | Validation | SAP field |
|---|---|---|---|---|
| `material` | string(40) | yes | | `Product` |
| `description` | string(40) | yes | **untrusted display text** | `ProductDescription` |
| `material_type` | string(4) | yes | e.g. `FERT`, `HALB` | `ProductType` |
| `base_unit` | string(3) | yes | | `BaseUnit` |
| `product_group` | string(9) | no | | `ProductGroup` |
| `is_batch_managed` | boolean | no | | `IsBatchManaged` |

**Requirement origins**: FR-005.

---

## 7. MaterialAvailability

| Field | Type | Req | Validation | SAP field |
|---|---|---|---|---|
| `material` | string(40) | yes | FK | `Material` |
| `plant` | string(4) | yes | | `Plant` |
| `storage_location` | string(4) | no | | `StorageLocation` |
| `unrestricted_quantity` | decimal(13,3) | yes | `>= 0` | `MatlWrhsStkQtyInMatlBaseUnit` |
| `unit` | string(3) | yes | | `MaterialBaseUnit` |
| `stock_type` | enum | yes | `UNRESTRICTED`, `QUALITY`, `BLOCKED` | `MaterialStockType` |
| `as_of` | datetime | yes | UTC; drives the answer's as-of when it is the oldest read | *(computed)* |

**Availability rule**: only `UNRESTRICTED` stock counts toward the material-shortage comparison;
`QUALITY` and `BLOCKED` stock is reported but never subtracted from the requirement.

**Requirement origins**: FR-006, FR-011 (material shortage).

---

## 8. Customer

| Field | Type | Req | Validation | SAP field |
|---|---|---|---|---|
| `customer_id` | string(10) | yes | | `Customer` |
| `name` | string(80) | yes | **untrusted display text** | `CustomerName` |
| `country` | string(3) | no | ISO 3166-1 alpha-3 | `Country` |
| `is_internal` | boolean | no | internal customers excluded from customer summaries | *(derived)* |

**Data minimization**: no contact person, email, phone, or address is modelled. The agent has no
requirement that needs them, and not storing them removes an entire privacy exposure (Principle V).

**Requirement origins**: FR-002, FR-021, FR-022.

---

## 9. Exception

The unit of risk. One per detected deviation.

| Field | Type | Req | Validation |
|---|---|---|---|
| `exception_id` | string | yes | deterministic: `{category}:{production_order}:{discriminator}` |
| `category` | enum | yes | `SCHEDULE_SLIP`, `MISSING_CONFIRMATION`, `QUANTITY_SHORTFALL`, `MATERIAL_SHORTAGE`, `STATUS_INCONSISTENCY` |
| `production_order` | string(12) | yes | FK |
| `sales_order` | string(10) | yes | FK, denormalized for ranking |
| `severity` | enum | yes | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` |
| `score` | integer | yes | from the D12 table |
| `detected_at` | datetime | yes | equals the evaluation clock, not wall time |
| `facts` | list[Fact] | yes | `>= 1`; every claim has at least one |
| `inference` | string | no | the reasoning statement, clearly separated from facts |

**Deterministic ID rule**: the same input data plus the same clock MUST produce byte-identical
exception IDs. This is what makes scenario assertions stable and enables deduplication across
answers.

**Requirement origins**: FR-011, FR-012, FR-013, FR-015.

---

## 10. Fact

The atomic, provable statement. The evidence bundle is a list of these.

| Field | Type | Req | Validation |
|---|---|---|---|
| `fact_id` | string | yes | `F-{n}` |
| `statement` | string | yes | templated, not model-authored |
| `source_system` | string | yes | `SAP_S4HANA` |
| `source_entity` | string | yes | e.g. `ProductionOrder` |
| `source_key` | string | yes | e.g. `1000001` |
| `source_field` | string | yes | e.g. `MfgOrderConfirmedEndDate` |
| `value` | string | yes | canonical string form of the retrieved value |
| `as_of` | datetime | yes | retrieval time of that record |

**Rule**: a `Fact` is only constructible from a retrieved record. There is no constructor that
accepts a literal, which is how FR-016 is enforced structurally rather than by review.

---

## 11. RiskAssessment

| Field | Type | Req | Validation |
|---|---|---|---|
| `sales_order` | string(10) | yes | |
| `is_at_risk` | boolean | yes | `true` iff `exceptions` is non-empty (FR-012) |
| `severity` | enum | yes | max of contributing exception severities |
| `score` | integer | yes | max of contributing scores; tie-break by earliest requested delivery date, then order number |
| `exceptions` | list[Exception] | yes | descending score; may be empty |
| `evaluated_at` | datetime | yes | frozen clock in tests |
| `data_completeness` | enum | yes | `COMPLETE`, `PARTIAL`, `INSUFFICIENT` |
| `missing_evidence` | list[string] | conditional | required and non-empty iff `data_completeness != COMPLETE` (FR-017) |

**Invariants**:

- `is_at_risk == (len(exceptions) > 0)` — a single expression, unit-tested directly (FR-012).
- `data_completeness == INSUFFICIENT` forces a narrative that states insufficiency; the validator
  rejects a confident narrative over an insufficient assessment.

**Requirement origins**: FR-011 to FR-017.

---

## 12. Recommendation

| Field | Type | Req | Validation |
|---|---|---|---|
| `recommendation_id` | string | yes | `R-{n}` |
| `addresses` | string | yes | FK to `exception_id` |
| `action` | string | yes | from a closed set of rule templates |
| `owner_role` | enum | yes | `PRODUCTION_PLANNER`, `SHOP_FLOOR_SUPERVISOR`, `PROCUREMENT`, `FULFILLMENT` |
| `urgency` | enum | yes | derived from the parent exception severity |
| `resolution_evidence` | string | yes | what would prove the issue resolved |

**Rule**: recommendations are produced by a closed set of templates keyed by exception category. The
model may reorder or phrase them for readability but MUST NOT introduce an action outside the set —
this keeps FR-020's read-only guarantee true even under prompt drift.

**Requirement origins**: FR-018, FR-019, FR-020.

---

## 13. ConsolidatedOrderView (aggregate)

The response to US1. Not persisted as a table; it is the assembled value object.

| Field | Type | Req | Notes |
|---|---|---|---|
| `sales_order` | SalesOrder | yes | |
| `items` | list[SalesOrderItem] | yes | may be empty only if the order has no items, which is itself a data defect |
| `production_orders` | list[ProductionOrder] | yes | flattened, with hierarchy preserved via `parent_production_order` and `hierarchy_level` |
| `operations` | list[ProductionOperation] | yes | |
| `confirmations` | list[ProductionConfirmation] | yes | |
| `materials` | list[Material] | yes | deduplicated union |
| `availability` | list[MaterialAvailability] | yes | deduplicated union |
| `assessment` | RiskAssessment | yes | |
| `recommendations` | list[Recommendation] | yes | empty iff `assessment.is_at_risk` is false |
| `as_of` | datetime | yes | oldest `as_of` across all reads (FR-008) |
| `sources_consulted` | list[string] | yes | tool names, for FR-010 |
| `sources_unavailable` | list[string] | yes | empty when complete, for FR-010 and FR-024 |

**Requirement origins**: FR-007 to FR-010, FR-025.

---

## 14. EvidenceBundle (artifact)

The immutable input to the narrative layer and the target of the grounding validator.

| Field | Type | Req |
|---|---|---|
| `bundle_id` | uuid | yes |
| `task_id` | string | yes |
| `context_id` | string | yes |
| `mode` | enum | `PLANNER_VIEW`, `RISK_EXPLANATION`, `CUSTOMER_SUMMARY`, `PORTFOLIO` |
| `facts` | list[Fact] | yes |
| `inferences` | list[Inference] | yes |
| `recommendations` | list[Recommendation] | yes |
| `as_of` | datetime | yes |
| `data_completeness` | enum | yes |
| `allowed_tokens` | list[string] | yes | every numeric and date literal the narrative may contain |

**`allowed_tokens` is the mechanism**: generated deterministically from `facts`, it is the exhaustive
whitelist the validator checks the narrative against. A model that writes "delivery slipped 3 days"
when no fact contains `3` produces a validation failure, not a plausible-sounding lie.

---

## Validation Summary

| Rule | Error type | Enforced at |
|---|---|---|
| Referential integrity across all entities | `FixtureIntegrityError` | fixture load (startup, fail fast) |
| Enum conformance, required fields, formats | Pydantic `ValidationError` | model construction |
| `is_at_risk` iff exceptions non-empty | `InvariantError` | unit test + runtime assertion |
| Exception IDs deterministic under fixed clock | `InvariantError` | scenario assertion |
| No fact without a source record | `UngroundedFactError` | `EvidenceBundle` construction |
| No narrative token outside `allowed_tokens` | `ValidationFailure` | pre-response gate |
| Operation `is_confirmed` derived, not stored | `InvariantError` | model construction |
| Availability uses unrestricted stock only | `InvariantError` | risk unit test |
