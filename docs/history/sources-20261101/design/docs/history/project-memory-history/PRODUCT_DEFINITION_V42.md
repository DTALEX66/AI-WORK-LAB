# PRODUCT_DEFINITION_V42

- 版本：`4.2`（唯一有效产品定义，替代 V4.0 草案；V3 及更早为历史参考）
- 任务：`V42-0201`｜状态：`ACTIVE`｜证据：E1
- 依赖：V42-0101..0108（Phase 1 P0 修复）全部通过
- SSOT：本文件 + `design-lab/config/product-manifest.json` 双向一致；
  README、架构、能力矩阵必须引用同一 SSOT，不得另立产品定义

## 中文定位

> **面向任意设计 AGENT 平台的能力增强中立层：模型中立、风格中立、领域中立、平台中立、权利安全，全面提升设计能力与设计质感。当前以 Open Design 软件平台为参考宿主/主入口（不绑定版本）。**

## 英文定位（manifest 一致）

> **Agent-platform-neutral Design Capability & Visual Quality Enhancement Layer: model-neutral, style-neutral, domain-neutral, platform-neutral, rights-safe, with commercial production preflight and editable delivery. Current reference host / primary entry: Open Design (version-agnostic).**

## 产品名称

- 仓库技术身份：`DESIGN-LAB`（保持兼容）
- 产品层推荐名：**Design Intelligence Capability Kit**
  （设计智能与设计质感能力增强套件 —— 面向任意设计 AGENT 平台）

## 一句话承诺

帮助新手、职业设计师、资深设计师和商业协作方，把灵感与商业目标转化为
高质量、可编辑、可验证、可生产和可交付的设计成果。

## 不是（非目标）

- 不是第二套 Open Design 或 Lovart；
- 不是 Agent、聊天客户端、模型网关或通用工作流平台；
- 不是纯资料库、Prompt 仓或大师风格生成器；
- 不是未经评测的开源资料聚合；
- 不替代 Open Design 主应用、Studio/画布、daemon、模型路由或 Artifact 系统；
- 不创建第四个聊天入口、Agent runtime 或模型网关；
- 不成为大型素材下载站或第三方仓库镜像；
- 不做大师签名风格生成器；
- 不以静态文件、模板数量、提示词长度或 VLM 自评冒充能力；
- 不把 MiniGame 的产品运营、广告、变现和上架作为平台主线。

## 核心差异化

- 职业领域深度，而不是泛生成；
- 高级视觉质量和反 AI 痕迹；
- CJK、本地商业、印刷、空间及复杂媒介标准；
- 人工可控、锁定、可回退和可编辑；
- 来源、权利、生产和交付完整；
- 每项能力有真实运行和人工评审证据。

## 五种中立

| 中立维度 | 定义 |
|---|---|
| 模型中立 | 不把某一家模型能力写死为产品能力；通过受控 Agent/媒体适配器接入 |
| 风格中立 | 不把 Apple、黑金、科技蓝、HUD 或任何大师风格设为全局默认 |
| 领域中立 | 公共内核服务 UI/UX、平面、品牌、电商、空间、3D、动效、视频、音频、游戏等 |
| 平台中立 | 面向任意设计 AGENT 平台（Open Design / Figma / Penpot / Blender / FFmpeg 等）作为宿主与入口，当前以 Open Design 为参考宿主，架构不绑定任何单一平台或版本 |
| 权利中立 | 每项来源、素材、字体、模型、标准和参考均有权利状态与使用模式 |

## 不可破坏原则

1. 人类做方向、取舍和最终批准；AI 提高分析、探索、执行和检查效率。
2. 参考转化必须保留原创性，禁止签名元素复制。
3. 设计质量、业务目标、可用性、权利和生产可行性同时成立。
4. 数据和知识必须有来源、版本、成熟度、适用条件和退出机制。
5. 能力声明不得高于证据等级。

## 唯一职责边界（详见 BOUNDARY_CONTRACT_V42）

| 组件 | 唯一职责 |
|---|---|
| Open Design | 当前参考宿主/主入口：项目、Studio/画布、Agent 启动、插件/Scenario/Atom 运行、Stage event、GenUI、Artifact、预览与导出（任意设计 AGENT 平台可接入） |
| DESIGN-LAB | 专业方法、Domain Pack、质量、来源权利、预检、交付合同、Benchmark 和证据 |
| 执行协调器 | 任务编排、状态、风险、审批、工具路由与证据汇总（Hermes/Codex/兼容 CLI，客户端中立） |
| MiniGame | `minigame-runtime` 为参考产品 + 跨媒体 Benchmark；冻结边界内安全修复与构建 |
| WORK-LAB | 完全切割，仅保留历史迁移指针 |
| GitHub | 分支、PR、exact-SHA CI、远端事实和发布证据 |

