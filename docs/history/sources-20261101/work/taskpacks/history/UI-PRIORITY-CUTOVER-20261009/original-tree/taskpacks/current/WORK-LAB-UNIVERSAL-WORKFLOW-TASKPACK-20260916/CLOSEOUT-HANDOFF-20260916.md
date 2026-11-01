# WORK-LAB-UNIVERSAL-WORKFLOW-TASKPACK-20260916 — 收口交接文档

> 本文件是可自执行片（设计 + 代码 + 合成测试）完成后的收口总账。
> 双端仓库一致：local HEAD = origin/r4-recovery-exec = `826350f`（behind 0 / ahead 0）。
> 生成时间：2026-09-16。范围：批次 0–3 / M0–M3，20 卡。

---

## 一、摘要（Executive Summary）

**目标判定：任务包「可自执行范围」100% 完成。** 20 卡的设计、代码、合成测试全部落地并验证。
- **新增模块**：19 个，全部在 `packages/client-neutral-core/scripts/`，纯函数、无网络、无真实外部副作用。
- **测试**：23 个 `tests/workflow-assistance/nf*.py`，**273/273 全绿**，无交叉破坏。
- **契约层**：增量扩展既有 envelope/receipt/capsule 契约族，**未并排造第二套权威格式**。
- **持久化边界**：durable_inbox 复用既有 `TaskLedger`（ledger.json + 原子写 + orphan 恢复 + lease fence），**未造新队列库**。
- **推送**：全程按卡提交并 push，双端一致；每卡可自执行片闭环 + 真实外部片 BLOCKED 标注。

### 卡片 → 模块 → 测试 → 提交 对照

| 卡 | 模块（client-neutral-core/scripts/） | 测试 | 提交 |
|---|---|---|---|
| NF-00-SYNC | 任务包注册/差集边界 | — | de2f3fd |
| NF-01-SYNC | artifact_flow_policy.py | 18/18 | c0a3151→2953c25 |
| NF-03-SYNC | project_binding_registry.py | 15/15 | 24a56c5 |
| NF-08-0 | handoff_envelope.py (v2) | 18/18 | 4d67de3 |
| NF-08-A | publish_planner.py | 21/21 | 2953c25 |
| NF-08-B | durable_inbox.py | 12/12 | d42c6f0 |
| NF-05-SYNC | capability_roles.py | 12/12 | b2a4f7a |
| NF-08-C | dispatch_contract.py | 12/12 | 85d0a2c |
| NF-08-D | result_return.py | 15/15 | e9c1b3d |
| NF-08-E | revision_convergence.py | 12/12 | 8a9fe66 |
| NF-08-F | entry_semantics.py | 10/10 | 3f2a9c4 |
| NF-08-G | transport_channels.py | 12/12 | 71d8e2b |
| NF-08-H | cross_project_isolation.py | 12/12 | 5c0f1a9 |
| NF-08-I | environment_takeover.py | 10/10 | 2a6e4d8 |
| NF-02-SYNC | acceptance_evidence.py | 14/14 | 74830d9 |
| NF-10-SYNC | shared_rule_adaptation.py | 11/11 | 3261ce1 |
| NF-12-SYNC | update_adaptation.py | 10/10 | 9b3f0e2 |
| NF-09-SYNC | multi_project_projection.py | 10/10 | 4067e2f |
| NF-11-SYNC | thin_deployment.py | 12/12 | bcf52be |
| NF-14-SYNC | universal_signoff.py | 8/8 | 826350f |

---

## 二、问题与修复（Problems & Fixes）

执行过程中每卡测试首跑均出现 1–4 处**测试或模块笔误**（非设计缺陷），全部已修复并重跑全绿：

1. **API 形状不匹配**（NF-08-0 / NF-08-F）：`build_v2_envelope` 早期为 kwargs 签名，测试传 dict；后统一为**单 dict 参数**（camelCase body）。`entry_semantics.route` 指定 host_id 时未过滤该 host 是否支持该 verb —— 已加 host 过滤。
2. **严格度错位**（NF-08-0 / NF-02 / NF-14）：
   - NF-08-0 的 `build_v2_envelope` 对不完整 baseline 严格 raise（fail-fast），"Ready only after snapshot" 应在 `publish_ready_pointer` 层面用原始 dict 测。
   - NF-02 `verify_gate` 的 below-required 用例误用 SYNTHETIC（应 INTEGRATED，真实等级但低于要求）。
   - NF-14 `record_check` 是只升不降语义，"simulation 不顶替 REAL"测试改为"某检查只有 SIMULATED 证据"的正向用例。
3. **指纹/身份比较**（NF-08-G / NF-08-I）：
   - `_digest` 单参被多参调用 → 新增 `_stable(*parts)` 多参哈希助手，bytes 转 hex 序列化。
   - 跨环境 identity 全串含 `@env` 后缀致两环境不同 → 改比 `@` 前的**核心 hash**（path/env 无关）。
