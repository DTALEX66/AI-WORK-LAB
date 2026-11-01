# WORK-LAB

**找资料先看：[历史资料与原件总入口](docs/history/owner-inputs/INDEX.md)**（文件名/别名/压缩包成员检索、归档登记、去重与历史摘要）。

`DTALEX66/WORK-LAB` 是面向个人 AI 工作环境的、客户端中立的 **工作流管理、治理、运行监测与问题闭环系统**。
它连接和管理用户使用的 AI Agent、开发工具、工作流软件、模型服务、插件及运行环境，发现并汇总问题，
生成解决建议或可交给现有 Agent 的修复任务包，跟踪验证修复结果，固化可复用方案，并把知识候选提交 AAOS
正式审核。它不是 Agent、通用 Agent Runtime、模型网关、通用聊天客户端或全项目专业审计官。

**2026-10-19 当前任务：权威与路线图收敛；其他任务冻结，未来能力冻结/延期。**
唯一 CURRENT：[taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md](taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md)；
路线图：[docs/current/authority-convergence-20261019/ROADMAP.md](docs/current/authority-convergence-20261019/ROADMAP.md)；
收敛报告：[docs/current/authority-convergence-20261019/AUTHORITY-CONVERGENCE-20261019.md](docs/current/authority-convergence-20261019/AUTHORITY-CONVERGENCE-20261019.md)。
UI优先任务包已 SUPERSEDED，WUI 及其他任务不再独立派工；冻结不等于关闭，既有状态与证据保留。
本轮完成权威、路线图、索引与来源登记，产品代码未开始实现；实现状态与本机/CI/发布证据分别读回。

> **规范 Authority 与唯一入口（必读顺序）**：`WORK-LAB-AUTHORITY.md`（顶层人类权威）→
> `.project/governance/project-authority-index.json`（顶层机器权威）→ `AGENTS.md` →
> `.project/governance/taskpack-authority-index.json` 指向的 current TaskPack →
> `taskpacks/current/OPEN-TASK-REGISTER.md`（唯一在册开放任务账本，不建第二个）→ 范围内机器合同。
> **找不到任务或文档时先读**：`docs/current/DOCUMENT-CENSUS.md`（文档与任务总索引：每个文档面的位置、
> 数量、最后触碰时间、是否规范、由哪条门禁守着，以及从 `D:/All projects/Record` 收回来的唯一副本）。
> 优先级：最新明确用户决定 ＞ Authority ＞ 机器索引 ＞ current TaskPack 与账本 ＞
> `AGENTS.md` 与范围内合同 ＞ 当前精确提交代码与 CI/运行时读回 ＞ 历史记录（冻结、非规范）。
> 审计入口：`python scripts/ci/verify_project_authority_reference.py`、
> `python scripts/ci/verify_blueprint_coverage.py`、
> 快照 `docs/audits/BLUEPRINT_SYNC_AUDIT_2026-10-06.md`。
>
> **当前定位（V2 converged）**：两个规范模块是 `packages/client-neutral-core`（任务/遥测账本、
> sidecar、adapter、交付门）与 `apps/observer`（严格只读投影）。支撑面 `services/`、
> `integrations/`、`config/`、`apps/token-monitor/` 服务这两个模块，不是独立模块根。
> 受管客户端：**Hermes · Codex · DSH · GitHub · Open Design · OpenHuman**，未来任何 AI 软件经同一
> Adapter 合同接入；CC Switch 为 LEGACY_OBSERVE（只观测、不主动写）。冻结历史在
> `docs/history/`（唯一检索锚点；见 `.project/governance/generated/WL_INHERITANCE_MATRIX.json`，MiniGame = `FOREIGN_HISTORICAL`）。
> 参见 [`docs/decisions/PROJECT_POSITIONING.md`](docs/decisions/PROJECT_POSITIONING.md)。

## 当前任务与历史范围

当前任务状态见`taskpacks/current/OPEN-TASK-REGISTER.md`，当前执行输入见唯一CURRENT（权威收敛）。WUI 行保留但已冻结。
原件与历史归档：`docs/history/owner-inputs/20261009/SOURCE-INTEGRITY.json`、`taskpacks/history/UI-PRIORITY-CUTOVER-20261009/FROZEN-MANIFEST.json`。
旧蓝图、Atlas、UI/Qoder/ORCA等计划已冻结为历史或逐条继承，不作为当前首版义务；有效实现与安全门保留。
历史coverage投影仍可用于追溯，不产生当前派工；候选名录保留证据，不授安装/部署权限。

