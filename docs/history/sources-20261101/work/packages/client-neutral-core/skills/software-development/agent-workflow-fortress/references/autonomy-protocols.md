# Autonomy Protocols

Companion reference for `agent-workflow-fortress`. Read when the user says
"继续 / 开启循环", "全部开始 / 全量推进", or supplies a handoff/superseding
tree. The SKILL.md keeps the Core Loop + Safety Rules + Stack Boundary; these
protocols govern autonomous iteration, parallel autonomy, handoff, and task
tickets.

## Autonomous Iteration Protocol

When the user says "继续" or asks for loops:

1. Start by reading project state (`git status`, key docs, test baseline). Do not invent tasks.
2. Pick the highest-value real gap that is evidenced by files/tests/docs.
3. Load and apply the relevant specialized skill; loading as decoration does not count.
4. Make the smallest useful change.
5. Run the project's verification command.
6. For autonomous/background loops, immediately print a visible task table/status summary after launch and on user request; include run_id, cycle, queue counts, each task executor, status, and evidence. Do not leave the user with only a PID. If a worker is running while the ledger is idle/no active loop, stop the idle worker and report that it was empty/finished rather than letting it silently spin.
7. Commit/push only when the user requested repository upload or the workflow already requires it.
8. For finite sleep loops, record the exact cycle budget and stop semantics in the scheduler itself. If the user changes "stop after N," update the scheduler immediately; do not rely on prose or memory.
9. If an interactive/manual repair becomes the final numbered cycle, treat it as that cycle only after code, tests, artifact verification, commit, and push complete; then remove the scheduled job so no extra cycle can fire.
10. For UI/game work, use real renderer output or the already-open official simulator as visual evidence. Do not claim a click, refresh, login, or mode transition unless the follow-up capture visibly proves it.
11. Enforce a **single writer per checkout**. Do not let a cron job, background agent, local sleep worker, and active session mutate the same worktree concurrently. Pause write-capable schedulers before handling an asynchronous review verdict or making manual fixes; resume only after ownership is explicit.
12. Match the automation engine to the task. If the project sleep ledger only supports read/search tasks, let it finish those bounded tasks and stop; do not present it as a release executor. Use one durable write-capable orchestrator for validation/commit/push, never a second concurrent scheduler.
13. If no real gap remains, stop and say so.

## Rapid Parallel Autonomy

When the user says progress is too slow, asks to split work into fast-mode tasks, or says "全部开始/全量推进", immediately fill all available delegation slots without another confirmation. Keep the main agent on the serial critical path and use child slots for independent read-only reconnaissance, contract/test design, mechanical audits, or isolated-worktree implementation. A frozen checkout still has one writer: spare slots may prepare the next phase read-only but must not edit the reviewed tree. Roll freed slots into the next ready task automatically.

Before parallel implementation, identify shared-file merge points and reserve them for serial integration. First review may be broad within the agreed risk surface; after a NO-GO, convert findings to negative controls and scope subsequent review to those findings plus regressions introduced by the fix. Never hide a new Blocker/High, but do not let each re-review expand into unrelated redesign. Report one compact slot/task/state matrix rather than narrating every micro-command, and state honestly when per-child model selection is unavailable.

## Superseding-tree narrow re-review

When the user supplies a superseding candidate tree and identifies the last delta, freeze and record that new tree, rerun the negative controls for every prior Blocker/High, then inspect only the stated delta and its direct regression surface. Do not turn the final re-review into a fresh broad audit or elevate unrelated pre-existing observations.

Exercise migration/deletion/backup behavior through the real deployment entry point in a temporary home, including first-run retirement, second-run user re-enable preservation, fixed-path deletion, custom-asset survival, and byte-for-byte backup recovery. Backup coverage must evolve with every newly deployed managed root (including newly added agent skills), not only with retired paths. Recheck `git write-tree` after each verification batch and immediately before the verdict.

Honor a narrow output contract literally: if the user requests "GO/NO-GO, exact blockers only," return `GO` alone when no Blocker/High remains; do not append passed-check narration.

## Portable Handoff and Project-Adapter Contract

When a project supplies a compact `HERMES_HANDOFF.md` after a long or compressed session, treat it as the **continuation entry point**, not an instruction to resume the oversized session. Read it first, then re-check live Git state, current user intent, active writers, and the relevant project policy before acting. A handoff records history; newer user direction and live repository/CI evidence always win.

Absorb only cross-project governance into this global pack: handoff discipline, single-writer ownership, risk-stratified verification, exact-tree review, project-local runtime-data boundaries, and cloud-first continuity. Keep product runtime, schemas, daemons, data paths, domain prompts, and project-specific executors in their owning repository.

The global `run_taskpack_agent.py` runner is an orchestration primitive, not a project fork template. Every invocation must explicitly select the target repository, its active remote ref, and the applicable project skill(s); never silently assume `origin/main` or preload a project-specific skill globally. Low-risk checkpoints use directed RED→GREEN and changed-file gates, then batch one full gate plus exact-SHA CI at the phase Release Train. Security, permissions, databases/migrations, architecture, packaging, dependencies, deployment, and release/merge actions bypass batching and close independently.

## CC Switch Task Ticket Pattern

When delegating to Codex, Claude Code, OpenClaw, or another agent, generate a task ticket with:

- task name
- mode: plan / implement / verify / review
- allowed paths
- forbidden paths
- required source docs
- exact commands to run
- output contract
- rollback plan

Use `templates/task-tickets/cc-switch-agent-task.md` as the base.

## Deterministic custom-bundle content slices

When an autonomous repository loop injects JSON/content into a hand-written JavaScript IIFE bundle, use canonical serialization, a real `node:vm` execution test, the package gate, and narrow commits. Treat content injection, runtime state/scheduling, and Canvas/UI wiring as separate vertical slices so each can go RED→GREEN and ship independently.
