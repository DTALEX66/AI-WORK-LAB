---
name: references
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: codex
archived_at: 2026-08-21
source_path: D:/All projects/WORK-LAB/10-workflow/workflow-assistance/codex-assets/skills/workflow-assistance-observer-delivery/references/workspace-discovery-requirement-2026-08.md
---

# Workspace discovery — user requirement (2026-08-11)

## User's durable requirement (verbatim intent)
"用户指定总工作区后，工作区里面的所有项目都可能是用户要执行的项目……例如：`D:\All projects` 是我现在的所有项目所在的总工作区，里面一共有两个项目一个外置的配置环境与软件，当检测到 HERMES 或者 CODEX 也就是发现工作流里的软件在跑任何的项目、载入的项目、执行的项目，都要发现他们并且更新到 OB 观测层里。"

Decomposed:
1. User names ONE total workspace root (e.g. `D:\All projects`).
2. EVERY Git project under it is a candidate for execution — register them all in the canonical registry.
3. When a workflow agent (Hermes / Codex / CC Switch / Claude / OpenCode) is LOADING or EXECUTING a project, that project must be detected and reflected in the Observer layer.
4. Non-Git dirs (e.g. `OS Environment`, an external config/software dir) are environment, not projects — do not register.
5. Observation ≠ execution: the Observer shows what agents are working on; it never executes, approves, or writes to those projects.

## Implementation (active_projects.py, workflow side)
- `discover_git_projects(workspace_root, max_depth=3)` reuses project_registry to find Git repos (is_git_root = `--show-toplevel` == path itself; see gitbash-windows-interop Pitfall 2).
- Activity detection is a conjunction, never fabricated:
  - agent process actually running (tasklist image names: hermes / codex / cc-switch / claude / opencode), AND
  - fresh evidence inside the project's `.hermes` / `.codex` / `.agents` (mtime ≤ 120 min; skip .log/.pyc/.db-wal/.db-shm; filenames + mtime only, contents never read).
- Windows does NOT expose a process working directory via tasklist/wmic/commandline — do not attempt cwd matching.
- `sync_workspace_projects()` registers all projects, sets status ACTIVE for detected ones, and flips stale ACTIVE → REGISTERED. Canonical store gains `update_project_status`.
- Command: `python .../active_projects.py --workspace-root "D:\All projects" --runtime-root "<repo>\.hermes\task-runtime\workflow"`.

## Live result observed
- 2 projects registered: work-lab (ACTIVE — Hermes running + fresh .hermes evidence) and open-design-assistance (REGISTERED).
- Observer projection then showed both with frontend states (running / idle).

## Verification links
- Observer UI real-data display + schema drift: `dashboard-schema-drift-2026-08.md`
- Live SSE push chain check: SKILL.md Workflow step 4 (probe write → count delta → mode LIVE).
