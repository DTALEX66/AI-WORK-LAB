---
name: codex-surface-recovery
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/codex-surface-recovery/SKILL.md
---

---
name: codex-surface-recovery
description: "Use when Codex launch is slow or broken."
version: 1.0.2
author: Hermes Agent
license: MIT
platforms: [windows, macos, linux]
metadata:
  hermes:
    tags: [codex, desktop, tui, cli, diagnostics, workflow]
    related_skills: [codex, agent-workflow-fortress, systematic-debugging]
---

# Codex Surface Recovery

## Purpose

Diagnose Codex surface failures without confusing the terminal CLI, interactive TUI, Desktop GUI, IDE extension, or cloud surface. Preserve the portable workflow boundary: CLI execution is the required automation surface; Desktop is an optional human-facing adapter.

Use this skill when a user reports that Codex no longer opens, starts slowly, changed language, opens the wrong interface, or a workspace handoff returns success without a visible window.

## Surface classification

Before changing anything, identify the requested surface:

- `codex --version`, `codex exec`, and `codex review`: CLI execution surfaces;
- `codex` with no subcommand: interactive terminal TUI, requiring a PTY;
- `codex app <workspace>`: Desktop handoff, not proof that Desktop is installed;
- IDE extension or cloud: separate products and separate health checks.

Never use a Desktop diagnosis to declare the CLI unhealthy, and never use a fast CLI version probe to claim that the Desktop GUI works.

## Read-only first diagnosis

1. Resolve the supported launcher/PATH and run `codex --version`.
2. Re-read the current `codex --help` and relevant subcommand help; do not assume flags or install paths are stable.
3. Measure startup separately for `--version`, `--help`, `exec --help`, and `app <workspace>`.
4. List processes and windows; distinguish a successful launcher message from a real Desktop process/window.
5. On Windows, inspect the `codex://` protocol registration and whether an open command exists. Do not print auth, tokens, state databases, or full user config. A `codex` command exiting `126` with `Permission denied` means the launcher resolved to a path Git Bash cannot execute (typically the WindowsApps Store copy) or to a stale/absent pinned path — follow the launcher-resolution section in `references/codex-surface-recovery-windows.md` before touching any install state.
6. Run the supported doctor command if available, redact sensitive fields, and separate CLI/config/provider health from GUI health.
7. Record the observed runtime version and file timestamps as run-specific evidence only, never as a permanent compatibility contract.

A `codex app` command that exits zero while no Desktop process/window appears is a handoff/installation-registration failure until proven otherwise. On Windows Store builds, the visible surface may be `ChatGPT.exe` while the Codex backend is a child `codex.exe` running `app-server`; do not require a separately named Codex window. Prove GUI health with the parent/child process relationship plus a visible workspace window.

## Launcher wrapper consistency (bash + .cmd)

WORK-LAB ships two wrappers for the same CLI entry: `bin/codex` (bash) and
`bin/codex.cmd` (Windows cmd). They MUST share the same candidate-resolution
logic. A fix applied only to the bash wrapper leaves the `.cmd` twin on the old
logic (e.g. a dead fixed path `bin\codex.exe`) — divergent entry points, and
the `.cmd` path silently falls through to `where codex.exe` or fails.

- Per-user CLI installs live under versioned directories
  `%LOCALAPPDATA%\OpenAI\Codex\bin\<commit>\codex.exe`, and Store updates ROTATE
  that directory (`cfac6bda` → `ed3ef5e` → `fb2cf19`) even when the binary
  version string is unchanged. Wrappers must glob `bin/*/codex.exe` (newest
  wins), never pin; `CODEX_CLI_PATH` in config.toml gets updated by Desktop to
  the new dir.
- After any Store update, re-verify BOTH wrappers: `./bin/codex --version` and
  `powershell.exe -NoProfile -Command "& '...\bin\codex.cmd' --version"` must
  print the same version.
- `git status` may not show the divergence if the repo copy was never synced;
  hash-compare repo vs live (`sha256` of `bin/codex.cmd`) and diff the two
  wrappers' candidate lists before trusting "both work".

## Store-shell and language diagnosis

For Store/Electron-style Codex surfaces, classify these independently:

- Store shell/package present;
- `ChatGPT.exe` visible window;
- child Codex `app-server` running;
- workspace/project rendered;
- Settings page loaded;
- app UI language selection.

A slow Settings page is renderer/state-loading evidence, not CLI startup evidence. If the app UI reports `Language = Auto detect` and the UI is English under a Chinese Windows/Hermes locale, use the official Settings language control; do not rewrite internal storage or infer that Hermes locale was lost. Capture the current setting and verify the visible UI after a user-facing change.

## Repair boundaries

Prefer the vendor's official Desktop repair/install channel. Do not hand-edit registry protocol commands, delete `.codex` state, delete sessions/logs/SQLite files, reset authentication, or change provider/proxy routing merely to repair a GUI launch. If a repair installer asks for login, permissions, or overwrite confirmation, stop for explicit user confirmation.

Keep CLI and Desktop repair separate. The vendor's Windows standalone installer may repair/update CLI, but it is not automatically a Desktop GUI installer. The official `openai/codex` GitHub repository is a terminal CLI source/release surface; cloning/building it is not a Desktop repair. If a development CLI build is deliberately used, isolate it, verify PATH precedence, re-run `codex --version` and help discovery, and do not let it silently replace the portable launcher.

## Language and speed diagnosis

Check OS and shell locale, but do not infer that locale controls native Codex UI copy. Codex CLI/TUI/help may remain English even when Hermes and Windows are Chinese. Do not invent an unsupported locale flag or rewrite user config. Keep Chinese orchestration in Hermes; pass Chinese task context to Codex when useful.

Treat slow Desktop startup separately from fast CLI probes. A normal `--version` timing does not exonerate a missing or broken GUI bundle, and a slow provider/network check does not prove that window creation is the root cause.

## Workflow contract

Represent health as:

```text
CLI runtime: required
Desktop GUI: optional
Desktop unavailable: warning
CLI unavailable: failure
```

Desktop absence must not block Codex `exec`, review, taskpack runners, CI, exact-tree review, or publication. The portable workflow must not pin an account-specific Desktop path, registry path, GUI version, or Store package identity.

## Verification after repair

Verify in order:

1. `codex --version` and relevant help still resolve through the intended launcher;
2. the Desktop process and visible window exist;
3. `codex app <workspace>` opens the intended repository;
4. the CLI path still preserves user config/rules/plugin discovery;
5. no provider/model/auth routing was changed;
6. the workflow doctor reports CLI required checks separately from optional GUI status.

For a GUI recovery claim, perform an official cold-cycle proof: use the vendor-supported quit action, verify that the relevant shell/app-server process set reaches zero, relaunch through the official Store/App launcher, then verify the visible window, UI language, project, location, and branch. Repeat the cycle when the symptom is intermittent; one successful warm window is not sufficient evidence.

If a failed vendor installer left a lock, inspect only that exact lock's metadata and remove it only when it is zero-byte, no installer process remains, and the active official runtime has passed cold-start verification. Never generalize this into deleting the runtime state directory.

Store session-specific Windows evidence, redacted command output, and repair observations in [`references/codex-surface-recovery-windows.md`](references/codex-surface-recovery-windows.md), not in the main skill.

## Safety

Never read or copy auth files, browser data, cookies, OAuth stores, API keys, or private session contents. Never force-kill Hermes, Codex, CC Switch, or other user processes as a first-line GUI repair. Never claim that a GUI click, login, or workspace open succeeded without a follow-up process/window capture.
