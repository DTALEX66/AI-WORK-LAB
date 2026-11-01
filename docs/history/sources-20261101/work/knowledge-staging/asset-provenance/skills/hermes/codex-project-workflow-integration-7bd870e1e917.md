---
name: codex-project-workflow-integration
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/codex-project-workflow-integration/SKILL.md
---

---
name: codex-project-workflow-integration
description: "Use when integrating repository or user-layer workflows into Codex without taking over private provider, model, authentication, MCP, plugin, session, or Desktop state."
version: 1.2.4
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
tags: [codex, workflow, agents, skills, project-rules, verification]
metadata:
  hermes:
    tags: [codex, workflow, project-rules, skills, verification]
---

# Codex Project Workflow Integration

## Purpose

Use this class-level skill when a repository owns workflow configuration, execution rules, skills, task ledgers, telemetry, adapters, or delivery gates and the user wants Codex to use that workflow directly. It also covers explicitly authorized Codex user-layer enhancement intended to work across arbitrary projects.

The objective is discoverability and execution alignment through Codex's official rule, skill, and command-policy surfaces—not takeover of Codex's private user configuration.

## Ownership model

Keep these layers separate:

- **Repository-owned:** `AGENTS.md`, project-local `.agents/skills/`, workflow launchers, Task Ledger contracts, Telemetry contracts, adapter manifests, and verification commands.
- **Explicitly managed user overlay:** a marker-delimited block in `~/.codex/AGENTS.md`, exact owned skill roots in `~/.agents/skills/`, an exact owned file in `~/.codex/rules/`, and only declared top-level defaults in `~/.codex/config.toml`.
- **User-owned:** Codex provider/model routing, base URL, authentication, user MCPs, user plugins, other skills, and personal preferences.
- **Platform-internal:** Codex Desktop databases, private state, browser state, sessions, sandbox internals, and ephemeral runtime data.
- **Forbidden:** credentials, `.env`, auth stores, cookies, tokens, prompt/response bodies, and private session data.

Current Codex skill discovery uses `$HOME/.agents/skills` for user skills and `<project>/.agents/skills` for project skills. Do not install current skills under `.codex/skills` or treat an explicitly prompted file read as proof of automatic skill discovery.

Never solve a repository workflow integration request by overwriting `C:\Users\<user>\.codex\config.toml` or by copying a Hermes skill tree into Codex wholesale.

## Procedure

1. Confirm the current Codex documentation and runtime version before assuming config keys or discovery paths. Treat official docs as the path/schema authority.
2. Inspect the repository root, applicable `AGENTS.md` files, current Codex user baseline using an allowlist of non-secret fields, and the workflow module's ownership contract.
3. Identify project-specific rules versus portable user-layer rules. Project rules stay in the repository; user routing, authentication, sessions, Desktop state, MCPs, and plugins remain unchanged.
4. Split mixed requests into two lanes immediately: the reusable repository/user-overlay change and the project-local handoff. Once direct-source facts are sufficient, produce the requested TaskPack or handoff artifact first in an ignored project artifact path, then continue the global integration and gates. Do not make the user wait for every umbrella audit, full gate, or publication check before receiving the transferable artifact. Keep progress narration to blockers and phase completions rather than narrating each lookup.
5. Add or update repository `AGENTS.md` with active modules, single-writer boundary, Observer/read-only boundary, runtime evidence root, and canonical quality gate.
5. If Codex needs a discoverable project procedure, add a narrow Codex-native skill under `.agents/skills/<class>/SKILL.md`. It must not assume Hermes-only tools.
6. For explicitly approved cross-project enhancement, use an owned synchronizer with `plan → apply → verify → rollback` operations:
   - merge only a marker-delimited `~/.codex/AGENTS.md` block;
   - manage exact `~/.agents/skills/<owned-name>` roots;
   - manage one exact `~/.codex/rules/<owned-name>.rules` file;
   - add only absent, declared top-level config defaults and preserve pre-existing values;
   - record only ownership metadata and hashes, never a copy of mixed-ownership config or credentials.
7. Preflight every owned target and revalidate at the mutation linearization point. If an owned-looking target or marker exists without valid ownership state, an exact managed block drifted, a mixed-ownership config changed after preflight, or a rules/skills path resolves through an undeclared junction/reparse boundary, stop rather than adopting, overwriting, or deleting it.
8. Treat persistent state schema and managed-target-set changes as migrations: retain backward compatibility, retire old targets only while their hashes still match recorded ownership, never adopt a new same-name target without prior ownership, and exercise interrupted apply/rollback recovery before deploying the new reader. Never make a previously deployed state unreadable or leave a partial lifecycle unrecoverable and then claim rollback remains available.
9. Verify project integration with real Codex in the target repository. Verify global integration in a separate minimal Git canary that cannot inherit the source project's project rules. Require Codex to report the default language, writer rule, configuration authorization boundary, evidence states, and all visible owned user skills with their paths.
10. Validate command policy with `codex execpolicy check` positive and negative controls, parse the effective config without printing secrets, and run the repository's targeted and canonical quality gates after the final code change.
11. Report project discoverability, user-layer discoverability, live model routing, local tests, rollback, exact-SHA CI, and release evidence as separate states.

## Registering a new managed platform/skill (order matters)

When the user directs another tool/platform into the enhancement module (e.g. OpenHuman, Open Design, GitHub), update the contract in this order so no layer contradicts the next:

1. `config/config-ownership.json` — add `adapter_defaults` entry (default layer/mode) and per-field declarations. Split the platform into tiers: global configuration/registry/pointer → `USER_OVERLAY`/`MANAGE` (this project owns it); private runtime → `RUNTIME_EPHEMERAL`/`IGNORE` or `PLATFORM_INTERNAL`/`OBSERVE`; cut-out internal assets → never touched. A platform that was partially split out is still owned at the global-config layer — only the cut content is out of scope.
2. `workflow-manifest.yaml` — extend `first_class_adapters`, `capabilities`, and `adapters.entries` (observe-only platforms: `support: experimental`, `writes: unavailable`).
3. `verify_client_neutral_manifest.py` (or the manifest verifier) — update `FIRST_CLASS_ADAPTERS`, `EXPECTED_ADAPTERS`, and any `adapters=N`/`first_class=N` message; update the mirroring test assertions.
4. Add the platform's Codex-native skill under `codex-assets/skills/<owned-name>/` (boundary + verification ladder + never-restore rule, mirroring the openhuman/open-design pattern).
5. Run `sync_codex_global_assets.py apply` then `verify` (expect the skill count to bump), re-run the quality gate from the module root, regenerate CURRENT_STATE, commit, PR, exact-SHA CI.

## Cross-project behavioral probe (quoted-rule check)

Disk evidence (installed skill dirs, hash equality, `installed_skills: N`) proves deployment, not that the overlay is loaded into model context. Add one behavioral probe: in an unrelated real project (not the sync repo), run

```bash
codex exec --ephemeral 'According to your loaded global workflow rules, what parameters must a PowerShell Remove-Item use, and what must follow it? Quote the rule. Do not call tools.'
```

A correct answer quoting a rule unique to the overlay file (e.g. `-LiteralPath` + `-ErrorAction Stop` + `Test-Path` postcondition from `workflow-assistance.rules`) proves the global rules are injected across projects. Confirm the session header shows the routed provider (`provider: cc-switch-official`) for end-to-end routing. Do the same for a platform skill by asking what its private boundary forbids. This complements — does not replace — the minimal-Git-canary discovery check.

## Fail-closed rules

- Existing user guidance outside the owned marker block is preserved; never replace it silently.
- User provider/model/base URL, authentication, MCPs, plugins, sessions, Desktop state, and unrelated skills are preserved.
- Do not copy the full mixed-ownership `config.toml` as a convenience backup; rollback should remove only exact owned fields/blocks/files whose identities still match recorded ownership.
- Observer remains a read-only projection and cannot write authoritative ledgers.
- One writer owns a checkout; parallel writers need separate worktrees.
- Local tests do not prove remote exact-SHA CI or publication.
- If Codex cannot automatically discover project or user rules/skills, stop and fix discovery before a write-capable run.
- A full gate started before the final edit is stale evidence. Rerun it after the last code or contract change.

## Common pitfalls

- **Transferable artifact held behind full closure:** when the user asks for both a reusable global integration and a project TaskPack, do not finish every global audit/gate before creating the TaskPack. Gather direct-source evidence, deliver the ignored artifact early, and continue the integration in parallel or immediately afterward.
- **Tool-by-tool narration:** repeated progress prose can become the dominant latency even when execution is correct. For an impatient or evidence-driven user, report only a blocker, a completed phase, or the final verified result; keep acting between those points.
- **Wrong skill root:** `.codex/skills` is not the current official discovery root. Use `.agents/skills` and prove automatic discovery in a fresh task.
- **Prompted read mistaken for discovery:** telling Codex an exact file path only proves it can read the file, not that the skill was loaded automatically.
- **Hardcoded asset counts in tests/verifiers:** adding a managed skill (10→11) or a first-class adapter (4→6) breaks every hardcoded count — sync-test `assertEqual(len(managed_skill_names), 10)`, verifier constants `FIRST_CLASS_ADAPTERS`/`EXPECTED_ADAPTERS`, and stdout-count assertions (`adapters=7`, `first_class=4`). Prefer deriving expected counts from the source tree (`len(module._skill_sources(ROOT / "codex-assets"))`) in tests; when a verifier must pin the set, grep for every constant and count assertion before pushing, and re-run the gate after the last change.
- **Project smoke overstated as global readiness:** a WORK-LAB or other source-repository smoke proves only that repository. Use an unrelated minimal Git canary for global claims.
- **Non-interactive approval display:** `codex exec` may show `approval: never` according to non-interactive command semantics even when interactive config defaults to `on-request`; verify the parsed config and do not misdiagnose that header alone as drift.
- **State schema lockout:** adding a required field to a deployed ownership-state file without migration can block the very `verify` and `rollback` operations intended for recovery.
- **TOML table leakage:** appending a supposedly top-level key after a `[table]` header silently places it inside that table. Remove the owned block, parse the remaining TOML, and insert top-level defaults before the first table header; parse and selectively read back afterward.
- **Wrong strict-config probe:** not every Codex subcommand accepts `--strict-config`. Use a supported session-shaped parser probe such as `codex --strict-config exec --help`, then separately read back only allowlisted non-secret fields.
- **Hermes assets copied wholesale:** reuse class-level workflow concepts, but author Codex-native rules and skills with commands Codex can execute.

## References

- [`references/execution-reliability-intake.md`](references/execution-reliability-intake.md): fast two-lane delivery for reusable hardening plus an early project TaskPack, including Windows cleanup, Git/SHA, Python/link preflight, lifecycle, and performance evidence rules.
- [`references/codex-project-workflow-integration.md`](references/codex-project-workflow-integration.md): project-local integration and discoverability evidence.
- [`references/codex-global-user-overlay.md`](references/codex-global-user-overlay.md): validated user-layer ownership, canary, command-policy, rollback, state migration, TOCTOU, interrupted lifecycle, retirement, and Windows path-boundary controls.
