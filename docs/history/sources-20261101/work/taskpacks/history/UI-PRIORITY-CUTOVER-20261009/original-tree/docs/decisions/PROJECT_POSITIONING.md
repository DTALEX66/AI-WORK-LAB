# WORK-LAB canonical project positioning

**Position:** client-neutral workflow control plane for the user's whole AI
workflow — it owns the highest user-level capability layer (global
configuration), not any single client's runtime and not any project's domain
logic.

**Repository:** `DTALEX66/WORK-LAB`

## What this repository is

WORK-LAB manages the user's **global configuration layer** — Rules, Skills,
plugin/MCP declarations, portable Memory, Capabilities and workflow policy —
as one client-neutral canonical source, then adapts it into native projections
for each current client. It stays neutral and unbound: no software platform,
agent platform, model, provider, version, port or install path is a hard
dependency of the core contract.

## Neutrality contract (unbound, unlocked)

- **Client-neutral**: one canonical source → per-client native projection;
  never six byte-identical copies.
- **Unbound**: Hermes, Codex, CC Switch, GitHub, Open Design, OpenHuman and
  DeepSeek Harness (DSH) are the *current* adapters, not permanent
  dependencies; future AI software plugs into the same Adapter contract.
  DSH is a replaceable Agent Runtime (temporary executor in the model
  control-plane taskpack), not a Hermes replacement and not a third active
  module.
- **Unlocked**: core schemas use stable IDs, capability discovery and Adapter
  contracts — never hard-coded programs, model IDs, versions, ports or paths.
- **Global configuration scope**: the current workflow software plus any future
  AI software; managed as desired state, applied only through an approved
  Adapter transaction (`UNSUPPORTED_APPLY` when no safe official write
  interface exists).

## Current client workflow

The current managed clients are:

```text
Hermes · Codex · CC Switch · GitHub · Open Design · OpenHuman · DeepSeek Harness (DSH)
```


DeepSeek Harness is an **Agent Runtime** executed in an isolated, task-scoped
Git worktree (pinned upstream, loopback-only, workspace-scoped). It consumes
the project's AGENTS.md rules (auto-injected) and the DSH skill catalog
(`.agents/skills` project-level + `~/.agents` user-level); it never applies
client config, completes a Task Ledger task, or lets credentials enter the
repository. Its configuration guide for other clients lives at
`docs/current/workflow-assistance/runtime-adapters/deepseek-harness-config-guide.md`.

Open Design is an external **client** (`nexu-io/open-design`, adapter id
`open-design`); `DTALEX66/DESIGN-LAB` is a separate, independent **project**.
These are two distinct identity axes and must never be merged.
`DTALEX66/OPEN-DESIGN-Assistance` is retained only as DESIGN-LAB's historical
migration alias.

## Canonical active modules

1. `packages/client-neutral-core` — client-neutral workflow governance,
   execution control, portable contracts and delivery boundaries.
2. `apps/observer` — strictly read-only derived observation, projections and
   evidence reports.

- **Historical products**: `30-products/minigame` is frozen product
  history/fixture/archive material (retired at the 2026-09 directory
  convergence), not an active canonical module.

## Data containment and spill governance

- Project task data, caches, logs and artifacts stay inside the project Git
  root (ignored `.project-local/` root: `runs/`, `artifacts/`; `.hermes/`
  task-runtime is a declared secondary runtime root) — never the user home,
  desktop, system temp or another project.
- The `E:\` and `F:\` data volumes are protected: any access requires
  explicit per-path, per-operation user authorization (machine truth in
  `.project/governance/project-data-boundary.json`, E+F in
  `forbiddenExternalRoots`).
- Any spill (a write outside the project boundary) is traceable, locatable,
  cleanable and migratable. See `.project/governance/project-data-boundary.json`.

## Explicit non-positioning

WORK-LAB is **not**:

- Hermes, Codex, CC Switch or another agent runtime;
- a model/provider gateway, credential store, chat UI or prompt/response
  archive;
- a platform deployment service, commercial marketplace or release host;
- an active MINIGAME product repository;
- a second database product or multi-user SaaS;
- permission to apply any client's live configuration, modify external
  systems, or publish releases.

## Authoritative source files

- `.project/governance/projects.json` — canonical module registry;
- `.project/governance/module-ownership.json` — ownership and writer boundary;
- `.project/governance/project-data-boundary.json` — data containment + spill governance;
- `.project/governance/contracts/contract-catalog.json` — canonical contract catalog;
- `config/config-ownership.json` — field-level ownership;
- `config/adapter-registry.json` — client adapter inventory;
- `taskpacks/current/OPEN-TASK-REGISTER.md` — single live open-task register;
- `taskpacks/current/WORK-LAB-UNIFIED-PRODUCT-CONVERGENCE-TASKPACK-20260918.md` — current authority taskpack;
- `README.md` — public repository entrypoint.

If another README, historical handoff or external description conflicts with
this file and the machine-readable registries, classify it as stale
documentation and update it; do not infer a second architecture.
