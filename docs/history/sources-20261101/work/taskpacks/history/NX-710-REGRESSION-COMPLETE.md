# NX-710 — Size, Performance & Boundary Regression

**Status:** `COMPLETED`
**Task pack:** `WORK-LAB-STAGE-2-ABSORPTION-INTEROP`
**Date:** 2026-08-08

## Goal

Produce a real local regression report for tree size, representative gate
latency, dedup/unknown-cost semantics, contamination controls, Observer
mutation surface, and human-calibration boundaries. No network or provider
calls are used.

## Deliverables

1. **`scripts/ci/regression_report.py`**
   - current tracked file/byte counts and parent-commit baseline metadata;
   - p50/p95/max measurements for usage rollup, design contract, and three-way
     offline pilot;
   - token dedup and unknown-cost checks;
   - memory contamination count, Observer mutation surface, human calibration;
   - network/credential/external-write boundary flags and node_modules check.

2. **`scripts/ci/verify_regression_report.py`** — validates size, bounded
   latency, quality semantics, boundaries, and calibration status.

3. **`tests/ci/test_regression_report.py`** — 4 tests.

4. Integration CI wiring.

## Verification

```text
REGRESSION_REPORT_PASS tracked_files=378 tracked_bytes=2500789 rollup_p95_ms=0.081 contract_p95_ms=0.035 pilot_p95_ms=0.249 dedup=ok unknown=preserved contamination=7 mutation_surface=empty calibration=pending
Ran 4 tests in 0.185s — OK
```

The report records a comparable parent-commit baseline status when available;
it does not invent a historical measurement that was not captured.

## Honesty and boundaries

- Timings are local fixture measurements, not production SLO claims.
- Human visual calibration remains pending.
- No node_modules, downloaded binaries, credentials, external writes, or live
  provider calls are introduced.

## Rollback

Remove the report, verifier, tests, CI steps, handoff, and ledger entry.
