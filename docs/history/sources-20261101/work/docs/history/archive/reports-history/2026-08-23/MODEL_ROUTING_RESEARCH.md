# 模型路由调研 + 可行性分析（2026-08-21）

> 对应 WLR-400（Model Reference）+ WLR-410（任务到能力到Lane解析）。行业最新调研。

## 1. 行业现状（2026-08 最新）

- Nvidia NeMo Switchyard（2026-08-20 发布）：软件路由器，AI 成本降 74%，Nvidia 官方
- Snowflake Cortex AI Gateway（2026-08-18）：动态模型路由，企业 AI 成本
- Zylos Research Agent Model Routing（2026-03）：Agent 模型路由策略综述
- codex-multi-model-orchestrator（GitHub）：Codex 多模型编排（路由/并行/成本/验证）
- cadtopo（GitHub）：成本感知多 agent 编排（动态拓扑/每轮选择/自停）

结论：模型路由是 2026 主流趋势（Nvidia/Snowflake 官方入场），可行性成熟。

## 2. WORK-LAB 差异化（WLR-410 落地）

行业方案多为网关型（代理请求转模型）。WORK-LAB 定位不同：

WORK-LAB（路由=规则引擎，零模型调用）  ->  客户端（执行）
任务分类(确定性规则) -> Lane推荐 -> InvocationPlan -> Hermes/Codex/DSH 调用
  风险/类型/上下文/隐私/预算            客户端中立（可替换）
  成本预算 + 缓存优先(WLR-420)

关键差异：路由本身零模型调用（WLR-410：常规路由判定不调用模型）——用规则而非 LLM 分类，省钱且确定。

## 3. 可行性结论：可行

- 行业验证：Nvidia/Snowflake/开源都有成熟方案
- WORK-LAB 基础：software-registry + cc-switch catalog（DeepSeek/OpenAI/本地 H3）+ policy_engine 已存在
- 客户端中立：产出 invocation plan，客户端执行（符合三项目分层）
- 成本控制：规则路由零模型开销 + 预算上限 + 缓存优先
- 本地模型：MiniMax H3（DESIGN-LAB 共用）作本地 Lane（隐私/离线）

## 4. 实现设计（WLR-410）

### Lane 设计

- Lane-A 快速/低成本：DeepSeek V4 Flash，用于日常/文档/简单代码/翻译
- Lane-B 强推理：gpt-5.6-terra (Codex)，用于复杂代码/架构/调试
- Lane-C 视觉：qwen2.5vl (本地)，用于图片/OCR/UI 理解
- Lane-D 本地/隐私：MiniMax H3 (本地)，用于敏感数据/离线

### 路由规则（确定性，零模型）

输入: 任务描述 + 元数据(风险/类型/预算/上下文长度/隐私要求/工具需求)
规则优先级:
  隐私敏感 -> Lane-D
  含图片/视觉 -> Lane-C
  高风险/复杂架构/调试 -> Lane-B
  简单/日常/低成本 -> Lane-A
  预算超限 -> 降级 Lane-A 或 BLOCKED
输出: { lane, model_ref, budget, cache_policy } (InvocationPlan)

### 与 WLR-400 衔接

WLR-400 Model Reference（注册 DeepSeek API / Codex 订阅 / 本地 H3）
  -> WLR-410 Lane 解析（规则路由产出 plan）
  -> WLR-420 缓存友好（稳定前缀）
  -> WLR-430 Token/成本真值（EXACT/ESTIMATED/SUBSCRIPTION_INCLUDED）

## 5. 风险与边界

- 不代理凭据（路由只产出 plan，凭据在客户端）
- 不承载模型请求正文（WLR 边界）
- 订阅 vs API 成本分开（Codex 订阅 token 不伪算 API 费）
- 路由误判 -> Eval 样本（WLR-440）校准
## 6. 成熟方案清单（2026 可用）

| 方案 | 类型 | 模式 | 特点 |
|---|---|---|---|
| LiteLLM | 网关 | 开源(MIT) | 最流行；统一 API + 100+ provider；路由/负载均衡/成本追踪/缓存 |
| OpenRouter | 托管网关 | 商业服务 | 统一 API 聚合模型；无需自托管 |
| Portkey | 网关 | 开源+商业 | 路由/可观测/缓存/守卫 |
| RouteLLM | 路由策略 | 开源 | 成本感知阈值路由；成本降 30-85% |
| Nvidia NeMo Switchyard | 网关 | 开源(2026-08) | Nvidia 官方；软件路由器；成本降 74% |
| route-switch | 网关 | 开源 | 轻量路由切换 |
| NotDiamond/Martian | 路由策略 | 商业 | 数据驱动路由选择 |

### 对 WORK-LAB 适用性（借鉴不照搬）

- WORK-LAB 边界 = 不代理请求正文/凭据（WLR 明确）——不是网关型
- 可借鉴：RouteLLM 成本阈值思路（进 WLR-410 规则）、LiteLLM provider 抽象（与 adapter 对齐）
- 可选接入：LiteLLM/NeMo Switchyard 可作执行后端（客户端经网关调模型）——需单独评估边界
- 结论：WLR-410 规则路由为主 + 成熟网关作可选执行后端（待用户决定）