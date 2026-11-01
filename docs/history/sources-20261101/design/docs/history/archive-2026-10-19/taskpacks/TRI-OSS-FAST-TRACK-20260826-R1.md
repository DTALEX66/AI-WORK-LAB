# 三项目开源复用、复刻与融合快速成品化总图

> **SUPERSEDED（历史证据）**：跨项目总规划。DESIGN-LAB 侧由 standalone-first（ADR-001）取代“依赖 WORK-LAB/ArcheAxis 运行”的表述；本图仅作历史证据保留，不作为 current 派工入口。

- 决策 ID：`TRI-OSS-FAST-TRACK-20260826-R1`
- 调研时间：`2026-08-26 UTC`
- 输入证据：三项目完整 ChatGPT 对话导出、三份最终任务包、R4 全量审计、三仓云端 `main`、上游官方仓库/文档
- WORK-LAB 基线：`main@2941412ec88b2b3e278753425255e31d97710295`
- ArcheAxis 基线：`main@bf0c48396c751647ac76ee4578bc38f44888a23e`
- DESIGN-LAB 基线：`main@38d322affaec163e7c7ca0e3610042285aab1f0f`
- 目标：停止通用能力重复自研，在 14 天内让三个项目各自出现一个可安装、可完成黄金流程、可失败、可恢复的真实版本
- 边界：本文件是实施裁决和任务入口，不声称上游已安装或三仓已经完成代码融合

## 0. 最终裁决

三个项目都需要用户界面，但都不应继续从零自研完整前端；三个项目也都需要后端，但只自研各自不可替代的真值与专业层。

| 项目 | 直接采用的产品底座 | 直接复用的后端/工具 | 本项目只保留的独有部分 |
|---|---|---|---|
| WORK-LAB | Builderz Labs Mission Control 下游产品壳 | Dagu 外置执行引擎；TokenTelemetry 只读观测；OPA/OTel/in-toto/Syft 等标准工具 | Authority、Canonical Config、Adapter、审批、预算、Receipt、跨软件连续性 |
| ArcheAxis | DeepTutor 下游学习产品壳 | Docling、MarkItDown、PaddleOCR、faster-whisper、sqlite-vec、py-fsrs、Cytoscape.js | Source、Anchor、Claim/Evidence、Provenance、人类学习与机器能力真值 |
| DESIGN-LAB | Open Design 主宿主/主界面 | OpenPencil 可编辑画布；Adobe UXP/各软件官方 API；ComfyUI 外置；Style Dictionary/Playwright 等 | Design IR、Domain Packs、专业 Jury、Human Gates、rights、preflight、可编辑交付 |

这不是把三个项目改名成开源项目。正确结构是：`上游完整产品能力 + 本项目权威扩展 + 可替换 Adapter + 锁定版本/补丁队列`。上游 UI、通用任务板、通用知识库、通用画布和运行器不再重复实现；本项目的真值对象永远不能被上游数据库替代。

## 1. 为什么几个月仍没有完整可用版

历史对话和当前仓库共同显示，瓶颈不是“还缺几个功能”，而是交付策略错误：

1. 同时自研产品壳、状态模型、运行时、观测、解析、适配器、设计画布和质量体系，范围远超单人短期可交付边界。
2. 历史把 `调研过 / 登记过 / 复制过 / 结构测试通过 / 真实运行` 混成“已吸收”，导致能力数量很大，产品主链仍断。
3. 多套 UI、多套桌面壳和多套状态账本并存；每次修一套，另一套仍在漂移。
4. 旧任务包把高匹配上游降为 P2 PoC，又继续给自研主线加功能，错过了整包复用的时间收益。
5. 许可证、第三方指令、模型权重和升级风险没有与“功能好不好”分开裁决，结果要么过度保守不用，要么登记后错误激活。

从本包开始，默认顺序改为：`直接运行上游 -> 用真实黄金流程验收 -> 建权威桥 -> 替换品牌/产品边界 -> 删除重复自研 -> 再增强`。

### 1.1 历史收集文档的实际覆盖

对三份完整对话导出按 GitHub 仓库 URL 去重，WORK-LAB 约 765 条、ArcheAxis 约 886 条、DESIGN-LAB 约 814 条。这里的数字是“历史中出现过的 URL”，不是等量的有效项目：它们混有组织页、topic/search、awesome 清单、第三方 README 的依赖、已删除候选、fork、同名误认和自动生成报告。

