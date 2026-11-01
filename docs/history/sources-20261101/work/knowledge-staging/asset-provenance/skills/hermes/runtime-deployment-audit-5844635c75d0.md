---
name: runtime-deployment-audit
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/runtime-deployment-audit/SKILL.md
---

---
name: runtime-deployment-audit
description: Audit deployable agent workflow packages and active runtimes for source/live drift, scheduler references, and Desktop/CLI release splits without changing user state.
version: 1.1.1
author: Hermes Agent
created_by: agent
license: MIT
metadata:
  hermes:
    tags: [audit, deployment, runtime, desktop, skills, scheduler, verification]
    related_skills: [agent-workflow-fortress, hermes-agent, project-data-boundary]
---

# Runtime Deployment Audit

## When to Use

Load this skill when the user asks whether an agent workflow installation has lost skills, configuration, plugins, tools, or runtime capabilities; when a portable deployment package may have drifted from the live installation; or when Desktop and CLI behavior appear inconsistent.

This is an **audit skill**. It defaults to read-only inspection and a remediation report. Do not sync, restart, upgrade, remove scheduled jobs, or alter a live runtime unless the user explicitly asks after reviewing the findings.

When the user explicitly authorizes restoring the official baseline and then reapplying their workflow assets/data, transition from audit to the layered remediation procedure in [`references/official-baseline-user-overlay-reconciliation.md`](references/official-baseline-user-overlay-reconciliation.md). Keep stock runtime, official config, user overlay, and durable data as separate evidence layers; never clean the first two by deleting the latter two.

## Audit Contract

Classify every finding as exactly one of:

- **Missing managed asset:** a source-controlled file is absent from its declared live destination.
- **Live/source drift:** both files exist but differ; a later sync may overwrite the live-only change.
- **Runtime split:** multiple active surfaces use different installation trees or versions.
- **Stale operational reference:** a cron/task/profile refers to a no-longer-installed asset.
- **Optional capability:** a disabled integration or unavailable credential/dependency that is not required for the user's current workflow.

Do not call an optional capability “missing configuration.”

## Update-Safety Audit

When the user asks whether a later workflow/software update can overwrite their settings, separate two claims:

- A **portable updater** can be proven safe only for the user-owned state it reads and promotes.
- An unrelated vendor installer cannot be controlled by the portable package; report source/live drift and require an explicit, reviewed reapply rather than claiming universal update immunity.

Audit a portable updater's config path as an ownership contract:

1. Confirm it has an explicit, narrow managed-key/asset schema and never wholesale-copies a live config.
2. Confirm it builds in private staging and promotes only after all validation; no live config write may occur before the preservation check.
3. Require an in-memory semantic snapshot of every user-owned surface. It must not log its values or secrets. It should cover model/provider routing, credential-related top-level fields, custom commands/model picker, unknown future fields, user MCPs, custom hooks, user plugins, and siblings of managed keys.
4. For merge-owned collections, check the ownership exception precisely. One-time retirement must be state-recorded; a plugin that a user re-enables after migration is user-owned on later updates.
5. Require a non-secret fail-closed marker and verify that a mismatch prevents promotion, leaving live state intact.
6. Verify with negative tests that deliberately mutate each protected class and with real first-run/second-run migration tests. Then run the package's canonical isolated quality gate.

This audit is structural and source-grounded. It must not read provider credentials, live routing values, or apply a sync merely to establish that the protection exists. See [`references/portable-update-preservation-audit.md`](references/portable-update-preservation-audit.md) for a compact evidence checklist.

## Read-Only Procedure

1. **Establish scope and ownership.** Read the package's sync/deployment script and ownership contract. Identify its managed source roots, exact live destinations, explicit retirement records, and preserved user state.
2. **Compare exact paths, not aggregate trees.** Hash each managed source file and its exact corresponding live path. Do not compare complete source and live directory trees: live installations legitimately include bundled skills, user-created assets, logs, session data, and runtime dependencies.
3. **Validate portable package health.** Inspect the gate runner before executing it. Under an explicit **read-only / no-modification** audit, do not run a canonical gate in the working tree if it generates ignored Context Pack, provider-inventory, or candidate-template artifacts: ignored does not mean non-mutating. Prefer isolated-temp verification and non-writing syntax/static checks, with bytecode output disabled where supported. If safe unit tests run in temporary directories, re-check `git status` plus staged and unstaged diffs afterward. Report a full-gate skip as deliberate, and record any exact test failure.
4. **Inventory runtime surfaces separately.** Check CLI version, installed skills, enabled toolsets, enabled non-bundled plugins, MCP connectivity, and scheduler status using non-secret commands. Verify Desktop shortcut target and working directory separately from the CLI install directory; inspect only non-secret build/version metadata.
5. **Validate scheduled references.** List jobs read-only and compare each referenced skill against the live skill inventory. A paused job with a retired skill is not currently executing, but must be repaired, migrated, or removed before any resume.
6. **Classify and prioritize.** Prioritize runtime splits and missing managed assets. Mark live/source drift as a decision: absorb into source, or intentionally retire it. Keep optional integrations as non-blocking notes.
7. **Close with a remediation boundary.** State the smallest safe next action and the needed authorization. Do not perform live synchronization, runtime replacement, cron resume, or credential changes as part of an audit-only request.

