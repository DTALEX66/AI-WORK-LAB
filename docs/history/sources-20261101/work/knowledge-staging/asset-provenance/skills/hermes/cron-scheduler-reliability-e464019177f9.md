---
name: cron-scheduler-reliability
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/cron-scheduler-reliability/SKILL.md
---

---
name: cron-scheduler-reliability
description: "Use when durable cron jobs must keep project work running."
version: 1.2.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [cron, scheduler, gateway, durable-work, evidence, recovery]
    related_skills: [sleep-mode, hermes-agent, project-data-boundary]
---

# Durable Cron Scheduler Reliability

## Trigger

Use this skill when a persistent cron job is expected to advance a project, but the user reports that it did not run, stopped, reverted cadence, or appears scheduled without producing work. It also applies when starting or resuming a continuous single-writer project queue.

This is a reliability companion to the project queue skill: it verifies the execution plane, not just the queue ledger.

## Core invariant

A cron job being present and `state=scheduled` is **not execution proof**. A reliable run requires all of:

1. The scheduler/Gateway execution service is running.
2. The job is enabled, has the intended cadence, and has the expected workdir.
3. The project's durable state is `active` and has no concurrent writer.
4. A fresh activity/state ledger event proves the selected task started or completed.
5. The run result and next schedule are consistent with the observed clock.

Never report “continuous” based only on a job ID, a `scheduled` flag, or a successful job registration call.

### Continuous-run truth gate

When a user reports that an overnight loop did not run, treat that as a failed execution claim until proven otherwise. Verify three layers in the same readback: (1) live cron fields (`enabled/state/schedule/last_run_at/next_run_at/last_status`) against the actual clock and timezone; (2) Gateway/scheduler heartbeat or execution receipt; and (3) a fresh project `state.json`/`activity.jsonl` event in the expected cadence containing a real task, command, test, CI, Git, or blocked result. `resume`, `run success`, `executed=true`, a background monitor exit code 0, or `state.mode=active` alone is control-plane evidence, not a cycle proof. If any layer is missing, report `configured/not proven executing`, set the project blocked or paused with the precise reason, and preserve the evidence.

When a writer auto-pauses after a required CI/test failure, do not leave a stale retry monitor unowned: reconcile the exact run and failure first, permit at most one justified bounded retry, keep monitoring until terminal, then either create a new root-cause task or resume only after a fresh activity event. Never repeatedly resume the old blocked prompt or rerun an unchanged candidate.

### Explicit autonomous merge authorization

A user request for autonomous upload/merge authorizes source `commit`/`push` and PR merge only when the request is explicit and the project boundary allows it. Keep merge separate from release: require independent read-only review, frozen changed-tree review, PR exact-head CI success, merge commit readback, and main exact-SHA CI success. This does not authorize immutable tags, GitHub Releases, production deployment, or credential actions unless separately stated.

### Checkout isolation invariant

A durable writer must never share its checkout with the active chat, a manual repair, another cron job, or a review process. Before enabling/resuming a write-capable job, bind it to a dedicated writer worktree and verify that worktree is clean, on the expected branch/HEAD, and not listed as any other worktree's path. Treat branch switching, staged WIP appearing in the user's checkout, or a writer changing the active session's branch as a hard ownership violation: pause the job, preserve the WIP, and do not reset/clean/recheckout. Keep candidate/review worktrees separate from the writer checkout; record both paths in the durable state.

### Manual-dispatch rule

“立即执行” is a real bounded run request, not proof of completion. Before dispatching, verify the prior run has a terminal ledger event and no active writer. Dispatch exactly once, then re-read scheduler fields, state, and the activity tail. Do not dispatch again because the UI has not shown a message while the run is still in progress. A successful dispatch may legitimately advance the task to a queued/in-progress external CI readback; report that checkpoint rather than claiming final completion. When an external exact-SHA CI reaches terminal success between scheduler ticks, one explicitly requested manual run may consume that result immediately; verify that the ledger changes from the pre-CI wait checkpoint to the next bounded task before reporting progress. Do not confuse a stale ledger checkpoint with a stale CI result.

### Release-cycle handoff

For a release queue, keep these terminal boundaries distinct and durable: PR exact-head CI → frozen-tree review → merge commit → main exact-SHA CI → immutable tag → draft Release workflow → draft asset/provider/download/identity/installer readback → explicit publish → public Release readback. A scheduler tick may advance only one boundary; it must not skip from CI success to “released”.

