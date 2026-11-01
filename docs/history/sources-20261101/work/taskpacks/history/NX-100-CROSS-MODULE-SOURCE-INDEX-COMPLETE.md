# NX-100 — Cross-Module Source Ledger V3 / Honest Absorption Index

**Status:** `COMPLETED`
**Task pack:** `WORK-LAB-STAGE-2-ABSORPTION-INTEROP`
**Date:** 2026-08-08

## Goal

Establish an honest cross-module source index so that a *decision* status
(`adopt-now`, `adapter-next`, `reference-now`) is never presented as an
*implementation* status. 33 historical Open Design `adopt-now` sources must not
claim WORK-LAB absorption.

## Deliverables

1. **`00-governance/cross-module-source-index.json`**
   - 33 entries, one per Open Design `adopt-now` source.
   - Each marked `decisionStatus=external-optional`, `implementationStatus=not-implemented`
     (owned by `DTALEX66/DESIGN-LAB`, transferred out of WORK-LAB).
   - Accounting: `adopt_now_total=33`, `complete_in_worklab=0`,
     `partial_in_worklab=0`, `no_worklab_targets=33`.
   - Source of truth: `DESIGN-LAB/opendesign-assistance/research/global-absorption/SOURCE_REGISTRY.json`.

2. **`scripts/ci/verify_cross_module_source_index.py`**
   - Fails if an Open Design-owned source claims WORK-LAB `local-verified`.
   - Fails if a `local-verified` claim lacks real existing target paths.
   - Fails if a WORK-LAB-absorbed entry references Open Design path prefixes.
   - Reconciles adopt-now accounting (complete + partial + none = total).

3. **`tests/ci/test_cross_module_source_index.py`** (4 tests)
   - Open Design source must not claim WORK-LAB implementation.
   - local-verified requires existing target.
   - Removing a target auto-downgrades → verification fails.
   - local-verified on an existing WORK-LAB path passes.

4. **CI** `.github/workflows/work-lab-gate.yml` integration job now runs the
   cross-module index verifier + tests.

## Verification

```text
CROSS_MODULE_SOURCE_INDEX_PASS entries=33 adopt_now=33 complete=0 partial=0 none=33 honest=true
tests/ci/test_cross_module_source_index.py: Ran 4 tests OK
```

## Honesty principle

`adopt-now` is a *decision* to consider absorption; it is **not** an
implementation claim. All 33 Open Design adopt-now sources have **zero**
WORK-LAB target paths, therefore they are recorded as `not-implemented` in
WORK-LAB. Their actual implementation, if any, lives in `DESIGN-LAB`.

## Rollback

Remove `cross-module-source-index.json`, the verifier, the test, and the two CI
steps. No runtime dependency.
