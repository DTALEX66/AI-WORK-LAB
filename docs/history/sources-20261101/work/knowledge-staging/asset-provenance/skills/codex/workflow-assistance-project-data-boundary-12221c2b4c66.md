---
name: workflow-assistance-project-data-boundary
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: codex
archived_at: 2026-08-21
source_path: D:/All projects/WORK-LAB/10-workflow/workflow-assistance/codex-assets/skills/workflow-assistance-project-data-boundary/SKILL.md
---

---
name: workflow-assistance-project-data-boundary
description: "Use when a task creates caches, logs, evidence, temporary environments, generated artifacts, downloads, or agent runtime state."
---

# Project data boundary

Keep task-generated state inside the current Git project. Prefer:

- `.hermes/task-runtime/` for caches, logs, temporary files, virtual environments, and transient state.
- `.hermes/task-artifacts/` for user-deliverable evidence and bounded handoff artifacts.

Before writing, verify the destination is inside the intended repository and ignored by Git when it is runtime-only. Do not place project state in the user profile, another repository, a browser profile, an auth store, or an external drive without explicit path-level authorization.

Never read or copy `.env`, credentials, private keys, cookies, tokens, prompt/response bodies, or session databases. Avoid broad cleanup. Remove only exact, verified, regenerable paths authorized by the user.

Private Codex memory under `$CODEX_HOME/memories/**` belongs to the user runtime,
not the project. A denied read is a successful boundary check; stop and use
tracked project truth or a user-provided redacted summary.

For a named residue below `.hermes/task-runtime/`, use:

```text
python <workflow-assistance>/bin/hermes-project-data.py --project . cleanup-path <relative-name>
```

The helper rejects absolute paths, parent traversal and reparse points. It does
not elevate, rewrite ACLs, or kill processes; permission/lock failures remain
`BLOCKED_RUNTIME_CLEANUP`, and success requires the target to be absent.

## Root-drive exfiltration tracing (盘根外溢排查)

When the user reports stray folders on drive roots (`C:\d`, `C:\tmp`,
`D:\cache`, `D:\AITEMP`, ...) and asks whether the data boundary works:

1. **Classify by creator, never assume.** Each stray root folder has a
   different origin. Trace with:
   - contents + mtime (`ls -la`, `stat`), 
   - `wmic process where "ProcessId=<pid>" get executablepath` for the owner,
   - file-name prefixes (e.g. `od-*` = Open Design, `AI_27_5` = Adobe
     Illustrator 27.5).
2. **Third-party software writes roots regardless of agent rules.** Adobe
   Illustrator (AIRobin.exe under `C:\Program Files\Adobe\...\Contents\
   Windows\`) creates `C:\AITEMP` / `D:\AITEMP\AI_27_5` as its scratch space;
   Open Design writes `C:\tmp` / `D:\tmp\od-*` skill markers. These are the
   SOFTWARE's own policy — the agent boundary never governed them. Fix via
   the app's settings (scratch disk / temp dir), not by "strengthening"
   agent rules.
3. **Old-workflow path-join residue** (`C:\d\All projects`, `D:\c\Users\admin`)
   comes from pre-boundary scripts that concatenated `C:\` + `D:\...` wrong.
   These are safe to delete once confirmed as stale (old mtime, empty or
   archived content).
4. **Answer honestly**: the agent boundary (Hermes/Codex lock state under
   `.hermes/task-runtime`) works — the strays were software behavior or
   pre-boundary residue, not boundary violations. Distinguish "agent
   exfiltration" (rule failure, fix the rule) from "software root-write"
   (app config, out of agent scope).

## Hermes global rule injection points (全局规则落点)

When adding a GLOBAL rule for Hermes (not project-scoped), know where it is
actually loaded:

- `HERMES_HOME/SOUL.md` — loaded into EVERY session (identity + rules). This
  is the correct place for global safety rules (E:\ protection, data
  boundary, credentials, destructive-op gates, per-side-effect approval).
- `.hermes.md` / `HERMES.md` — discovered from the project cwd walking up to
  the git root; project-scoped, NOT global.
- `AGENTS.md` — read only at the project cwd top level; NOT loaded from
  HERMES_HOME. A global AGENTS.md in HERMES_HOME silently does nothing.
- Verify actual load points in `hermes-agent/agent/prompt_builder.py`
  (`_load_soul_md` / `_find_hermes_md` / `_load_agents_md`) before relying on
  a rule file; docstrings can be misleading.
