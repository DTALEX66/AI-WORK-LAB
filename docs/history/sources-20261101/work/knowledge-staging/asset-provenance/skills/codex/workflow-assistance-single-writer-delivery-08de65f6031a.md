---
name: workflow-assistance-single-writer-delivery
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: codex
archived_at: 2026-08-21
source_path: D:/All projects/WORK-LAB/10-workflow/workflow-assistance/codex-assets/skills/workflow-assistance-single-writer-delivery/SKILL.md
---

---
name: workflow-assistance-single-writer-delivery
description: "Use for Git changes, parallel agents, code review, commits, pull requests, CI, merge, release, or delivery closure."
---

# Single-writer delivery

- One writer owns a checkout. Parallel implementation requires separate branches and worktrees.
- Capture branch, HEAD, tree, status, staged paths, and unstaged paths before work and before a verdict.
- Read-only review binds to an exact candidate tree. Any edit, rebase, rebuild, amend, or conflict resolution invalidates that verdict.
- Verification is not authorization to commit or publish.
- Before a requested commit, stage only intended paths, run staged checks, and record `git write-tree`.
- Before a requested push, fetch, verify the target branch and remote, push without force, then read back the remote SHA.
- CI evidence must match the exact delivered SHA. A green run for another SHA is not evidence.
- Merge, tag, release, remote deletion, and history rewrite require explicit approval for that exact action.

## Orchestration extension (absorbed from 2026-08-12 research: langgraph / myclaude / openai-agents patterns)

Single-writer is the *ownership* rule, not a ban on parallel work. When a task
set has explicit dependencies, schedule as a DAG instead of a serial queue:

1. Task cards carry `depends_on` (explicit task ids). No implicit ordering.
2. Topological order for execution; branches with no dependencies run in
   parallel, each in its own worktree (existing isolated-writer mechanism).
3. A task's verdict is recorded only when its dependencies are recorded;
   a DAG edge is not satisfied by "looks related".
4. Handoffs between parallel writers are merge-committed sequentially on main
   (squash per PR), never concurrent pushes.
5. Session lifecycle: register owner/pid/heartbeat per active writer; a
   timed-out session is reclaimed, never assumed dead by a stale lock.