For canonical-store, snapshot-projection, and SSE/LIVE audits, use the end-to-end field trace, falsy-coverage probes, restart revision checks, mutation-to-event matrix, and per-request scan budget in [`references/backend-evidence-projection-sse-audit.md`](references/backend-evidence-projection-sse-audit.md).

To prove a project-data-boundary terminal guard is actually blocking, feed the
guard the exact Hermes hook payload (`{"tool_name":"terminal","tool_input":{...}}`)
from stdin — a wrong shape (`{"tool_call":...}`) silently passes and looks broken.
Blocks still exit 0, so judge by the stdout `"action":"block"` field. See
[`references/project-data-guard-testing.md`](references/project-data-guard-testing.md).

## Repository-Only Workflow Asset Conflict Audit

Use this variant when the user requests a static audit of the package itself and explicitly prohibits reading live homes, user directories, credentials, or network resources.

1. Inventory tracked policy with `git ls-files` and the current checkout with `git status --short`. If the scope says “working tree” or “global,” identify relevant ignored artifacts with `git check-ignore -v`; report them as local/non-shipped evidence, not deployed policy.
2. Treat ownership as a three-way reconciliation: the declarative schema, the portable config, and the sync implementation. For MCPs, verify every repository server is in the schema's owned-name set and that the implementation removes/replaces only those named owned servers.
3. Reconcile managed skill roots with `skills/**/SKILL.md` frontmatter and any provenance manifest. Check duplicate names, duplicate/nested roots, missing roots, unowned skills, and stale provenance. Use the repository's canonical provenance checker when available: hash utilities can intentionally normalize CRLF/LF, so a raw SHA mismatch is not evidence by itself.
4. Trace every documented portable asset to both an ownership declaration and a deployment/copy or atomic-replace path. A file described as portable but absent from the deployment path is a deployment-ownership gap.
5. Search current docs and relevant ignored handoff/context artifacts for obsolete ownership or retirement claims. Cite each conflict as `path:line`, and distinguish a shipped-doc defect from ignored stale evidence.
6. Report `Critical`, `Warning`, and `Suggestion`, explicitly state clean categories (for example, no duplicate names/roots), and do not claim that live runtime behavior was observed in a static audit.

## Privacy and Safety Boundaries

- Never read, print, diff, copy, or hash `.env`, `auth.json`, browser cookies, credential stores, tokens, or active provider routing.
- Use structural health checks rather than dumping live config.
- Never restart or terminate a user-facing Desktop process merely to obtain version evidence.
- Never resume a paused scheduler job merely to test it.
- Preserve unknown live-only data until the user chooses whether to absorb or retire it.

## Third-party desktop app runtime evidence (E3) + entrypoint uniqueness

When you must prove a live desktop app (Electron/NSIS) actually consumed a repo
artifact, read-only, and/or restore a single official entrypoint: combine
process + named-pipe liveness, **read-only SQLite** (`?mode=ro` on
`%APPDATA%\<app>\namespaces\<ns>\data\app.sqlite`), provenance/`sourceNotes`
files in the app's own tree, and multi-source version reconciliation (config
`appVersion` is the major package; UI About + plugin source path are the
runtime truth). Named-pipe-only daemons bind **no TCP port** and their CLI needs
an app-injected `OD_DAEMON_URL`; don't spend time scanning ports. Never launch
a GUI app from a non-interactive bash pipe (crashes Electron with
`EPIPE: broken pipe`). See
[`references/desktop-app-runtime-evidence.md`](references/desktop-app-runtime-evidence.md).

