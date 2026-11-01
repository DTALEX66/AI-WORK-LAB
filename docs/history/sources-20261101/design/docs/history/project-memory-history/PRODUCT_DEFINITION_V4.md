# PRODUCT_DEFINITION_V4

- 版本：`4.0`（唯一有效产品定义，替代 V3）
- 任务：`ODA4-0201`｜状态：`ACTIVE`｜证据：E1
- 依赖：Phase 01 Gate 0 全部通过

## 中文定位

> **以 Open Design 为主入口，模型中立、风格中立、领域中立、工具中立、权利安全的专业设计智能与视觉质量平台。**

## 英文定位

> **Open Design-first Neutral Professional Design Intelligence & Visual Quality Platform.**

## 核心承诺

把 Brief、业务目标、现有资产和参考资料转化为：
- 有专业判断的设计方向；
- 有构图、字体、色彩、材质、光影和节奏质量的视觉结果；
- 可编辑的源文件和结构化资产；
- 可进入开发、印刷、包装、施工、视频、音频和 3D 制作的生产交付；
- 有来源、权利、版本、评分、预检和回滚证据的交付包。

## 五种中立

| 中立维度 | 定义 |
|---|---|
| 模型中立 | 不把某一家模型能力写死为产品能力；通过受控 Agent/媒体适配器接入 |
| 风格中立 | 不把 Apple、黑金、科技蓝、HUD 或任何大师风格设为全局默认 |
| 领域中立 | 公共内核服务 UI/UX、平面、品牌、电商、空间、3D、动效、视频、音频、游戏等 |
| 工具中立 | Open Design 是主入口，下游可适配 Figma、Penpot、Blender、FFmpeg 等工具 |
| 权利中立 | 每项来源、素材、字体、模型、标准和参考均有权利状态与使用模式 |

## 组件所有权边界

| 组件 | 唯一职责 |
|---|---|
| Open Design | 项目、Studio/画布、Agent 启动、插件/Scenario/Atom 运行、Stage event、GenUI、Artifact、预览与导出 |
| HERMES | 唯一用户入口、任务编排、状态、风险、审批、工具路由与证据汇总 |
| Codex writer | 单 writer 修改 Schema、脚本、测试、Manifest、Domain Pack 和文档 |
| Codex reviewer | 对 frozen exact tree 做全新进程、只读、独立复审 |
| DESIGN-LAB | 专业方法、Domain Pack、质量、来源权利、预检、交付合同、Benchmark 和证据 |
| GitHub | 分支、PR、exact-SHA CI、远端事实和发布证据 |
| WORK-LAB | 与本项目完全切割；只保留历史迁移指针 |

## 非目标

- 不替代 Open Design 主应用、Studio/画布、daemon、模型路由或 Artifact 系统；
- 不创建第四个聊天入口、Agent runtime 或模型网关；
- 不成为大型素材下载站或第三方仓库镜像；
- 不做大师签名风格生成器；
- 不以静态文件、模板数量、提示词长度或 VLM 自评冒充能力；
- 不把 MiniGame 的产品运营、广告、变现和上架作为平台主线。

## 七层目标架构

```text
Open Design Studio / Agent Entry
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
3. 协议层：Brief、Reference DNA、Direction、Design System、Artifact、Score、Preflight、Handoff、Provenance 和 Capability Evidence Schema。
4. 能力层：可测试 Atom；对外收敛为三个公开入口 `commercial-design-core` / `visual-quality-core` / `production-handoff`。
5. 领域层：职业 Domain Pack（manifest/brief/scenario/profile/rubric/preflight/handoff/source mapping/benchmark/evidence）。
6. 执行与适配层：Open Design 主运行时 + Figma/Penpot/浏览器/Blender/FFmpeg/图像/音频/3D 受控 Adapter。
7. 证据层：确定性检查、视觉回归、人工 Jury、真实生产反馈、exact-SHA CI 与客户验收。

## WORK-LAB 与 MiniGame 边界

- **WORK-LAB**：完全切割，仅保留历史迁移指针，不维护本项目。
- **MiniGame**：位于 `DESIGN-LAB/minigame-runtime`，角色为独立参考产品 + 跨媒体 Benchmark；不移回 WORK-LAB，不定义公共 Core，其暗色 HUD 审美不作为平台默认。

## 证据分级承诺

- 无 E3 不称运行可用；无 E4 不称发布完成；无 E5 不称商业验证完成。
- 所有 synthetic/static 结果按 E1/E2 报告。
- 默认不 commit/push/PR/merge/tag/release，停在 `READY_FOR_USER_APPROVAL` 等待授权。

## 唯一性

本文件为 V4 唯一产品定义。V3 的 `PROJECT_DEFINITION_V3.md` 及更早版本保留为历史参考，不再作为活动定义。
