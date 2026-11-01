# Fixed-wall-clock Cron Verification

## When to use

Use when a recurring project writer must fire on stable clock boundaries and the user reports that update, resume, or manual run restarted the countdown.

## Safe sequence

1. Read the current clock, job fields, Gateway status, project `state.json`, and the activity ledger tail.
2. If the cadence is a relative interval such as `every 10m`, recognize that configuration or dispatch operations may recalculate `next_run_at` relative to the operation time.
3. Convert the job to an equivalent wall-clock cron expression, for example `*/10 * * * *`, while preserving the pinned model/provider, workdir, prompt, and single-writer rules.
4. Verify `next_run_at` is the next ten-minute boundary. Do not manually run while proving the next natural tick.
5. At the boundary, verify all three layers:
   - scheduler: `last_run_at`, `last_status`, and next boundary;
   - execution plane: Gateway/cron status and execution output;
   - project plane: state heartbeat, active task, activity start/progress/complete or blocked event, and real file/test evidence.
6. If pausing is required for cleanup, record the old schedule and keep the pause scoped. Resume with the fixed-wall-clock expression rather than assuming an interval preserves the old phase.

## Evidence rule

`update`, `resume`, `run`, `scheduled`, and `success=true` are control-plane evidence only. They do not prove that the project writer advanced. Require a fresh project ledger event and real task evidence before claiming progress.

## Cleanup interaction

When reclaiming build caches, freeze the project writer first, delete exact regenerable target directories only, re-scan retained runtime/evidence paths, then resume without an extra manual run. Keep browser caches and active WebView/runtime profiles unless a separate retention decision proves they are disposable.
