---
name: windows-development-environment
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/windows-development-environment/SKILL.md
---

---
name: windows-development-environment
description: "Use when debugging Windows Node, Python, Git-Bash, PowerShell, path, encoding, or local-server failures."
version: 1.4.0
author: Hermes Agent
license: MIT
platforms: [windows]
tags: [windows, nodejs, powershell, python, git-bash, encoding, paths]
metadata:
  hermes:
    tags: [windows, nodejs, powershell, python, git-bash, encoding, paths]
    related_skills: [project-data-boundary]
---

# Windows Development Environment

## Overview

Use this skill for Windows-specific development failures and for safe execution from Hermes' Git-Bash/MSYS terminal. It covers shell selection, encoding, executable resolution, subprocess launching, paths, local servers, Git, and small deployment-pack checks.

This skill is **not** a provider, VPN, proxy, plugin, Desktop-layout, or credential-management skill. Use `model-switch` for provider/model work, `project-data-boundary` for project containment, and the official Hermes/Codex commands for authentication or runtime configuration.

## When to use

- Node.js, Next.js, npm, Python, or Git operations on Windows.
- `spawn EINVAL`, `WinError 2`, `ETIMEDOUT`, or npm exit-handler failures.
- PowerShell scripts with CJK/non-ASCII content.
- Git-Bash commands involving spaces, Unicode, or Windows `.cmd` wrappers.
- Local development servers that fail after a restart or appear on the wrong port.
- A repository or deployment pack needs encoding, path, or staging verification.
- Configuring/repairing a locally-installed desktop tool (Open Design / Codex / OpenHuman) whose `doctor`/`configure` diagnostic reports FAIL — see `references/desktop-tool-config-repair.md`.
- Migrating/copying a pnpm or junction-based app tree (DeepSeek Harness etc.): junction loops, `robocopy /E` expanding junctions, boot errors like `exists and is not a symlink`, proving session/data integrity — see `references/windows-junction-node-modules-migration.md`.
- pnpm installs that reset manual node_modules edits, junction-heavy workspaces left with empty shell dirs, or missing native optional binaries (lightningcss-win32-x64-msvc, node-pty prebuilds): official patch flow (`pnpm patch` / `patchedDependencies`), `supportedArchitectures`, known pnpm 11.x bugs (#13503/#13676/#14001), approve-builds scope — see `references/pnpm-windows-dependency-management.md`.
- Node-pty `AttachConsole failed` crashes in console-less (service / nssm / detached) hosts, Windows lockfile PID-reuse misjudgment, or spawning genuinely no-console test processes — see `references/windows-node-runtime-pitfalls.md` and `references/windows-detached-process-testing.md`.

## 1. Shell and encoding

### PowerShell selection policy

Hermes `terminal` uses **Git-Bash/MSYS** by default; use POSIX syntax there. When PowerShell is required, prefer **PowerShell 7** via `pwsh` (`powershell.exe` only for legacy/Desktop-only cases).
- **Git-Bash expands `$name` before `pwsh` sees it.** Wrap PowerShell source in Bash single quotes (short commands) or write an ASCII/UTF-8 `.ps1` under `.hermes/task-runtime/` and run `pwsh -NoProfile -File ...` (multi-line / state-changing). Do not rely on `--%` or scattered `\$` escapes.
- Prefer ASCII-only `.ps1`; PowerShell 5.1 misparses CJK in UTF-8 from Git-Bash. CJK *text* → code-point escapes; full recipe in `references/validated-cases.md`.
- Check touched text files before upload: `git diff --check` + a UTF-8/CRLF probe.

## 2. Executable and subprocess resolution

- **PATH shadowing:** Hermes may bundle a Node while another appears earlier in `PATH`. Verify before changing code: `command -v node`, `node --version`, `python -c "import sys; print(sys.executable)"`. Use the project interpreter. Do not assume `python` and `python3` resolve to the same interpreter. Hermes workflow scripts use `python`.
- **`.cmd` launchers** can't be spawned directly by `CreateProcess` (Node `spawn` / Python `subprocess`). Prefer a real `.exe`, else `cmd.exe /d /s /c "tool --version"`. From Git-Bash, `cmd //c ...` can print the banner and NOT run — use `cmd.exe /d /s /c` or PowerShell `& 'C:\path\tool.cmd'`.
- **GUI exe with spaces:** use PowerShell `Start-Process -FilePath '...' -WorkingDirectory '...'`, never `cmd start` (Git-Bash mangles the nested quotes into a spurious "找不到文件" dialog). Full recipe in `references/validated-cases.md`.

## 3. Paths, workdirs, and Git-Bash

- **Never pass MSYS paths (`$HOME`, `$(pwd)`, `/c/...`) to Windows-native programs** — use `C:/Users/...` forward-slash form; `cygpath -w` to convert. MSYS paths are for bash `cd` only.
- **`PYTHONPATH` on Windows is `;`-separated** even from Git-Bash: `PYTHONPATH='src;scripts;...'` (colon form is Linux-only).
- Quote paths with spaces; prefer forward slashes in Bash and JSON/YAML.
- Native Windows `git` cannot open MSYS `/tmp/...` paths — pass the Windows form (details in `references/validated-cases.md`). Avoid `>NUL` in Git-Bash (creates a literal `NUL` file); use `>/dev/null 2>&1`.
- **Commit messages with backticks:** write to a file and `git commit -F msg.txt` — backticks in `-m` are command substitution in Bash (details in `references/validated-cases.md`).

## 4. npm and lockfiles

| Symptom | Likely cause | First check |
|---|---|---|
| `spawn EINVAL` | `.cmd` launched without `cmd.exe` | executable path and launcher type |
| `Exit handler never called!` | registry or npm process failure | registry configuration and network status |
| `ETIMEDOUT` | lockfile points at an unavailable registry | lockfile URLs (without credentials) |
| wrong Node version | PATH shadowing | `command -v node`, `node --version` |

Lockfile regeneration is destructive: identify exact paths → save a diff → get explicit approval → remove only confirmed paths → regenerate (`npm install --ignore-scripts --no-audit --no-fund`). Never print `.npmrc`, tokens, or private registry credentials.

## 5. Local Windows servers

- After stopping a server, the port may stay in `TIME_WAIT`; verify the listener before restarting: `netstat -ano | grep ':PORT' | grep LISTEN`.
- **Stale uvicorn/FastAPI child:** killing the wrapper often leaves a detached uvicorn child alive, still serving OLD code (new routes return 422) and possibly holding the runtime/DB lock. Diagnose by PID: `netstat -ano | grep ':8000' | grep LISTEN` then `taskkill /F /PID <pid>` (never `taskkill //PID`). PowerShell one-liner to kill by port + full symptoms in `references/validated-cases.md`.
- Re-verify readiness with a health check + a request against a *newly added* route, never an old screenshot or remembered port.

## 6. Workflow-assistance deployment boundary

Use the repository's canonical synchronizer, not ad-hoc `cp`:

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
HERMES_HOME="${HERMES_HOME:?Set HERMES_HOME to the intended Hermes Home}"
python scripts/workflow/sync_hermes_workflow_assets.py --repo "$REPO_ROOT" --home "$HERMES_HOME"   # dry-run
# authorized deployment adds --apply, then: hermes config check
```

The sync deploys only owned skill roots/binaries, never mixed-ownership config or provider/model/auth/MCP/plugin/session/memory state, and fails closed on drift. A drifted managed root may be a user customization — skip with a recorded reason or stop for approval. This skill does not enable plugins, change MCP, edit `AGENTS.md`, change provider routes, or copy credentials.

## 7. Windows junctions and node_modules migration (pnpm apps)

pnpm and apps like DeepSeek Harness lay out node_modules with Windows directory junctions; a naive copy breaks them. Key rules (full recipes in `references/windows-junction-node-modules-migration.md`):

- **Detect junctions with Node, not Python**: `fs.lstatSync(p).isSymbolicLink()` — Python `Path.is_symlink()` returns False for junctions.
- **Never `robocopy /E` a tree containing node_modules**: junctions expand into real dirs and circular chains (`cordis → cordis-plugin-include → cordis`) loop forever. Copy with `/XD node_modules`, then `pnpm install --frozen-lockfile` at the destination to rebuild clean links.
- **Circular junction trees cannot be deleted** (`rd /s /q`, `Remove-Item -Recurse -Force`, `fs.rmSync` all throw ENOTEMPTY) — **rename them aside** (`fs.renameSync`) and let the app rebuild.
- **pnpm `nodeLinker: hoisted` can pollute an app-managed junction area** with real directories (DSH: `$DSH_HOME/profiles/node_modules/@deepseek-ai/*` must stay junctions or boot fails with `exists and is not a symlink`). Stop the running app (its own migration/install child may be recreating the pollution — check `Get-CimInstance` for stray robocopy/pwsh), rename the polluted dir, boot once to rebuild junctions, then start the service.
- **Prove "nothing was lost"** by comparing per-directory file counts + sizes src vs dst for session/state dirs (equal counts = intact; small byte diffs are WAL/append timing). Keep the original location untouched during a copy-based migration.

## 8. pnpm dependency management on Windows

pnpm's node_modules layout and store make three recurring Windows failures predictable — all official fixes and known pnpm issue numbers in `references/pnpm-windows-dependency-management.md`:

- **Manual node_modules edits get reverted on install**: files are hardlinks into the store; editing node_modules corrupts the store copy, pnpm re-fetches and overwrites. Use `pnpm patch` / `patchedDependencies` (never hand-edit, never patch-package — pnpm docs say it's unnecessary).
- **Empty shell dirs after installs**: known pnpm 11.x bugs with `nodeLinker: hoisted` (#13503 dedupe moves deps to `.ignored`, #13676 interrupted install orphans nested dirs). One `pnpm install --force` clears; enable Developer Mode so pnpm uses symlinks instead of junctions.
- **Missing native optional binaries**: `supportedArchitectures` in pnpm-workspace.yaml + `--force` to re-materialize; check vc_redist before assuming the file is missing. v11 reads settings only from pnpm-workspace.yaml, not the package.json `pnpm` field.

## 9. Detached / no-console process testing on Windows

To reproduce service/session-0 behavior (node-pty crashes, background daemons), you must spawn a child with **no console at all** — `-WindowStyle Hidden` keeps a console, `cmd /c` wrappers and `powershell.exe -File` children are unreliable under `DETACHED_PROCESS` (powershell exits 0 without running the script; node via `cmd /c` exits 1 with empty logs). The validated recipe — a C# console exe compiled via `Add-Type -OutputAssembly -OutputType ConsoleApplication`, launched with `CreateProcess(..., DETACHED_PROCESS=0x8)` and stdio captured through `CreateFile` handles + `STARTF_USESTDHANDLES` — plus the exact pitfalls (NULL `lpApplicationName` → ERROR_PATH_NOT_FOUND; PowerShell Int64→UInt32 overflow on `0x80000000`; `bInheritHandles=false` drops child stdout silently) is in `references/windows-detached-process-testing.md`.

Verified Win32 facts that settle "no-console" debates fast: `FreeConsole()` returns TRUE in a console-less process; `AttachConsole(deadPid)` fails err 87; `AttachConsole(live console process)` succeeds even from a no-console process — so attach failures mean "target is dead/console-less", never "caller has no console".

## Validated case studies

Detailed dated cases (with full command recipes) live in `references/validated-cases.md` — read on demand:

CRLF-normalized hashes · gh CLI dead credential helper · GitHub API rate limit · rebase+force-push `before` sha · stale exported env vars · `--source head` vs working tree · `utf-8-sig` BOM · sqlite-vec `vec0` fingerprint · `uv pip` wrong venv · bare `pip` pydantic-core drift · TESSDATA_PREFIX OCR skips · Bash wrapper `--` and `pwd` traps · GUI `Start-Process` · backticks in `-m` · Windows junction/node_modules migration (DSH) — see `references/windows-junction-node-modules-migration.md`.

## Common pitfalls

1. Treating Git-Bash as PowerShell.
2. Launching a `.cmd` through Python/Node without `cmd.exe`.
3. Fixing PATH shadowing by editing global config instead of verifying the executable.
4. Regenerating a lockfile before preserving the exact diff.
5. Restarting a server before checking `TIME_WAIT` and listener ownership.
6. Using a stale localhost port or cached screenshot as proof of the current project.
7. Killing the wrapper but leaving a detached uvicorn child alive (still serves OLD code, may hold the lock).
8. Replacing a canonical deployment with direct copies.
9. Treating managed-root drift as permission to overwrite user customization.
10. Reading or printing credentials while diagnosing registry/OAuth/proxy/provider symptoms.
11. Staging `NUL`, `.env`, runtime databases, or task artifacts.
12. Copying a node_modules tree with `robocopy /E` (junctions expand; circular chains loop forever).
13. Trusting Python `Path.is_symlink()` on Windows (misses junctions — use Node lstat).
14. Trying to delete circular junction trees instead of renaming them aside.
15. Restarting the app while its own migration/install script is still running (concurrent writers recreate the broken state — check `Get-CimInstance` first).
16. Using `powershell.exe -File` or a `cmd /c` wrapper as a `DETACHED_PROCESS` child (exits 0/1 without running) or passing NULL `lpApplicationName` (ERROR_PATH_NOT_FOUND) — use a compiled C# exe + explicit `lpApplicationName`; see `references/windows-detached-process-testing.md`.
17. Passing `0x80000000` (Int64) to a UInt32 P/Invoke parameter from PowerShell (silent conversion failure → null handle) — cast `[uint32]` explicitly.
18. Trusting pid-liveness checks for Windows lockfiles: PIDs recycle (SearchFilterHost etc. can reuse a dead lock holder's pid) — use an OS-level lock, pid+creation-time identity, or mtime staleness; see `references/windows-node-runtime-pitfalls.md`.

## Verification checklist

- [ ] Shell and interpreter were identified explicitly.
- [ ] Executable resolution was checked before changing code.
- [ ] Touched text files are UTF-8 and pass `git diff --check`.
- [ ] Paths were quoted and no unsafe deletion or global trust change was made.
- [ ] Local server ownership and port state were verified if relevant.
- [ ] Deployment used the canonical path and only owned assets.
- [ ] User configuration, credentials, provider/model routes, plugins, MCP, sessions, and memory were preserved.
- [ ] Runtime artifacts remain under the project ignored runtime/evidence directories.
- [ ] Tests and the canonical quality gate were run after edits.
- [ ] Exact changed paths, commit, and verification evidence are recorded.