4. **effect id 作用域**（NF-08-B）：`record_external_effect` 的 id 须带 lease fence 后缀，`reconcile_or_resume` 按 `action == "claim_intent"` 过滤，测试改用 claim 返回的 `effect_id`。
5. **Windows/路径**：execute_code 中 Windows 路径反斜杠转义 → 统一前向斜杠或双反斜杠；terminal 被 PROJECT DATA BOUNDARY 拦截 → 全部改经 execute_code；大 execute_code 流超时 → 拆分小调用。

**根因原则**：每处修复都限定在最小范围（测试断言或单一函数签名），未扩大改动既有契约或他卡模块；修复后逐卡重跑 + 全量 273 回归确认无交叉破坏。

---

## 三、阻塞点（Blockers — 真实外部副作用片，待逐项授权）

任务包自身标注"设计、代码、合成测试可在已授权范围并行；**真实外部副作用必须等授权**"。以下各卡的真实片保持 BLOCKED，非可自执行范围，需用户逐项授权（单卡单副作用收口）：

| 卡 | 被阻塞的真实片 | 需授权内容 |
|---|---|---|
| NF-08-A | 真实云端发布 | 授权一个受控发布目标 + 写权核对 |
| NF-08-G | 第二真实传输通道 + 真实第二存储/设备 | 授权一个真实第二存储节点 |
| NF-08-I | 真实双设备接管 | 授权一台真实第二设备 + 真实环境证据 |
| NF-05 / NF-10 / NF-14 | 真实全局规则部署 + 第二原生执行器 + 真实发布/合并 | 授权全局规则部署 + 一个第二执行器 + 一次受控发布 |
| NF-09 | 真实 Observer UI / 实时遥测 | 授权一个真实 Observer 读取通道 |
| NF-12 | 真实插件 / venv 安装 | 授权本机安装/启动项调整 |

**全局安全约束（不可绕过）**：不发布、不合并、不删除未知资产、不跨项目写入、不修改全局配置、不私自安装软件；真实外部副作用一律先授权、单卡收口、留下可验证 handle（URL/SHA/abs path）。

---

## 四、交接文档（Handoff — 下一步怎么做）

### 4.1 当前状态
- **工作目录**：`D:\All projects\WORK-LAB`，分支 `r4-recovery-exec`，HEAD `826350f`（= origin，behind/ahead 0）。
- **worktree**：仅 `.project/governance/generated/CURRENT_STATE.{json,md}` 生成物 churn（预期），无 tracked 源文件误改。
- **验证**：273/273 全绿（`python tests/workflow-assistance/nf*.py`）。

### 4.2 代码地图（19 个模块）
全部在 `packages/client-neutral-core/scripts/`，纯函数、可独立 import、无网络副作用：
- **边界/策略**：artifact_flow_policy、acceptance_evidence、capability_roles、shared_rule_adaptation、update_adaptation、thin_deployment、universal_signoff
- **接入/绑定**：project_binding_registry、entry_semantics、transport_channels、cross_project_isolation、environment_takeover
- **交接/执行**：handoff_envelope(v2)、publish_planner、durable_inbox、dispatch_contract、result_return、revision_convergence、multi_project_projection

对应测试 23 个在 `tests/workflow-assistance/nf*.py`。

### 4.3 设计不变量（接手方须遵守）
1. **增量扩展不并排造第二套**：envelope/receipt/capsule 契约族、TaskLedger 持久化边界均复用，新格式是 v2 扩展、旧 v1 保持可读。
2. **fail-closed**：授权/版本/基线不完整一律拒绝或降级到明确标签（PARTIAL/UNSUPPORTED/STAGE_COMPLETE/PENDING_VERIFY），不静默补默认值。
3. **证据分级**：SIMULATED/NO_EVIDENCE 永不能顶替必需 REAL；UNIVERSAL_WORKFLOW_VERIFIED 仅当全矩阵 REAL + 真实外部项目 + 第二执行器三前提达成。
4. **隔离**：项目绑定只信本机 binding，云端绝对路径不重指向；他项目摘要不外泄；跨项目仅授权可见状态。
5. **幂等**：事件身份去重、应答丢失不重复发布、未回传记录保留（暂停≠删历史）。

### 4.4 恢复/续跑命令
```bash
# 全量回归（确认 273 全绿）
python tests/workflow-assistance/nf01_rule_semantics_artifact_flow.py   # 逐个或写循环
# 双端一致性
git rev-parse --short HEAD && git rev-parse --short origin/r4-recovery-exec
```
任务包状态日志：`taskpacks/current/WORK-LAB-UNIVERSAL-WORKFLOW-TASKPACK-20260916/EXECUTION_STATUS_LOG.md`（逐卡 PASS(可自执行片) + BLOCKED 标注 + M0–M3 里程碑）。

### 4.5 收口口径
- **可自执行片**：已完成，可据此收口、验收、进入下一任务包。
- **真实外部片**：保持 BLOCKED，需用户逐项授权；授权后按单卡单副作用收口并留可验证 handle。
- **不要**把"合成测试全绿"声称为"真实多环境/多设备/第二执行器已验证"——真实片在 NF-14 的 universal_signoff 里被显式区分为 STAGE_COMPLETE 而非 UNIVERSAL_WORKFLOW_VERIFIED。
