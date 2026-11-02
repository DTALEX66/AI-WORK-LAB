# ArcheAxis Workspace 增量补充任务包 v1.0

> 主题：个人研究型开源吸收、Windows 构建环境、学习体验与知识表征层  
> 中文产品名：元枢工作台  
> 英文产品名：ArcheAxis Workspace  
> 日期：2026-08-09  
> 文档类型：现行主任务包 v3.0 的增量裁决与 Codex 执行包  
> 状态：active amendment；合入 `docs/truth/**` 后转为 historical/evidence  
> 适用范围：当前仓库及其未来正式重命名后的同一项目  
> 不涉及：WORK-LAB、通用 Agent OS、商业产品规划  

---

## 0. 本轮最终裁决

本增量包增加三条不可被后续代理删除或误读的正式决策：

1. **项目运行属性**：ArcheAxis Workspace 当前是个人所有、非商业、学习研究型项目。项目优先追求学习价值、开放知识、可验证研究和能力吸收，不为商业闭源、商业授权或企业市场预留路线。
2. **开源吸收原则**：从“宽松许可证优先、GPL/AGPL 默认排除”升级为“**许可证合规前提下，允许依赖、复制、修改、合并、fork、vendor、sidecar、API/CLI/格式适配与后期自研替换**”。GPL/AGPL 可以进入，但必须接受相应组合、公开源码、网络提供源码等义务；“非商业”不是许可证豁免。
3. **学习辅助层**：视图、表格、卡片、时间线、学习地图、课件、图解、动画、交互演示、模拟实验、2D/2.5D/3D 记忆宫殿及未来 VR/AR 都属于正式、永久的 **Learning Experience & Representation Layer**。它们按 Horizon 分期，不能因为当前先修 PDF 就从总蓝图消失。

三条决策不改变唯一产品定位：

> **ArcheAxis Workspace / 元枢工作台是一套面向个人与其 AI 的、本地优先、证据驱动、开放兼容的人机双向学习与知识工作台。**

固定短句仍是：

> **同一份开放格式资料，人学得更深，AI 用得更准。**

---

## 1. 对现行主任务包的增量覆盖关系

本文件只覆盖下列旧表述，不建立第二套产品路线：

| 旧表述 | 新裁决 |
|---|---|
| GPL/AGPL 源码原则上不进入核心 | 只要许可证兼容、项目接受其义务并完成证据，可直接吸收、修改或合并 |
| OpenHuman 等 GPL 项目只能做行为参考 | 当前顶层许可证未决时先 clean-room；完成 License Composition Decision 后可依法选择源码吸收 |
| Visual Teaching / Spatial Memory 只是模糊探索项 | 升级为永久 LER 产品层；高级形态仍分期、实验性晋升 |
| 3D/VR 延期等于不再规划 | 延期只代表不阻塞当前 Release，不代表删除 |
| Windows 构建由零散脚本和 CI 间接控制 | 建立单一 PowerShell 7 入口、工具链锁、doctor、构建配置和干净环境证据 |
| 多语言各自发展 | 固定语言职责，禁止把同一业务规则复制到 Python/Rust/TypeScript/PowerShell |

本增量包合并时必须更新 `product_truth_digest`，并使旧的未绑定 digest TaskPack 自动 stale。

---

## 2. Personal Research Operating Profile v1

### 2.1 Machine Truth 字段

```yaml
project_operating_profile:
  owner_mode: personal
  purpose: learning_and_research
  commercial_status: noncommercial_current
  public_repository: true
  public_binary_distribution: true
  network_service: local_by_default
  future_commercialization: not_a_planning_goal
  license_waiver: false

reuse_policy:
  principle: license_compliant_absorption_first
  permissive_only: false
  copyleft_allowed: true
  allowed_modes:
    - dependency
    - source_copy
    - source_merge
    - fork
    - vendor
    - dynamic_link
    - static_link
    - sidecar
    - cli
    - api
    - open_format
    - behavior_reference
    - clean_reimplementation
  later_self_replacement_allowed: true
  historical_obligations_survive_replacement: true
```

### 2.2 “非商业”到底改变什么

它改变产品决策：

- 不需要为了未来闭源销售而排除 copyleft；
- 可以优先采用已经成熟、可研究、可修改的开源实现；
- 可以接受把相应组合代码继续按 GPL/AGPL 等许可证公开；
- 可以先形成高质量学习研究系统，再在技术成熟后逐个替换自研；
- 不以商业市场、SaaS、多租户、付费墙、企业集成为路线约束。

它**不**改变：

- 著作权和许可证义务；
- GitHub 公开源码、Windows 安装器和 source bundle 的分发事实；
- AGPL 网络交互条款；
- LICENSE、NOTICE、署名、Corresponding Source、修改说明和 SBOM；
- 模型、训练数据、字体、图标、Logo、音视频、3D 素材、测试文件各自的许可；
- 无许可证仓库默认“保留所有权利”的事实。

