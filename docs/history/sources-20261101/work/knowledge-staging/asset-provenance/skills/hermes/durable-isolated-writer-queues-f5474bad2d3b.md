---
name: durable-isolated-writer-queues
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/durable-isolated-writer-queues/SKILL.md
---

---
name: durable-isolated-writer-queues
description: "Use when durable cron writers need isolated worktrees."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [sleep-mode, cron, durable-work, single-writer, worktree-isolation, fail-closed]
    related_skills: [sleep-mode, cron-scheduler-reliability, project-data-boundary, agent-workflow-fortress]
---

# Durable Isolated Writer Queues

## Trigger

Use this skill when a user wants a project to keep progressing unattended through sleep mode, cron, overnight automation, or a durable writer while the interactive session remains available for review. Use it especially after a cron job changed branches in the user's checkout, created dirty WIP, overlapped a manual run, or reported success without a durable project evidence event.

## Core invariant

A scheduled job is not a writer boundary. A durable writer is valid only when all of these are true:

1. The writer has a dedicated Git worktree path that the interactive session never edits.
2. Exactly one durable job owns that worktree and its project ledger.
3. Each cycle acquires and verifies ownership before editing; branch, HEAD, worktree path, and clean/dirty state are part of the lease.
4. One cycle selects exactly one bounded task and cannot overlap a manual catch-up run or another natural tick.
5. A terminal ledger event proves task completion or fail-closed blocking; `cronjob.run` success, a moved `next_run_at`, or an agent response is not execution proof.
6. A dirty worktree, branch drift, stale writer-start event, missing Gateway heartbeat, stale ledger, or concurrent writer causes pause/block without reset, clean, overwrite, or retry storms.

## Setup protocol

1. Pause the old writer before changing its goal, workdir, or prompt. Preserve its last run and project ledger.
2. Inspect the current checkout. If it is dirty or contains useful WIP, do not discard it. Review, validate, commit, or leave it explicitly blocked before creating a new writer path.
3. Create a dedicated worktree under the project's approved local workspace, normally from `origin/main` or a reviewed candidate commit. Give it a distinct branch such as `sleep/continuous-writer`; never reuse the interactive branch.
4. Initialize a project-local ignored ledger in the writer worktree:
   - `.hermes/sleep-mode/state.json`
   - `.hermes/sleep-mode/activity.jsonl`
5. Make the cron prompt self-contained. It must name the exact writer worktree and ledger, forbid writing any other worktree, require one bounded task per cycle, require live Git/CI evidence, and define the stop/block rules.
6. Update the one existing job's `workdir` and prompt. Do not create a second active writer for the same project. Keep legacy jobs paused and explicitly distinguish them by workdir.
7. Verify the Gateway heartbeat and `hermes cron status` before resuming. Resume only after the writer worktree is clean and the ledger is `active`.

## Cycle protocol

At cycle start, read the writer ledger and verify:

- `project_root` equals the dedicated writer path;
- the job ID matches the ledger;
- the current branch is the writer-owned branch or the explicitly recorded task branch;
- `git status --short` is clean unless the same cycle owns a recorded WIP checkpoint;
- no prior `writer_started`/`cycle_started` event lacks a terminal event;
- no other writer lease is active;
- the previous task and its CI/review evidence are terminal.

Then select one task from live evidence, not from stale prose. For implementation tasks, use a separate task branch inside the dedicated writer worktree only after the worktree is clean. Do not switch branches in an interactive checkout. Use parallel agents only for read-only audits, test analysis, or isolated worktrees; reserve the writer checkout for the single writer.

At cycle end, record a compact append-only event with task ID, branch, HEAD/tree, changed paths, test/lint results, PR/CI URLs and conclusions, and the next dependency. Mark `completed` only with real evidence. On any failed gate or ownership anomaly, append a blocked event, set `mode=blocked`, pause the job, and preserve the exact worktree and logs.

## Manual run rule

A manual "run now" is itself a writer cycle. Before invoking it, verify no natural tick is active and no writer-start event is open. After invocation, reread the ledger and job fields. Never click/run again merely because the tool returned `success=true` or the UI did not show a message. If the natural schedule is near, wait instead of forcing a second cycle. A scheduler can execute successfully while delivery is local-only; the project ledger is the authoritative progress proof.

## Release and high-risk boundaries

Keep source push, PR creation, PR merge, tag creation, GitHub Release draft, publication, asset upload, and deployment as separate gates. A durable writer may prepare and verify a candidate, but merge/tag/release require the project's explicit authorization and exact identity readback. Never reuse or overwrite an immutable failed tag; create a new remediation version and validate source/workflow/artifact contracts before tagging.

For draft-first GitHub Releases, keep the temporary draft URL (`untagged-*`) distinct from the eventual canonical tag URL. Artifact-side identity should bind the canonical URL; draft readback must compare against that canonical expected URL rather than the draft's temporary `html_url`. If this provenance check fails after tag creation, preserve the immutable tag and unpublished draft, fix the workflow in a new commit, and use a new remediation version.

For a release remediation, the safe sequence remains:

```text
candidate worktree
→ frozen tree review
→ commit/push
→ PR exact-head CI
→ merge
→ main exact-SHA CI
→ new immutable remediation tag
→ draft-only Release
→ asset/provider/download/identity/installer readback
→ publish
→ public readback
```

## Recovery protocol

When a writer appears ineffective:

1. Do not trigger another run immediately.
2. Read Gateway status, cron status, job `last_run_at/last_status`, writer state, activity tail, and Git status in parallel.
3. Distinguish dispatch evidence from project progress evidence.
4. If the writer changed the interactive checkout, pause the job and preserve the dirty/staged WIP. Do not reset or clean.
5. Review the WIP in the current single-owner context, commit only after frozen-tree validation, and move future automation to a dedicated worktree.
6. If the job overlaps itself, preserve the concurrency-block event and require a terminal event before resume. Do not manually run again during an active cycle.
7. Resume only after the isolated worktree is clean, the ledger is active, and Gateway heartbeat/cron execution are verified.

## Data boundary

Keep task runtime, logs, caches, review artifacts, and ledgers under the project-local ignored `.hermes/` paths. Do not copy credentials, sessions, user data, or external archives into the writer worktree. Do not use `git clean -fdx`, broad deletion, or stale state-file overwrites to repair the queue.

## Verification checklist

- [ ] Only one active job exists for the project.
- [ ] Legacy writer jobs are paused and have distinct workdirs.
- [ ] Writer worktree is separate from interactive worktree.
- [ ] Writer worktree is clean before resume.
- [ ] State and activity ledgers are in the writer worktree and append-only.
- [ ] Gateway heartbeat and `hermes cron status` confirm automatic execution.
- [ ] One manual or natural cycle has a fresh terminal ledger event.
- [ ] No commit, PR, tag, Release, or publication is claimed from dispatch evidence alone.

See `references/worktree-lease-recovery.md` for the concrete branch-drift, dirty-WIP, overlapping-cycle, and isolated-worktree recovery pattern. See `references/draft-release-url-provenance.md` for draft-versus-canonical Release URL identity checks.