## Start/resume procedure

1. Read the live project state and activity ledger tail first.
2. List cron jobs and confirm exactly one job for the project.
3. Confirm the schedule against the user's established cadence. Do not silently replace a known 10–15 minute cadence with a skill default such as 30 minutes.
4. Check the scheduler/Gateway status using the platform's authoritative status command.
5. **Respect an explicit no-start boundary.** If the user requests sleep mode but the project/session policy explicitly forbids installing or starting Gateway, do not create or leave an enabled writer job and do not mark the project `active` as if it were executing. Record `mode=blocked` with the exact `scheduler_unavailable` reason, pause the newly created job if necessary, and report “configured but not continuously executing.” Only resume after the boundary changes and the Gateway heartbeat plus cron status are verified. A job ID, `scheduled` state, or a successful create/pause call is never execution proof. Also treat `state.mode=blocked|paused` as a hard stop even when the scheduler reports the job enabled: pause the job, reconcile the ledger and writer checkout, update the self-contained goal, then resume only after `mode=active` and the first fresh evidence event are both present.

6. **Re-read after external ledger writes.** If a state/activity write reports that another worker or sibling modified the file after the last read, stop and re-read both ledgers before any retry. Apply a narrow patch against the new content; never overwrite the file from a stale snapshot. Preserve append-only activity events and record the concurrent update rather than treating it as corruption.

7. If the queue is active and no writer-start event is present, trigger exactly one manual run when immediate progress is requested.
8. After triggering, reread the activity ledger, state, and the cron execution result/output. Require `last_status=ok` (or an explicit, understood terminal status) plus a fresh project ledger event; `cronjob.run` returning `success=true` / `executed=true` alone is not enough. Do not trigger again while a writer task is active or while the previous run lacks a terminal evidence event.
9. Report the task ID, scheduler state, cadence, last/next run, Gateway status, model/provider pin, and ledger evidence.

## User-facing update cadence

When the user requests checkpoint-only updates (for example, “不要汇报过程，完成一项再汇报”):

- Do not narrate tool calls, polling, retries, or intermediate CI status before every action.
- Persist that operational detail in the project ledger instead.
- Send a concise user update only after a verifiable checkpoint completes: a tested change, commit, PR creation, exact-SHA CI conclusion, or a real blocked/fail-closed outcome.
- Waiting for CI or the next cron tick is not a completion. Mention it only when the user asks for live status or when it is the precise reason work is blocked.

## Windows stale-Gateway recovery before queue resume

On Windows, `hermes gateway status` can report a stale `gateway_state.json`: the file says `running`, but its recorded PID no longer exists. Treat this as a stopped execution plane, not as a healthy Gateway and not as a cron failure. Before resuming a project writer:

1. Inspect Gateway status and recent lifecycle/exit diagnostics without editing state files by hand.
2. If an explicitly authorized foreground recovery is allowed, run `hermes gateway run` (do not install a service as a side effect), then verify the real PID, a fresh ticker heartbeat, and `hermes cron status` saying jobs will fire automatically.
3. Only after those checks pass, transition the project ledger from `blocked` to `active`, resume the one project job, and trigger at most one bounded catch-up run. Re-read `state.json` and the append-only activity ledger for a real task-start/completion/block event; `cronjob resume` or `executed=true` alone is not execution proof.
4. If Gateway startup again reports an unclean prior life, preserve that evidence and stop on the next lifecycle failure. Do not repeatedly restart, clear stale state blindly, or resume a writer while heartbeat/ledger evidence is missing.

A foreground Gateway is not a durable service: report that it will stop when its owning process ends, and keep automatic service installation as a separate, explicitly authorized operation.

## Catch-up and missed tick recovery

When the wall clock has passed `next_run_at` but `last_run_at` and the project ledger have not advanced:

- Treat the tick as missed or unverified, not as successful.
- Check Gateway status before changing the job.
- Compare system time, scheduler-reported times, and ledger timestamps. A time-source skew can make a job look late or early.
- If there is no active writer, run one catch-up cycle and verify its ledger event.
- Never run a catch-up cycle if state/activity indicate an active writer; wait for its evidence instead.
- If the Gateway is stopped, fix the Gateway first. Manual run is a one-cycle recovery, not a replacement for the execution service.