本轮没有按出现次数批量采用，而是逐层恢复历史语义：`实际运行依赖 / 曾吸收代码或方法 / 受控 Adapter / 研究候选 / 历史噪声`。Mission Control、Dagu、TokenTelemetry、DeepTutor、OpenTutor、Docling、Open Design、OpenPencil、Penpot、ComfyUI、CLI-Anything 等均在历史中已有轨迹；本轮新增的是当前身份、许可、Windows/硬件、产品重合、退出成本和真实黄金流程裁决。UIClip、Flue 等未绑定唯一仓库身份的旧名称继续保持 `UNRESOLVED`，不得靠名称恢复为 active。

### 1.2 2026-08-26 云端 main 复审

| 项目 | 当前实现事实 | 对复用路线的影响 |
|---|---|---|
| WORK-LAB | 当前仍有 React 18/Vite/Tailwind/Recharts Observer 和 Tauri 壳，但生产前端门禁与 UNKNOWN 真值仍不完整 | 保留 WORK 独有 Receipt/Drift 组件；通用任务、Agent、成本、session UI 迁到 Mission Control/TokenTelemetry |
| ArcheAxis | 当前 React/Vite 产品壳依赖很薄，历史 UI 合同迁移不完整，且存在双 Tauri 产品根 | 不再补齐一整套通用学习 UI；用 DeepTutor 先成品化，再迁入 ArcheAxis 独有证据/学习合同 |
| DESIGN-LAB | 当前定位本就强调 host-native，根树没有成熟的中央产品前端，反而保留大量复制知识、能力索引和第三方指令 | 直接把 Open Design 设为正式主宿主；DESIGN 收缩为插件、专业真值、质量门和 Adapter |

三仓 exact SHA 与本文件页首一致。绿色 CI 只证明当前受测范围，不代表这些上游已接入；所有采用状态在产生当前 SHA 的安装/运行/回滚证据前均为 `TODO`。

## 2. 统一复用方式

| 状态 | 含义 | 代码进入仓库方式 | 典型对象 |
|---|---|---|---|
| `ADOPT_PRODUCT_BASE` | 直接作为可用产品壳，维护窄下游分支 | 独立 upstream remote、锁 tag/commit、维护 patch queue；不复制散落源码 | Mission Control、DeepTutor |
| `ADOPT_HOST` | 作为正式外部宿主/入口 | 安装已发布版本；本仓只放插件、schema、adapter 和锁文件 | Open Design |
| `EMBED_LIBRARY` | 稳定库直接成为内部依赖 | 包管理器锁版本，封装窄接口，加入 SBOM/NOTICE | sqlite-vec、py-fsrs、Cytoscape.js |
| `EXTERNAL_RUNTIME` | 因 GPL、体积、GPU 或升级独立运行 | localhost/CLI/MCP/API adapter；数据目录、升级与卸载独立 | Dagu、ComfyUI、Blender、Krita |
| `EXTRACT_MODULE` | 只吸收方法、组件或算法 | 明确来源文件和许可证；重写最小模块并保留 attribution | OpenTutor 学习块、CLI-Anything 方法 |
| `BAKE_OFF` | 只允许短期双候选对比 | 固定 24～48 小时和退出条件 | TokenTelemetry vs TMA1、Marker vs olmOCR |
| `REFERENCE_ONLY` | 有启发但不进入运行面 | 只保留裁决摘要和上游链接 | 重型平台、未来 3D/图投影候选 |
| `QUARANTINE/REJECT` | 身份、许可、安全或价值不闭合 | 不进入 prompt、工具发现、构建、SBOM 能力计数 | 第三方控制指令、零 hash 权重、同名未解析项目 |

### 2.1 许可证硬边界

- MIT/Apache/BSD/ISC：可以 fork、修改或嵌入，但必须保存许可证、NOTICE、修改记录和来源 commit。
- LGPL/MPL：优先动态/进程边界或保留文件级修改边界；逐项由发布合规检查确认。
- GPL/AGPL：默认只作未修改外置程序，通过公开 CLI/API/localhost 交互；不得复制 GPL/AGPL UI、后端代码或组件进入宽松许可核心。
- 模型代码许可、权重许可、训练数据声明分别记录；代码 Apache 不代表权重可商用。
- “复刻”只复用合法代码、协议和通用交互模式，不复制商标、品牌装潢或闭源产品素材。

### 2.2 上游锁定合同

