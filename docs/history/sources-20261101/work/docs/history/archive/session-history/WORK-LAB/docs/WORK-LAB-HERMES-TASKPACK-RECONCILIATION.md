# WORK-LAB Hermes Task-Pack Reconciliation

Current source of truth: v2.0.0 supersedes the historical v1 snapshot. See 00-governance/PROJECT_POSITIONING.md and 50-taskpacks/WORK-LAB-V2-HANDOFF.md.

- **最终优先级来源**：`.hermes/desktop-attachments/WORK-LAB-HERMES-TASKPACK-v2.0.0.zip`
- **附件 SHA-256**：`e404fc15048be0eb583bbc35999b2be060949b32e1a5fa4493dd137dc496c610`
- **任务图**：`work-lab/task-cards/v2`
- **当前 HEAD**：`f89b2acbe5de2b6aade12861d9e6036de3a5b858`
- **当前停止点**：`READY_FOR_USER_APPROVAL`

## 1. 优先级与命名空间

附件任务包是最终任务基线。此前资料中的任务只作为历史证据或兼容内容来源，不得覆盖附件任务的定义、验收条件或安全边界。

| 历史来源 | 处理方式 |
|---|---|
| `MIG-001..MIG-008`（旧迁移快照） | 重新解释为 `HIST-MIG-001..HIST-MIG-008`；保留历史记录，不计入附件任务包完成度 |
| `GOV-001..GOV-008`（旧治理快照） | 重新解释为 `HIST-GOV-001..HIST-GOV-008`；保留历史记录，不覆盖新的 `ROOT-*` 任务 |
| 旧 Workflow-assistance dirty 工作树 | 只读来源；不 reset、clean、stash、覆盖或提交 |
| 当前 WORK-LAB 本地实现和验证 | 仅在与附件任务 ID、验收和边界兼容时合并 |
| Hermes live、Git commit/push/PR/merge/release | 继续独立审批，不因任务包附件自动授权 |

## 2. 当前事实基线

```text
root governance: 5/5 PASS
root governance contracts: 6/6 PASS
root contract catalog: 20/20 PASS
module dependencies: PASS; runtime_edges=0
project data boundary: PASS
supply chain: PASS
Workflow: 193 PASS, 4 skipped
Open Design: 203/203 + 223/223 + 10/10 + 460/460 PASS
MINIGAME local product gate: 321/321 PASS (historical/fixture evidence only; not an active canonical module)
```

旧 Workflow-assistance 与 WORK-LAB 目标模块（排除 `.git`、`.hermes`、`node_modules`、构建物、缓存和 Python bytecode）：

```text
source-only: 0
target-only: 0
byte-identical: 115
same-path divergent: 19
```

因此旧仓库没有未被吸收的独有路径；剩余工作是 19 个同路径差异的最终取舍，而不是整树复制。

## 3. 双 MINIGAME 当前差异

附件中的历史 `47 相同 / 55 分叉` 只保留为旧基线。当前重新读取结果为：

```text
Open Design minigame-runtime: 108 files
独立 D:\All projects\MINIGAME: 293 files
common paths: 102
same content: 4
divergent common paths: 98
Open Design-only: 6
standalone-only: 191
```

`MIG-003`、`OD-002`、`MG-003` 不能据旧数字宣称完成。副本删除、资产去重和独有内容迁回均继续保持审批阻塞。

## 4. 19 个 divergent 文件决策

所有决策均以 WORK-LAB 当前内容为最终候选；旧内容只作为历史参考。没有发现应反向覆盖 WORK-LAB 的兼容性缺口。

