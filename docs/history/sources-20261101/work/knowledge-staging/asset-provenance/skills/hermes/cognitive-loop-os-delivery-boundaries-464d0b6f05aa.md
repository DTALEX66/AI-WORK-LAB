---
name: cognitive-loop-os-delivery-boundaries
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/cognitive-loop-os-delivery-boundaries/SKILL.md
---

---
name: cognitive-loop-os-delivery-boundaries
description: "Use for Cognitive-Loop-OS delivery and CI."
version: 1.0.0
platforms: [windows]
metadata:
  hermes:
    tags: [cognitive-loop-os, git, ci, boundaries, fail-closed]
---

# Cognitive-Loop-OS delivery boundaries

## Scope

Use for implementation, cleanup, CI, PR, release-readiness, or runtime-boundary work in `D:/All projects/Cognitive-Loop-OS`.

## Non-negotiable boundaries

1. Canonical project root is `D:/All projects/Cognitive-Loop-OS`; do not use stale external worktrees or similarly named directories.
2. Never access `E:/` unless the user gives the exact path, operation, and impact range in the current request.
3. Hermes global infrastructure under `C:/Users/ALEX/AppData/Local/hermes` is not project output. Do not start, install, stop, repair, or manually edit Hermes Gateway, cron, config, auth, profiles, skills, plugins, or state for a project task.
4. Keep project runtime, cache, logs, artifacts, and recovery evidence under the project `.hermes/` boundary.
5. Treat a dirty checkout as protected user state. Never use `git reset`, `git clean`, force-push, or broad staging.

## Selective delivery workflow

1. Run `git status --short --branch` before edits.
2. Read AGENTS.md and the relevant source, tests, workflow, and recent history.
3. Separate agent-owned files from user WIP by exact file and hunk. Existing staged files remain protected even when adding agent files.
4. Use `git commit --only <agent-files>` when the index already contains user-staged WIP. Verify `git show --stat` immediately.
5. Push explicitly to the intended PR branch using `git push origin HEAD:<branch>`; do not assume the current local branch is the PR branch.
6. Verify the remote PR head SHA before interpreting checks.
7. Read only checks attached to that exact SHA. Old successful runs do not prove the new candidate.
8. For CI failures, inspect failed job logs and active steps before changing code. Do not re-run unchanged candidates or treat dependency gate failures as independent root causes.
9. After a remote green result, verify PR state, merge SHA, and main exact-SHA CI separately. Local main ahead/behind output is not remote-main proof.

## Known failure modes and preventions

- **Existing staged WIP mixed into an apparent R0 stage:** `git add` adds agent files but does not remove existing staged user files. Use `git diff --cached --name-status`, inspect target-file diffs, and commit with `git commit --only`.
- **Wrong branch assumption:** local `main` can contain the candidate while PR branch is elsewhere. Always query PR `headRefName` and `headRefOid`; push with an explicit refspec.
- **Old CI evidence reused:** exact-head evidence is mandatory. Record run ID, head SHA, every required job result, and the stable A0 gate.
- **A0 gate failure misread as a second root cause:** inspect `needs.*.result`; fix the underlying job first.
- **Windows NSIS lifecycle race:** `CloseMainWindow()` can return true while the Tauri native close callback is still unwinding. Do not add a force-kill fallback to a graceful-shutdown assertion. Keep the deferred Tauri exit and validate on the real Windows runner; if timing is changed, run Rust tests, A0 contract tests, and exact-head CI.
- **CI watcher timeout misread:** a timed-out `gh pr checks --watch` is not a pass or failure. Query `gh run view <run-id>` and inspect active step state.
- **Tool path conversion on Windows:** `search_files` may convert a `D:/All projects/...` path incorrectly to `/d/...`. Prefer `terminal` with `workdir`, `read_file` with the absolute Windows path, or `git grep` from the project root.
- **Hermes status command bookkeeping:** read-only-looking Hermes status commands can update `state.db`/cron metadata. Avoid repeated global status queries for project work and never claim absolute zero global writes.
- **Raw shell temp leakage:** project tests/builds may inherit `C:/Users/ALEX/AppData/Local/Temp`. Load the project environment wrapper before project commands that create runtime/cache/build output.

## Verification record

For every delivery, report separately:

- local tests/lint and exact commands;
- changed commit SHA and file scope;
- pushed PR head SHA and URL;
- exact CI run ID and all required job conclusions;
- merge SHA and remote main readback, only if actually performed;
- remaining blockers and rollback boundary.

Never report a plan, a single exit code, or an old CI run as completion evidence.
