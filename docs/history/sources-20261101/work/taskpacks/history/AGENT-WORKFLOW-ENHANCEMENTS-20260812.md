# Agent Workflow Enhancement Plan（2026-08-12）

> 全网调研（GitHub + HuggingFace，2026-08-12）提炼的 WORK-LAB 工作流增强方向。
> 已按用户要求**排除门禁验证类**（quality gate / exact-SHA CI / 评估基准）。
> 本文为 tracked 增强规划（roadmap），落地时按单 writer 纪律逐项立项。

## 全局范围声明（2026-08-12 补充）

增强落地于**全局全工作流**，三面生效，不限于本项目：

1. **实现层**：`10-workflow/workflow-assistance` 模块（TaskLedger / TelemetryLedger /
   sidecar_lock / 新脚本）——全局工作流基础设施，任何项目/会话可调用
2. **Hermes 侧**：Hermes 全局 skills（sleep-mode 已吸收 DAG 编排）
3. **Codex 侧**：受管 skills sync 到 live（14 skills，全局生效）

新增能力按"workflow-assistance 模块 = 全局工作流实现层"的定位暴露，
各项目消费方（CLO/Observer/任务包）经模块 API 使用，不各自复制。

## 调研来源

### GitHub（框架/工具，真实可落地）
| 工具 | ★ | 能力 | 调研结论 |
|---|---|---|---|
| langchain-ai/langgraph | 39.5k | 弹性 agent 图编排（状态机/依赖图/重试/持久化） | 任务依赖 DAG 参考 |
| huggingface/smolagents | 28.8k | code-thinking agent 库 | 方法论参考 |
| microsoft/autogen | 60.4k | agentic 编程框架（多角色/群体协作） | 多角色协作参考 |
| crewAIInc/crewAI | 57k | 角色编排（role-playing autonomous agents） | 角色化任务分派 |
| openai/openai-agents-python | 28.6k | 轻量多 agent 工作流（handoff/guardrails） | 委派/handoff 模式 |
| pydantic/pydantic-ai | 19.2k | 类型安全 agent 框架 | 结构化输出参考 |
| letta-ai/letta | 24.2k | stateful agents + 长期记忆 | 结构化项目记忆参考 |
| run-llama/llama_index | 51.6k | 文档/知识 agent | 知识检索参考 |
| stellarlinkco/myclaude | 2.7k | 跨 CLI 多 agent 编排（Claude Code/Codex/Gemini/OpenCode） | 多 CLI 并行编排 |
| nullclaw/nullhub | 2.0k | Agent 管理控制台（安装/配置/监控） | 会话生命周期治理 |
| AvivK5498/The-Claude-Protocol | 344 | 多 agent 编排 + 自动任务管理 | 任务队列增强 |
| traccia-ai/traccia-py | 98 | OpenTelemetry 原生 agent 追踪（span/调用链） | Trace 级可观测性 |
| palucdev/owflow | 3 | Spec-driven 开发工作流 | Spec→任务链 |

### HuggingFace（经代理 127.0.0.1:7890 访问）
- agents-course（官方 agent 课程）——方法论学习素材
- agent-leaderboard——评估榜（**接近验证类，排除**）
- jupyter-agent / computer-agent——工具型 agent，非工作流
- HF 侧框架集中在 GitHub，此处仅课程/模型有价值

## 增强方向（按价值排序，全部非门禁）

### 1. 多 Agent 编排层（任务依赖 DAG + 受控并行）——高优先
- **现状**：WORK-LAB 单 writer 串行；sleep-mode 单队列顺序推进；durable-isolated-writer-queues 仅隔离并行 writer
- **差距**：无任务依赖图；无"有依赖自动等待、无依赖自动并行"的编排
- **落地**：任务卡加 `depends_on` 字段 → sleep-mode 调度器升级为 DAG（拓扑序推进，独立分支并行）；writer 隔离沿用现有 worktree 机制
- **参考**：langgraph（状态机/持久化）、myclaude（跨 CLI 编排）、openai-agents（handoff 模式）
- **验收**：5 个任务的 DAG 中 2 个独立分支并行完成，耗时 < 串行

### 2. Agent 会话生命周期治理——高优先
- **现状**：sidecar 只有状态投影（LIVE/只读）；无会话注册/暂停/恢复/超时回收
- **差距**：僵尸会话/锁（历史 ERR：sidecar 锁被误判、zombie lock）无系统治理
- **落地**：sidecar 加会话注册表（session_id/owner/pid/心跳/超时）→ 超时自动回收 + 锁刷新
- **参考**：nullhub（管理控制台）、agent_session_manager（Elixir 会话库）
- **验收**：崩溃会话 5 分钟内自动回收，锁不再残留

### 3. Trace 级可观测性（调用链/span）——中高优先
- **现状**：Telemetry Ledger 有任务级事件，无 span/调用链
- **差距**：任务→子操作→工具调用的关联不可查（排查靠日志拼接）
- **落地**：telemetry 事件加 `trace_id`/`parent_id`；sidecar 提供 trace 视图（任务树）；不引入新依赖（手写 span 协议，OpenTelemetry 语义参考）
- **参考**：traccia-py（OpenTelemetry 原生）、LangSmith 模式（商业参考）
- **验收**：一次任务的全部工具调用可按 trace_id 树状回放

### 4. 结构化长期记忆（决策/教训自动沉淀）——中高优先
- **现状**：error-ledger（46 条）+ 交接文档（人工写）；记忆散落
- **差距**：无自动化的"为什么"层（决策原因不可查询）
- **落地**：ledger 事件自动聚合 → 项目知识文件（决策记录/教训/已验证模式）；引用 hermes-codex-config-drift 等已沉淀 skill 作为模式来源
- **参考**：letta（可学习记忆）、MemGPT 模式
- **验收**：新会话能查询"某决定为什么这样定"（从 ledger 自动检索）

### 5. Spec→任务链自动拆解——中优先
- **现状**：任务包 v1 权威（docs/truth 17 文件 + 4 ADR）；拆卡人工
- **差距**：无 spec→task 自动生成
- **落地**：任务包 spec 文件 → 自动生成任务卡链（含 depends_on/验收标准），人工确认后入 ledger
- **参考**：owflow、Spec-Kit/OpenSpec 模式（juejin 综述）
- **验收**：一个任务包自动产出完整任务卡链（人工只确认）

## 落地原则

1. 逐项立项（单 writer 纪律），每项独立 PR + 验证
2. 先做 #1（DAG）或 #2（会话治理）——对现有 sleep-mode/sidecar 收益最大
3. 不引入重型依赖（langgraph/letta 等仅作模式参考，落地用手写轻量实现）
4. 五维基线约束：新组件不增加启动阻塞、skills <10KB
5. 门禁验证类不扩展（现有 quality gate 已是最终防线）

## 状态

- [x] #1 多 Agent 编排层（DAG）——`TaskLedger.ready_tasks()` 拓扑就绪选择器（PR #75）
- [x] #2 会话生命周期治理——`SingleInstanceLock.acquired_at` + `status()`（锁时间戳/状态查询）
- [x] #3 Trace 级可观测——`TelemetryLedger.trace()` / `trace_tree()`（trace_id/parent_id 树）
- [x] #4 结构化长期记忆——`error_ledger_summary.py`（error-ledger → lessons 知识文件）
- [x] #5 Spec→任务链——`spec_to_tasks.py`（任务包 md → 任务卡声明 JSON）

全部落地于 workflow-assistance 模块（全局工作流实现层），配套测试
（task_ledger 20 / sidecar_lock 4 / telemetry 6 / enhancements 2）。
