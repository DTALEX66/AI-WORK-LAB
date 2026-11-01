# NX-410 — Task Ledger Replay + Side-Effect Consistency

**Status:** `COMPLETED`
**Task pack:** `WORK-LAB-STAGE-2-ABSORPTION-INTEROP`
**Date:** 2026-08-08

## Goal

Deterministic replay harness proving that external side effects are never
duplicated and the writer is never blocked on CI/network waits.

## Deliverables

1. **`10-workflow/workflow-assistance/scripts/workflow/task_ledger_replay.py`**
   - `ReplayHarness`: deterministic state transition replay with side-effect
     idempotency (guarded by `effect_id` + `intent_digest`).
   - 8 failure scenarios:
     1. crash-mid-run → idempotent, no duplicate
     2. old-writer-revival (stale fence) → FAIL_CLOSED
     3. push-unknown → idempotent
     4. ci-no-job-4h → writer not blocked (waitpoint releases writer)
     5. rate-limited → idempotent
     6. duplicate-webhook → idempotent
     7. task-upgrade → readable/not silently mis-run
     8. corrupt-event (missing intent) → FAIL_CLOSED

2. **`verify_task_ledger_replay.py`** — runs all 8 scenarios, asserts no
   duplicate side effect and fail-closed where required.

3. **`tests/test_task_ledger_replay.py`** (8 tests).

4. **`run_quality_gate.py`** — `task-ledger-replay` gate; wired into CI.

## Verification

```text
TASK_LEDGER_REPLAY_PASS scenarios=8 pass=6 fail_closed=2 no_duplicate_side_effect=true
test_task_ledger_replay: Ran 8 tests OK
QUALITY_GATE_PASS gates=task-ledger-replay
```

## Honesty

- Never repeats external side effects (idempotency by intent).
- Never blocks the writer on CI/network waits (waitpoint releases lease).
- Old-version/corrupt tasks fail closed or explicitly migrate; never silently mis-run.

## Rollback

Remove `task_ledger_replay.py`, `verify_task_ledger_replay.py`,
`test_task_ledger_replay.py`, the gate + CI step. No runtime dependency.