| 路径 | 最终决策 | 原因 |
|---|---|---|
| `.github/workflows/governance.yml` | KEEP_WORKLAB_FINAL | 兼容范围、无交互 pip、当前 monorepo 治理；符合 `ROOT-007` |
| `AGENTS.md` | KEEP_WORKLAB_MODULE | 根 `AGENTS.md` 已提供全局安全规则，模块文件只保留模块边界，避免重复/冲突 |
| `README.md` | KEEP_WORKLAB_FINAL | WORK-LAB monorepo canonical URL 和根 workflow 路径优先 |
| `config/config.yaml` | KEEP_WORKLAB_FINAL | `display.skin` 属于用户选择，不由增强模块管理 |
| `config/managed-config-schema.yaml` | KEEP_WORKLAB_FINAL | 不把用户皮肤纳入 managed config |
| `docs/workflow/project-definition.md` | KEEP_WORKLAB_FINAL | 当前入口指向 WORK-LAB，旧仓库仅标为 legacy dirty source |
| `scripts/workflow/sync_hermes_workflow_assets.py` | KEEP_WORKLAB_FINAL | plan-only、真实内容 SHA、皮肤保护和用户配置保留规则优先 |
| `scripts/workflow/task_ledger.py` | KEEP_WORKLAB_FINAL | 状态落在项目 ignored `.hermes/task-runtime/`，符合边界规则 |
| `scripts/workflow/verify_client_neutral_manifest.py` | KEEP_WORKLAB_FINAL | Hermes 为可选兼容范围，不把客户端运行时变成核心依赖 |
| `scripts/workflow/verify_core_schemas.py` | KEEP_WORKLAB_FINAL | 使用明确 `SchemaError` 负向验证，避免宽泛异常吞错 |
| `scripts/workflow/verify_portable_install.py` | KEEP_WORKLAB_FINAL | 使用兼容范围与 snapshot，不永久锁定精确版本 |
| `setup.ps1` | KEEP_WORKLAB_FINAL | 默认 plan-only，`-Apply` 才能进入 live 写入路径 |
| `setup.sh` | KEEP_WORKLAB_FINAL | 默认 plan-only，显式 apply、backup/readback/rollback 边界保留 |
| `tests/test_action_plan_sync.py` | KEEP_WORKLAB_FINAL | 增加隔离 repo/home 和源文件 mutation fail-closed 回归 |
| `tests/test_client_neutral_manifest.py` | KEEP_WORKLAB_FINAL | 验证可选 Hermes compatibility range 与无 Hermes CLI 环境 |
| `tests/test_project_data_boundary.py` | KEEP_WORKLAB_FINAL | 使用当前 monorepo 根和项目内 runtime 临时目录 |
| `tests/test_task_ledger.py` | KEEP_WORKLAB_FINAL | 测试 canonical `.hermes/task-runtime/task-ledger` 路径 |
| `tests/test_workflow_governance.py` | KEEP_WORKLAB_FINAL | 皮肤保护、兼容范围和当前治理合同优先 |
| `workflow-manifest.yaml` | KEEP_WORKLAB_FINAL | 兼容范围加 snapshot 是附件任务包要求的版本治理方式 |

## 5. 64 个附件任务的当前状态

ROOT-003「补齐契约 Schema」以及 `WA-001`、`WA-006`、`CONT-001`、`CONT-002` 已完成本地闭环：7 个 catalog contract 均有真实 schema 引用，Adapter interface、bounded retry、Ledger persistence 和 checkpoint/state-machine readback 均通过测试。

完整逐 ID 矩阵位于 ignored 证据：

`.hermes/task-artifacts/taskpack-assessment-20260806.json`

| 状态 | 数量 |
|---|---:|
| PASS | 25 |
| PARTIAL | 9 |
| PARTIAL_BLOCKED | 2 |
| NOT_RUN | 20 |
| READY_FOR_APPROVAL | 2 |
| BLOCKED | 3 |
| BLOCKED_USER_DECISION | 1 |

关键合并原则：

- 旧 `HIST-MIG-*` / `HIST-GOV-*` 的历史 PASS 不会自动满足附件 `MIG-*` / `ROOT-*`。
- 本地静态、隔离和单元证据不冒充 live runtime、云端 CI、真机、商业或 release 证据。
- `PASS` 只表示对应层级实际验证通过，不表示整个 batch 完成。
- `NOT_RUN`、`BLOCKED` 和 `*_USER_DECISION` 保持未完成，不通过文档合并伪造为完成。

## 6. 合并结果

- 兼容源内容：115 个完全一致路径已由 WORK-LAB 保留；不重复复制。
- 冲突内容：19 个 divergent 路径均采用 WORK-LAB 当前治理版本；旧版本不覆盖。
- 历史状态：迁移状态和旧 handoff 保留，但明确标为 historical/stale。
- 当前任务包：作为唯一 active task namespace 和 acceptance baseline。
- 源仓库：`D:\All projects\Workflow-assistance` 未被修改。
- Hermes Home：未写入、未 apply、未重载。
- Git：未 commit、push、PR、merge、release。

## 7. 仍需单独审批/决定

1. Hermes `LIVE_APPLY_AND_READBACK`。
2. WORK-LAB Git commit/push/PR/merge/release。
3. 双 MINIGAME 副本退役、删除、去重或迁回。
4. 首发平台选择：微信或抖音。
5. 根许可证与第三方资产许可处理。
6. 第二参考客户端选择及第二适配器实现。

本文件是 reconciliation 结果，不是 live deployment、Git delivery 或 release 证明。