## Neutrality (unbound, unlocked)

- **Client-neutral**: one canonical source → per-client native projection, not
  byte-identical copies.
- **Unbound**: the current clients (Hermes · Codex · DSH · GitHub · Open Design ·
  OpenHuman; CC Switch is LEGACY_OBSERVE, observe-only) are the *current*
  adapters, not permanent dependencies; future AI software plugs into the same
  contract. DSH is a replaceable agent runtime (temporary executor in the model
  control-plane taskpack), not a Hermes replacement; see
  [`docs/decisions/PROJECT_POSITIONING.md`](docs/decisions/PROJECT_POSITIONING.md).
- **Unlocked**: core schemas use stable IDs and capability discovery — never
  hard-coded programs, model IDs, versions, ports, or install paths.

## Workspace mission

WORK-LAB turns a request that spans planning, execution, review and delivery into
an auditable task-pack loop:

```text
request / task pack
  -> ownership + allowed paths + data boundary
  -> one writer with read-only parallel audits
  -> RED -> GREEN -> targeted/module/aggregate gates
  -> exact tree review + recovery evidence
  -> explicit commit/push/release approval
```

The global workflow surface is repository-controlled portable source under
`packages/client-neutral-core`. Hermes Home, credentials, sessions, cron
metadata, provider routes and live caches remain **global platform state**; they
are never absorbed into this repository. Project task data and generated
evidence stay under the current Git root's ignored `.project-local/` boundary.

## Canonical active modules

The machine module model (`.project/governance/projects.json`) defines exactly
two canonical modules:

- `packages/client-neutral-core` (module id `workflow-assistance`) — global,
  client-neutral workflow governance, task/telemetry ledgers, sidecar,
  adapters and delivery gates
- `apps/observer` (module id `work-lab-observer`) — strictly read-only
  derived observation, projections and evidence reports

Active implementation / supporting source surfaces that serve those modules
(not separate module roots): `services/` (orchestration, policy,
execution-federation, receipts, session-federation, task-governance, radar,
security and cleanup), `integrations/`, `config/` and `apps/token-monitor/`.

Frozen history lives under `docs/history/` (single retrieval anchor, incl.
converged report history from `90-archive/` via MOVE-005; `90-archive/`
retains only its `BOUNDARY.md` gate marker). MiniGame and pre-cutover
r4-era material remain archive evidence, not active modules.

The repository preserves source history and keeps module implementations under
their canonical prefixes. Root governance owns stable contracts, task/evidence
formats, CI, release policy and cross-module ownership; it does not duplicate
module implementations.

## Task-pack responsibility

All substantial work is represented by a reviewed task pack under
`taskpacks/current/`. A task pack must identify the writer, read-only reviewers,
allowed/forbidden roots, input evidence, completion contract, verification
commands, rollback handle and external-mutation approval. Missing evidence,
dirty ownership, boundary violations or incomplete required jobs fail closed.

## Safety boundaries

- One Git root; module rules may narrow root rules but never weaken them.
- `.project-local/` holds ignored runtime + evidence data; frozen history
  lives under `docs/history/` (single retrieval anchor — `90-archive/`
  converged into it, retaining only its `BOUNDARY.md` gate marker).
  Durable handoffs may be retained only when explicitly
  covered by a recovery contract.
- Secrets, credentials, prompt/response bodies and private browser data never enter evidence.
- Project artifacts never spill outside the project Git root; any spill is
  traceable, locatable, cleanable and migratable (see
  `.project/governance/project-data-boundary.json`).
- The `E:` and `F:` data volumes are protected: any access requires explicit per-path,
  per-operation user authorization.
- External mutation, active-path switching and release actions require explicit approval.
- Windows paths are checked case-insensitively before release.

See `docs/decisions/PROJECT_POSITIONING.md`, `.project/governance/projects.json`,
module `AGENTS.md` files, and
`taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md` for the
current positioning and migration record.
