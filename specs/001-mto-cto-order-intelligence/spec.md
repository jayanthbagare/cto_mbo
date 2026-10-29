# Feature Specification: MTO/CTO Sales Order and Production Order Intelligence Agent

**Feature Branch**: `001-mto-cto-order-intelligence`

**Created**: 2026-10-29

**Status**: Draft

**Input**: User description: "An AI agent for Production Planners and Fulfillment Teams that consolidates SAP S/4HANA sales order and production order data, identifies delays and risks, and provides actionable recommendations through conversational intelligence."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Unified Order View for a Single Order (Priority: P1)

A production planner receives a customer escalation and has an order number. Instead of opening
several ERP transactions and cross-referencing screens by hand, the planner asks the agent about
the order in plain language and receives one consolidated answer: the sales order header, its
items, every linked production order at every level, the latest confirmations, and material
availability — all in a single response.

**Why this priority**: This is the core value and the minimum viable product. It alone removes the
20–30 minute manual consolidation that drives the business case, and every other capability builds
on the data it assembles.

**Independent Test**: Ask the agent about a known order number that has linked production orders and
verify the response contains the complete, internally consistent picture without the planner
consulting any ERP transaction.

**Acceptance Scenarios**:

1. **Given** a sales order with three linked production orders, **When** the planner asks for the
   status of that order, **Then** the response shows the sales order header, its items, all linked
   production orders with status and planned/confirmed dates, and material availability for each item.
2. **Given** a sales order with no linked production orders, **When** the planner asks for its status,
   **Then** the response explicitly states that no production orders are linked and still reports the
   sales order status.
3. **Given** an order number that does not exist, **When** the planner asks for it, **Then** the agent
   states that no such order was found and asks for a correction, without inventing any data.
4. **Given** a partial order reference that matches several orders, **When** the planner asks for it,
   **Then** the agent lists the candidate orders with enough identifying detail to disambiguate and
   asks which one is meant.
5. **Given** a consolidated answer has been shown, **When** the planner asks a follow-up such as
   "what about the second production order?", **Then** the agent answers in the context of the
   previous order without requiring the planner to repeat the order number.

---

### User Story 2 - Exception Detection Without Manual Triage (Priority: P2)

A planner needs to know which orders need attention today rather than checking each one. The agent
identifies production orders that are late, unconfirmed, inconsistent, or short of material, and
names the specific exception category that triggered each flag.

**Why this priority**: Detecting problems is the capability that turns reactive investigation into
proactive planning. It is separable from the risk narrative and delivers value on its own.

**Independent Test**: Run the agent against a known set of orders containing on-track and at-risk
examples and verify it flags exactly the at-risk ones with the correct triggering category.

**Acceptance Scenarios**:

1. **Given** a production order whose confirmed completion date is later than the customer's
   requested delivery date, **When** the order is assessed, **Then** it is flagged as at risk with
   the schedule-slip category and both dates shown.
2. **Given** a production order with an operation that has passed its planned completion date and has
   no confirmation, **When** the order is assessed, **Then** it is flagged with the missing-confirmation
   category and the overdue operation identified.
3. **Given** a fully confirmed, on-schedule production order, **When** it is assessed, **Then** it is
   NOT flagged as at risk.
4. **Given** a planner asks "which orders are at risk?", **When** the agent responds, **Then** it
   returns a ranked list of at-risk orders with their exception categories and states the scope it
   searched (which orders, which time window, as of when).
5. **Given** an order whose data sources disagree about status, **When** it is assessed, **Then** it is
   flagged with the status-inconsistency category and both conflicting values are shown.

---

### User Story 3 - Risk Explanation That Separates Fact From Inference (Priority: P3)

A planner must be able to defend what the agent says in a planning meeting. Every statement in a risk
explanation is labelled either as a confirmed fact retrieved from the system of record or as an
inference drawn by the agent, and each is backed by the specific record and value behind it.

**Why this priority**: Trust is the gating factor for adoption. An unlabelled risk claim cannot be
acted on or escalated, and the business explicitly requires confirmed facts and inferred risks to be
distinguishable.

**Independent Test**: Present an at-risk order and verify every assertion carries a fact/inference
label plus source evidence, and that an order with missing data produces an explicit
"insufficient evidence" statement rather than a guess.