OSI 对“开源”的定义本身不允许按商业/非商业用途歧视；因此写着“仅非商业”的代码通常是 source-available 或自定义许可，不能只凭“个人项目”把它当标准开源项目处理。参考：[OSI Open Source Definition](https://opensource.org/osd) 与 [OSI FAQ](https://opensource.org/faq)。

### 2.3 四条使用/分发通道

| 通道 | 场景 | 许可含义 | 是否可进入正式能力 |
|---|---|---|---|
| `local_lab_only` | 仅本人本机、未推送、未分享、未打包 | 可做更宽研究；仍服从明确的自定义条款 | 否，只能 Experimental Lab |
| `public_source` | 代码、补丁或 fork 进入公开仓库 | 已构成公开提供；必须满足源码许可证与兼容性 | 可，经技术/许可门禁 |
| `public_binary` | wheel、Tauri、installer、捆绑 sidecar/model | 必须绑定安装器内容、许可证、源码和资产义务 | 可，经 installed evidence |
| `network_use` | 局域网/公网用户与修改后的服务交互 | AGPL 等网络义务可能触发 | 可，经网络许可门禁 |

当前项目的正式 `main` 与公开 Release 默认按 `public_source + public_binary` 治理，不能用 `local_lab_only` 的私人使用例外为合并或发布背书。GNU 的官方 FAQ 明确区分私人修改与向公众发布；私人使用不要求发布源码，但向公众提供修改版后必须履行 GPL 条件。参考：[GNU GPL FAQ](https://www.gnu.org/licenses/gpl-faq.html.en)。

---

## 3. License-Compliant Absorption Policy v1

### 3.1 新原则：Compliance-first，不再 Permissive-only

每个候选先回答两个问题：

1. 技术上最省工作量、最成熟的吸收方式是什么？
2. 该方式的许可证义务能否被当前项目完整履行？

只要第二问为“能”，就允许进入候选，包括直接源码吸收。不得再以“GPL/AGPL”三个字自动否决；也不得以“非商业”三个字自动通过。

### 3.2 License Composition Profiles

| Profile | 常见许可 | 允许的吸收方式 | 进入公开仓库/安装器的关键义务 |
|---|---|---|---|
| `LP-00-PUBLIC` | Public Domain、CC0（软件） | 直接并入、修改、vendor | 保留来源与证据；核实素材权利 |
| `LP-10-PERMISSIVE` | MIT、BSD、ISC、Apache-2.0 | 直接并入、依赖、链接、fork、bundle | LICENSE/NOTICE/版权/修改标记；Apache 专利和 NOTICE 条款 |
| `LP-20-FILE-COPYLEFT` | MPL-2.0 | 直接并入或修改，维持文件级边界 | MPL 文件及其修改继续提供源码；Larger Work 另行许可 |
| `LP-21-WEAK-COPYLEFT` | LGPL-2.1/3.0 | 动态链接优先；源码修改、静态链接按专项合同 | 可替换/重新链接、库源码、许可证和修改说明 |
| `LP-30-STRONG-COPYLEFT` | GPL-2.0/3.0 | **允许**直接复制、修改、链接或合并，前提是整个结合作品许可证兼容 | 对应源码、构建/安装脚本、同许可分发；版本兼容矩阵 |
| `LP-31-NETWORK-COPYLEFT` | AGPL-3.0 | **允许**直接复制、修改、链接或合并，前提是结合作品兼容并实现网络源码入口 | GPL 类义务 + 远程交互用户取得 Corresponding Source 的显著入口 |
| `LP-40-CUSTOM` | research-only、NC、BSL、附加条款 | 按原文逐条决定；不得自称 OSS | 用途、修改、公开源码、二进制、网络和再分发分别批准 |
| `LP-50-MODEL-DATA` | 模型权重、数据集、自定义 AI 许可 | 独立于代码评估；按需下载优先 | 模型卡、权重哈希、用途/再分发、训练数据和输出边界 |
| `LP-60-ASSET` | 字体、图标、图片、音视频、3D、fixture | 逐资产处理 | 署名、ShareAlike/ND/NC、商标、隐私与肖像权 |
| `LP-90-NO-LICENSE` | 无 LICENSE 或权属不明 | 不复制、不修改、不分发；只读公开行为或请求授权 | 获得明确许可或换候选 |

### 3.3 推荐的顶层许可决策

当前仓库顶层许可证必须先由 Owner 明确，不能由 Codex 猜测。新增两个可选研究策略，由 `AXW-006A` 做依赖实测后给出最终选择：

#### Strategy R-P：Permissive Core

- 核心维持宽松许可证；
- MIT/BSD/Apache 等可直接吸收；
- GPL/AGPL 主要用独立应用、公开 API/CLI/格式或独立许可子项目；
- 优点是未来复用自由；缺点是不能把强 copyleft 源码直接并入同一结合作品。

#### Strategy R-C：Research Copyleft Composition

- 选择与实际候选兼容的 GPLv3-or-later 或 AGPLv3-or-later 顶层策略；
- 允许 OpenHuman、GPL/AGPL 学习工具等源码按兼容矩阵进入；
- 公开对应源码、构建脚本、修改记录和网络源码入口；
- 优点是最大化合法源码吸收，符合个人非商业研究目标；缺点是必须持续管理 GPLv2-only、AGPL、MPL、Apache、自定义条款之间的兼容性。

**本增量包不擅自选择 R-P 或 R-C。** 但按用户当前偏好，`AXW-006A` 应把 R-C 作为首选可行性方案，而不是把“保留未来闭源可能”设为默认目标。GNU 官方说明 GPLv3 与 AGPLv3 可在许可证规定的特殊边界内组合，但仍须同时满足相应条件；GPLv2-only 与 GPLv3 并不自动兼容。参考：[GNU License Compatibility FAQ](https://www.gnu.org/licenses/gpl-faq)。

### 3.4 每个候选的 Reuse Decision Record

```yaml
component_id:
name:
upstream_url:
upstream_tag:
upstream_commit:
source_archive_sha256:
license_spdx_expression:
license_text_sha256:
copyright_holders: []
notice_required: false
absorption_mode:
composition_profile:
approved_lanes: []
copyleft_boundary:
transitive_dependencies: []
modified_files: []
modification_patch_or_fork:
model_data_asset_components: []
fixture_license:
replacement_port:
upgrade_plan:
rollback_plan:
decision_status:
owner_approval:
```

SPDX 标识用于机器化许可证表达，REUSE 风格用于逐文件版权/许可信息；参考 [SPDX Overview](https://spdx.dev/learn/overview/) 和 [REUSE Specification](https://reuse.software/spec/)。

### 3.5 直接吸收的代码布局

```text
third_party/
  vendored/<component>/
    UPSTREAM.toml
    LICENSES/
    NOTICE
    PATCHES/
    source/...
  forks/<component>/
    FORK_BASE
    MODIFICATIONS.md
  sidecars/<component>/
    PROVIDER_CONTRACT.md
    SOURCE_OFFER.md
  assets/<asset-id>/
    ASSET_LICENSE.yaml

LICENSES/
THIRD_PARTY_NOTICES.md
docs/current/UPSTREAM_LEDGER.md
docs/evidence/licenses/<release-sha>/
```

vendor/fork 不是把第三方代码伪装成自研；每个文件必须保留可追溯来源、许可、修改和上游 revision。

### 3.6 后期替换自研

允许先吸收、再替换，但必须从第一天建立稳定 Port/Adapter：

```text
Product Contract
   ├─ Upstream-backed Provider v1
   └─ Self-developed Provider v2
```

替换验收：

- 使用同一批合法 golden fixtures 和 semantic oracle；
- 新 provider 的质量、错误语义、性能和开放导出不低于旧 provider；
- 有数据/配置迁移和一键 rollback；
- 若开发者持续参考原实现，不得虚称 clean-room；
- 当前 Release 移除第三方后可更新当前 SBOM/NOTICE，但旧 commit、tag、Release 和历史义务永久保留；
- 许可证义务不会因“已经换自研”而追溯消失。

---

## 4. 开源学习辅助吸收地图

以下是当前优先候选，不是未经复核即可安装的最新版清单。每项落地前仍需固定 exact revision、逐包许可证、字体/素材/示例内容和传递依赖。

### 4.1 Structured Views：表格、卡片、矩阵、时间线、对比

| 能力 | 候选 | 初始方式 | 主要价值 | 阶段 |
|---|---|---|---|---|
| Headless 表格/数据视图 | TanStack Table | TS dependency，锁 tag/license | 排序、筛选、分组、虚拟化；UI 可自定义 | H2–H4 |
| 图表/统计视图 | Apache ECharts | TS dependency | 柱线散点、关系、时间、地理、可访问性配置 | H2–H5 |
| 声明式统计图 | Vega/Vega-Lite | JSON spec + renderer | 表征可保存、比较、导出、重建 | H4–H6 |
| 简洁绘图 | Observable Plot / D3 | dependency | 快速来源化数据图与教学图 | H4–H6 |
| Timeline | ECharts/Vega 或独立适配器 | RepresentationSpec | 事件、版本、因果链与学习进度 | H4–H6 |

所有表格/图表必须显示：数据来源、过滤条件、单位、时间范围、缺失值和变换步骤。图表本身不是 Evidence。

### 4.2 Learning Maps：大纲、概念图、Canvas、Graph

| 能力 | 候选 | 初始方式 | 阶段 |
|---|---|---|---|
| JSON Canvas | obsidianmd/jsoncanvas | 直接实现开放格式 | H3 |
| 节点图编辑 | XYFlow/React Flow | MIT dependency | H3–H4 |
| 关系/知识图 | Cytoscape.js | dependency | H4–H6 |
| Markdown 图解 | Mermaid | source-linked fenced block | H4–H5 |
| Mind map | markmap | Markdown→derived view | H4–H5 |
| 手绘式图解 | Excalidraw | adapter/依赖或独立文件 | H5–H6 |

Canvas/Graph/Learning Map 是开放知识组织视图；它们与 3D Memory Palace 共享 Anchor/Node contract，但不被 3D 实现绑架。

### 4.3 Visual Teaching & Courseware：课件、图解、互动内容

| 能力 | 候选 | 方式 | 许可/集成注意 | 阶段 |
|---|---|---|---|---|
| HTML/Markdown 演示稿 | reveal.js | TS/HTML renderer | MIT；可导出静态 HTML/PDF | H4–H6 |
| Markdown 课件 | Slidev/Marp | adapter 或 optional authoring provider | 固定 exact package/license | H5–H6 |
| 互动课件/题型 | H5P | 独立 content-package adapter | H5P 代码和内容类型许可并不完全相同，逐包核验 | H5–H7 |
| 可执行计算笔记 | marimo/JupyterLite | optional provider | 代码、kernel/package、输出分别追踪 | H6–H7 |

H5P 可提供 Interactive Video、Quiz、Timeline、Memory Game、Drag and Drop、Flash Cards 等可复用学习形态，但官方也说明部分 PHP library 因第三方代码采用 GPL；因此必须按实际组件而非“H5P 整体 MIT”判断。参考：[H5P Licensing](https://h5p.org/licensing)。

### 4.4 Animation & Dynamic Explanation：动画、步骤播放、动态说明

| 能力 | 候选 | 方式 | 阶段 |
|---|---|---|---|
| 数学/科学解释动画 | Manim Community | Python provider/sidecar，输出视频/SVG/scene metadata | H6–H7 |
| Web 动画 | Web Animations / Motion Canvas / Lottie renderer | TS renderer | H5–H7 |
| 步骤回放 | 自有 Representation Timeline | 基于 EvidenceAnchor/OperationStep | H4–H6 |
| 动态图解 | Mermaid/Graph/ECharts transition | declarative spec | H5–H6 |

Manim Community 是面向解释性数学动画的 Python 引擎，当前官方仓库采用 MIT 许可；真正并入时仍需固定 release、检查 FFmpeg/LaTeX/字体等外部链。参考：[Manim Community](https://github.com/ManimCommunity/manim)。

### 4.5 Simulation & Practice Lab：交互演示、模拟实验

候选方式：

- H5P 交互题型；
- Pyodide/JupyterLite/marimo 受控计算沙箱；
- p5.js 或 Canvas/WebGL 交互演示；
- 物理/数学/统计专项开源模拟器通过 Adapter 接入；
- 外部模拟器先导入参数、步骤、输出和引用，不能把黑箱截图当知识。

模拟必须记录初始条件、参数、随机种子、版本、运行环境、输出和结论范围。模拟结果是 RuntimeEvidence 或 Candidate，不自动成为外部世界事实。

### 4.6 Spatial Memory：2D、2.5D、3D、VR/AR 记忆宫殿

| 层级 | 建议技术 | 产品形态 | 降级路径 |
|---|---|---|---|
| 2D | Canvas/Graph/SVG | 房间平面、路线、位置节点 | 大纲/卡片/表格 |
| 2.5D | CSS 3D/Canvas/WebGL | 分层场景、可缩放路线、物件锚点 | 2D scene |
| 3D | Three.js / React Three Fiber | 场景、房间、物件、空间线索、复习路径 | 2D map + list |
| VR/AR | WebXR/A-Frame 等 optional provider | 沉浸回忆、空间复习、教学体验 | Desktop 3D/2D |

Three.js 官方仓库采用 MIT 许可并提供 WebGL/WebGPU 3D 渲染能力；适合 Tauri WebView 中的可选 3D 表现层。参考：[three.js](https://github.com/mrdoob/three.js)。

Memory Palace 的 canonical data 不能是某个 Three.js scene：

```text
SpatialMemoryMap
  scene_id
  learning_objective_ids[]
  evidence_anchor_ids[]
  loci[]
  route[]
  cue_asset_ids[]
  retrieval_prompts[]
  fallback_2d_spec
  accessibility_description
  revision
```

3D 模型、纹理、HDRI、字体、声音和动画素材各自进入 Asset Ledger；未登记资产不能进安装器。

---

## 5. Learning Experience & Representation Contract v1

### 5.1 正式对象

```text
RepresentationSpec
ViewDefinition
TableView
ComparisonView
TimelineView
LearningMap
CoursewarePackage
AnimationSpec
SimulationSpec
SpatialMemoryMap
RepresentationRun
LearningInteractionEvent
LearningEffectEvaluation
```

每个对象至少包含：

- stable ID 与 revision；
- LearningObjective；
- 输入 KnowledgeBlock/EvidenceAnchor；
- transformation provenance；
- 人工编辑与 AI 生成部分的区分；
- LossReport；
- renderer/provider/version；
- accessibility fallback；
- export format；
- license/asset references；
- installed capability requirement。

### 5.2 双状态成熟度

```text
technical_state:
planned → prototype → source_grounded → workflow_integrated
→ installed_verified → released

learning_evidence_state:
untested → usability_observed → behavior_observed
→ retention_observed → transfer_observed → controlled_verified
```

技术上能显示 3D 场景，只能证明 `prototype`；不能证明记忆提升。没有足够研究数据时，公开文案只能说“提供某种学习表征/支持可测闭环”，不能说“已证明提高学习效率”。

### 5.3 永久反漂移规则

1. LER 是 Human Learning Core 的正式一等产品层，普通代理无权删除。
2. LER 不阻塞 H0 PDF、Evidence、Workspace 和 Obsidian C4；高级功能按 Horizon 激活。
3. 每个视觉节点必须能回到 EvidenceAnchor；推断和视觉补全明确标识。
4. 表格、图解、动画、模拟、3D 都是 projection，不是唯一事实层。
5. 每个高级表现必须有文本/2D/键盘/屏幕阅读器 fallback。
6. GPU、VR 头显和本地大模型不是基础工作台构建前置。
7. 演示视频、截图和模型自评不算学习效果证据。
8. LER 产物不能绕过 Candidate→Review→Approve，也不能自动成为 AI Rule/Skill。
9. 删除整个 LER Program 属于 Product Truth 重大变更，必须由用户明确决定。

---

## 6. LER Horizon 与路线

| Horizon | 版本方向 | LER 交付 |
|---|---|---|
| H0 / v0.5.1 | PDF 生存闭环 | 转换状态、错误视图、最小双视图 |
| H1 / v0.6 | PDF/Evidence | 页/块/表格视图、来源对比、批注 |
| H2 / v0.7 | Office/OCR/HTML | 工作表、幻灯片、表格、图片结构化视图 |
| H3 / v0.8 | Obsidian C4 | Canvas、Graph、Learning Map、附件表现 |
| H4 / v0.9 | 双学习核心 | 卡片、复习、课程视图、基础课件、来源化图解 |
| H5 / v1.0 | 稳定开放产品 | 2D 表征稳定、无障碍、开放导出、低配降级 |
| H6 / v1.1–1.4 | 生态与教学扩展 | Visual Teaching、课件、时间线、动画脚本、互动内容 |
| H7 / v1.5 | 学习研究实验室 | 动画、模拟实验、2.5D 空间记忆与效果研究 |
| H8 / v2.x | 高级空间学习 | 3D/VR/AR 记忆宫殿、受控对照研究 |

H6–H8 是正式未来路线，不是本轮立即并行开工清单。

---

## 7. Windows Development Environment Contract v1

### 7.1 目标

Windows 本地环境必须做到：

- 新开 PowerShell 7 即可得到一致入口；
- 不依赖用户全局 Python/npm 包或偶然 PATH；
- 同一 commit、lock 和 toolchain 能稳定复现 backend、web、desktop 和 installer；
- 环境问题先由 `doctor` 给出确切层级，不用“删缓存/重装一切”碰运气；
- 本机开发证据与正式 Release 证据分开；
- Windows 专有问题进入固定 failure corpus，不反复从零审计。

### 7.2 不猜本机版本

已知用户本机有 PowerShell 7；除此以外，本包不猜 Python、Rust、Node、MSVC、Windows SDK 或 WebView2 的实际版本。`AXW-007A` 先只读探测并生成 machine baseline，再决定精确 pin。

### 7.2.1 本增量包生成时发现的仓库缺口

以下只绑定审计基线 `main@492fac5982c693eb668d31cc51a6a59bac83b7a1`，执行时由 AXW-000/007A 重查：

- `pyproject.toml` 只规定 Python `>=3.11`；CI/Release 以 3.12 为主，但没有锁定 patch；
- `uv.lock` 已存在，但 bundle preparation 会复制当前 `sys.base_prefix`，可能把个人机 ambient Python 带进安装包；
- Rust `Cargo.toml` 使用 edition 2024、`rust-version=1.88`，但没有 `rust-toolchain.toml`，所以 rustc/cargo/rustfmt 会随本机漂移；
- `Cargo.lock` 存在；Tauri crate/CLI 有锁定基础，但仍缺 OS toolchain truth；
- Node 当前只服务 `desktop/` 下的 Tauri CLI，不是独立业务前端编译链；Node/npm 自身未锁；
- `desktop/package-lock.json` 的 resolved registry 需要统一来源并复核 integrity，不能把本机镜像状态带进 Release；
- Windows CI 使用 runner 预装的 MSVC/SDK/Node/Rust，仓库没有表达个人机与 CI 是否一致；
- NSIS、WebView2、Playwright browser 和外部格式 provider 缺统一工具链/分发清单；
- 当前动态端口选择存在“先 bind(0) 取得端口、释放、再由 child 绑定”的竞争窗口，需要保留 reservation 或由 child 自报端口。

这些缺口解释了为什么“CI 偶尔绿、本机仍有不同问题”：依赖 lock 只覆盖语言包，没有覆盖实际编译器、Windows SDK、WebView2、安装器工具和被打包的 Python runtime。

### 7.3 工具链真相文件

```text
.python-version
uv.lock
rust-toolchain.toml
desktop/src-tauri/Cargo.lock
.node-version              # 或仓库选定的唯一等价文件
desktop/package-lock.json
toolchains/windows.policy.v1.json
toolchains/windows.lock.v1.json
.local/archeaxis-build/windows-observed.json
build-evidence/<run-id>/build-provenance.json
```

四类真相严格分开：

1. `windows.policy`：支持范围、必需组件、profile 规则，不含本机路径；
2. `windows.lock`：canonical bundle 的精确工具、官方来源、hash、许可和组件 ID；
3. `windows-observed`：doctor 看到的本机路径、VS instance、OS/WebView2 等，gitignored；
4. `build-provenance`：本次 source/tree/dirty、lock/toolchain/observed digest、命令和产物 hash。

`toolchains/windows.lock.v1.json` 记录：

- Windows edition/build/architecture；
- PowerShell 7；
- Python/uv；
- Rust/rustup/Cargo/target；
- Node/npm；
- MSVC Build Tools/VC toolset；
- Windows SDK；
- WebView2 Runtime；
- Tauri CLI；
- NSIS/installer tools；
- external providers：Tesseract、language packs、FFmpeg、Docling/OCR models 等；
- 版本、来源、安装模式、hash、license 和 capability profile。

WebView2 Evergreen 不伪装成可逐字节锁定：policy 记录最低兼容范围，observed/evidence 记录本次实测版本；只有采用 Fixed Version Runtime 时才另建精确分发 RDR。

Tauri 在 Windows 开发需要 Microsoft C++ Build Tools 和 Edge WebView2，Rust 应使用正确的 MSVC target；这是正式前置，而不是某次 CI 的偶然环境。参考：[Tauri Windows prerequisites](https://v2.tauri.app/start/prerequisites/) 和 [rustup MSVC prerequisites](https://rust-lang.github.io/rustup/installation/windows-msvc.html)。

### 7.4 语言职责固定

| 语言/工具 | 唯一主职责 | 禁止扩张 |
|---|---|---|
| Python | FastAPI、导入/转换、Evidence、Learning、AI assets、provider orchestration | 不负责桌面窗口/安装器生命周期；不生成前端 UI 作为长期架构 |
| TypeScript/JavaScript | Workspace UI、PDF.js、表格/图表、Canvas/Graph、动画、3D、无障碍交互 | 不复制 Evidence promotion/权限/数据迁移业务规则 |
| Rust | Tauri 壳、本机进程监管、权限边界、数据根、文件/协议/installer bridge | 不把知识、学习、AI domain 迁入 Rust；控制编译面和二进制体积 |
| PowerShell 7 | Windows doctor/bootstrap/build/test/package/diagnostic 编排 | 不承载产品业务逻辑；不要求运行时用户安装 PS7 |
| SQL/migrations | durable schema 演进 | 不在脚本里临时改库绕过 migration runner |
| Java/C/C++/其他 | 只作为明确批准的 optional provider/sidecar | 不因一个候选引擎把新语言变成核心开发栈 |

结论：**不做语言重写。** 当前最合理的是收紧边界，而不是把 Python 改 Rust、把 Rust 改 C++ 或把 PowerShell 变成运行时框架。

### 7.5 Python 环境

- 主开发/产品 minor 保持 Python 3.12；其 exact patch 由 AXW-007B 基于实际 bundle 选定；3.11/3.13 用于依赖/接口变化、nightly/RC 兼容矩阵；
- 只用 `uv` 管理项目环境；不直接在全局 Python 执行 `pip install`；
- `.venv` 只属于当前 checkout，不提交；
- 开发/CI 使用 `uv sync --locked` 或 `--frozen`；依赖升级是独立 TaskPack；
- dependency groups 拆为 `core/dev/pdf/office/ocr/media/ai/full`，避免 lint/browser/Windows smoke 各自安装全部重量依赖；
- wheel/bundled runtime 使用同一 `uv.lock` 导出和 hash；
- parser/provider 改动必须跑真实格式及 installed bundled runtime；
- bundle 从 `windows.lock` 指定的 base Python distribution 构造 staging，禁止继续复制任意 ambient `sys.base_prefix`；
- 不允许“源码环境 import 成功”冒充安装版能力。

uv 官方说明 lockfile 固定跨平台解析结果，`--locked/--frozen` 可防止命令静默更新依赖。参考：[uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)。

### 7.6 Rust/Tauri 环境

- `rust-toolchain.toml` 固定经过验证的精确 stable 版本、`rustfmt`、`clippy` 和 `x86_64-pc-windows-msvc`；
- `Cargo.lock` 必须提交并与根 package version 一致；
- 构建使用 `cargo ... --locked`；更新 crate 是独立依赖包；
- Rust 仅保留 shell/process/token/window/installer/native bridge；
- `desktop-fast` 不构建 NSIS；`desktop-build` 构建 release shell；`installer` 才运行 NSIS 安装/卸载全生命周期；
- cargo audit 只在 Cargo.lock 变化、nightly、RC/Release 运行；
- release target directory 和缓存目录要短、明确且不与用户数据混合；
- antivirus/file-lock 问题记录进 doctor，不自动关闭 Defender。

Cargo 官方建议应用提交 `Cargo.lock`，其内容固定准确依赖 revision；`rust-toolchain.toml` 可在仓库内锁定工具链。参考：[Cargo.toml vs Cargo.lock](https://doc.rust-lang.org/cargo/guide/cargo-toml-vs-cargo-lock.html) 和 [rustup overrides](https://rust-lang.github.io/rustup/overrides.html)。

### 7.7 Node/UI 环境

- 当前 Node 只服务 `desktop/` Tauri CLI；不为了“现代化”先引入第二套前端框架或根级 Node workspace；
- 固定一个 Node LTS 精确版本和一个 npm major；
- 只保留一个 `package-lock.json` 权威；
- 将非 canonical registry 的 resolved 来源作为独立依赖维护变更审计、重锁和校验，禁止无审查机械替换 lock；
- 干净构建使用 `npm ci`，不允许 CI/Release 执行会更新 lock 的 `npm install`；
- 不依赖全局 `vite/tauri/playwright`；全部经 package scripts 或锁定 runner；
- 浏览器 binary/cache 与 node_modules 分开；browser smoke 只在 UI 变更触发；
- 学习图表/动画/3D 组件分别进入可延迟加载 chunk，避免主 Workspace 启动即加载全部引擎。

当 LER 真正需要前端构建链时，由 AXW-090 对 Node/TypeScript build topology 做一次显式 ADR；不能让远期 3D 需求反向扩大当前 v0.5.1 构建面。

`npm ci` 要求 lock 与 `package.json` 一致、不会写 lock，并在安装前清理现有 `node_modules`。参考：[npm ci](https://docs.npmjs.com/cli/v11/commands/npm-ci/)。

### 7.8 PowerShell 7 单一编排入口

```text
scripts/windows/axw.ps1
scripts/windows/modules/Axw.Environment.psm1
scripts/windows/modules/Axw.Build.psm1
scripts/windows/modules/Axw.Diagnostics.psm1
```

统一命令：

```powershell
pwsh -NoProfile -File scripts/windows/axw.ps1 doctor
pwsh -NoProfile -File scripts/windows/axw.ps1 bootstrap -Plan
pwsh -NoProfile -File scripts/windows/axw.ps1 bootstrap -Apply
pwsh -NoProfile -File scripts/windows/axw.ps1 sync -Profile dev
pwsh -NoProfile -File scripts/windows/axw.ps1 build -Profile backend
pwsh -NoProfile -File scripts/windows/axw.ps1 build -Profile web
pwsh -NoProfile -File scripts/windows/axw.ps1 build -Profile desktop-fast
pwsh -NoProfile -File scripts/windows/axw.ps1 build -Profile installer
pwsh -NoProfile -File scripts/windows/axw.ps1 verify -AffectedFrom <sha>
pwsh -NoProfile -File scripts/windows/axw.ps1 collect-diagnostics
```

脚本规则：

- `Set-StrictMode -Version Latest`；`$ErrorActionPreference = 'Stop'`；
- 每次 native command 检查 `$LASTEXITCODE`；
- 一律 `-NoProfile`，防止用户 alias/profile 污染；
- 使用参数数组和 `Join-Path`，不拼接未经转义的命令字符串；
- 统一 UTF-8；日志保留原始 exit code；
- GitHub Actions 跨 step 数据只经 `$GITHUB_OUTPUT`/artifact，不依赖 PowerShell 变量继续存在；
- profile 决策、Capability 判定、Release identity、manifest/digest 和其他复杂 JSON 规则放在可测试的 Python 模块；PowerShell 只传参、发现 Windows 环境、调用原生命令并传递 exit code；
- `bootstrap` 默认只输出计划；修改 admin、machine PATH、registry、Windows feature 必须显式 `-Apply` 并提示；
- `clean` 只能清解析后位于明确 build/cache root 的目录，禁止 repo root、workspace parent、用户数据根和未解析环境变量。

### 7.9 构建配置

| Profile | 网络 | 目标 | 允许使用缓存 | 退出证据 |
|---|---|---|---|---|
| `dev` | 可同步依赖 | 快速 backend/web/Tauri dev | 是 | 能启动与定向测试 |
| `verify` | sync 后尽量无网络 | frozen locks、受影响测试、wheel/runtime smoke | 是，必须命中正确 digest | Gate evidence |
| `desktop-fast` | sync 后无网络 | Rust/Tauri shell，不打 installer | 是 | shell/process lifecycle |
| `bundle` | frozen | wheel + bundled Python + frontend + Tauri release | 是 | bundle manifest/hash |
| `installer` | frozen | NSIS 安装/启动/关闭/卸载 | 构建缓存可用，安装态全新 | installed lifecycle |
| `full` | frozen | exact-SHA、全部当前 release-required profiles | 可验证缓存 | release qualification |
| `offline-rebuild` | 禁网 | 仅使用已批准 cache/vendor/source bundle | 受控 | 缺包明确失败；无隐式下载 |

### 7.9.1 Online bootstrap 与 cached/offline

- `bootstrap -Mode Online`：只从 lock 中的官方来源下载，逐项校验 hash；需要管理员权限、VS/SDK 大体积变更时停止并输出 Owner Action；
- `bootstrap -PrepareOfflineKit`：建立 content-addressed kit，包含选定 Python/uv、Node/npm、rustup/toolchain、VS/SDK layout、WebView2、Cargo vendor、npm cache、Windows wheelhouse、Playwright、Tauri/NSIS 和已批准 provider；
- `bootstrap -Mode Cached`：强制 uv/Cargo/npm 离线模式；cache miss 报确切对象 ID 并停止，绝不静默联网；
- Python 先按目标 Windows/Python 构造带 hash wheelhouse；
- Rust 先 `cargo fetch --locked --target ...`，可搬运 kit 使用 `cargo vendor --locked`；
- npm 只在 `desktop/` 运行 locked clean install，确保 Tauri CLI 对应 Windows optional binary 已缓存；
- 下载缓存可复用并只读校验；编译缓存可删除；用户数据永不缓存；Release outputs 永不当缓存输入；
- bundle 可复用经过 hash 校验的下载物，但不复用旧 `.venv`、`node_modules`、Cargo target 或 staged runtime；
- v0.5.1 的硬门槛是“同一台个人 Windows online bootstrap 后可 cached-only clean bundle”；可搬到另一台新机的完整 offline kit 是下一增强，不阻塞 PDF 生存修复。

### 7.10 Windows 常见故障分类与固定处理

| 类别 | 常见表现 | Doctor 必查 | 处理原则 |
|---|---|---|---|
| PATH/多版本 | `python/node/cargo` 指向错误 | `Get-Command -All`、实际 binary hash | 使用 repo pin 和明确入口，不改全局碰运气 |
| MSVC/SDK | linker、`windows.h`、target 错 | vswhere、VC tools、SDK、arch | 报缺失组件与安装计划 |
| WebView2 | 白屏、启动失败、版本差异 | Runtime version、Evergreen/Fixed mode | 明确 runtime 策略和 fallback |
| 路径 | 空格、中文、MAX_PATH、UNC | checkout/temp/cache/data path | 测空格/中文/长路径；不要求用户改目录掩盖 bug |
| 编码/换行 | 中文乱码、BOM、CRLF 差异 | console/file encoding、`.gitattributes` | UTF-8 + 明确 newline；不改全局 Git 配置 |
| 文件锁 | wheel/EXE/DB 无法替换 | 持有进程、PID/start time、Defender event | 有界 retry/诊断；不静默 kill 无关进程 |
| 端口/防火墙 | 8000 占用、启动超时 | listener/PID、loopback、proxy | 动态端口握手；不固定端口猜测 |
| 子进程 | WM_CLOSE 后残留 Python | process tree、token、job object | Rust shell 持有进程身份并强制回收 |
| DLL/native | 缺 VC runtime/DLL/arch 混用 | PE arch、DLL search、bundle manifest | bundled probe；错误显示缺哪一项 |
| SQLite/WAL | locked、残留 WAL、迁移冲突 | owner lease、journal、process | 单一 migration operator、备份、超时和恢复 |
| 权限/数据根 | Program Files 写失败 | effective roots、ACL、portable flag | 程序与数据分离；不 fallback 到未知目录 |
| 杀毒/同步盘 | 随机慢/隔离/文件变化 | quarantine/OneDrive status（只读） | 建议隔离 build cache；不自动关闭防护 |
| 时区/时钟 | 复习计划、token、mtime 漂移 | timezone/UTC/clock | durable UTC + UI local projection |
| GPU | 3D/OCR/模型崩溃 | adapter/GPU/driver capability | CPU/2D fallback；GPU 不是 core 前置 |

端口实现必须消除 TOCTOU：由 child 自己绑定 `127.0.0.1:0` 并通过受认证 readiness channel 报告实际端口，或由 parent 持有 reservation 直到 child 接管；不能只测试“通常没撞端口”。

Windows 传统 `MAX_PATH` 仍可能在部分工具中出现；即使系统启用 long paths，应用也需 opt-in。项目既要支持用户选择的普通路径，也要在 doctor 中解释限制。参考：[Microsoft Maximum Path Length](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation)。

### 7.11 Doctor 输出

```text
artifacts/local/<commit-or-dirty-id>/<run-id>/
  environment.redacted.json
  toolchains.json
  path-and-permission.json
  capabilities.json
  commands.jsonl
  logs/
  build-manifest.json
  artifacts.sha256
```

要求：

- 标记 commit/tree、dirty、lock digest、toolchain digest、profile；
- 环境变量白名单采集，路径可记录在 machine evidence，但不得上传 secret；
- dirty build 标记 `local-unqualified`；
- 不把本地构建冒充云端 exact-SHA Release evidence；
- 同一失败签名命中既有 KnownIssue 时执行定向诊断，不重跑全仓审计。

---

## 8. 新增 Codex Program Cards

以下均是 Program Card；只能执行 child，不得用父 ID 建一个巨型 PR。

### AXW-006｜Personal Research License & OSS Absorption

**类型：** Governance/Foundation  
**依赖：** AXW-000、AXW-004A；与 PDF 实现可并行，不阻塞已批准的现有宽松依赖  

| Child | 内容 | 验收 |
|---|---|---|
| `AXW-006A` | 顶层 LICENSE/依赖组合清点，R-P 与 R-C 决策 | Owner 选择、兼容矩阵、无猜测 LICENSE |
| `AXW-006B` | Distribution Lane + LicenseProfile + Upstream Ledger schema | 每个组件可分别批准 local/source/binary/network |
| `AXW-006C` | `LICENSES/`、NOTICE、SPDX SBOM、modification/source bundle 生成 | exact-SHA installer 内容能反查到来源与许可 |
| `AXW-006D` | vendor/fork/sidecar/source-copy 目录和门禁 | 未登记源码、模型、字体、资产不能进入 build |
| `AXW-006E` | 自研替换 Port/fixture/migration/rollback 合同 | 替换不改写历史义务，可在同 fixture 上切 provider |

**禁止验收捷径：** “个人项目”“免费”“GitHub 可见”“有 Stars”“README 写 open source”均不是许可证据。

### AXW-007｜Windows Toolchain Truth & Doctor

**类型：** Developer Foundation  
**依赖：** AXW-000；应在下一次 installer 修复前完成  

| Child | 内容 | 验收 |
|---|---|---|
| `AXW-007A` | read-only `doctor` + 当前机器 baseline | 无 secret；能准确指出 Python/Rust/Node/MSVC/SDK/WebView2/NSIS/provider 缺口 |
| `AXW-007B` | toolchain truth/locks 与版本漂移门禁 | 新终端、CI、干净用户得到相同工具链选择 |

### AXW-008｜Windows Bootstrap & Offline Cache

**类型：** Developer Foundation  
**依赖：** AXW-007A/B  

| Child | 内容 | 验收 |
|---|---|---|
| `AXW-008A` | 薄 PowerShell wrapper + Python bootstrap/cache engine | online 模式只从 lock 来源下载并验 hash；系统级改变停为 Owner Action |
| `AXW-008B` | content-addressed cache + cached-only mode | 缺任一对象稳定报 cache ID，零联网 fallback |
| `AXW-008C` | portable offline kit | 区分同机缓存与另一台新机 kit；manifest、license、hash 完整 |

### AXW-009｜Windows Build Profiles & Exact-SHA Qualification

**类型：** Developer Foundation / Release Qualification  
**依赖：** AXW-003、AXW-007、AXW-008；正式 Release 另依赖对应产品能力 TaskPack  

| Child | 内容 | 验收 |
|---|---|---|
| `AXW-009A` | `axw.ps1` 单入口与 dev/verify/bundle profiles | `-NoProfile`、幂等、native exit code、JSON logs；复杂决策在 Python |
| `AXW-009B` | Windows bug corpus/hardening | 空格/中文/长路径/锁/端口/WebView2/进程退出/SQLite/portable fixtures |
| `AXW-009C` | clean exact-SHA bundle provenance | 拒绝 dirty、ambient runtime、lock/toolchain drift；产物/digest 可回读 |
| `AXW-009D` | clean machine installer qualification | install→真实资料→restart→close/force-kill→uninstall；无孤儿/端口/数据泄漏 |

### AXW-090｜Learning Experience & Representation Layer

**类型：** Permanent Product Program  
**依赖：** Product Truth；各 child 另依赖相应数据/Evidence/Human Learning 基础  

| Child | 名称 | 最早 Horizon | 验收重点 |
|---|---|---:|---|
| `AXW-090A` | Representation Contract | H1 | Anchor/provenance/loss/fallback/export/license |
| `AXW-090B` | Tables/Cards/Timeline/Comparison | H2 | 真实 Office/PDF 数据、过滤与来源可见 |
| `AXW-090C` | Learning Map/Canvas/Graph | H3 | JSON Canvas 往返、开放导出、1k 节点性能 |
| `AXW-090D` | Visual Teaching/Courseware | H4–H6 | 课件回原证据、静态导出、无障碍 |
| `AXW-090E` | Animation/Dynamic Explanation | H5–H7 | 时间线、可暂停、文本替代、asset ledger |
| `AXW-090F` | Simulation/Practice Lab | H6–H7 | 参数/种子/环境/输出/结论范围 |
| `AXW-090G` | Spatial Memory 2D/2.5D | H6–H7 | loci/route/retrieval，2D fallback |
| `AXW-090H` | Spatial Memory 3D/VR/AR | H8 | 无高端硬件仍可用；真实 retention/transfer 评测 |
| `AXW-090I` | Learning Effect Evaluation | H4 起 | pretest、即时/延迟回忆、迁移、Teach Back、限制 |

---

## 9. 对现有执行顺序的最小调整

不允许这三个 Program 再次拖慢产品闭环。执行顺序调整为：

```text
AXW-000 云端冻结
├─ AXW-003 CI false-green hotfix
├─ AXW-001A / AXW-004A / AXW-004C Truth
├─ AXW-006A/B License decision/schema（与产品修复并行）
├─ AXW-007A/B Windows doctor/toolchain truth（与产品修复并行）
└─ AXW-008A/B bootstrap/cache（需要重建 bundle 时激活）

AXW-002A + AXW-011A
→ AXW-010
→ AXW-012 Installed PDF Survival
   同时复用 AXW-007A/B 与 AXW-009 对应 child 的环境证据

AXW-020/021/022/024
→ AXW-090A/B（早期结构化表征）
→ AXW-025 Early Human Learning Proof

AXW-040–045
→ AXW-090C Canvas/Graph/Learning Map

AXW-051–054
→ AXW-090D–I 按 Horizon 独立激活
```

`AXW-006C–E`、`AXW-008C`、`AXW-009B–D` 可以逐步交付；不得以“先把所有 369 个上游、完整跨机离线包或所有 Windows bug 都治理完”为由阻塞 PDF。

---

## 10. 增量 Definition of Done

### OSS 吸收

- 不再把 copyleft 自动等同于不可用；
- 每项吸收方式和分发通道有明确许可结论；
- 允许合法源码复制/合并/fork/vendor；
- exact revision、LICENSE/NOTICE/SBOM/source/patch/asset 全链存在；
- 后期自研可替换，但历史义务不被删除。

### Windows 构建

- PowerShell 7 单入口可从新终端运行；
- Python/Rust/Node/MSVC/SDK/WebView2/installer/provider 都有机器化版本真相；
- `dev/verify/desktop-fast/bundle/installer/full/offline-rebuild` 边界清楚；
- 本机常见 bug 有固定 signature、诊断与回归 fixture；
- clean Windows 安装态真实用户流通过；
- 不需要把业务逻辑重写到 Rust 或 PowerShell。

### 学习辅助层

- LER 在 Product Truth 和 Master Blueprint 中永久登记；
- 视图、表格、图谱、课件、动画、模拟、空间记忆各有对象、任务和 Horizon；
- 所有表现回到 EvidenceAnchor，能开放导出并有低配/无障碍 fallback；
- 技术完成与学习效果证据分开；
- 3D/VR 不阻塞当前闭环，但也不再从蓝图消失。

---

## 11. 本轮禁止语句

Truth-Drift Gate 增加以下禁句或等义表达：

- “非商业所以可以随便复制源码”；
- “个人项目不受 GPL/AGPL 约束”；
- “sidecar 自动规避许可证”；
- “换成自研后可以删除旧 Release 的许可证记录”；
- “3D/记忆宫殿已从路线取消”；
- “展示了动画/3D 就证明提升学习”；
- “所有语言都可以随便承载业务逻辑”；
- “本地能编译就等于 Release qualified”。

---

## 12. Codex 首包执行提示

```text
读取最新 main、Product Truth 和本增量包，只执行 AXW-007A。
在用户实际 Windows checkout 中以只读方式建立 doctor 与 machine baseline；
不得安装、卸载、修改 PATH/registry、删除缓存或运行完整 installer；
输出 Python/uv、Rust/Cargo、Node/npm、MSVC/SDK、WebView2、Tauri/NSIS、
外部 provider、路径/编码/端口/进程环境的脱敏 JSON 证据和缺口清单。
完成后停止，不跨入 AXW-007B。
```

许可证首包另行执行：

```text
读取最新依赖树和仓库 LICENSE 真相，只执行 AXW-006A。
比较 R-P 与 R-C 对当前 Python/npm/Rust/Tauri/installer/模型/资产的兼容性；
以“最大化合法源码吸收”为首选目标，不以未来闭源商业化为默认约束；
输出 Owner Decision，不直接重许可、不复制第三方源码、不发 Release。
```

---

## 13. 一句话增量路线

> **该项目可以在合规前提下尽量直接吸收成熟开源代码，并通过稳定 Provider 逐步替换自研；Windows 用锁定工具链和 PowerShell 7 单入口把环境问题变成可诊断证据；学习辅助层从表格、图谱、课件、动画一直延伸到 3D 记忆宫殿，全部服务于可追溯、可测量、可降级的人类学习。**
