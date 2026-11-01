# WORK-LAB Branch Convergence & Anti-Regression Rules (2026-09-17)

> **性质**：分支合并与历史决策防回退的权威规则。登记于 taskpacks/current/。
> 当前 r4-recovery-exec 已推进至 `53f6bf9`（任务包原始 SHA 快照基于 `f02edd3`，DSH 后续 5 个提交已推进 r4）。

## §1 — main 是未来唯一主线

```text
r4-recovery-exec (最新执行候选线)  →  main (最终 authority)
```

**不得**再建立 `r5-recovery`、`r6-final` 等长期第二主线。

## §2 — 决策优先级链

P0 当前项目最新用户明确指令 → P1 后续用户纠偏/supersession → P2 当前 WORK-LAB 最新有效任务包/AGENTS/decision → P3 当前云端 exact-SHA 实际代码与 CI → P4 历史对话/历史任务包/旧审计 → P5 老 branch 自身 claims。

越旧的内容只能帮助恢复原始目标，**不能覆盖后来明确纠偏**。

## §3 — 当前必须保留的最新项目定义

- §3.1 WORK-LAB = 跨项目、跨软件、客户端中立的 Workflow / Agent Operations / Governance / Federation Control Plane。Hermes/Codex/DSH 是管理/适配的执行面，不重拆平行产品。
- §3.2 五维基线持续有效：官方标准入口 / 入口真实可达 / 官方标准+用户配置 / 不制造阻塞和过重上下文 / 保留原生模型推理能力不降级。
- §3.3 治理必须轻量：Global User Rule + Project Delta + Software Adapter + On-demand Skills。不再增加第二套 ledger/authority/规则发布器/配置同步器/重复状态文件。

## §4 — 目录标准

当前有效运行数据边界 = `.project-local/`。旧 `.hermes/`、旧编号目录（`00-/10-/20-/30-/40-/50-taskpacks/80-evidence/90-archive-manifests`）只作为迁移历史和兼容证据，不得从旧 branch 恢复为未来标准。旧 `.hermes` 结论只适用于其当时历史阶段。

## §5 — 当前分支权威关系（2026-09-17 刷新）

```text
main              = e5231f0   (r4 祖先)
migration/wl-dir… = c6b7e8f   (r4 祖先)
r4-recovery-exec  = 53f6bf9   (最新)
```
PR #123 (migration→main) 实际状态 = **OPEN** → `SUPERSEDED_BY_R4` → 必须关闭/退役。

## §6 — 六类分支判定

ACTIVE / ABSORBED / SUPERSEDED / RESIDUAL_TO_PORT / HISTORICAL_KEEP / FOREIGN。
RESIDUAL_TO_PORT 是唯一允许从旧 branch 进 main 的类型，须同时满足 6 条件（仍符合最新定义 / 未被后续推翻 / 当前 r4 确无 / 非纯文档宣称 / 有实际使用价值 / 能通过当前架构边界），且只能最小 cherry-pick 或当前架构重写，**禁止整支 merge**。

## §7 — 禁止用 commit 数量判断价值（逐功能对照，非 ahead/behind）

## §8 — 旧分支有效内容必须"抽取"，不能整支合并；main 来源只有 r4 最新收敛状态

## §9 — 已明确不能恢复的旧方向

- `migration/minigame-local-head`：FOREIGN / NOT_WORK_LAB / DO_NOT_MERGE。审计实测：该分支已是 r4 祖先，minigame 内容仅存于 r4 `docs/history/archive/`（历史档案，非 live-code）。
- Open Design / OpenHuman 旧 MANAGE → OBSERVE：SUPERSEDED，保留 integration Skill，不恢复旧 ownership。
- 旧编号目录：SUPERSEDED，由 `packages/services/apps/integrations/config/.project/.project-local` 替代。移植代码 ≠ 恢复旧架构。

## §10 — Universal Workflow 是当前有效新增层，但不是新项目主线

NF-00~NF-14 可自执行片已落地（19 模块 + 273 测试全绿），只作为 WORK-LAB Control Plane 能力层存在。不因此丢掉 Observer、配置管理、Skill/Plugin 管理、模型/版本适配、Session Federation、Execution Federation、Memory、Radar、Repo/Spill、Task governance。

## §11 — BR-RESIDUAL-AUDIT（2026-09-17 已完成）

| 判定 | 数量 | 说明 |
|---|---|---|
| SUPERSEDED_HISTORICAL | 52 | 只含旧编号布局 / 纯历史交接文档，DL-DIR-MIG-R1 已有意移走 |
| ABSORBED | 3 | r4 祖先，内容已在 r4 |
| RESIDUAL_TO_PORT（live-code） | **0** | 无旧分支有 r4 缺失的 packages/services/apps/integrations/tests/config 文件 |
| FOREIGN | 0 | minigame 实为 r4 祖先（非 FOREIGN 分支），内容已作历史档案在 r4 |

**结论：cutover 无需任何残余 port；main = r4 as-is（+ §12 B/C 人工复核）。**

## §12 — MAIN Cutover 前最终组成

A. r4 当前有效全部实现（= 53f6bf9，main..r4 = 148 commits）
B. 最新对话明确要求但尚未完成的必要修复（由 P0/P1 逐条核实）
C. 历史对话中仍有效且被遗漏的能力（§11 残余审计 = 0 live-code）
D. 旧 branch residual audit 确认的少量唯一有效残余（§11 = 0）

明确排除：旧治理错误、已 supersede 政策、旧 runtime 根、旧 authority、小游戏、已迁出业务资产、重复实现、纯历史 CURRENT_STATE、旧 handoff claims、错误软件 ownership。

## §13 — MAIN 完成后重新定义历史

main = ACTIVE / AUTHORITATIVE；其余 branch → DELETE 或 TAGGED_HISTORY；任何 Agent 默认读 main，不得扫描全部分支自己猜"更先进旧分支"。

## §14 — Branch Retirement Ledger

删除前生成 `BRANCH-RETIREMENT-LEDGER-20260917.json`（本仓已生成，登记于 taskpacks/current/）。
每条字段：branch / tip_sha / historical_purpose / latest_decision_status / superseded_by / ported_commits / current_equivalent / archive_tag / safe_to_delete / reason。
以后不再重复解释"为什么当年这个分支没 merge"——直接查 ledger。

## 最终原则

> 未来 MAIN = 立项至今的原始目标 × 后续所有用户明确纠偏 × 当前最新有效架构 × 当前云端真实代码 × 尚未被 supersede 的历史有效能力 - 历史错误/漂移/误混项目/已废止政策。

**旧分支永远不是未来主线候选；它们最多只是"证据源"和"残余能力供体"。**
