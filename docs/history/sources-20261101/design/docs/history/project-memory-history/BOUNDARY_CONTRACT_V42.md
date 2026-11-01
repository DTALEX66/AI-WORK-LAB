# BOUNDARY_CONTRACT_V42 — 职责边界合同

- 版本：`4.2`｜任务：`V42-0202`｜状态：`ACTIVE`｜证据：E1
- 依赖：V42-0201（唯一产品定义 V4.2）
- 权威：本文件 + `PRODUCT_DEFINITION_V42.md` + `config/product-manifest.json` SSOT 一致

## 目的

固化 Open Design 与 DESIGN-LAB 的职责边界，保证本仓库
**不成为第二前端、第二 Agent runtime、模型网关、独立账号系统或泛用向量库**。
任何实现、文档或能力声明不得越过本合同的边界。

## 1. Open Design（当前参考宿主/上游软件本体）的职责

Open Design 软件本体（stable）是**当前主入口/参考宿主**（架构面向任意设计 AGENT 平台，不绑定版本），负责：

| 领域 | 职责 |
|---|---|
| 工作区 | 项目、项目树、主窗口/Figma-like 画布 |
| 交互 | 用户主界面、设计流程执行、人工选择与确认 |
| AI 调用 | Agent 启动、模型调用界面、生成请求 |
| 运行时 | 插件/Scenario/Atom 运行时、Stage event、GenUI |
| 产物 | Artifact 创建、预览、导出、版本管理 |
| 配置 | 插件发现、安装、权限、私有 app-config（本仓库不得写） |

**推论**：当前一切设计流程执行、AI 调用、画布操作和生成都发生在 Open Design（参考宿主）里；架构上任意设计 AGENT 平台均可作为宿主接入。

## 2. DESIGN-LAB 的职责（只做增强，不做替代）

本仓库是**面向任意设计 AGENT 平台的能力增强层**（当前参考宿主：Open Design），只负责：

- 协议与合同：Brief、Reference DNA、Direction、Design System、Score、
  Preflight、Handoff、Provenance、Evidence Schema；
- 专业方法：Domain Pack、Scenario、Bundle、Plugin/Atom 的协议定义；
- 知识资产：开源资料、标准、大师方法（匿名化）、失败模式、来源治理；
- 质量门禁：视觉质量、设计 Critique、反 AI 痕迹、预检；
- 交付合同：可编辑交付、资产打包、权利 BOM、Benchmark、人工评审和能力证据。

**不负责**：

- ❌ 不做第二套 Open Design / Lovart 类应用壳；
- ❌ 不做 Agent 运行时、聊天客户端、模型网关或通用工作流平台；
- ❌ 不拥有自己的 provider/model 认证（不写死模型，不持有 API Key）；
- ❌ 不建独立 SaaS、账号系统或泛用向量库；
- ❌ 不复制 Open Design 的画布、项目、模型路由或 Artifact 系统；
- ❌ 不把静态文件、Schema 通过或 VLM 自评冒充运行可用。

## 3. 执行协调器（Hermes/Codex/兼容 CLI）的职责

- 唯一用户入口之一（Open Design 内的人工操作 + 外部协调器的编排）按任务授权执行；
- 负责任务编排、状态、风险、审批、工具路由与证据汇总；
- **客户端中立**：任务包不绑定固定客户端或模型版本；
- 默认不 live apply、不 commit/push/PR/merge/改 Ruleset/release，停在
  `READY_FOR_USER_APPROVAL` 等待授权。

## 4. MiniGame 边界（冻结）

`minigame-runtime` 已存在于云端 main，只允许：

- 安全修复、构建修复、资产完整性、既有测试；
- HUD/UI/图标/视觉规范/皮肤/提示词/设计 fixture/runtime reference。

**禁止**：平台工程、广告、变现、发行、运营和完整产品逻辑扩张。

## 5. WORK-LAB 边界

- 与本项目完全切割；
- 仅保留历史迁移指针（handoff 指针和 Git 历史）；
- 不维护、不重耦合、不复制模块/runtime。

## 6. 边界硬规则（Gate）

1. 全仓不得出现第二前端应用壳；
2. 全仓不得出现第二 Agent runtime（不实现自己的 daemon/事件循环/任务调度器）；
3. 全仓不得出现模型网关（不实现 provider 路由/密钥管理/统一推理 API）；
4. 全仓不得出现独立账号系统或泛用向量库；
5. 任何文档不得宣称本仓库“拥有”Open Design 的画布/项目/模型路由；
6. 证据等级声明不得超过真实证据（E1/E2/E3/E4/E5 不冒充）。

## 7. 一致性检查

- `config/product-manifest.json` 的 `primaryRuntime: "Open Design (current reference host...)"`、`nonGoals`
  与本文件一致；
- `README.md`、`PRODUCT_DEFINITION_V42.md`、架构文档、能力矩阵引用同一 SSOT；
- 若发现上述任一条被违反，按 `06_PROJECT_DRIFT_CONTROL` 标记 `DRIFTED` 并修复，
  触碰不可变边界则 `BLOCKED_REAUTH`。
