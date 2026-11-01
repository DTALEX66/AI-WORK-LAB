# AI Agent Control Tower — 设计文档与观测层审计（2026-08-17）

状态：审计 + 设计草案。基于现有 WORK-LAB Observer 层能力盘点与开源 Agent Observability 方案对照。

## 0. 执行摘要

- **现有观测层不是"可抛弃"，而是"分层重组"**：平台适配、跨项目事实、Context 治理是自研独特价值（开源无法替代）；LLM Trace、评估、日志、可视化是真实缺口（开源明显更强）。
- **结论：保留核心事实层，抛弃弱可视化与重复组件，吸收开源栈补强 Trace/Eval/Logs/可视化。**
- 目标架构 = **自研事实层 + 开源观测栈** 的混合 Control Tower，而非二选一。

---

## 1. C 盘孤儿目录审计（只读，未动作）

| 路径 | 归属 | 类型 | 大小 | 结论 |
|---|---|---|---|---|
| `C:\Users\ALEX\Aether-Radar` | **DTALEX66/Aether-Radar**（git remote 确认） | 独立 GitHub 项目 | 446.7 MB / 26,900 文件 | 真实项目，未组织进 `All projects` |
| `C:\Users\ALEX\Cognitive-OS` | **DTALEX66/Cognitive-OS**（git remote 确认） | 独立 GitHub 项目 | 80.1 MB / 3,935 文件 | 真实项目，未组织进 `All projects` |
| `C:\Users\ALEX\d\All projects\*` | — | 空壳残留（仅 `.hermes`） | 0 | 废弃 release 残留 |
| `C:\Users\ALEX\d\wa-review` | — | 空壳（仅 `.hermes\task-runtime`） | 0 | 废弃残留 |
| `C:\Users\ALEX\.codex-session-delete` | Codex CLI 运行时 | 会话删除残留 | 小 | 可清理 |
| `C:\Users\ALEX\bin\scoop-shims-backup-20260816` | 8/16 备份 | scoop shims 备份 | 小 | 可清理 |

