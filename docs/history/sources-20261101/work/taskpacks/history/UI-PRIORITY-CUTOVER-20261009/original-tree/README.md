# WORK-LAB

`DTALEX66/WORK-LAB`（对外 **工作流实验室 / Workflow Lab**）是**客户端中立的个人 AI 工作流治理、
控制与交付系统**——个人 AI 工程控制平面。它把最高一层的用户级能力（Rules、Skills、
plugins/MCP 声明、Portable Memory、Capabilities、workflow policy）收成一份规范源，再为每个当前
客户端投影出原生形态，并裁决任务边界、权限、预算、证据与完成度。它**不是** agent runtime、
不是产品平台、不是第四个产品，也不因统一界面而取得写权。

核心价值是**工作方法的可迁移**：更换 Codex、DSH、Hermes、Qoder、WorkBuddy 或其他客户端时，
项目规则、任务合同、受管技能、工具声明、授权范围与验收标准不随品牌消失。企业化、K8S 与集中
账号不是前置条件。

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
> `docs/history/`（唯一检索锚点；见 `WL_INHERITANCE_MATRIX.json`，MiniGame = `FOREIGN_HISTORICAL`）。
> 参见 [`docs/decisions/PROJECT_POSITIONING.md`](docs/decisions/PROJECT_POSITIONING.md)。

## 当前 / 未来 / 候选（展示状态：Ongoing）

- **当前（有证据范围）**：规范源与配置事务治理、Task Ledger 与交付门、只读 Observer（React +
  Tauri 2）、模型注册与用量汇总、错误台账与权威链校验。证据等级一律用
  `NO_EVIDENCE / SIMULATED / SYNTHETIC / INTEGRATED / REAL`，`REAL` 必须有可核验句柄、身份与
  readback；跳过、取消或缺失的必需作业不计聚合 PASS。
- **未来（在册未成）**：真 Windows 桌面表面证明（U19/T03）、薄 Control 写路径（T04/AG-15）、
  结构化 Super Entry handoff（T05/AG-16/17）、双执行器黄金链（T06/AG-09）、模型真实消费者与
  OCR/ASR 验收（AG-10/AG-11）、缺失原件恢复（T07/AG-19）。逐行状态见
  [`docs/future/WORK-LAB-BLUEPRINT-COVERAGE.md`](docs/future/WORK-LAB-BLUEPRINT-COVERAGE.md)
  的生成投影，唯一可变源是 `.project/governance/blueprint-coverage.json`。
- **候选（按需触发，不按名单部署）**：`.project/governance/future-candidate-registry.json`，
  状态词表 `DEFERRED / PILOT_CANDIDATE / PILOT / PROMOTED / REJECTED`；22 条候选覆盖蓝图 §16 的 19 行，
  每行另有 `discovery` 上游回读、`native_evidence` 现存路径与 `decision`（2026-10-07 判定：15 退役 / 7 保留 / 0 晋升）。
- 完整项目描述与未来蓝图的仓库承接：
  [`docs/future/WORK-LAB-BLUEPRINT-20261006.md`](docs/future/WORK-LAB-BLUEPRINT-20261006.md)。

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
`taskpacks/current/WORK-LAB-UNIFIED-PRODUCT-CONVERGENCE-TASKPACK-20260918.md` for the
current positioning and migration record.
