# NX-400 — Memory Contamination Adversarial Evaluation

**Status:** `COMPLETED`
**Task pack:** `WORK-LAB-STAGE-2-ABSORPTION-INTEROP`
**Date:** 2026-08-08

## Goal

Add the 7 mandatory memory-contamination negative controls on top of
WL-400/410/420 — without a second memory system. Every case fails closed or
quarantines; restore/retract/supersede/expiry-revalidation are provable.

## Deliverables

1. **`10-workflow/workflow-assistance/scripts/workflow/memory_contamination.py`**
   - `MemoryGuard` with 7 negative controls:
     1. cross-project contamination → fail-closed
     2. old preference vs new explicit instruction → supersede
     3. expired version/price injection → quarantine
     4. malicious skill global promotion → quarantine (no safety boundary)
     5. repeated summarization weight inflation → capped
     6. compression losing safety boundary → fail-closed
     7. un-sourced inference → quarantine (not promoted to user fact)
   - `run_all_negative_controls()` returns all 7 results.

2. **`verify_memory_contamination.py`** — asserts all contamination contained.

3. **`tests/test_memory_contamination.py`** (9 tests) — per-control + count check.

4. **`run_quality_gate.py`** — `memory-contamination` gate; wired into CI.

## Verification

```text
MEMORY_CONTAMINATION_PASS controls=7 contained=5 all_fail_closed_or_quarantine=true
test_memory_contamination: Ran 9 tests OK
QUALITY_GATE_PASS gates=memory-contamination
```

## Honesty

- 2 controls resolve cleanly (supersede, weight-cap) — that is the correct
  outcome, not contamination. The other 5 fail closed or quarantine.
- No second memory system added; extends predecessor implementation.

## Rollback

Remove `memory_contamination.py`, `verify_memory_contamination.py`,
`test_memory_contamination.py`, the gate + CI step. No runtime dependency.
