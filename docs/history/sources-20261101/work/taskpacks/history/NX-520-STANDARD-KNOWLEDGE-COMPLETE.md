# NX-520 — Standards Knowledge & Master-Evidence Association

**Status:** `COMPLETED`
**Task pack:** `WORK-LAB-STAGE-2-ABSORPTION-INTEROP`
**Date:** 2026-08-08

## Goal

Convert the required standards into sourced, searchable, testable local
knowledge/validators rather than copying web pages. Associate predecessor
master-evidence cards without allowing ungated evidence to produce
`authoritative` or `commercial-ready` conclusions.

## Standards covered

- WCAG 2.2
- ARIA Authoring Practices Guide
- CLREQ
- JLREQ
- Ghent PDF/X print preflight
- Smithsonian accessible exhibition guidance
- NPS exhibition accessibility
- GOV.UK Service Manual
- 18F Methods
- Plain Language Guidelines

## Deliverables

1. **`10-workflow/workflow-assistance/scripts/workflow/standard_validators.py`**
   - ten sourced validators with transferable rule descriptions;
   - case-insensitive searchable index;
   - deterministic per-rule coverage and pass/fail results;
   - versioned master-evidence association;
   - source gate required before authoritative readiness.

2. **`verify_standard_validators.py`** — validates source presence, rule
   coverage, searchability, and source-gated evidence behavior.

3. **`tests/test_standard_validators.py`** — 8 tests covering full/partial
   coverage, unknown inputs, search, source gates, and schema versioning.

4. **`run_quality_gate.py`** — `standard-validators` gate; wired into CI and
   `VERIFY_ORDER`.

## Verification

```text
STANDARD_VALIDATORS_PASS standards=10 sourced=true searchable=true testable=true authoritative_source_gated=1
Ran 8 tests in 0.000s — OK
QUALITY_GATE_PASS gates=standard-validators
```

## Honesty and boundaries

- These are local rule/validator representations with source labels, not copied
  webpages and not a claim of legal or certification authority.
- Master evidence that has not passed the source gate cannot become
  authoritative/commercial-ready.
- Generation guidance is expressed as transferable methods; no signature style
  or specific artwork composition is copied.

## Rollback

Remove the two validator scripts, the test, this handoff, the quality-gate/CI
wiring, and the ledger entry. No runtime provider or external mutation is used.