每个进入运行面的项目必须登记：

`upstream_repo / upstream_tag / upstream_commit / archive_sha256 / SPDX / NOTICE / patches[] / consumer / data_scope / network_scope / install / update / rollback / last_verified / evidence_level`。

禁止引用 `main/latest` 作为发布证据。所有一键安装脚本先下载、验 hash、扫描，再执行；默认关闭匿名遥测、更新检查和非必要出网。

## 3. 三项目最终拓扑

```text
                           WORK-LAB
 Authority / Config / TaskPack / Policy / Receipt / Continuity
         |                         |                       |
 Mission Control UI           Dagu execution      TokenTelemetry view
         |                         |                       |
         +---------- versioned Envelope / Receipt --------+
                                  |
                 +----------------+----------------+
                 |                                 |
              ArcheAxis                         DESIGN-LAB
 Source/Anchor/Knowledge/Learning       Design IR/Domain/Jury/Rights
         |                                      |
     DeepTutor UI                        Open Design host UI
         |                                      |
 Parser/Search/ASR adapters       OpenPencil/Adobe/Blender/Comfy adapters
```

WORK 不读取另外两仓内部数据库；ArcheAxis 和 DESIGN 也不依赖 WORK 才能启动。跨项目只传版本化 `Envelope / Query / Candidate / Receipt`，任一项目离线时另外两个仍能工作。

## 4. WORK-LAB 开源融合方案

### 4.1 第一选择

#### Mission Control — `ADOPT_PRODUCT_BASE`

用途：替换当前从零自研的 Control Surface 主体，复用任务板、Agent/Session、审批、活动、调度、成本、安全、权限、API、实时更新和桌面/本地产品结构。

融合方式：

1. 新建受控下游分支，不把整仓源码散复制进 WORK 现有目录。
2. 第 1 阶段原样运行，只用合成数据验证 Windows 安装、任务、审批、失败和恢复。
3. 第 2 阶段把 Mission Control 的任务/Agent 数据层改接 WORK API；其 SQLite 只保存 UI/缓存/会话，不成为 Authority。
4. 删除或禁用与 WORK 冲突的 Memory 真值、SOUL 真值、Skills 安装权、模型配置真值和私有会话扫描。
5. 将 Aegis Review 映射到 WORK policy/approval receipt；`done` 必须由 WORK Receipt 放行。
6. 品牌和导航可调整，升级以 patch queue 重放，禁止长期深 fork。

放弃条件：48 小时内无法在 Windows 本地完成“建任务→审批→执行投影→失败→重试→回执→重启读回”，或数据层无法隔离时，退回 `shadcn-admin-kit + Tremor + React Flow` 的薄壳组合，不再维护现有两套 UI。

#### Dagu — `EXTERNAL_RUNTIME`

用途：立即获得 Windows 单文件 DAG、调度、重试、人工步骤、运行历史、MCP 和 coding-agent harness，替代 WORK 自研通用执行器。

边界：Dagu 为 GPL-3.0 外置进程。WORK `WorkUnit` 是唯一任务真值；Dagu YAML 和 run ID 是可删除执行投影。每次投影记录输入 hash，Dagu 完成后转换成 `RuntimeReceipt`；禁止两边同时人工修改同一状态。

#### TokenTelemetry — `ADOPT_READONLY_OBSERVER`

用途：立即获得 Hermes、Codex 等客户端的 session/token/cost/tool trace 前端，替代当前 Observer 中大量自造解析和错误的 UNKNOWN 映射。

边界：只读读取本机日志；默认 `DO_NOT_TRACK=1`、`TT_NO_UPDATE_CHECK=1`，loopback 绑定；prompt/response 正文默认不进入 WORK。其成本仅为 observation，不是账单真值。WORK Observer 可以先链接/嵌入其页面，后续只抽取已验证的聚合 API。

### 4.2 WORK 候选裁决矩阵