## Cadence discipline

- Preserve the user's explicit cadence across pause/resume/update operations.
- If the user says “continue” or “keep pushing” and a cadence already exists, do not reset it to a default.
- A shorter cadence does not justify overlapping writers; each cycle must still select exactly one bounded task.
- A recurring job with `repeat=forever` may keep the queue alive, but the project state must still transition to `blocked` or `completed` when the queue contract requires it.

## Fixed-wall-clock cadence

Interval syntax such as `every 10m` is a relative timer. In Hermes, update, pause/resume, and manual run operations may recalculate its `next_run_at` from the operation time. That is expected interval semantics, but it violates a user's expectation of stable wall-clock ticks.

When the cadence must remain aligned to clock boundaries, use a cron expression such as `*/10 * * * *` instead of `every 10m`. After changing it, verify that `next_run_at` is the next ten-minute boundary, not roughly ten minutes after the configuration call. During an automatic-tick proof window, do not issue unnecessary update, pause/resume, or manual-run calls. If a cleanup requires pausing the writer, record the pre-pause schedule, expect resume to recalculate interval timers, and convert to a fixed-wall-clock expression before resuming when preserving the boundary matters.

A successful `update`, `resume`, or `run` is configuration/dispatch evidence only; it is not proof that the project writer advanced. Re-read Gateway status, job fields, project state/activity, and execution output after the next natural boundary.

### Stale state versus live writer reconciliation

A paused/blocked project ledger may describe an obsolete branch while the isolated writer has since advanced to a clean, evidence-backed PR. Before resuming, reconcile live `git status --short --branch`, HEAD, worktree ownership, PR head/state/checks, and the current state/activity tail. If they differ, preserve the old event, append a redacted reconciliation event, update the same job's prompt and state to the live task, and only then resume; never create a second writer or blindly resume an old prompt. The first resumed cycle must monitor the current exact-SHA CI/PR terminal state before selecting another task.

### Convention failures are commit-object failures

When a convention gate is invoked with `--source head`, a fix that exists only in the working tree cannot satisfy it. For errors such as `missing-final-newline`, verify the file's terminal byte is LF, commit the minimal fix, push the new exact SHA, and re-read that SHA's CI. Local unit/Ruff success is not a substitute for the repository convention job.

### Desktop-session delivery caveat

In the Hermes desktop chat, `deliver=origin` can mean that a cron result is stored for the origin session without a live channel capable of injecting a new chat message. Treat `executed=true`/`last_status=ok` as scheduler execution evidence, not message-delivery evidence. Before claiming that a scheduled ping appeared in the current conversation, require a delivery receipt or an explicitly connected Gateway/platform channel; otherwise state that the task is enabled and its output is saved but not live-delivered. A read-only “continue” ping may coexist with the single writer, but it must never write the repository, mutate the project ledger, or be counted as writer progress.

## Model/provider pinning

Hermes protects unpinned cron jobs from silent global inference-config changes. If a scheduled writer must use a user-selected model line, pin the exact provider and model during create/resume/update, then verify the live job reports those values. A run may otherwise be skipped before any inference call with a global-config-drift error; this is a safety stop, not evidence that the project writer ran. Never solve it by changing the user's requested model—pin the model/provider the user explicitly selected. Include the pin in the recovery report and re-run only after the live job shows it.

## Mid-run goal mutation and quiescence

Changing a durable writer’s final goal while it is scheduled is a control-plane migration. Use this sequence when the user upgrades scope (for example, source publication → versioned GitHub Release) or changes release authorization:

1. Pause the cron job first. A project state of `blocked` does not prove scheduler quiescence; a natural tick may already have started.
2. After pause returns, reread `last_run_at`, project `state.json`, the activity-ledger tail, Git/index identity, and writer locks. If a state write tool reports that the file changed externally, stop and reread before writing again. Preserve any late tick as an append-only ledger event rather than replacing its evidence.
3. Record the old goal, new goal, authorization delta, exact candidate version, and next bounded task. Update both the queue state and the cron’s self-contained prompt/name/workdir. When the scheduler tool cannot set user-owned inference pins, use the supported `hermes cron edit --model ... --provider ...` path and verify the live job fields.
4. Resume only when state, cron prompt, cadence, and authorization agree. If immediate progress was requested, trigger one bounded cycle, then verify a fresh state/ledger event. `execution_success` is dispatch evidence, not task-progress evidence.
5. Keep publication classes separate: source push, PR merge, tag, GitHub Release, asset upload, and production deployment require distinct authorization and readback. A version-level target is complete only with the intended tag target, exact-SHA gates, retained assets, checksums/provenance, release metadata, and provider-side readback; `main` merge alone is not sufficient.