**建议**（待批准后动作）：`Aether-Radar`/`Cognitive-OS` 迁入 `D:\All projects\`（保持 git 历史）；`d`、`.codex-session-delete`、scoop-shims-backup 删除。

---

## 2. 现有观测层能力审计（canonical.sqlite 事实）

### 已有（自研）
| 能力 | 载体 | 成熟度 |
|---|---|---|
| 跨项目 Git/平台观测 | `source_quality` + `platform_observations` + `git_map` | ✅ 强 |
| Token 统计 | `usage_samples`（input/output tokens） | ✅ 有 |
| 成本估算 | `cost_estimate` / `cost_reconciled` | ✅ 有（粗粒度） |
| 执行实例/会话 | `agent_instances` / `sessions` / `execution_instances` / `execution_evidence` | ⚠️ 结构有，数据 0 行 |
| 任务/遥测事件 | `tasks` / `task_events` / `telemetry_events` | ✅ 有 |
| 只读投影 + SSE | `snapshot_api` (v3) / `sse_hub` | ✅ 强 |
| 上下文治理 | Context Control Plane / Drift Guard / Bundle | ✅ 独特 |
| 真相契约 | GET-only / loopback-only / UNKNOWN≠0 / fail-closed | ✅ 独特 |

### 缺口（开源明显更强）
| 缺口 | 说明 | 开源方案 |
|---|---|---|
| **LLM 调用链 Trace** | 无 span/trace_id，只有用量汇总 | Langfuse / Phoenix / AgentOps |
| **评估/质量** | 无 LLM 输出评估、幻觉检测、RAG 评估 | Phoenix / DeepEval / Ragas / Opik |
| **日志聚合** | 无集中日志（agent/tool/error 日志） | Loki |
| **指标可视化** | 自研前端弱，无 Grafana 级总台 | Grafana + Prometheus |
| **Agent 行为审计** | 无"做了什么/为什么/是否越权"录像 | AgentLens 类（未来） |
| **系统级监控** | 无 eBPF 级文件/网络/进程观测 | AgentSight（未来方向） |

---

## 2.5 开源项目 License 合规审计（GitHub API 实测 2026-08-17）

> 决定"可共用源码直接吸收"的第一约束是 license。数据来自 GitHub API 实时查询（仓库 license 字段 + LICENSE 文件内容）。

| 项目 | 仓库 | License | 源码可吸收? | 吸收方式 |
|---|---|---|---|---|
| Langfuse | langfuse/langfuse | **MIT**（核心；`ee/` 目录企业版专有） | ✅ | 自托管社区版（Docker） |
| Phoenix | Arize-ai/phoenix | **ELv2**（非 OSI 开源，限内部使用） | ⚠️ 仅内部自托管，禁止对外 SaaS | Docker 运行，不并入源码 |
| OpenLLMetry | traceloop/openllmetry | Apache-2.0 | ✅ | npm 依赖 |
| OTEL Collector | open-telemetry/opentelemetry-collector | Apache-2.0 | ✅ | 二进制/服务 |
| Grafana | grafana/grafana | **AGPL-3.0** | ❌ 传染性，不可并入仓库 | 独立 Docker 服务 |
| Prometheus | prometheus/prometheus | Apache-2.0 | ✅ | 二进制/服务 |
| Loki | grafana/loki | **AGPL-3.0** | ❌ 传染性，不可并入仓库 | 独立 Docker 服务 |
| Opik | comet-ml/opik | Apache-2.0 | ✅ | 自托管/源码 |
| AgentOps | AgentOps-AI/agentops | MIT | ✅ | Python SDK 依赖 |
| Helicone | Helicone/helicone | Apache-2.0 | ✅ | 自托管 |
| Laminar | lmnr-ai/lmnr | Apache-2.0 | ✅ | 自托管/源码 |
| DeepEval | confident-ai/deepeval | Apache-2.0 | ✅ | Python 库 |
| Ragas | explodinggradients/ragas | Apache-2.0 | ✅ | Python 库（维护慢，2026-02 后少更新） |

**合规结论**：
1. **可并入 WORK-LAB 源码/依赖**（Apache-2.0/MIT）：OpenLLMetry、AgentOps、Opik、Laminar、Helicone、DeepEval、Ragas、Prometheus、OTEL Collector。
2. **仅可独立服务运行**（AGPL-3.0：Grafana/Loki；ELv2：Phoenix）——Docker 自托管，**禁止**把源码并入 WORK-LAB 仓库（AGPL 传染性 / ELv2 使用限制）。
3. **Langfuse**：核心 MIT 可自托管社区版，`ee/` 企业功能不吸收。
4. **Ragas** 15k stars 但维护慢，选型降权（仅 ArcheAxis RAG 场景评估用）。

---

## 3. 开源方案选型对照（按你的分类）

### A. Agent 全链路监控（核心）
| 项目 | 定位 | 采用 |
|---|---|---|
| **Langfuse** | LLM/Agent Observability：trace + prompt 版本 + 成本归因 + 评估 | ✅ **吸收（自托管）** |
| AgentOps | Agent 运行监控（面向 Agent SDK） | ◐ 参考，不部署（与自研执行层重叠） |
| Phoenix | AI Debug：RAG/embedding/幻觉 | ◐ 内部自托管（**ELv2**，仅限内部） |
| Opik | LLM 评估 + 实验 | ◐ 可选（与 Phoenix 二选一，倾向 Phoenix） |
| Helicone | API Proxy 监控 | ✕ 不采用（proxy 模式与 OTEL 采集冲突） |
| Laminar | Agent Trace | ◐ 参考（Langfuse 已覆盖） |

### B. Token 实时监控
| 项目 | 定位 | 采用 |
|---|---|---|
| TokenTelemetry | Claude Code/Codex token/hour/day 统计 | ✅ **吸收其数据源**（自研采集器兼容） |
| TokenAnalytics | 项目级 token/成本排行 | ◐ 概念吸收进自研 usage 汇总 |

### C. 行为审计
| 项目 | 定位 | 采用 |
|---|---|---|
| AgentLens | Agent 行为录像（启动→计划→工具→结果） | ✅ **设计吸收**（自研"行为事件流"） |
| AgentSight | eBPF 系统级监控（未来） | ✕ 暂缓（P2，需 Linux/eBPF） |

### D. 采集标准
| 项目 | 定位 | 采用 |
|---|---|---|
| **OpenLLMetry** | LLM 领域 OTEL 采集器 | ✅ **吸收（统一采集层）** |
| **OTEL Collector** | 基础设施采集标准 | ✅ **吸收（网关）** |

### E. Dashboard / 指标
| 项目 | 定位 | 采用 |
|---|---|---|
| **Grafana** | 总控制台（指标+日志+数据源） | ◐ **独立 Docker 服务**（AGPL，不可并入源码） |
| **Prometheus** | 指标数据库 | ✅ **吸收**（Apache-2.0，二进制/服务） |
| **Loki** | 日志系统 | ◐ **独立 Docker 服务**（AGPL，不可并入源码） |

### F. 评估
| 项目 | 定位 | 采用 |
|---|---|---|
| DeepEval | LLM 测试框架 | ◐ 可选（接 Langfuse/Phoenix） |
| Ragas | RAG 评估 | ◐ 仅 ArcheAxis 知识系统用 |

---

## 4. AI Agent Control Tower 架构

```
┌────────────────────────────────────────────────────────────┐
│ Control Tower 总台（Grafana 11 + 自研 Observer 面板）       │
│  指标面板 · Trace 面板 · 日志面板 · 业务事实面板 · 成本面板  │
├────────────────────────────────────────────────────────────┤
│ 可视化/查询层                                               │
│  Grafana  ── Prometheus(指标) ── Loki(日志) ── Langfuse(UI)│
├────────────────────────────────────────────────────────────┤
│ 存储层                                                     │
│  Prometheus TSDB · Loki · Langfuse Postgres ·               │
│  canonical.sqlite(自研事实) · execution_instances(执行)    │
├────────────────────────────────────────────────────────────┤
│ 处理层                                                     │
│  Langfuse(LLM trace/评估/成本) · 自研 snapshot_api(v3)     │
├────────────────────────────────────────────────────────────┤
│ 采集层（统一）                                              │
│  OpenLLMetry SDK ─→ OTEL Collector ─→ (Langfuse/Prometheus)│
│  自研 collectors(git/platform/process/usage) ─→ canonical  │
├────────────────────────────────────────────────────────────┤
│ 数据源（Agent 平台）                                        │
│  Hermes · Codex · CC Switch · OpenHuman · Open Design      │
│  + 跨项目（WORK-LAB/DESIGN-LAB/ArcheAxis/Obsidian-Assistance）│
└────────────────────────────────────────────────────────────┘
```

**分层职责**：
1. **采集层**：OpenLLMetry 统一采集模型调用（替代自研 usage 采集的 LLM 部分）；自研 collectors 继续采集项目/平台/执行事实。
2. **处理层**：OTEL Collector 路由到 Langfuse（trace/评估）和 Prometheus（指标）；自研 snapshot_api 作为业务事实 API。
3. **存储层**：各司其职——指标入 Prometheus、日志入 Loki、trace 入 Langfuse、业务事实入 canonical.sqlite。
4. **总台**：Grafana 聚合指标/日志/数据源；自研 Observer 前端保留业务事实面板（平台状态、跨项目矩阵、Context 治理）。

---

## 5. 吸收 / 抛弃决策表

### 保留（自研独特价值，开源不可替代）
| 组件 | 理由 |
|---|---|
| canonical_store + collectors | 跨项目/平台业务事实，开源无对应 |
| Context Control Plane / Drift Guard / Bundle | 治理边界，开源无对应 |
| Truth Contract（只读/UNKNOWN/fail-closed） | 安全契约，必须保留 |
| snapshot_api / sse_hub | 作为业务事实数据源供 Grafana/自研面板消费 |
| 平台适配层（Hermes/Codex/CC Switch/OpenHuman/Open Design） | 采集面，开源不识别这些平台 |

### 吸收（开源补强）
| 开源组件 | 吸收方式 | 解决缺口 |
|---|---|---|
| OTEL Collector + OpenLLMetry | 自托管/源码 | 统一 LLM 采集 |
| Langfuse | 自托管（Docker/源码） | LLM Trace + 评估 + 成本归因 + prompt 版本 |
| Phoenix | 自托管 | 模型质量/RAG/幻觉 debug |
| Grafana + Prometheus + Loki | 自托管 | 指标/日志/可视化总台 |
| TokenTelemetry 数据源 | 采集器适配 | Claude Code/Codex token 实时 |
| AgentLens 行为流 | 设计吸收为自研"行为事件流" | Agent 行为审计 |

### 抛弃 / 退休
| 组件 | 理由 |
|---|---|
| observer_event.py / observer_runtime.py（旧事件系统） | 已标记 P0 移除，双事件写入面 |
| 自研前端的指标类面板 | 交给 Grafana（避免重复造轮子） |
| 自研 usage 汇总的 LLM 采集部分 | 让位 OpenLLMetry（保留项目级归因） |

---

## 6. 实施路线（阶段 + 验收）

### Phase 0 — 基线（现状）
- [x] Observer 层作为"业务事实层"保留
- [x] P0 修复（跨项目串值/伪0/token 字段/last-good）已合入
- 验收：76 前端 + 88 后端测试绿

### Phase 1 — 采集统一
- 引入 OTEL Collector（本地，Docker 或 Windows 二进制）
- 用 OpenLLMetry 包装现有 LLM 调用点（Hermes/Codex 侧），输出 OTEL 格式
- 自研 collectors 保持不变，输出进 canonical.sqlite
- 验收：OTEL 端到端（agent→collector→控制台）可见

### Phase 2 — LLM Trace + 评估
- 自托管 Langfuse（Postgres + 应用）
- OTEL Collector → Langfuse 接入
- 配置成本模型（按 provider/model 单价）
- 验收：真实会话出现完整 trace（span 链、token、cost、latency、error）

### Phase 3 — 总台
- 自托管 Grafana + Prometheus + Loki
- Prometheus 抓取：OTEL Collector 指标 + 自研 snapshot 指标
- Loki 收集：agent/tool/error 日志
- 验收：总台聚合指标/日志/业务事实，Dark/Light 可用

### Phase 4 — Control Tower 集成
- Grafana 面板模板（Token/成本/执行/平台状态）
- 自研 Observer 前端保留业务事实视图，指标链接到 Grafana
- 行为事件流（AgentLens 式）设计落地
- 验收：单入口总台，多项目/多平台/多 Agent 一览

---

## 7. 部署形态（"可共用源码直接吸收"）

- **Langfuse / Phoenix / Grafana / Prometheus / Loki**：优先 Docker Compose 自托管（
`D:\All projects\OS External Configuration\20-runtimes\agent-observability`），镜像从国内源拉取。
- **OTEL Collector**：Windows 二进制（独立运行，作为 Windows 服务）。
- **OpenLLMetry**：npm 包（DSH/自研采集器内 import）。
- 若不部署 Docker：Langfuse/Phoenix 有 Node/Python 源码可本地运行，但 Grafana/Prometheus/Loki 建议 Docker（Windows 原生支持有限）。
- 机器资源评估：Ollama 已占部分内存；Langfuse+Postgres+Grafana+Loki 预估 2-4 GB 内存，需确认。

---

## 8. 风险与边界

1. **网络**：当前 github.com:443 不通，docker 镜像与 npm 包需走国内源（registry.npmmirror.com 已验证可用）。
2. **资源**：本地新增 4-5 个常驻服务（Langfuse/Postgres/Grafana/Prometheus/Loki），需确认内存/端口。
3. **数据边界**：OpenLLMetry/Langfuse 默认采集 prompt/response——**必须配置脱敏**（WORK-LAB AGENTS.md 禁采集 prompt/response body）。
4. **只读契约**：Control Tower 各组件读 canonical 投影，不得反向写权威状态（保持 Truth Contract）。
5. **自研 vs 开源重叠**：采集/汇总逻辑避免双写（OTEL 与自研 collectors 职责分离：LLM 调用→OTEL，业务事实→自研）。

---

## 9. 下一步（待批准）

1. 处理 C 盘孤儿（Aether-Radar/Cognitive-OS 迁入 All projects；d/.codex-session-delete/backup 删除）
2. 确认部署形态（Docker 自托管 vs 源码运行）
3. 确认内存预算（Langfuse 栈 2-4GB）
4. 启动 Phase 1（OTEL Collector + OpenLLMetry 验证）