| 项目 | 前/后端 | 裁决 | 复用点 | 不采用原因/边界 |
|---|---|---|---|---|
| Mission Control | 全栈 | `ADOPT_PRODUCT_BASE` | 完整控制台、任务、审批、RBAC、API、实时状态 | Alpha；必须锁版本、隔离 DB 与扫描权限 |
| Dagu | 全栈/运行时 | `EXTERNAL_RUNTIME` | DAG、调度、重试、人工步骤、Windows、MCP | GPL；不能成为第二任务真值 |
| TokenTelemetry | 全栈/观测 | `ADOPT_READONLY_OBSERVER` | Hermes/Codex 观测、成本、工具调用、Windows | 默认匿名遥测开启；必须强制关闭并最小化正文 |
| TMA1 | 全栈/OTel | `BAKE_OFF_24H` | OTel、Codex、单二进制、反馈闭环 | 与 TokenTelemetry 重复；不允许双生产 |
| AgentLens | 后端/模式 | `EXTRACT_METHOD` | hash-chain、MCP/OTel 事件思路 | 体量与成熟度不足以作产品底座 |
| OpenTelemetry Collector | 后端 | `OPTIONAL_SIDECAR` | OTLP 标准化与 exporter | 不作任务/成本真值 |
| OPA/Conftest | 后端 | `EMBED_TOOL` | 复杂策略和 CI policy-as-code | 简单规则仍保留内置快速路径 |
| in-toto/Cosign | 后端/供应链 | `EMBED_TOOL` | 可验证执行/发布证明 | 不引入中心服务为 P0 前置 |
| Syft/Grype/OSV/Trivy | 工程 | `EMBED_TOOL` | SBOM、漏洞和镜像扫描 | 扫描结果需版本和例外治理 |
| React Admin/Refine | 前端 | `FALLBACK_ONLY` | 快速 CRUD/内部工具 | 只有 Mission Control 退出才启用一个 |
| shadcn-admin-kit/Tremor | 前端 | `FALLBACK_UI_DONOR` | 管理台、数据表、图表、响应式 | 不再造第二设计系统 |
| React Flow | 前端 | `EMBED_LIBRARY_IF_NEEDED` | DAG/依赖图 | 仅可视化，不定义调度真值 |
| Langfuse/HyperDX/SigNoz | 全栈 | `REFERENCE_OR_OPT_IN` | 深度 LLM/OTel 分析 | 默认部署过重且数据面重叠 |
| Prefect/Hatchet/Kestra | 后端 | `REJECT_FOR_V1` | 成熟工作流能力 | 与 Dagu 重复、运维更重 |

### 4.3 WORK 两周黄金闭环

`在 Mission Control 创建 WorkUnit -> WORK policy 生成 plan -> 人工批准 -> 投影 Dagu -> Codex/Hermes 执行 -> TokenTelemetry 观测 -> WORK 收 RuntimeReceipt -> UI 显示成功或真实失败 -> 重启后三方状态可对账 -> rollback`。

未完成上述一条链前，禁止新增 Agent 框架、第二观测平台、第二任务数据库或美化现有 Observer。

## 5. ArcheAxis 开源融合方案

### 5.1 DeepTutor — `ADOPT_PRODUCT_BASE`

DeepTutor 已提供本地 Web+CLI、统一 Chat/Solve/Quiz/Research/Visualize、Co-Writer、Book Engine、知识库、Space、记忆和可扩展工具，是 ArcheAxis 当前最缺的完整用户体验。它不再只是“教学 sidecar”，而是第一版产品壳。

融合方式：

1. 先用已发布稳定版完成 Windows 本地安装，不修改代码跑通“导入资料→有引用问答→Quiz→Book/Notebook→重启”。
2. 建 `ArcheAxisAuthorityAdapter`：DeepTutor KB/Memory 只存可重建投影；原始文件、Anchor、Claim/Evidence、rights、掌握度仍由 ArcheAxis API 决定。
3. 将 DeepTutor citation 映射到 `Anchor/v2`，不能定位到源版本的回答显示 `UNANCHORED`。
4. DeepTutor Quiz/Book/Chat 产生 proposal 和 `LearningEvent`，不直接写 verified knowledge 或机器能力。
5. 保留窄 upstream patch queue；优先写插件/adapter，不大改其内部 Agent runtime。
6. 现有 ArcheAxis React/Tauri 主壳转为 `LEGACY_COMPAT`；黄金流程迁完后删除重复页，不双线开发。

### 5.2 ArcheAxis 模块裁决矩阵