Parallel agents do not relax checkout ownership. Keep one writer on the active checkout; use spare slots for read-only release-gap audits/reviews or isolated-worktree implementation, and integrate through the single owner.

## Queue exhaustion under an explicit continuous goal

A queue reaching `completed` with `queue_exhausted_all_tasks_completed` is normally correct. When the user explicitly asks to “keep pushing”, “continue continuously”, or equivalent, treat that as a new authorized continuation contract—not as permission to fabricate work. Keep the scheduler alive, read the project's live roadmap/design/status and dependency evidence, create exactly one next bounded TaskPack from a named roadmap item, append a continuation/reopen ledger event, and verify the new task through a real run. If no evidence-backed next task exists, remain scheduled but report the honest blocked/completed boundary instead of inventing an O-NNN task.

If the blocker is an ordinary, project-local engineering gap that can be implemented and tested without credentials, external writes, or elevated approval, create exactly one bounded unblock TaskPack, execute it, and then resume the original task. Do not repeatedly re-run the unchanged blocked task. If the blocker is a permission, credential, approval, external-upload, or other high-risk boundary, keep it blocked with the precise reason and do not route around it.

## Evidence contract

For each recovery or scheduled cycle, capture only durable, non-secret evidence:

- job ID and exact schedule;
- Gateway/scheduler status and heartbeat;
- project root and workdir;
- state mode, active task, failure streak, and stop reason;
- last activity event and its test/gate evidence;
- live `last_run_at` and `next_run_at`.

Do not treat terminal process listings as complete proof of cron execution: cron agent runs may not appear as terminal background processes. Conversely, an empty process list does not prove that a cron run is active or stopped; use the scheduler plus project ledger.

## Failure handling

### Bounded CI retry and truthful recovery

When a scheduled writer's required exact-SHA CI fails:

1. Re-read the PR head SHA, failed job/step, changed-file set, prior known-green run, project `state.json`, and cron list. A job ID or prior `resume` result is not proof that the queue is still active.
2. If the candidate does not touch the failed subsystem and the same source/tree has a recent known-green run, one bounded rerun of the failed jobs may be justified. Record the exact reason, original run ID, retry count, and retry run state in the append-only ledger before resuming monitoring.
3. Never loop reruns. If the bounded retry fails again, leave `state.mode=blocked`, preserve logs and workspace, and create a new root-cause task instead of repeating the unchanged candidate.
4. When a convention check uses `--source head`, fix committed bytes (for example a missing final LF) with a minimal commit, push the new SHA, and re-run the convention gate against that exact HEAD. A working-tree-only fix is not evidence.

- If Gateway is unavailable, report the exact status and repair it before claiming automatic scheduling.
- If only the job is missing, do not silently create a duplicate when the project state says `active`; reconcile first.
- If the ledger is stale, do not rewrite it to make a run appear complete. Use a real catch-up run or mark the cycle blocked.
- Preserve dirty WIP and project-local evidence. Never reset, clean, delete, or upload project data as part of scheduler recovery.
- Do not commit, push, release, or modify credentials unless separately authorized.

## Windows note

On Windows, a Gateway start may require a user-level service or a login-start fallback when administrator approval is not available. After any start/install action, verify both `hermes gateway status` and `hermes cron status`; the latter must explicitly say cron jobs will fire automatically. See `references/windows-gateway-recovery.md` for a compact command sequence and verification checklist. See `references/cron-run-verification.md` for model-drift, stale-ledger, queue-exhaustion, and three-layer run verification evidence. See `references/fixed-wall-clock-cadence.md` for fixed-boundary scheduling and cleanup interaction. See `references/mid-run-goal-upgrade-race.md` for pause/tick race reconciliation, authorization upgrades, and version-release goal readback.

## Related skills

- `sleep-mode`: owns the project queue, single-writer policy, and durable state transitions.
- `project-data-boundary`: keeps runtime/test/cache artifacts inside the project boundary.
- `hermes-agent`: authoritative Hermes CLI and Gateway documentation.
