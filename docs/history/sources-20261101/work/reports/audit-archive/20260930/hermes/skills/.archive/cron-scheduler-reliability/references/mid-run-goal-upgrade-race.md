# Mid-run goal upgrade race: recovery checklist

Use this reference when a durable cron writer is already scheduled and the user changes the final delivery target or authorization.

## Observable race pattern

A queue may be `blocked` while the cron remains enabled. Pausing near a wall-clock boundary can race with a tick that already started: `pause` succeeds, then `last_run_at`, `state.json`, or the append-only ledger advances once more. A subsequent state write can warn that the file changed externally.

Do not treat this as proof of corruption and do not overwrite repeatedly. The durable ledger is the arbitration source.

## Safe sequence

1. Pause the exact job ID; do not create a replacement job.
2. Re-read cron `last_run_at`/`next_run_at`, state, ledger tail, Git status/index tree, and writer lock.
3. If a late tick appears, preserve its ledger event and reconcile its state fields before applying the new target.
4. Write the single-object state atomically; append—not rewrite—the goal-change JSONL event.
5. Update the job’s self-contained prompt, name, workdir, skills, cadence, and user-selected model/provider pin. The agent-facing cron API may not expose model/provider mutation; use `hermes cron edit <job> --model <model> --provider <provider>` and verify with a fresh list/readback.
6. Resume. For an immediate-progress request, dispatch one manual cycle only when no run is active.
7. Verify progress from a fresh state plus ledger event. `success=true`, `executed=true`, or `last_status=ok` proves dispatch/terminal status only.

## Goal taxonomy

Record authorization independently for:

- local implementation and tests;
- commit/push;
- PR creation and merge;
- immutable version tag;
- GitHub Release publication;
- artifact upload;
- production deployment.

A version-level release requires exact tag target, post-merge exact-SHA gates, retained downloadable assets, checksums/provenance, release notes/metadata, and provider-side readback. A green PR or merged `main` is not a version release.

## Parallelism boundary

“Run agents in parallel” means one checkout writer plus concurrent read-only audits/reviews, or isolated worktrees with explicit ownership. Never resume the cron writer while a foreground agent is modifying the same checkout. Control-plane state/ledger reconciliation may be performed by the orchestrator only while the writer is paused.