| 项目 | 前/后端 | 裁决 | 复用点 | 边界 |
|---|---|---|---|---|
| DeepTutor | 全栈 | `ADOPT_PRODUCT_BASE` | 完整学习 UI、KB、Quiz、Research、Book、CLI | KB/Memory 不是真值；锁稳定版 |
| OpenTutor | 全栈/算法 | `EXTRACT_MODULE` | 学习块、FSRS/BKT、study plan、认知负荷 UX | Beta、Windows 次级；不运行第二套产品 |
| Docling | 后端 | `PRIMARY_PARSER` | PDF/Office/表格/公式/图片/音频统一解析 | DoclingDocument 是 derivative，不取代 Source |
| MarkItDown | 后端 | `NARROW_FALLBACK` | 轻量 Office/HTML/EPUB 转换 | 关闭远程 URI 和宽插件 |
| PaddleOCR | 后端/模型 | `OPTIONAL_OCR` | 中英扫描件和布局 OCR | 代码/权重/模型 hash 分开资格化 |
| Marker/olmOCR | 后端 | `BAKE_OFF_48H` | 复杂 PDF/OCR 备选 | 只选一个补充 Docling，不三套常驻 |
| sqlite-vec + SQLite FTS5 | 后端 | `EMBED_SEARCH_V1` | 单机混合检索、备份简单 | v1 不上 Qdrant/Neo4j 集群 |
| LanceDB | 后端 | `FALLBACK_SEARCH` | 嵌入式向量/多模态 | sqlite-vec 不能满足规模后再启用 |
| py-fsrs | 后端 | `EMBED_LIBRARY` | 间隔重复 | 只调度，不代表掌握真值 |
| faster-whisper | 后端 | `ASR_SIDECAR` | 本地 ASR、时间戳 | transcript 必须可校正并绑定音频锚点 |
| Cytoscape.js | 前端 | `EMBED_LIBRARY` | 知识/证据/掌握关系图 | 图是投影，不成为数据库 |
| Graphiti/MemOS | 后端 | `DEFERRED_PROJECTION` | 时态图、机器运行记忆 | v1 不引入；可删除、可重建 |
| LightRAG/GraphRAG/HippoRAG | 后端 | `REFERENCE_ONLY_V1` | 图检索方法 | 不同时堆多套 RAG |
| Studyield/OpenViking | 全栈 | `EXTERNAL_OR_RESEARCH` | teach-back、上下文文件系统思路 | AGPL；不并入核心 |

### 5.3 ArcheAxis 两周黄金闭环

`导入 PDF/DOCX -> ArcheAxis 保存原件/fixity/rights -> Docling 生成结构 -> DeepTutor 阅读与引用 -> 用户批注/Quiz/teach-back -> py-fsrs 安排复习 -> LearningEvent 重放 -> Source/Anchor/掌握度关闭重开一致 -> 导出带 provenance 的学习包`。

未完成这条链前，禁止 3D/VR/AR、第二图数据库、第二 Tutor、通用 Planner 和现有壳的新页面扩张。

## 6. DESIGN-LAB 开源融合方案

### 6.1 Open Design — `ADOPT_PRIMARY_HOST`

Open Design 已提供 Windows 桌面应用、Agent/CLI/MCP、插件、skills、design systems、沙箱预览及 HTML/PDF/PPTX/MP4 交付，直接解决 DESIGN 缺完整前端和宿主的问题。

融合方式：

1. 安装并锁定发布版；DESIGN 不复制其 200+ skills，也不把数量算作自身能力。
2. 新建 `design-lab-core` 官方格式插件，只暴露 Brief、Direction、Design IR、Human Gate、Jury、rights、preflight、delivery receipt。
3. 将现有经审核的 atoms/bundles/scenarios 提炼为少量插件和 `DESIGN.md`，所有 vendored `AGENTS/CLAUDE/install/affiliate` 保持惰性隔离。
4. Open Design 负责入口、预览、Agent 驱动和通用导出；DESIGN API 决定 gate、专业质量和证据等级。
5. 上游内部 SQLite、skills 和记忆不成为 DESIGN SSOT；升级通过插件契约测试和 patch-free 优先策略。

### 6.2 OpenPencil — `ADOPT_EDITABLE_CANVAS`

OpenPencil 作为正式可编辑 UI/vector lane，复用 node tree、components/variants、auto-layout、`.fig/.pen`、CLI、SDK 和 MCP。DESIGN 通过 MCP/CLI 生成和修改结构，再执行 close/reopen/readback；不嵌入第二套自研 canvas。

Penpot 保留为可选协作/团队 lane，不与 OpenPencil 双主宿主。涉及 Penpot MCP 代码执行时必须使用专用文件、最小权限、timeout 和操作白名单。

### 6.3 DESIGN 候选裁决矩阵