**Acceptance Scenarios**:

1. **Given** an at-risk order, **When** the agent explains the risk, **Then** each statement is
   labelled as a confirmed fact or an inferred risk.
2. **Given** a confirmed fact is stated, **When** the planner asks "where does that come from?",
   **Then** the agent identifies the source record, the field, and the value, with the data's as-of time.
3. **Given** the underlying data is incomplete or stale, **When** the agent reports on the order,
   **Then** it states that evidence is insufficient and names what is missing instead of speculating.
4. **Given** the agent states a date, quantity, or status, **When** the planner compares it to the
   source record, **Then** the values match exactly.

---

### User Story 4 - Recommended Next Actions for Planners (Priority: P4)

After explaining why an order is at risk, the agent recommends concrete steps the planner can take —
what to check, whom to contact, and in what order of urgency — without taking any action itself.

**Why this priority**: Recommendations convert insight into an outcome, but they depend on detected
exceptions and a trustworthy explanation, so they follow those capabilities.

**Independent Test**: Given an at-risk order, verify the response contains at least one specific,
actionable recommendation per exception, ordered by urgency, and that no data was changed anywhere.

**Acceptance Scenarios**:

1. **Given** a missing-confirmation exception, **When** the agent recommends an action, **Then** the
   recommendation names the production order and operation to check and the type of follow-up needed
   (for example, contacting the shop-floor supervisor for a confirmation update).
2. **Given** multiple exceptions on one order, **When** recommendations are produced, **Then** they are
   ordered by urgency and each is tied to the exception it addresses.
3. **Given** the planner asks the agent to expedite, reschedule, or change an order, **When** the agent
   responds, **Then** it declines to make the change, explains that it is read-only, and offers the
   corresponding manual step.
4. **Given** a recommendation is made, **When** the planner reads it, **Then** it states who owns the
   action and what evidence would confirm the issue is resolved.

---

### User Story 5 - Customer-Ready Status Summary (Priority: P5)

A customer service representative needs to reply to a customer without exposing internal order
mechanics. The agent produces a short, jargon-free summary stating what is confirmed, what is
estimated, and what cannot yet be promised.

**Why this priority**: It directly addresses the escalation driver, but it is a presentation of
capabilities delivered in prior stories, so it ranks after them.

**Independent Test**: Request a customer summary for an at-risk order and verify it is understandable
without internal codes or internal identifiers, separates confirmed from estimated dates, and is
accurate against the underlying data.

**Acceptance Scenarios**:

1. **Given** a customer service representative asks for a customer summary, **When** the summary is
   produced, **Then** it contains no internal order numbers beyond the customer-facing sales order
   reference, no internal status codes, and no internal organizational identifiers.
2. **Given** a delivery date is an estimate rather than a confirmed commitment, **When** the summary is
   produced, **Then** the date is presented as an estimate and the confirmed position is stated.
3. **Given** the order cannot meet the requested date, **When** the summary is produced, **Then** it
   states the shortfall plainly without over-promising and without inventing a new date.

---

### Edge Cases

- **Order does not exist**: the agent says so and asks for correction; it never fabricates a partial
  answer to fill the gap.
- **Very large order** (more than 50 linked production orders): the agent summarizes by exception and
  offers the remainder on request rather than rendering an unreadable dump.
- **Multi-level production hierarchy**: sub-assemblies are shown with their parent relationship so the
  planner can see where in the chain the delay originates.
- **Partially confirmed production order**: partial quantities and dates are reported as partial, and
  the unconfirmed remainder is never presented as delivered.
- **Closed or cancelled orders**: reported as closed or cancelled, and excluded from at-risk ranking.
- **Stale or unavailable data source**: the agent discloses which source was unavailable, states how
  old the remaining data is, and does not silently present incomplete data as complete.
- **Conflicting values across sources**: both values are shown with their sources; the agent does not
  pick a winner silently.
- **Configured-to-order variants**: when materials depend on a specific configuration, the agent
  reports only the materials actually linked to that configuration and says so.
- **Ambiguous or non-numeric order reference**: the agent asks for clarification instead of guessing.
- **Requests to change data**: declined with an explanation that the agent is read-only.
- **Non-English input**: the agent responds in English and states that only English is supported.
- **Planner asks about a customer rather than an order**: the agent explains that lookup is by order
  number in this release and asks for one.

