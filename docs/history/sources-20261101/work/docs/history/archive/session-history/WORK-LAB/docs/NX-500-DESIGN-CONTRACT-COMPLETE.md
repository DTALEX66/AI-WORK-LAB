# NX-500 — Design Core Contract Adaptation (DTCG / DESIGN.md)

**Status:** `COMPLETED`
**Task pack:** `WORK-LAB-STAGE-2-ABSORPTION-INTEROP`
**Date:** 2026-08-08

## Goal

A structured brief passes contract checks, produces token/method/quality-gate
selection, and completes a lossless readback after delivery. Local WORK-LAB
contract layer — does not vendor Open Design app code.

## Deliverables

1. **`10-workflow/workflow-assistance/scripts/workflow/design_contract.py`**
   - `DtcgRoundTrip`: DTCG token import/export/lint with lossless round-trip.
   - `DesignContractChecker`: parses a structured brief, produces token/method/
     quality-gate selection, runs contract check, and returns a readback
     (lossless + brief digest).
   - Supports DTCG token types (color/dimension/number/fontFamily/fontWeight/
     duration/cubicBezier/shadow).

2. **`verify_design_contract.py`** — brief contract check + DTCG round-trip probe.

3. **`tests/test_design_contract.py`** (7 tests) — round-trip lossless, lint
   (unknown type / duplicate), brief passes/fails, readback digest stability.

4. **`run_quality_gate.py`** — `design-contract` gate; wired into CI.

## Verification

```text
DESIGN_CONTRACT_PASS tokens=2 methods=2 gates=2 readback=lossless dtcg=roundtrip
test_design_contract: Ran 7 tests OK
QUALITY_GATE_PASS gates=design-contract
```

## Honesty

- Never just a doc directory: a brief produces real tokens/methods/gates and a
  lossless readback.
- Local contract only; Open Design app code not copied.

## Rollback

Remove `design_contract.py`, `verify_design_contract.py`, `test_design_contract.py`,
the gate + CI step. No runtime dependency.