| 项目 | 前/后端 | 裁决 | 复用点 | 边界 |
|---|---|---|---|---|
| Open Design | 全栈/宿主 | `ADOPT_PRIMARY_HOST` | 完整桌面 UI、插件、Agent/MCP、预览与导出 | 只通过官方扩展面；不复制全部 skills |
| OpenPencil | 全栈/画布 | `ADOPT_EDITABLE_CANVAS` | 可编程 node tree、Figma 文件、组件、布局、MCP | 当前快速演进；锁版本、限定黄金格式 |
| Penpot + official MCP | 全栈 | `OPTIONAL_COLLAB_HOST` | 协作、tokens/components、读写 | MPL 与代码执行边界；不作第二默认宿主 |
| Adobe UXP samples | 前端/插件 | `COPY_OFFICIAL_STARTERS` | Photoshop/Premiere 面板、命令、文件读写骨架 | 每个 Adobe 版本独立读回；官方 API 优先 |
| Figma plugin samples/API | 前端/插件 | `COPY_OFFICIAL_STARTERS` | 插件 UI、文档节点、export | 专用测试文件；不得写私人空间 |
| Inkscape/Krita/GIMP/Blender/Scribus | 外部软件 | `EXTERNAL_RUNTIME` | 矢量、绘画、图像、3D、出版原生交付 | GPL 程序外置；只传动作计划和产物 |
| ComfyUI | 外部生成 | `EXTERNAL_RUNTIME_V1` | 既有生态、节点工作流、局部生成 | GPL；模型权重单审；8GB VRAM profile |
| InvokeAI/Krita AI Diffusion | 外部生成 | `FALLBACK_BAKEOFF` | 更聚焦创作/局部编辑的 UX | 不与 ComfyUI 双生产 |
| OpenCut | 全栈/视频 | `EXTERNAL_BAKEOFF_LATER` | 本地时间线和未来 API/MCP | 当前重写/接口仍演进，不阻塞 v1 |
| FFmpeg | 后端/外部 | `EXTERNAL_TOOL` | 确定性转码、探测、缩略图 | 构建配置/codec 许可单审 |
| Style Dictionary + DTCG | 后端/规范 | `EMBED_TOOL/SPEC` | tokens 编译到多宿主 | 只保存 canonical tokens，不复制宿主状态 |
| Storybook | 前端/质量 | `EMBED_TOOL` | 组件目录、交互和视觉 fixture | 不是产品前端 |
| Playwright/pixelmatch/axe-core | 工程 | `EMBED_TOOL` | 点击、视觉差异、可访问性门 | 不能替代真人 Jury |
| OpenAssetIO/OTIO/OCIO/MaterialX | 后端/标准 | `DOMAIN_OPTIONAL` | 资产、时间线、色彩、材质互操作 | 只由真实黄金案例启用 |
| psd-tools | 后端 | `READ_ONLY_LIBRARY` | PSD 结构读取/检查 | 不作为权威写回 |
| ag-psd | 后端 | `LIMITED_WRITE` | 受限 PSD 读写 | 文字/色彩/特性不完整；Photoshop UXP 为权威写 |
| VTracer/resvg | 后端 | `EMBED_LIBRARY` | 矢量化、SVG 安全渲染 | 人工质量和 SVG 清洗必需 |
| SAM2/GroundingDINO/BiRefNet/PaddleOCR | 模型 | `QUALIFY_ONE_BY_ONE` | 分割、检测、抠图、OCR | code/weight/data license 与 8GB 实测 |
| OmniParser/LayerD/StarVector 未闭合权重 | 模型 | `QUARANTINE` | 仅研究 | 许可、remote code、身份或硬件未闭合 |

### 6.4 DESIGN 两周黄金闭环

`Open Design 输入真实 Brief -> DESIGN 插件锁定 Direction/Rights -> OpenPencil 生成可编辑 UI/矢量稿 -> 人工 Quality Gate -> Photoshop UXP 或 Blender/Inkscape 完成原生编辑 -> close/reopen/readback -> Playwright/视觉/a11y/preflight -> 导出 editable source + preview + BOM + rights + receipt`。

第一条黄金案例只选一个 UI/品牌任务；不要同时追品牌、包装、视频、3D、出版五条线。其余作为回归候选，等第一条 E4 后展开。

## 7. 72 小时、14 天和 6 周实施列车

### 7.1 前 72 小时：只验证上游，不改大架构