**边界硬规则**：本仓库不得拥有第二前端、第二 Agent runtime、模型网关、
独立账号系统或泛用向量库；Open Design 是当前主入口（参考宿主），架构面向
任意设计 AGENT 平台，不绑定单一平台或版本。

## 五类用户与五种渐进模式（详见 USER_MODES_V42）

| 用户 | 模式 | 必须提供的价值 |
|---|---|---|
| 小白、新手 | Guided | Brief 向导、安全默认值、逐步解释、模板、版权和生产防错 |
| 职业设计师 | Copilot | 参考 DNA、三方向、Token/组件、批量变体、跨格式、精修、预检 |
| 资深设计师、艺术指导 | Director | 自定义 Rubric、方向评审、局部锁定、人工覆盖、版本比较、回退 |
| 大师、研究者、教育者 | Method | 有来源的方法拆解、匿名转译、反模仿、专家校对、版本演进 |
| 品牌方、客户、生产方 | Production | Brief/审批追踪、品牌一致性、权利 BOM、规格、可编辑交付、签收 |

同一能力引擎提供不同披露与控制强度，不创建多套产品。
“大师能力”不得做成姓名风格按钮；只允许基于证据拆解方法，最终生成指令
不得含大师姓名，不得复制签名元素。

## 四类对象模型（详见 OBJECT_MODEL_V42 与 schemas/object-model.schema.json）

| 对象 | 职责 | 关键约束 |
|---|---|---|
| Project | 一次商业设计任务的端到端状态 | 生命周期、版本、决策可追溯 |
| Knowledge | 有来源的专业知识资产 | 来源、成熟度、适用条件、退出机制 |
| Evidence | 能力与结果的可验证证据 | 等级、SHA、运行时、命令、Artifact 回读 |
| Artifact | 可编辑交付与生产产物 | 版本、权利、hash、provenance 引用 |

## 完整闭环

```text
Inspiration → Brief → Research → Direction → Design System
→ Create/Edit → Critique/Repair → Production Preflight
→ Editable Handoff → Evidence/Feedback/Learning
```

## 七层目标架构

```text
Design AGENT Platform / Studio / Agent Entry（当前参考宿主：Open Design）
          ↓
Neutral Intake & Design Router
          ↓
Professional Design Core
          ↓
Domain Packs
          ↓
Media Pipelines & Tool Adapters
          ↓
Quality / Rights / Preflight / Evidence
          ↓
Editable Multi-format Delivery
```

1. 治理层：来源、许可、隐私、安全、证据等级、风险、审批、版本和发布策略。
2. 知识层：专业设计方法、标准、风格谱系、大师方法、行业规则、失败模式和生产知识。
3. 协议层：Brief、Reference DNA、Direction、Design System、Artifact、Score、
   Preflight、Handoff、Provenance 和 Capability Evidence Schema。
4. 能力层：可测试 Atom；对外收敛为三个公开入口
   `commercial-design-core` / `visual-quality-core` / `production-handoff`。
5. 领域层：职业 Domain Pack。
6. 执行与适配层：当前 Open Design 主运行时（参考宿主）+ 受控 Adapter，任意设计 AGENT 平台可接入。
7. 证据层：确定性检查、视觉回归、人工 Jury、真实生产反馈、exact-SHA CI 与客户验收。

## WORK-LAB 与 MiniGame 边界

- **WORK-LAB**：完全切割，仅保留历史迁移指针，不维护本项目。
- **MiniGame**：位于 `DESIGN-LAB/minigame-runtime`，角色为独立参考产品 +
  跨媒体 Benchmark；不移回 WORK-LAB，不定义公共 Core，其暗色 HUD 审美不作为平台默认。

## 证据分级承诺

- 无 E3 不称运行可用；无 E4 不称发布完成；无 E5 不称商业验证完成。
- 所有 synthetic/static 结果按 E1/E2 报告。
- 默认不 commit/push/PR/merge/tag/release，停在 `READY_FOR_USER_APPROVAL` 等待授权。

## 唯一性

本文件为 V4.2 唯一产品定义。`PRODUCT_DEFINITION_V4.md`（4.0 草案）、
`PROJECT_DEFINITION_V3.md` 及更早版本保留为历史参考，不再作为活动定义。
