# WORK-LAB 生态调研对比分析（GitHub 实测 2026-08-17）

> 对《WORK-LAB 全球生态深度研究档案》所列项目进行联网核实：GitHub API 查询 license/stars/活跃度，对照报告吸收策略，修正高估/低估项。

## 1. 实测数据总表

### Control Plane 层
| 项目 | 仓库 | License | Stars | 活跃 | 报告策略 | 实测修正 |
|---|---|---|---|---|---|---|
| AGNT | agnt-gg/agnt | NOASSERTION | 516 | ✅ 2026-08 | ★★★★★ | ✅ 真实，本地优先 OS |
| AgentField | Agent-Field/agentfield | Apache-2.0 | 2519 | ✅ 2026-08 | ★★★★★ | ✅ 真实，API/微服务式 Agent |
| HumanLayer ACP | humanlayer/agentcontrolplane | NOASSERTION | 459 | ⚠️ **停滞 2025-07** | ★★★★★ | ⚠️ 一年多未更新，吸收需谨慎 |
| Mission Control | ykbryan/mission-control-for-agents | NONE | 8 | ⚠️ 2026-03 | ★★★★★ | ⚠️ repo 存疑（8⭐），需确认正确项目 |
| Nasiko | 未找到明确 GitHub | — | — | — | ★★★★★ | ⚠️ 未定位到活跃仓库 |

### Harness 层
| 项目 | 仓库 | License | Stars | 活跃 | 报告策略 | 实测修正 |
|---|---|---|---|---|---|---|
| **Omnigent** | omnigent-ai/omnigent | **Apache-2.0** | **8969** | ✅ 2026-08 | S 最高 Adopt | ✅✅ 最值得参考，meta-harness |
| OpenHarness | Cicizz/OpenHarness | MIT | **0** | ⚠️ 2026-04 | A 参考 | ⚠️ **几乎不存在**，可忽略 |
| **Bernstein** | sipyourdrink-ltd/bernstein | Apache-2.0 | 915 | ✅ 2026-08 | S Adopt | ✅ 确定性编排，值得参考 |

### Observer/Telemetry 层
| 项目 | 仓库 | License | Stars | 活跃 | 报告策略 | 实测修正 |
|---|---|---|---|---|---|---|
| Langfuse | langfuse/langfuse | MIT 核心 | 33240 | ✅ | S 参考 | ✅（前轮已审计） |
| AgentOps | AgentOps-AI/agentops | MIT | 5778 | ✅ | S 参考 | ✅（前轮已审计） |
| **TokenTracker** | xiufengsun/TokenTracker | MIT | 1346 | ✅ 2026-08 | S Adopt | ✅ 31 工具用量统计，贴合需求 |
| AI Observer | 未定位 | — | — | — | S | ⚠️ 未确认 |

### Governance 层
| 项目 | 仓库 | License | Stars | 活跃 | 报告策略 | 实测修正 |
|---|---|---|---|---|---|---|
| **MS Agent Governance Toolkit** | microsoft/agent-governance-toolkit | **MIT** | **5964** | ✅ 2026-08 | S+ 最重要 | ✅✅ 政策/零信任/MCP 治理，最值得学 |
| Nucleus | coproduct-opensource/nucleus | MIT | **20** | ✅ 2026-08 | S Adopt | ⚠️ **小众（20⭐）**，只参考 Action Receipt 概念 |

### Memory / Model 层（报告 Reference）
| 项目 | 仓库 | License | Stars | 活跃 | 实测 |
|---|---|---|---|---|---|
| Letta | letta-ai/letta | Apache-2.0 | 24283 | ✅ | ✅ 知名 |
| Mem0 | mem0ai/mem0 | Apache-2.0 | 63439 | ✅ | ✅ 知名 |
| LiteLLM | BerriAI/litellm | MIT | 高 | ✅ | ✅（未重新查询） |

## 2. 对比结论

### 报告描述准确的（可放心吸收）
- **Omnigent**（meta-harness，8.9k⭐ Apache）—— 最高优先级参考
- **MS Agent Governance Toolkit**（5.9k⭐ MIT）—— Policy/MCP 治理蓝本
- **AgentField**（2.5k⭐ Apache）—— Control Plane 架构参考
- **Bernstein**（915⭐ Apache）—— 确定性控制原则参考
- **TokenTracker**（1.3k⭐ MIT）—— 用量统计，贴合 WORK-LAB
- **Letta / Mem0**（24k/63k⭐ Apache）—— Memory 层参考

### 报告高估的（吸收降级）
| 项目 | 报告 | 实际 | 修正 |
|---|---|---|---|
| Nucleus | S Adopt | 20⭐ | 仅参考 Action Receipt 概念，不投入 |
| OpenHarness | A 参考 | 0⭐ | 忽略 |
| HumanLayer ACP | ★★★★★ Adopt | 停滞 2025-07 | 吸收需谨慎（项目可能弃维护） |

### 报告未定位的
- Nasiko / AI Observer / Mission Control 正确仓库 —— 未确认活跃仓库，按概念参考

## 3. 对 WORK-LAB 的收敛启示（结合前次收敛审计）

1. **不必再"吸收源码"**：真正值得参考的是**架构/概念**（Omnigent 的 adapter 层、MS Governance 的 policy、Bernstein 的确定性控制、TokenTracker 的用量事件），而非复制代码。
2. **WORK-LAB 自研核心**（报告独有壁垒）：Cross-Agent Control + Cross-Project + Evidence-Driven + Local-first —— 开源项目都不完全覆盖，需自研。
3. **优先任务不变**（收敛成本）：
   - **Work Unit Engine**（报告最重要实体，自研）
   - **Agent Fleet / Timeline**（OB 界面按报告 Phase1 重做）
   - **Policy Engine 起步**（参考 MS Governance，自研轻量版）
4. **参考资源就位**：Omnigent（adapter）、MS Governance（policy）、Bernstein（控制）、TokenTracker（usage 事件）的架构可随时查阅，无需部署。

## 4. 建议

- 保持收敛：观测栈冻结，不再加开源服务
- 下一轮任务：Work Unit Engine（自研核心实体）+ OB 界面 Agent Fleet/Timeline
- 参考链：Omnigent adapter 层 → WORK-LAB Adapter 统一；MS Governance policy → 自研 Policy Engine；TokenTracker 用量事件 → 统一 Usage Adapter
