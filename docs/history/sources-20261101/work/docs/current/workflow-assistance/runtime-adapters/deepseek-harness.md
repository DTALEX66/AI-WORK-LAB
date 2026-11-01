# DeepSeek Harness (DSH) — agent-runtime adapter

DSH is an **agent runtime** adapted into WORK-LAB as a replaceable,
approval-gated executor. It runs bounded agent tasks in an isolated, task-scoped
Git worktree. It is **not** a WORK-LAB core module, not a model gateway, not a
Hermes replacement, and it never writes client config or completes a Task Ledger
task.

> **SUPERSEDED (2026-10-08).** The identity below is the community DSH Desktop 2.0.x build at `D:\All projects\DSH`. AGENTS.md now records the managed entry as the official DeepSeek Harness 0.2.0-rc.2 installed at the vendor default per-user path, with the install root resolved from the uninstall registry entry or the shortcut TargetPath and never hardcoded. Read this page as the record of that migration and of the retired 0.1.x contract, not as current launch instructions.

## Deployed identity (2026-09-02 verified)

The machine DSH switched from the 0.1.x source-checkout lineage to the **2.0.x
community desktop build** (see upgrade records in the DSH handoff + skill
`dsh-administration` references/dsh-2.0.4-upgrade.md):

| Field | Value |
|---|---|
| Product | `anywhere-labs/dsh-desktop` community desktop (Electron shell + bundled full harness, `dsh-plugin-desktop`) |
| Version | **2.0.4** (verified 2026-08-30; 2.0.2 → 2.0.4 NSIS upgrade) |
| Single entry | `D:\All projects\DSH\DSH Desktop.exe` (D-drive; LOCALAPPDATA copy removed) |
| Config root | `C:\Users\<user>\.dsh\` (settings/profiles/sessions/memory/skin-center/task-board/storages) |
| Web | loopback `http://127.0.0.1:43120` (community build port; legacy 0.1.x used 3080) |
| Sessions | 94 UUID dirs preserved under `~/.dsh/sessions/<project>/<uuid>/` (4 project dirs) |
| Legacy 0.1.x | `deepseek-ai/deepseek-harness` pinned `47f94385` — retired; full body backed up under the then-git-ignored .hermes/task-runtime/dsh-011-removed-20260824/ quarantine, relocated to `.project-local/quarantine/` and deleted under authorization 2026-10-07 (SPILL-20261006); no rollback baseline remains |

The adapter module (`integrations/executors/dsh/deepseek_harness_adapter.py`)
reports `detect()`/`observe()` against this community-desktop identity; the
legacy `UPSTREAM_*` pin remains as the historical governance record of the
retired isolated-checkout contract.

## Contract invariants (taskpack §4.1)

| Field | Value |
|---|---|
| `install_mode` | `community-desktop` (legacy contract: `isolated_source_checkout`) |
| `entrypoints` | `web` via desktop shell (single launcher: `DSH Desktop.exe`) |
| `network` | `loopback_only` — `127.0.0.1` (localhost / ::1), port `43120` default (community web); legacy 0.1.x `3080` |
| `workspace_scope` | `task_scoped_git_worktree_only` |
| `secrets` | `runtime_secret_only` — never in repo/receipt/Observer; `~/.dsh/.credentials.yaml` read by the app only |
| `execution_authority` | `execute_only_no_task_completion_authority` |
| `external_mutation` | `approval_required` |
| `plugin_policy` | `builtins_only` |
| `upgrade_policy` | `official_installer_upgrade + explicit_upgrade_task + compatibility_evidence` (community releases via NSIS installer; never manual pnpm in app-managed dirs) |
| `rollback` | stop app → preserve `~/.dsh` config → quarantine old version; restore = reinstall prior release + config preserved |

## Runtime data (git-ignored, never committed)

Community desktop keeps its own data under `~/.dsh` (outside the repo). The
legacy isolated-checkout layout `.project-local/runs/deepseek-harness/`
(under it source/ and dsh-home/) is retained only as the historical/rollback surface of
the retired 0.1.x contract and must not be treated as live state.

## Start / stop / health (approval-gated)

These are **not** performed by the adapter by default; each is an approval item.

- **Launch**: start `D:\All projects\DSH\DSH Desktop.exe` (Electron loads
  `http://127.0.0.1:43120`; ~20-40 s boot). HTTP 403 on `/` is the app's route
  control — service is up, not a fault.
- **Stop**: quit the app process tree (no `taskkill /F` on unknown PIDs).
- **Health**: loopback readback on `127.0.0.1:43120` + process presence;
  version read from `<dshInstallRoot>/resources/app.asar.unpacked/package.json` (no side
  effects). Never a screenshot as proof of binding.

## Configuration location (no values)

DSH config and credentials live under `~/.dsh` (settings.yaml, profiles,
`.credentials.yaml`, memory, skin-center, task-board). The model key is entered
by the user in the DSH UI; Hermes never reads, displays, or writes it, and only
verifies a redacted credential descriptor.

## Permissions

- Workspace must be a Git worktree under the project — never `D:\All projects`
  itself, never the user home, never a drive root.
- Default: no file-write / command / network permission outside the approved
  task; every external mutation is approval-required.

## Evidence (receipt)

A receivable receipt may only contain: `task_id`, `adapter_id`, `upstream_commit`,
start/end time, repo-relative workspace id, command kind, approval result, exit
code, test summary, file-change summary (path+hash), error kind, evidence hash.

Forbidden in any receipt: API keys, full prompts, full responses, source text,
raw session ids, private paths, provider-private headers, unredacted logs.

## Failure classes and rollback

- **Version/install drift** (expected version vs installed) → verify
  `<dshInstallRoot>/app.asar.unpacked/package.json`; reinstall the official release on mismatch.
- **Non-loopback listener** → stop and report immediately.
- **Web won't boot after app launch** → app is alive but `:43120` not listening:
  check `~/.dsh` integrity (task-board ledger lock etc. — see skill
  `dsh-administration` pitfalls) before any reinstall.
- **Secret in dump/receipt** → fail closed, redact, do not serialize.

Rollback: stop the app, keep `~/.dsh` config untouched, reinstall the previous
official release; never destructive reset/clean.

## Upgrade

Any upstream upgrade is a separate `WL-DSH-UPGRADE-*`: release notes review →
config-backup (`~/.dsh` excluded node_modules) → stop app → official installer
→ verify version + sessions preserved → schema/adapter compatibility. Follow
the skill `dsh-administration` reference `dsh-2.0.4-upgrade.md` for the
validated NSIS path.