| 时间 | WORK | ArcheAxis | DESIGN |
|---|---|---|---|
| 0～8h | 锁 Mission Control/Dagu/TokenTelemetry 版本和许可；建立独立数据目录 | 锁 DeepTutor/Docling/sqlite-vec；建立独立 workspace | 锁 Open Design/OpenPencil；创建专用测试项目 |
| 8～24h | 原样跑通任务、审批、失败、重启；TokenTelemetry 关闭出网 | 原样跑通导入、引用问答、Quiz、Book、重启 | 原样跑通 brief、预览、插件、可编辑文件、重启 |
| 24～48h | 建最薄 WorkUnit→Dagu 与 Receipt adapter | 建 Source/Anchor→DeepTutor citation adapter | 建最薄 DESIGN gate 插件和 OpenPencil adapter |
| 48～72h | 真实 Codex/Hermes 一次执行；裁决 TMA1 | 一个真实学习资料黄金流；裁决解析 fallback | 一个真实 UI/品牌黄金流；裁决 Comfy lane |

每一步必须产生：固定版本、安装日志、配置 diff、数据目录、端口、成功/失败截图、产物 hash、卸载/恢复说明。72 小时结束仍只有 README 或 mock，即判定该上游退出，不继续研究。

### 7.2 第 1 周：做最薄权威桥

- WORK：Mission Control 只通过 WORK API 写状态；Dagu 只接收 projection；TokenTelemetry 只读；统一 identity/idempotency/receipt。
- ArcheAxis：DeepTutor 所有来源引用映射 Anchor；学习动作转 LearningEvent；KB/Memory 可删后重建。
- DESIGN：Open Design 插件编译现有核心合同；OpenPencil/官方宿主动作均经过 HumanGate；第三方指令不进入插件发现。

### 7.3 第 2 周：发布三个 `0.1-usable`

每项目只发布一条黄金流程，包含 Windows 安装/启动/退出/重启、离线或 provider 失败、数据备份、恢复和卸载。Release 不能写“平台完成”，只能写已验证的具体流程、上游版本和未完成项。

### 7.4 第 3～6 周：收敛而非继续铺开

1. 删除或归档已被上游替代的重复 UI、运行时和状态代码。
2. 补品牌、可访问性、迁移、自动更新、SBOM/NOTICE、安全和性能。
3. 每项目增加第二条黄金流程；一个新上游必须替换一个旧实现或关闭一个已证明缺口。
4. 三个项目各自发布稳定安装包后，再做 WORK→DESIGN→ArcheAxis→WORK 联邦闭环。

## 8. 必须停止的自研与重复建设

### WORK

- 停止扩展现有 Observer 自造成本、session parser 和通用 Agent 仪表盘。
- 停止自研 DAG 调度器、通用审批 UI、通用 terminal/session 管理。
- 不再同时评估多个 Agent OS、工作流引擎或观测平台。

### ArcheAxis

- 停止给当前轻量 React 壳继续增加聊天、Planner、Book、Quiz 和通用 RAG 页面。
- 停止并行建设多套图数据库、记忆引擎和解析器。
- 不再把“自研 UI 合同”误解为“所有组件必须自己写”；合同保留，控件与产品壳复用。

### DESIGN

- 停止自研第二画布、第二通用设计聊天壳、第二模型网关。
- 停止把复制来的 skills/README/AGENTS 数量当能力。
- 停止同时建设多套生成图、视频、3D runtime；一个黄金案例只用一条已资格化路径。

## 9. 删除和迁移规则

任何旧实现进入删除前必须满足：

1. 新上游黄金流程在相同输入上通过；
2. 旧数据已迁移或可只读打开；
3. 反向依赖为零或有 adapter；
4. 备份、恢复 commit 和卸载读回存在；
5. 所有独有方法、测试和 UI 合同已提炼；
6. Owner 明确批准物理删除。

先做 `STOP_ACTIVE -> READ_ONLY_LEGACY -> EXTRACT -> ARCHIVE -> DELETE_APPROVED`，禁止一次性清空历史收集。

## 10. 每个上游的验收卡

每项必须回答：

