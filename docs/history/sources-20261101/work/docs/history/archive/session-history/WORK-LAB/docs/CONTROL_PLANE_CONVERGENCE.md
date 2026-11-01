# WORK-LAB Control Plane 收敛审计（对照全球生态调研档案）

> 依据：用户提供的《WORK-LAB 全球生态深度研究档案（完整版）》。目标：符合项目定位（Local AI Engineering Control Plane）、收敛成本、明确项目能做的任务。

> **2026-08-18 更新（v5 三项目分层）**：WORK-LAB 定位 = 控制平面 + 转化器（ArcheAxis 的知识调用者与归档回写者）。知识最终归 ArcheAxis（唯一真源），但**分阶段演进**：现有规则/技能/插件（已转化沉淀完成）阶段 1 归 WORK-LAB 自有；阶段 2 待 ArcheAxis 完整后逆向归档。WORK-LAB 不存知识、不建运行时。详见 `00-governance/THREE_PROJECT_LAYERING_DECISION.md`。

## 1. 定位校准

报告定义 WORK-LAB = **本地 AI 工程控制平面**（不拥有 Agent，只管理 Agent；Model 与 Agent 分离）。
五大核心能力：**Agent Registry · Work Unit Engine · Runtime Control · Governance Engine · Evidence System**。
明确 Ignore：不新建 Agent Framework、不做聊天 UI、不做模型训练平台。

## 2. 当前实现 vs 报告对照

| 报告能力 | 当前实现 | 状态 |
|---|---|---|
| Agent Registry（Module02） | `project_registry.py` + `agent_instances` 表 + `runtime_registry.py` | ◐ 有基础，缺统一 Agent 注册字段（capabilities/permissions） |
| Work Unit Engine（Module03，最重要实体） | `task_ledger.py`（任务台账，非标准 WorkUnit 状态机） | ⚠️ 缺 CREATED→PLANNED→ASSIGNED→RUNNING→VERIFYING→COMPLETED 状态机 + verification/evidence/cost 字段 |
| Runtime Control（Module04） | `codex_adapter` `hermes_adapter` `deepseek_harness_adapter` `acp_adapter` `adapter_sdk` | ✅ 较完整（报告 Phase2 核心） |
| Governance（Module08） | `model_policy.py` `memory_governance.py` + Context Control Plane | ◐ 雏形，缺 Policy Engine 统一规则 + Permission Inbox + Approval |
| Evidence（Module10，核心壁垒） | `execution_evidence.py` `workspace_evidence.py` `evidence_aggregator.py` `production_evidence.py` | ◐ 有分类证据，缺 Action Receipt 执行回执闭环（Nucleus 吸收点） |
| Observer（Module09，需重做） | Control Tower 观测栈（Grafana/Phoenix/Prometheus/Loki/OTEL）+ OB 界面原生指标 | ◐ 观测栈已部署且够用；报告要求重做为 **Agent Fleet 总览 + Execution Timeline**（OB 界面方向正确） |
| Sandbox（Module06） | 无专门 Sandbox Manager | ⚠️ 缺失（Level0-3 分级未实现） |
| MCP Gateway（Module07） | 无 | ⚠️ 缺失 |

## 3. 过度投入 / 需收敛

- **Observer 观测栈**（Grafana/Phoenix/Prometheus/Loki/OTEL/metrics）：已部署可用，**冻结不再扩张**。报告明确 Observer 是五层之一，不是主体；主体是 Control Plane。
- **前端（OB 界面）**：保留原生指标 + 业务面板，**下一步聚焦 Agent Fleet / Timeline**（报告 Module09），不追求更多 iframe/集成。
- **DSH session 挖掘/估算**：已产出 Token/成本（ESTIMATED），够用，不再深化。

## 4. 项目能做的任务（收敛成本，按报告 Phase 优先级）

### P0（Phase0 基础模型，当前最该补）
| 任务 | 内容 | 成本 |
|---|---|---|
| **Work Unit Engine**（报告最重要实体） | `work_unit.py`：标准状态机 CREATED→PLANNED→ASSIGNED→RUNNING→WAITING→VERIFYING→COMPLETED（+FAILED/BLOCKED/NEED_APPROVAL/QUARANTINE）；字段含 project/goal/agents/workspace/verification/evidence/cost；事件化（Event Bus） | ✅ 已实现（2026-08-17，测试通过）|
| **Agent Registry 完善** | `agent_registry.py`：统一注册字段（id/type/runtime/provider/capabilities/permissions）；对接现有 Adapter | ✅ 已实现（2026-08-17，测试通过）|

### P1（Phase1 Observer 重构——OB 界面升级）
| 任务 | 内容 | 成本 |
|---|---|---|
| **Agent Fleet 面板** | OB 界面：活跃 Agent 列表（runtime/status/cost/session），数据来自 `agent_instances` + Adapter `get_status` | ✅ 已实现（fusion-v3 renderAgentFleet）|
| **Execution Timeline** | OB 界面：时间线视图（WorkUnit + Session + Tool Call 事件流），数据来自事件表 | ✅ 已实现（fusion-v3 renderTimeline）|

### P2（Phase2 已验证，补全）
| 任务 | 内容 | 成本 |
|---|---|---|
| **Runtime Adapter 统一接口** | 按报告 Harness Adapter 抽象：start/stop/send/get_status/get_logs/get_usage/export_trace；`adapter_sdk.py` 已对齐 | ✅ 已实现（adapter_sdk + DSH adapter）|
| **DeepSeek Harness Adapter 完善** | 独立 Adapter 接管启停/状态/日志/Token/证据（报告：不修改上游） | 中 |

### P3（Phase3 Governance 起步）
| 任务 | 内容 | 成本 |
|---|---|---|
| **Policy Engine** | `policy_engine.py`：路径保护/危险命令/能力门；确定性评估 | ✅ 已实现（2026-08-17，测试通过）|
| **Action Receipt** | `action_receipt.py`（Nucleus 吸收）：回执账本（身份/策略/执行/结果/证据）| ✅ 已实现（2026-08-17，测试通过）|

### 暂缓（非当前重点，控制成本）
- Sandbox Manager（Level0-3）、MCP Gateway、Memory 三层、Harness Benchmark、Agent Provenance —— 报告后期 Phase4-5，当前不做。

## 5. 结论

- **当前已占位**：Runtime Adapter（强）、Evidence 分类（中）、Registry（中）、Observer 观测栈（已部署）。
- **最该补（收敛成本后）**：**Work Unit Engine**（报告最重要实体，是 Control Plane 的骨架）+ **Agent Fleet/Timeline**（OB 界面按报告重做方向）。
- **停止扩张**：观测栈不再加组件；前端不追求更多集成。
- **不动**：不新建 Agent Framework、不做聊天 UI（报告 Ignore 边界）。

## 6. 建议下一步

1. 冻结 Control Tower 观测栈（已可用），不再加服务
2. 实现 `work_unit.py`（Work Unit Engine 状态机 + 事件）—— 对照 task_ledger 演进
3. OB 界面加 Agent Fleet 面板 + Execution Timeline（Phase1 重构方向）
4. 后续：Agent Registry 完善 → Policy Engine → Action Receipt