When the audit finds the runtime's **skills/plugins/design-systems are missing
on a fresh or rebuilt Open Design 0.19+ install**, the repo's SSOT assets are
present but not wired in — register them with the project's official
`install_op_expert_suite.py`, not the daemon CLI (local `--source` 404s,
`marketplace add` is https-only). See
[`references/open-design-personal-workspace-registration.md`](references/open-design-personal-workspace-registration.md)
for the installer flow, verification (read-only `installed_plugins`), the
Electron GUI-launch pitfall from Git-Bash, and the doctor model-baseline
staleness trap. NOTE: the daemon asset APIs are **workspace-auth-scoped** — a
bare curl returns 0/partial, so verify with the FULL `x-od-workspace-*` header
set, and never report "installed" from the installer's own stdout alone (see
the reference's workspace-auth-scoped section). When assets verify present but
the UI still shows them missing, the user-validated fix is a **full app restart**
(cache rebuild) before any owner-PATCH or re-install — see the reference's
"Restart-first remediation" section.

## Five-dimension runtime baseline audit (entry/desktop/official/overhead/full-power)

When the user asks whether every managed tool is healthy end-to-end — unique
entry point, desktop-launchable, official+user config, no blocking overhead,
full-power model — run the five-dimension audit validated 2026-08-11 on
WORK-LAB (Hermes/Codex/CC Switch/OpenHuman/Open Design):

1. **Unique entry per software.** Enumerate every launch path per tool (desktop
   shortcut, PATH wrapper, versioned install dirs, Start Menu). A tool with
   MULTIPLE wrapper variants must resolve identically: after fixing the bash
   wrapper's versioned-glob, the `.cmd` twin still had a dead fixed path
   (`bin\codex.exe` when the real install is `bin\<commit>\codex.exe`) — the
   entry uniqueness audit must diff every variant, not just the primary one.
   Batch `.cmd` glob: `for /d %%d in ("%LOCALAPPDATA%\OpenAI\Codex\bin\*") do
   if exist "%%d\codex.exe" set BEST=%%d\codex.exe`.
2. **Desktop reachability.** Every GUI tool's `.lnk` chain must resolve
   end-to-end: enumerate both user + public desktops via WScript.Shell, print
   `TargetPath` + `Test-Path`, and for wscript-based shortcuts also read
   `Arguments` (Hermes chain: `Hermes.lnk → wscript.exe →
   hermes\launchers\Hermes_Desktop.vbs`). CLI-only tools (Codex) legitimately
   have no desktop entry — record "official CLI form" instead of forcing a
   meaningless shortcut.
3. **Official standard + user config.** The ownership contract must declare
   `preserve_unknown: true` per adapter and never override user
   provider/model/auth/desktop state.
4. **No blocking overhead.** Size-check global rules/skills/guidance
   (`du -sh`, `wc -c`) against lean targets (skills ~<10KB each,
   guidance+rules <20KB total); verify wrappers have no dead candidates that
   stall startup.
5. **Full-power model.** No rate limits / cost caps / degraded reasoning:
   - CC Switch (read-only `sqlite3` on `~/.cc-switch/cc-switch.db`): providers
     table `is_current`, `cost_multiplier` (1.0 = no markup), empty
     `limit_daily_usd`/`limit_monthly_usd`; proxy_config table streaming
     timeouts + `enabled`. Do not read auth columns.
   - Hermes `agent.reasoning_effort`: official default is EMPTY (= medium);
     an explicit `low` is a silent downgrade. Fix with
     `hermes config set agent.reasoning_effort medium` (the CLI may print a
     "Did you mean: agent.reasoning_overrides" notice — verify with
     `grep -n reasoning_effort config.yaml`, the value DID apply).
   - Provider routing must be the official provider, not a throttled relay.

Full command recipes and the audit table: see
[`references/five-dimension-runtime-baseline-audit.md`](references/five-dimension-runtime-baseline-audit.md).

## Windows / Git-Bash Pitfall

Git-Bash/MSYS uses POSIX shell semantics. Use `>/dev/null 2>&1` for discarded output. Do **not** use Windows-style `>NUL`: it may create a real repository artifact named `NUL`/`nul` and interfere with Git operations. Remove only the confirmed zero-byte artifact created by the audit command itself.

## Verification Checklist

- [ ] Managed source-to-live paths compared individually
- [ ] No secrets or private config content inspected
- [ ] Canonical package gate passed, or its exact failure recorded
- [ ] MCP/tool/plugin findings separated into required vs optional
- [ ] Desktop and CLI install identities compared when both are in use
- [ ] Scheduled jobs checked for references to retired skills
- [ ] No live state changed during audit-only work
- [ ] Remediation actions are proposed separately from audit evidence
