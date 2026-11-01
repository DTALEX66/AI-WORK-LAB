# Hermes Desktop Source-Root Repair Handoff

> Date: 2026-07-24
> Scope: Hermes Desktop runtime/update path only
> Executor: Codex (only after the active Hermes Desktop session is fully closed)

## 0. Current state — revalidated 2026-07-25

The original safe launcher/rebuild transition described below has since been
superseded by a canonical Git-root runtime. Treat this section as authoritative
for any continuation; retain the earlier sections only as historical recovery
context.

```text
Current Desktop shortcut target
→ C:\Users\ALEX\AppData\Local\hermes\hermes-agent\apps\desktop\release\win-unpacked\Hermes.exe

Current canonical Hermes root
→ C:\Users\ALEX\AppData\Local\hermes\hermes-agent
→ .git present
→ remote: NousResearch/hermes-agent

Retired transition paths
→ C:\Users\ALEX\AppData\Local\hermes\hermes-desktop-source-root.cmd
→ C:\Users\ALEX\AppData\Local\hermes\hermes-agent-rebuild\hermes-agent-main
```

The legacy launcher and rebuild checkout are no longer present. Do **not** try
to recreate, invoke, or roll back to those retired paths merely because they
appear in this historical handoff.

The canonical root is not yet update-safe: at revalidation it has two modified
Desktop chat-message files and is `ahead 6, behind 1` of `origin/main`. Before
running `hermes update`, resetting files, rebasing, or replacing runtime data,
Codex must first identify the owner and intent of those modifications, preserve
a rollback point, then complete a normal Desktop restart and UI acceptance
check. No update command is authorized while that working tree is dirty.

## 1. Task objective

Repair Hermes Desktop so its self-update check and update flow use a valid Hermes Git source checkout instead of the non-Git pip/runtime directory.

The desired end state is:

```text
Desktop backend/update root
→ valid Hermes Git checkout
→ `hermes update --check` is supported
→ Desktop update UI no longer reports "isn't a git checkout"
→ backend boot, settings, appearance and chat remain functional
```

Do not replace or delete a working runtime without a verified recovery point.

## 2. Root cause evidence

The Desktop update UI reported:

```text
C:\Users\ALEX\AppData\Local\hermes\hermes-agent isn't a git checkout — desktop self-update only runs against a source install.
```

Read-only verification found:

```text
C:\Users\ALEX\AppData\Local\hermes\hermes-agent
  exists: yes
  .git: no
  contains: pyproject.toml, package.json, venv

C:\Users\ALEX\AppData\Local\hermes\hermes-agent-rebuild\hermes-agent-main
  exists: yes
  .git: yes
  branch: codex/hermes-runtime-recovery
  worktree: clean at handoff creation
  origin: git@github.com:NousResearch/hermes-agent.git
```

The installed CLI also reports:

```text
pip installs are no longer an officially supported platform and will not receive further updates.
hermes update --check → Already up to date.
```

The CLI's successful result does not contradict the Desktop error: the CLI package can report its pip/runtime state, while the packaged Desktop update checker requires a Git source root.

## 3. Changes already made

### 3.1 Safe launch override

Created:

```text
C:\Users\ALEX\AppData\Local\hermes\hermes-desktop-source-root.cmd
```

The launcher sets:

```text
HERMES_DESKTOP_HERMES_ROOT=C:\Users\ALEX\AppData\Local\hermes\hermes-agent-rebuild\hermes-agent-main
```

and starts the existing packaged Desktop executable:

```text
C:\Users\ALEX\AppData\Local\hermes\hermes-agent-rebuild\hermes-agent-main\apps\desktop\release\win-unpacked\Hermes.exe
```

### 3.2 Shortcut update

Updated:

```text
C:\Users\ALEX\Desktop\Hermes.lnk
```

to target the source-root launcher. The existing icon remains configured as:

```text
C:\Users\ALEX\AppData\Local\hermes\hermes-agent-rebuild\hermes-agent-main\apps\desktop\release\win-unpacked\resources\icon.ico
```

Backup created:

```text
C:\Users\ALEX\Desktop\Hermes.lnk.pre-source-root-20260724.bak
```

The current running Hermes Desktop process was deliberately not terminated.

## 4. Required precondition

Do not perform runtime migration while the current Hermes Desktop session is open.

Before any canonical-root change:

1. Ask the user to fully exit Hermes Desktop naturally.
2. Do not force-kill the process hosting the current chat.
3. Confirm no Hermes Desktop backend, gateway, or installer process is holding the target files.
4. Re-check Git status and exact paths; do not rely only on this document.

A shortcut relaunch through the new `.cmd` is safe after the current session closes and is the immediate non-destructive validation path.

## 5. Preferred Codex execution path

### Phase A — verify the safe override first

After the user has closed Hermes Desktop:

1. Launch `C:\Users\ALEX\Desktop\Hermes.lnk`.
2. Open Desktop update checking.
3. Confirm the previous `not-a-git-checkout` message is gone.
4. Run a read-only update check from the Git source root if applicable:

```bash
git -C 'C:/Users/ALEX/AppData/Local/hermes/hermes-agent-rebuild/hermes-agent-main' status --short --branch
```

5. Verify backend boot, chat, settings and appearance.

### Phase B — decide whether canonical-root migration is necessary

If the explicit source-root launch works and the user accepts the launcher, do not perform a risky runtime swap.

If the user requires a direct/native canonical install with no launcher, perform a staged migration only after Phase A passes:

1. Create a dated recovery copy or verified rollback path for the current non-Git runtime. Do not delete the only copy.
2. Ensure the destination source checkout is clean, complete and compatible with the installed Python/Node dependencies.
3. Preserve the current venv until the replacement is proven functional.
4. Prefer the official Hermes source-install/update workflow documented at:

```text
https://hermes-agent.nousresearch.com/docs/getting-started/installation
https://hermes-agent.nousresearch.com/docs/getting-started/updating
```

5. Do not blindly junction or copy only `.git` into the pip/runtime directory. Git metadata without a matching worktree is not a valid repair.
6. Do not replace `C:\Users\ALEX\AppData\Local\hermes\hermes-agent` with an incomplete source tree or a source tree with no working Python environment.
7. After staged replacement, verify all of:

```text
canonical active root has .git
Hermes backend starts
hermes --version succeeds
hermes update --check succeeds without not-a-git-checkout
Desktop update UI succeeds
settings/appearance renderer loads
chat and model switching remain functional
```

8. Keep the old runtime available until all checks pass.
9. Only then remove a demonstrably redundant, reproducible backup, and record the exact path and reason.

## 6. Theme-related separate finding

A separate audit found the blue skin is not caused by the Git/update error.

Hermes Desktop Local Storage contains:

```text
key: hermes-desktop-theme-v2
value: midnight
```

The source defines `midnight` as a deep blue-violet theme. `Preferences` only contains:

```json
{"themeSource":"dark"}
```

Do not change or delete the theme key as part of the runtime migration. Treat theme selection as a separate user-facing change and preserve other Local Storage data.

## 7. Hard safety boundaries

- Do not access, enumerate, read, copy, move, rename, modify or delete anything under `E:\`.
- Do not read or expose Hermes private config, `.env`, authentication files, OAuth/API credentials, cookies, provider databases or Codex auth/config files. Treat them as `[REDACTED]`.
- Do not force-kill the current Hermes Desktop session.
- Do not batch-clean `%TEMP%`.
- Do not delete `hermes-agent`, `hermes-agent-rebuild`, backups, state DBs or venvs based only on size or age.
- Keep Codex temporary files, logs, reports and test output under the active project boundary:

```text
D:\All projects\Workflow-assistance\.hermes\task-runtime\
D:\All projects\Workflow-assistance\.hermes\task-artifacts\
```

- Do not upload Hermes runtime, user data, session databases, backups, logs or credentials to `DTALEX66/Workflow-assistance`.
- This handoff is documentation only; do not commit or push runtime files.

## 8. Acceptance criteria

The task is complete only when all statements below are verified with fresh tool output:

- Desktop launches from the intended root after a normal restart.
- The update page no longer reports `not-a-git-checkout`.
- `git -C <chosen-root> status` and branch/remote checks succeed.
- `hermes update --check` returns a supported result.
- Desktop backend boot completes without timeout.
- Settings and Appearance render correctly.
- The selected theme is unchanged unless the user explicitly requests a theme change.
- Existing runtime remains recoverable until the new path is proven.
- No E: drive access occurred.
- No secrets or private configuration were read, copied, logged or uploaded.

## 9. Recovery commands

If the new launch path fails, restore the shortcut from:

```text
C:\Users\ALEX\Desktop\Hermes.lnk.pre-source-root-20260724.bak
```

Do not delete the source-root launcher or old runtime until the user confirms the new Desktop path is stable.
