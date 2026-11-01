# WORK-LAB execution rules

> 全局执行标准（跨软件跨项目）：见 `docs/decisions/global-execution-standard.md`（执行生命周期：理解→扫技能→分片→执行→验证→落地）。
> 经验教训铁律（核实优先/治理最小化/官方优先）：见 `docs/decisions/LESSONS_LEARNED.md`。
> 全局部署与升级：按需读取 docs/current/workflow-assistance/workflow/official-plus-user-configuration-standard-2026-08-11.md；软件、模型、技能数量由当前发现与机器合同确定。2026-10-05 修复归档见 docs/history/archive/workflow-convergence-20261005.md，仅作历史证据。

## Mandatory audit bootstrap (normative)

Every audit and every execution task MUST resolve current authority in this order,
before touching any implementation:

1. Resolve current `origin/main` exact commit and tree.
2. Read `WORK-LAB-AUTHORITY.md` (top human authority).
3. Read `.project/governance/project-authority-index.json` (top machine authority).
4. Read this `AGENTS.md`.
5. Read the CURRENT taskpack referenced by `.project/governance/taskpack-authority-index.json`.
6. Read the single live open-task register `taskpacks/current/OPEN-TASK-REGISTER.md`.
7. Read scope-relevant machine contracts.
8. Consult a specifically named historical record only when needed.

Precedence: latest explicit user decision > `WORK-LAB-AUTHORITY.md` >
`project-authority-index.json` > current taskpack / open register >
`AGENTS.md` + scoped machine authorities > current exact-SHA code + CI/runtime
readback > historical records. Historical records are frozen, non-normative
evidence. Machine verifier: `scripts/ci/verify_project_authority_reference.py`.

## Scope

This is a single-root monorepo. Canonical module roots (per
`.project/governance/module-ownership.json`, the machine authority) are exactly
two: `packages/client-neutral-core` (workflow-assistance: Task Ledger,
Telemetry Ledger, sidecar, adapters, delivery gates) and `apps/observer`
(work-lab-observer, read-only projection). Active supporting source surfaces
(not module roots): `services/` (orchestration/policy/receipts),
`integrations/`, `config/`, `apps/token-monitor/`, `scripts/`, `tests/`. The
legacy `10-workflow/workflow-assistance` path was split out at the 2026-09
directory convergence and is no longer tracked. The
managed client workflow is Hermes · Codex · CC Switch · GitHub · Open Design ·
OpenHuman, plus any future AI software through the same Adapter contract.
DSH (DeepSeek Harness, official build `0.2.0-rc.2`, installed at the vendor DEFAULT per-user path `%LOCALAPPDATA%\Programs\DeepSeek Harness` — resolve the install root from the uninstall registry entry or the shortcut TargetPath, never hardcode a drive letter; NSIS silent installs reset desktop .lnk TargetPath+IconLocation to the temp install dir — after ANY upgrade re-pin all .lnk fields per skill `dsh-administration` and error-ledger ERR-087) is a managed agent runtime client
through the same Adapter contract. CC Switch is LEGACY_OBSERVE (observe-only;
no active writes) unless evidence restores it to active status.
Open Design is an external *client* (`nexu-io/open-design`); the separate
`DTALEX66/DESIGN-LAB` project owns its own design domain (historical migration
alias: `DTALEX66/OPEN-DESIGN-Assistance`).

### Open Design client vs DESIGN-LAB project (two distinct identities)

WORK-LAB manages the Open Design **client** USER_GLOBAL desired state (rules,
skills, plugins, workflow policy, capability mapping) as `MANAGE` with
`apply_supported=false` until a reviewed adapter and stable official interface
exist. Since 2026-08-21 the user authorized WORK-LAB to manage Open Design
**plugins** (install/update/inventory of the client plugin layer); design
**capability** (models/tools/generation params/assets/specs/quality gates) stays
with `DTALEX66/DESIGN-LAB` and is not managed here. Design **capability** (models/tools, generation params, design assets,
specs, design systems, quality gates, editable handoff) belongs to the
`DTALEX66/DESIGN-LAB` project and is **neither collected nor managed here**
(`IGNORE`). Field-level ownership lives in
`config/config-ownership.json` (adapter
`open-design`, external project `design-lab-project`).

## Ownership

One writer owns a task. Read-only reviewers may inspect exact trees but may not
edit them. Cross-module changes require one explicit cross-module task card.
Module instructions can narrow these rules, never weaken them.

## Safety