## Requirements *(mandatory)*

### Functional Requirements

**Data retrieval and consolidation**

- **FR-001**: The agent MUST accept an order reference supplied in a conversational, natural-language
  request and extract the order number from it.
- **FR-002**: The agent MUST retrieve sales order header data including customer, requested delivery
  date, overall status, and all line items with their quantities and materials.
- **FR-003**: The agent MUST retrieve every production order linked to the sales order, including all
  hierarchy levels, with status, planned and confirmed dates, quantities, and plant.
- **FR-004**: The agent MUST retrieve production confirmations per production order, including partial
  confirmations, confirmed quantities, and confirmation dates.
- **FR-005**: The agent MUST retrieve product master data for each material referenced by the order.
- **FR-006**: The agent MUST retrieve stock and availability data for each material referenced by the
  order, at the supplying plant.
- **FR-007**: The agent MUST present the retrieved data as a single consolidated view organized by
  sales order, item, and production order, rather than as separate per-source dumps.
- **FR-008**: The agent MUST state the as-of timestamp of the data in every consolidated view.
- **FR-009**: The agent MUST maintain conversational context so follow-up questions refer to the order
  and entities under discussion without requiring repetition.
- **FR-010**: The agent MUST disclose which data sources were consulted for a given answer and which,
  if any, were unavailable.

**Exception detection and risk**

- **FR-011**: The agent MUST classify an order as at risk when at least one of these conditions holds,
  and MUST name the condition: schedule slip (confirmed or planned completion after the requested
  delivery date), missing confirmation (an operation past its planned completion date with no
  confirmation), quantity shortfall (confirmed quantity below ordered quantity without a compensating
  open quantity), material shortage (available stock below open requirement at the required date), or
  status inconsistency (conflicting status across linked records).
- **FR-012**: The agent MUST NOT classify an order as at risk when none of the FR-011 conditions hold.
- **FR-013**: The agent MUST produce a ranked list of at-risk orders when asked for one, ordered by
  severity, and MUST state the scope and time window that was searched.

**Transparency and evidence**

- **FR-014**: The agent MUST label every substantive statement as a confirmed fact or an inferred risk.
- **FR-015**: The agent MUST attach evidence to every risk claim: the source record, the field, the
  value, and the data's as-of time.
- **FR-016**: The agent MUST NOT present a value, date, quantity, or status that does not exist in the
  retrieved data.
- **FR-017**: When evidence is insufficient to support a conclusion, the agent MUST say so explicitly
  and name the missing evidence rather than inferring on thin data.

**Recommendations and safety**

- **FR-018**: The agent MUST provide at least one specific recommended action for each detected
  exception, with the owning role and the evidence that would confirm resolution.
- **FR-019**: The agent MUST order recommendations by urgency and tie each to the exception it addresses.
- **FR-020**: The agent MUST operate read-only and MUST decline requests to create, change, release,
  reschedule, or delete data, explaining the manual alternative instead.
- **FR-021**: The agent MUST restrict retrieved data to what the requesting user is authorized to see and
  MUST NOT expand that visibility through aggregation or inference.

**Customer-facing output**

- **FR-022**: The agent MUST produce a customer-ready summary on request that contains no internal
  status codes, internal identifiers, or internal organizational details.
- **FR-023**: The agent MUST distinguish confirmed dates from estimated dates in every customer-facing
  summary.

**Operational**

- **FR-024**: The agent MUST answer a single-order request end to end within 5 minutes, and MUST
  continue to respond when one data source is unavailable by degrading and disclosing the gap.
- **FR-025**: The agent MUST be demonstrable end to end using representative synthetic order scenarios
  covering on-track, at-risk, and delayed cases before live enterprise data is connected.
- **FR-026**: The agent MUST allow its data source to be switched from synthetic scenarios to live
  enterprise data without any change to conversational behavior, outputs, or user-visible rules.
- **FR-027**: The agent MUST record, for each answer, which data was consulted and which conclusions
  were derived, so the answer can be reconstructed afterward.
- **FR-028**: The agent MUST respond in English and MUST state that other languages are not supported
  when the request is made in another language.

### Key Entities *(include if feature involves data)*

- **Sales Order**: A customer commitment. Key attributes: order number, customer, requested delivery
  date, overall status, and its line items.
