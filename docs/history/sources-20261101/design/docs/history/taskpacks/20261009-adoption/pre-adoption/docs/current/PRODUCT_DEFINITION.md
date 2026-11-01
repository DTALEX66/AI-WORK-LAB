# PRODUCT_DEFINITION — DESIGN-LAB（设计实验室）

- 版本：`1.1`｜状态：`ACTIVE`｜SSOT 角色：Authority 下的当前产品定义
- 顶层权威：`/AUTHORITY.md`（`DL-AUTHORITY-2026-09-18-R2`）
- 当前统一剩余任务入口：`docs/taskpacks/DESIGN-LAB-FINAL-AUTHORITY-CONVERGENCE-TASKPACK-2026-09-18.md`
- 一致性合同：`design-lab/config/product-manifest.json` + `docs/architecture/BOUNDARY_CONTRACT.md`

## 中文定位

> **DESIGN-LAB（设计实验室）是一个面向职业视觉设计的、AI 原生、平台中立的设计智能与生产能力实验室。它把设计研究、合规知识、设计方法、领域能力、视觉质量、专业工具适配、生产预检、可编辑交付和证据体系，组织为可组合、可执行、可验证、可回滚的设计能力闭环。**

## 英文定位（manifest 一致）

> **Agent-platform-neutral design intelligence and production laboratory for professional visual design with commercial production preflight and editable delivery (evidence & provenance). It organizes design research, compliance knowledge, design methods, domain capability, visual quality, professional tool adaptation, production preflight, editable handoff and an evidence system into composable, executable, verifiable, rollback-safe design capability loops. Host-native; no default host, agent, or model binding.**

## 唯一身份

| 项 | 值 |
|---|---|
| 英文正式名 | DESIGN-LAB |
| 中文正式名 | 设计实验室 |
| 技术 ID | design-lab |
| 云端 | DTALEX66/DESIGN-LAB |
| 本地 | D:\All projects\DESIGN-LAB |
| 产品 manifest | `design-lab/config/product-manifest.json`（namespace `design-lab/product-manifest/v1`）|

旧名（`OPEN-DESIGN-Assistance` / `Open Design Assistance` / `opendesign-assistance` / `Design Intelligence Layer` / `Design Intelligence Capability Kit`）退出活动产品命名，仅允许出现在：
1. `docs/history/` 与 `reports/history/` 的不可篡改历史；
2. 明确标注的第三方 Host Adapter（如 Open Design）；
3. 外部来源、兼容性或 Git 历史引用。

## 视觉设计是第一主线

视觉设计不是一个附加 Domain Pack，而是本产品第一主线。优先范围：

```text
品牌视觉 / 平面与编辑 / UI·UX / 电商视觉 / 包装
空间与展陈 / 3D / 动效 / 视频视觉 / 游戏视觉与交互界面
```

研究资料、开源资产、模型、Agent、Host 和工具均是能力来源或执行对象；它们不是产品身份。

## 不是二选一：资料库还是前后端产品？

DESIGN-LAB 既不是静态资料库，也不应变成第二个通用设计软件前端。它是一个**产品化的设计能力系统**：

```text
研究/开源资料                    = 受治理的知识与证据底座
可测试的 Method / Rubric / Pack   = 可复用专业能力
Host / Agent / Tool Adapters      = 在现有工作界面中执行能力
Preflight / Handoff / Evidence    = 商业生产闭环
```

当前采用 **standalone-first + host-native editing**：`apps/workbench/` 是 DESIGN-LAB 唯一用户可见设计控制面，负责 Projects、Brief、References、Directions、Design System、Review、Preflight、Handoff 与 Evidence 的编排和读回；真正原生编辑仍在已接入的专业宿主中完成。不得为此重建第二画布、聊天客户端、模型网关或通用 SaaS 后端。

Workbench 可以展示 Brief、方向、质量评分、预检、证据、适配器可用性和交付状态；它不是设计编辑器，不托管用户帐号、模型或宿主画布，不与专业宿主竞争。

## 六能力域

```text
01 Design Intelligence   Brief理解、商业目标、Reference DNA、方向生成、设计系统、Critique/Refinement
02 Professional Visual Domains  Brand、Graphic、UIUX、E-commerce、Editorial、Packaging、Spatial、Exhibition、3D、Motion、Video、Game Visual
03 Visual Quality        去 AI 味、构图、版式、比例、层级、材质、光影、颜色、可读性、商业感、一致性
04 Creative Toolchain    Host / Agent / Adobe / Figma / Blender / ComfyUI / FFmpeg / Media Model adapters
05 Production & Handoff  规格、字体、色彩、分辨率、出血、格式、源文件、BOM、包、版本、回滚
06 Research & Evidence   Sources、licenses、methods、benchmarks、evals、E0–E5、human jury、production validation
```

## 核心对象（唯一可交换语言）

```text
Brief / ReferenceSet / ResearchFinding / MethodCard / Direction / DesignSystem
DomainPack / Artifact / ToolRun / QualityAssessment / PreflightReport / HandoffPackage / EvidenceRecord
```

所有 adapter 的输入输出必须能映射到这些对象；不得以 Prompt 文本、私有聊天记录或不带版本的截图充当唯一事实。

## 边界硬规则

- 本仓库只允许 `apps/workbench/` 这一套设计控制面，不得拥有第二应用壳、第二画布、第二 Agent runtime、模型网关、独立账号系统或泛用向量库；
- 产品契约（manifest）不得包含 `primaryRuntime` / `fiveNeutralities`；宿主选择属于本地 profile / 项目级配置；
- Open Design 是可验证的 Host Adapter，不是默认绑定；
- MiniGame 仅是游戏视觉设计 fixture，不是产品线；
- 未达 E3 不得写"已集成"；未授权不得 commit/push/PR/merge/release。
