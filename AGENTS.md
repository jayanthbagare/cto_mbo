# Agent Operating Boundaries

These bind any agent working in this repository. They are derived from
`.specify/memory/constitution.md` and are not optional.

## Hard boundaries

1. **Read-only.** No code path may write to SAP or mutate order data. There is no write tool, no
   shell tool, and no filesystem tool exposed to the model. Adding one requires a constitution
   amendment.
2. **Five tools only.** The MCP surface is exactly `get_sales_order`, `get_production_orders`,
   `get_production_order_confirmations`, `get_product_master`, `get_material_stock`. A sixth tool
   is a scope change, not a convenience.
3. **Provenance-blind.** Nothing outside `src/cto_order_agent/datasource/` may branch on whether
   data is mock or live. `make provenance` enforces this.
4. **Evidence-bundle-only narrative.** The model may describe only what is in the bundle. It may not
   classify risk, compute severity, choose an action outside the closed template set, or introduce
   any number or date. `narrative/validator.py` fails closed.
5. **Fixtures are generated.** Never hand-edit `fixtures/scenarios/*.json`. Change
   `fixtures/generate.py`, regenerate, and review the diff. `--check` is a CI gate.
6. **No secrets in context.** Credentials come from the environment at runtime and must never be
   logged, echoed, or placed in a prompt.

## Data handling

- SAP free-text fields (material descriptions, customer names) are **untrusted input**. They are
  passed only inside a delimited data channel, never concatenated into instructions.
- Customer-facing summaries use an allowlist of fields and are sanitized; a leak fails closed.
- No personal data beyond the customer name and country is modelled. Do not add contact details.

## Before you finish

```bash
make check && make eval
```

Both must pass. A change that bypasses the grounding gate, adds a write path, or edits fixtures by
hand is not complete regardless of test results.