- **Sales Order Item**: A line on the sales order. Attributes: item number, material, ordered quantity,
  requested date, plant. Links to one or more production orders.
- **Production Order**: A manufacturing instruction fulfilling a sales order item. Attributes: order
  number, material, quantity, plant, status, planned and confirmed dates, and hierarchy level relative
  to a parent production order.
- **Production Operation**: A step within a production order. Attributes: operation number, planned
  start and completion, and confirmation state.
- **Production Confirmation**: A record of work actually completed. Attributes: confirmed quantity,
  confirmation date, and the operation or order it applies to. May partially cover an order.
- **Material (Product Master)**: The item being produced or consumed. Attributes: material number,
  description, unit of measure, and product type.
- **Material Availability**: Stock position for a material at a plant at a point in time. Attributes:
  available quantity, unit, plant, and as-of time.
- **Exception**: A detected deviation belonging to one of the five FR-011 categories, attached to a
  specific production order and carrying its supporting evidence.
- **Risk Assessment**: The judgement that an order is at risk, with severity, the contributing
  exceptions, and the fact-versus-inference split.
- **Recommendation**: A proposed next action tied to an exception, with an owning role and a
  confirmation condition.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A planner obtains a complete consolidated order status in under 5 minutes measured from
  question to answer, against a baseline of about 30 minutes, with a median of under 60 seconds for a
  single order.
- **SC-002**: 100% of substantive statements in an agent response are labelled as confirmed fact or
  inferred risk, verified across the evaluation scenario set.
- **SC-003**: The agent identifies 100% of orders deliberately designed as at risk in the evaluation
  set, and flags no more than 5% of deliberately on-track orders as at risk.
- **SC-004**: 100% of risk claims trace to a retrievable source record, field, and value; zero
  fabricated values appear across the evaluation set.
- **SC-005**: 8 out of 10 planners, on first use without training, complete a full order consolidation
  and correctly state the order's risk position.
- **SC-006**: 90% of customer-facing summaries are judged usable without editing by a customer service
  reviewer.
- **SC-007**: Planners report a reduction in time spent per order investigation of at least 70%
  relative to the 30-minute baseline.
- **SC-008**: Switching the data source from synthetic scenarios to live enterprise data produces zero
  behavioral differences across the full regression scenario set.
- **SC-009**: Every detected exception is accompanied by at least one recommendation that a planner
  rates as actionable, for at least 90% of exceptions in the evaluation set.

## Assumptions

- **Interaction language**: English only for this release. Translated output is out of scope.
- **Primary lookup key**: Order number. Lookup by customer name, material, or free-text portfolio
  description is out of scope for this release and is handled by asking the planner for an order number.
- **Risk definition**: The five FR-011 categories are the complete definition of "at risk" for this
  release. A configurable risk threshold engine is out of scope.
- **Portfolio scope**: On-demand ranking of at-risk orders is in scope for open orders within a
  12-month window. Scheduled, unattended push alerting to planners is out of scope for this release.
- **Read-only by design**: No write-back to the enterprise system of record. Approval workflow,
  scheduling changes, and confirmations posting are out of scope.
- **Date and quantity authority**: The enterprise system of record is authoritative for all dates and
  quantities; the agent never computes a delivery promise independently of it.
- **Synthetic data**: Realistic synthetic scenarios covering on-track, at-risk, delayed, multi-level,
  and partially confirmed orders are delivered as part of this feature so acceptance can be evaluated
  before live connectivity. They are synthetic only and contain no production data.
- **Authentication and authorization**: Users are already authenticated, and their visibility matches
  their existing enterprise roles. Identity provisioning is out of scope.
- **Live connectivity**: Network access, credentials, and authorizations for live enterprise data are
  prepared in parallel and are not a dependency for acceptance of this release.
- **Timing and calendars**: Dates are interpreted in the plant's time zone using the enterprise
  planning calendar; plant-specific calendar rules are consumed from the system of record, not
  reimplemented.
- **Volume**: Typical orders have up to 10 linked production orders and up to 5 hierarchy levels; orders
  beyond 50 linked production orders are summarized by exception.
- **Unavailable interfaces**: Production routing, production version, sales order change history,
  customer material information, bill of materials, and business partner master data interfaces are
  excluded from this release because they are not available in the target landscape.