Do not read, print, copy, commit, or upload credentials, `.env` files, auth
stores, private keys, browser data, tokens, prompt bodies, or response bodies.
Never access `E:\` or `F:\` — read or write — without explicit per-path,
per-operation user authorization (machine truth:
`.project/governance/project-data-boundary.json`, E+F in
`forbiddenExternalRoots`). All content this project produces — builds,
caches, temp files, evidence, downloads, generated artifacts — stays locked
inside the project Git root: build/cache/temp roots live under
`.project-local/runs/` (TMP, npm/uv/pip caches, node_modules), evidence under
`.project-local/artifacts/` or `reports/`; nothing spills to user
directories, other projects, or the shared library unless explicitly
authorized. Any spill is traceable, locatable, cleanable and migratable
(`.project/governance/project-data-boundary.json`). Never use destructive
reset/clean/force-push operations.

## Managed global configuration (Hermes)

WORK-LAB manages a declared Hermes user overlay on the official baseline:
the managed **assets** — 13 skills (overlay `skills/`; the tracked sources are
`packages/client-neutral-core/skills/**/SKILL.md`, measured 13), `config/SOUL.md`, and
`bin/` launchers (overlay `bin/`; tracked sources under
`packages/client-neutral-core/bin/`, measured 6: `codex`, `codex.cmd`, `hermes-npx`,
`hermes-npx.cmd`, `hermes-project-data.py`, `hermes-project-terminal-guard.py`). There is
no repository-root `skills/` or `bin/` directory: those two names are Hermes-Home overlay
paths, and the distinction matters because a reader who greps the repo for `skills/` finds
nothing and concludes the assets are missing. The managed
**config fields** are only `display.language` and `display.busy_input_mode`;
every other Hermes field (`sessions.auto_prune`, `memory.*`,
`hooks.pre_tool_call`, `mcp_servers.*`, `hermes.model.*`, `plugins`) is
OBSERVE — never overwritten. `config-ownership.json` (WL3-200) is the single
authority for field layers and modes; `preserve_unknown: true` — never
override user provider/model/auth/desktop state. Deploy to Hermes Home only
through `sync_hermes_workflow_assets.py` (backup-before-publish staging,
updates `skill-provenance.yaml` live hashes in the same change); never
promote the mixed-ownership live `config.yaml` wholesale.

## Verification

Run checks from the exact module path. Report structural checks separately from
live execution checks. Any failed, cancelled, missing, or skipped required job
fails the aggregate gate.

## Workflow Assistance execution contract

Workflow-assistance (now `packages/client-neutral-core` + `services/`) is the active owner of
workflow configuration, Task Ledger, Telemetry Ledger, sidecar, adapters, and delivery gates.
`apps/observer` (work-lab-observer) is a strict read-only projection: it may read
Workflow-owned projections but must not execute, approve, retry, apply, rollback,
change task state, or write the Telemetry Ledger.

When working through Codex, use the project-local workflow contract and exact
module paths. Bounded writers own one checkout; parallel writers require separate
worktrees. Prefer the canonical quality gate:
`python services/orchestration/run_quality_gate.py verify`.
Keep Task Ledger and runtime evidence under `.project-local/runs/` and
`.project-local/artifacts/`; do not treat local tests as exact-SHA CI or release
evidence. Codex may prepare changes and readback evidence, but must not commit,
push, publish, or modify global Codex/Hermes configuration without explicit
approval for that side effect.

## Five-dimension runtime baseline (mandatory, audited)

Every managed software surface must satisfy — and every audit must verify — the
following baseline, owned by the enhancement module:

1. **Unique entry per software.** One canonical launch path per tool — the
   OFFICIAL standard release format (whatever the vendor ships is the entry).
   Hermes: official desktop app (`apps/desktop/release/win-unpacked/Hermes.exe`,
   Electron) + `hermes` CLI; Codex: single wrapper (`bin/codex` bash +
   `packages/client-neutral-core/bin/codex.cmd`, identical versioned-glob resolution to the official
   runtime); DSH: official DeepSeek Harness `0.2.0-rc.2` (Electron, installed at the
   vendor default per-user path `%LOCALAPPDATA%\Programs\DeepSeek Harness\DeepSeek Harness.exe`;
   the install root is RESOLVED from the uninstall registry entry or the shortcut
   TargetPath, never hardcoded — the earlier community DSH Desktop 2.0.13 build and its
   `D:\All projects\DSH` path are SUPERSEDED; if a launch ever falls back to an empty C:
   skeleton while data sits elsewhere, check the `DSH_HOME` user env var layer first, ERR-088);
   CC Switch / OpenHuman / Open Design: single desktop shortcut to
   their installed official executables. No duplicate or conflicting launchers;
   entries are the official standard formats — WORK-LAB never invents custom
   launcher formats (e.g. .vbs) that replace the vendor-shipped binary.
2. **Desktop entry.** Every GUI tool opens from its desktop shortcut; shortcut
   target chains must resolve (Test-Path true end-to-end).
3. **Official standard + user configuration.** Official baselines win; the
   enhancement module only manages declared overlay fields and never overrides
   user provider/model/auth/desktop state (`config-ownership.json`,
   `preserve_unknown: true`).
4. **No blocking overhead.** Global rules/skills/guidance must stay lean
   (skills ~<10KB each, guidance+rules <20KB total) and load on demand, never
   blocking startup or execution. Wrappers must not stall on missing candidates.
5. **Task-level model policy.** Each task declares its own quality/cost/privacy/
   latency constraints (four-dimensional strategy). Provider routing is official
   (cost_multiplier=1.0, no daily/monthly caps by default). Model and
   reasoning_effort follow the user's native choice; this baseline only verifies
   that native capabilities/params are supported and nothing overrides the user's
   selection (low/medium/high are not, by themselves, failures). Pricing must include
   provider/model/currency/effective_at/source/version; missing fields display
   UNKNOWN. No global rate limits or cost caps — constraints are per-task and
   auditable.

When any dimension regresses (new entry point, config bloat, provider cap,
reasoning downgrade), fix at the root and record in the error ledger before
merging.
