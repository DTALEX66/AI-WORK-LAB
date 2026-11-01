# BOUNDARY_CONTRACT — 职责边界合同

- 版本：`1.0`｜状态：`ACTIVE`｜SSOT 角色：边界契约

## 目的

固化 DESIGN-LAB 与宿主/工具/Agent 的职责边界，保证本仓库**不成为第二前端、第二 Agent runtime、模型网关、独立账号系统或泛用向量库**。

## DESIGN-LAB 的职责（只做增强，不做替代）

- 协议与合同：Brief、ReferenceSet、Direction、DesignSystem、QualityAssessment、Preflight、Handoff、Evidence；
- 专业方法：MethodCard、DomainPack、Rubric、Scenario、Bundle、Adapter 协议；
- 知识资产：受治理的来源、方法、标准、注册表、BenchmarkCase；
- 质量门禁：视觉质量、设计 Critique、反 AI 痕迹、预检；
- 交付合同：可编辑交付、资产打包、权利 BOM、人工评审和能力证据。

## 不负责

- ❌ 不做第二套设计软件前端/画布/编辑器；
- ❌ 不做 Agent 运行时、聊天客户端、模型网关或通用工作流平台；
- ❌ 不拥有自己的 provider/model 认证（不写死模型，不持有 API Key）；
- ❌ 不建独立 SaaS、账号系统或泛用向量库；
- ❌ 不复制任何宿主的画布、项目、模型路由或 Artifact 系统；
- ❌ 不把静态文件、Schema 通过或 VLM 自评冒充运行可用。

## 宿主职责（平台中立）

- 工作区、画布、设计流程执行、AI 调用、插件/Scenario/Atom 运行时、Artifact 创建/预览/导出、配置；
- 任意设计 Agent 平台或创意工具均可通过 Host Adapter 接入；Open Design 仅为其中一个兼容对象。

## 边界硬规则

1. 全仓不得出现第二前端应用壳；
2. 全仓不得出现第二 Agent runtime；
3. 全仓不得出现模型网关；
4. 全仓不得出现独立账号系统或泛用向量库；
5. 任何文档不得宣称本仓库"拥有"宿主的画布/项目/模型路由；
6. 证据等级声明不得超过真实证据。
