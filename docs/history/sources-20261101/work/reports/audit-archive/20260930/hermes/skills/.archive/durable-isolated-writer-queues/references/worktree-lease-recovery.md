# Worktree lease recovery pattern

## Failure signature

A scheduled writer can appear healthy while the interactive checkout is actually being mutated. The decisive evidence is a mismatch between the expected worktree/branch and live `git status --short --branch`, especially a branch switch plus staged WIP. A successful scheduler dispatch does not prove the intended project advanced.

## Recovery sequence

1. Pause the one active job. Do not trigger a second run, reset, clean, or switch the dirty checkout.
2. Read the job record, Gateway/cron status, writer `state.json`, activity tail, `git status`, `git diff --cached --stat`, and `git worktree list` in parallel.
3. Classify the WIP. If it is coherent, preserve it and validate its frozen tree; if ownership or scope is unclear, leave it blocked for review.
4. Complete the current candidate in the single foreground owner: run tree identity, diff, conventions, lock, targeted tests, and lint. Commit/push only after the candidate is frozen and the scope is reviewed.
5. Create a separate writer worktree from `origin/main` or the reviewed candidate, using a distinct branch such as `sleep/continuous-writer`.
6. Initialize the new worktree's append-only sleep ledger and update the one cron job's exact `workdir` and self-contained prompt. Keep legacy jobs paused.
7. Verify the new worktree is clean, Gateway heartbeat is fresh, and `hermes cron status` says jobs will fire automatically. Resume without an extra manual run when a natural tick is imminent.
8. For the first cycle, require a fresh terminal ledger event. If it detects dirty state, branch drift, an open previous writer event, or any second writer, it must block and pause itself.

## Evidence fields

Record only non-secret evidence:

- old and new worktree paths;
- branch and HEAD before/after;
- staged path count and diff/tree identity;
- exact tests/lint/lock results;
- PR and exact-SHA CI URLs/conclusions;
- job ID, workdir, last/next run, Gateway PID/heartbeat;
- block reason and whether repository source writes occurred.

Do not record credentials, raw logs, session contents, or user data.

## Release-specific note

If the WIP is a version/remediation candidate, do not reuse an immutable failed tag. Validate the version contract in the candidate, merge through exact-head and main exact-SHA CI, then create a new immutable tag and use draft-first asset/provider/download/identity/installer readback before publication.