- 是否解决当前一条黄金流程，而不是“未来可能有用”？
- Windows 11、64GB RAM、RTX 5060 8GB 能否运行？CPU fallback 是否诚实？
- 安装、升级、退出、卸载、数据目录和端口是否明确？
- 是否要求账号、云服务、远程遥测或宽文件权限？
- 哪个数据库是真值？上游数据删除后能否重建？
- 是否存在官方插件/API/CLI/MCP，还是只能 UI 自动化？
- 许可是否允许 fork/嵌入/商业使用？模型权重是否另有限制？
- 上游停更后能否用已锁版本继续工作？补丁队列多大？
- 成功、失败、取消、重试、回滚和重启读回是否全部有证据？
- 采用它后明确删除哪段自研代码？若没有替代对象，为什么要引入？

## 11. 发布完成定义

三个项目任何一个只有同时满足以下条件，才可称为“可用完整版本”的第一阶段：

1. 普通 Windows 用户按一份说明在 30 分钟内安装并启动；
2. 一条项目黄金流程从真实输入走到真实产物，不依赖 mock；
3. 上游版本、commit/hash、许可证、NOTICE、SBOM 和补丁均可追踪；
4. 项目独有真值没有被上游私有数据库取代；
5. 未知显示 UNKNOWN，失败不会伪装成功，人工门不能被模式绕过；
6. 完全退出、重启、断网/provider 失败后状态可恢复；
7. 有备份、迁移、卸载和回滚；
8. 至少一位独立使用者按任务完成验收；
9. Release 只声明已验证边界，并列出上游和未完成项；
10. 被替代自研线已经冻结，不再双轨维护。

## 12. 官方上游索引

### WORK-LAB

- [Builderz Labs Mission Control](https://github.com/builderz-labs/mission-control)
- [Dagu](https://github.com/dagucloud/dagu)
- [TokenTelemetry](https://github.com/VasiHemanth/tokentelemetry)
- [TMA1](https://github.com/tma1-ai/tma1)
- [OpenTelemetry Collector](https://github.com/open-telemetry/opentelemetry-collector)
- [Open Policy Agent](https://github.com/open-policy-agent/opa)
- [in-toto](https://github.com/in-toto/in-toto)
- [Syft](https://github.com/anchore/syft) / [Grype](https://github.com/anchore/grype) / [OSV-Scanner](https://github.com/google/osv-scanner)
- [shadcn-admin-kit](https://github.com/marmelab/shadcn-admin-kit) / [Tremor](https://github.com/tremorlabs/tremor) / [React Flow](https://github.com/xyflow/xyflow)

### ArcheAxis

- [DeepTutor](https://github.com/HKUDS/DeepTutor)
- [OpenTutor](https://github.com/zijinz456/OpenTutor)
- [Docling](https://github.com/docling-project/docling)
- [MarkItDown](https://github.com/microsoft/markitdown)
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- [sqlite-vec](https://github.com/asg017/sqlite-vec)
- [py-fsrs](https://github.com/open-spaced-repetition/py-fsrs)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [Cytoscape.js](https://github.com/cytoscape/cytoscape.js)

### DESIGN-LAB

- [Open Design](https://github.com/nexu-io/open-design) 与 [插件规范](https://github.com/nexu-io/open-design/blob/main/plugins/spec/README.md)
- [OpenPencil](https://github.com/open-pencil/open-pencil)
- [Penpot MCP](https://github.com/penpot/penpot-mcp)
- [Adobe Photoshop UXP Samples](https://github.com/AdobeDocs/uxp-photoshop-plugin-samples)
- [Figma Plugin Samples](https://github.com/figma/plugin-samples)
- [Style Dictionary](https://github.com/style-dictionary/style-dictionary) 与 [DTCG](https://www.designtokens.org/)
- [Storybook](https://github.com/storybookjs/storybook)
- [Playwright](https://github.com/microsoft/playwright) / [pixelmatch](https://github.com/mapbox/pixelmatch) / [axe-core](https://github.com/dequelabs/axe-core)
- [OpenAssetIO](https://github.com/OpenAssetIO/OpenAssetIO) / [OpenTimelineIO](https://github.com/AcademySoftwareFoundation/OpenTimelineIO) / [OpenColorIO](https://github.com/AcademySoftwareFoundation/OpenColorIO) / [MaterialX](https://github.com/AcademySoftwareFoundation/MaterialX)
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) / [OpenCut](https://github.com/OpenCut-app/OpenCut)
- [C2PA Rust SDK](https://github.com/contentauth/c2pa-rs)

研究结论仅在上述时间点成立；实施必须重查上游 tag、release、许可证、漏洞、Windows 安装和模型权重。项目热度不是采纳标准，真正标准是黄金流程、退出成本、权威边界和当前硬件证据。
