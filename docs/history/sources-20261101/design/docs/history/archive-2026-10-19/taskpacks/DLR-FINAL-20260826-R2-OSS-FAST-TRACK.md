# DESIGN-LAB 最终执行任务包

> **SUPERSEDED（历史证据）**：本包由 `docs/taskpacks/DESIGN-LAB-TODAY-EXECUTION-TASKPACK-2026-09-04.md`（DL-TP-20260904-STANDALONE-FIRST）取代。仅作历史证据保留，不作为 current 派工入口；其中与 standalone-first（ADR-001）冲突的表述以 ADR-001 为准。

- TaskPack ID：`DLR-FINAL-20260825-R1`
- 目标仓库：[DTALEX66/DESIGN-LAB](https://github.com/DTALEX66/DESIGN-LAB)
- 审计基线：`main@38d322affaec163e7c7ca0e3610042285aab1f0f`
- 基线核验时间：`2026-08-25 UTC`
- 状态：`READY_FOR_P0_EXECUTION`
- 前序包：`DL-DEEPEN-20260825-V1`（被本包取代，保留为历史证据）
- 执行边界：只修改 DESIGN-LAB；宿主软件、模型与外部工具通过官方 API/CLI/MCP/插件或受控 sidecar 使用。

## 0. 执行者先读

本包把 DESIGN-LAB 从“能力/开源项目数量很大”收敛为“少量真实商业设计闭环可证明”。执行者必须以执行时远端、真实软件版本、专用测试资产和人工 Jury 为准。当前仓库已有大量合同、方法、隔离材料和历史完成声明；不得重新做身份迁移，也不得把它们合并成聚合 `DONE`。

状态只允许 `TODO / IN_PROGRESS / BLOCKED_RUNTIME / CONDITIONAL / DONE / REJECTED`。E0～E5 是单个 Adapter/能力/场景的证据等级，不能用一个 E3 推高整个 creative toolchain。

## 1. 不可漂移的产品定位

DESIGN-LAB 是面向职业视觉设计的、AI 原生、平台中立、宿主原生的专业设计智能与生产能力层。它拥有：

- Design Brief、Reference、Direction、Design System、Design IR、Domain Pack 和 Method；
- 品牌、UI/UX、平面/出版、电商/营销、包装、动效/视频、3D/VFX 等设计域能力；
- 专业 Jury、视觉质量、反 AI 痕迹、可访问性、rights 与 production preflight；
- Host/Tool Adapter、可编辑交付、BOM、provenance、readback 与 rollback；
- 设计实践产生的受审 `KnowledgeCandidate`，但长期知识真值归 ArcheAxis。

它不拥有：

- 第二画布、通用聊天客户端、Agent runtime、模型网关、账号系统或通用知识库；
- WORK-LAB 的跨软件全局配置、权限、任务和 Observer；
- ArcheAxis 的长期知识与学习状态；
- Adobe/Figma/Penpot/Blender 等宿主的私有数据库或用户个人素材库。

Open Design 是可选外部宿主/入口，不是 DESIGN-LAB 产品身份或 SSOT。MiniGame 是游戏视觉 Domain/回归 fixture，不是项目运行时产品线。

## 2. 本轮云端仓库复审结论

### 2.1 当前 P0 硬问题

| 问题 | 当前证据 | 裁决 |
|---|---|---|
| 生产模式绕过人工节点 | `design-lab/scripts/generate_review_surface.py` 把 `production` approval 列表设为空，并输出“生产模式：无人工判断节点” | P0 fail closed；方向/质量/权利/交付关键门不得被模式绕过 |
| 当前状态过期 | `PROJECT_STATUS.json` 仍绑定 `a6fdc5e...`、2026-08-21，且与 current HEAD 不一致 | P0 修复生成器和 stale gate |
| 发布状态过期且阻塞 | `RELEASE_READINESS.json` `fresh:false`，blockers 含 human jury、E4、rights、branch protection、pro-tool E3 | 保持 BLOCKED，逐项证据关闭 |
| 重建能力无当前证据 | `RECONSTRUCTION_CAPABILITY.json` 为 `boundSha:null/current:false/NONCURRENT`，全部 lifecycle false | “pixel-perfect”名称降级；只有 evidence record 绑定后晋级 |
| 未校验模型默认启用 | LayerD/SAM2/BiRefNet/PaddleOCR/GroundingDINO checksum 全 0、`UNQUALIFIED_CHECKSUM`，却 `defaultEnabled:true` | P0 全部 fail closed/disabled，逐模型资格化 |
| 第三方指令进入活跃面 | vendored 目录含 `AGENTS.md`、`CLAUDE.md`、`.cursorrules`、安装/affiliate/外部身份规则，并被索引 | P0 从控制链、prompt、capability index、SBOM 语义中隔离 |
| 能力索引把文件当能力 | README、LICENSE、requirements、安装器/规则等可被计算为 capability | P0 只接受显式 capability manifest |
| 根规则仍不自包含 | 当前根 `AGENTS.md` 已存在，但启动规则外链 WORK；把 MiniGame 称“运行时”，且绝对禁止任何跨库知识输出 | P0 自包含并细化 KnowledgeCandidate 出口 |
| 真实软件成熟度被聚合夸大 | 多数 Adapter 仍 E0/E1；历史 ComfyUI/H3 E3 不能代表 Adobe/Figma/Penpot/Blender | 每个工具/版本/场景独立晋级 |

### 2.2 旧任务包需要纠正的地方

- 旧基线 `9468c40...` 已过期；当前基线为 `38d322a...`。
- 旧包“根 AGENTS 缺失”已被当前 main 修复；新问题是根合同外链、不自包含和边界措辞错误。
- 新合入的矢量重建 pipeline 只证明实现进入 main，不证明模型、黄金集、性能、宿主读回或商业质量。
- Open Design 上游发展极快，当前官方仓库已是大体量多宿主系统；只能锁版本走官方扩展面，不可 vendoring 或追随 `latest`。
- 本包新增行业互操作层：OpenAssetIO、OpenTimelineIO、OpenColorIO、MaterialX、OpenUSD/glTF；按设计域按需启用，不一次装全套。

## 3. 最终 Workbench 与执行架构

```text
Brief / References / Constraints / Rights
                    |
          Direction + Design IR
                    |
      Domain Pack + Method + Quality Rules
                    |
             ToolActionPlan
                    |
      Human approval (risk/phase based)
                    |
   Host Adapter -> Native editable artifact
                    |
    Readback -> Jury -> Preflight -> Delivery
                    |
 Artifact / Quality / Production / Rollback Receipts
```

Workbench 只负责：brief、方向、证据、计划、审批、状态和交付。像素/矢量/3D/时间线的最终编辑在宿主原生环境完成；DESIGN-LAB 不再造第二画布。

## 4. Evidence 等级重新冻结

| 等级 | 必须证明 | 不能冒充 |
|---|---|---|
| E0 `DECLARED` | 身份、范围、许可候选、owner | README、链接、prompt |
| E1 `STRUCTURAL` | schema/manifest/adapter 合同与静态测试 | 文件存在、mock response |
| E2 `CONTROLLED_RUNTIME` | 固定版本、合成/专用 fixture 的真实调用与读回 | 只启动进程、只截图 |
| E3 `REAL_WORKFLOW` | 真实 brief→原生可编辑产物→重开读回→失败/回滚 | 一个旧版本/另一个工具的 E3 |
| E4 `INDEPENDENT_ACCEPTANCE` | 独立人审、黄金集、质量/rights/preflight 全通过 | VLM 自评、像素相似度 |
| E5 `RELEASED/REPEATABLE` | exact-SHA release、安装/升级/恢复、连续复现 | 历史 release、手写 status |

任何 evidence record 必须绑定 repo SHA、adapter version、host version、OS、fixture hash、artifact hash、命令/动作、审批、readback 和 rollback。

## 5. 开源项目与行业标准裁决

以下裁决来自 2026-08-25 对官方上游的复核。代码并入仍需锁不可变 commit/tag、SPDX、模型权重许可与 SBOM。

### 5.1 宿主与 Adapter 基座

| 上游 | 许可/状态 | 最终裁决 | 吸收范围 | 禁止范围 |
|---|---|---|---|---|
| [Open Design](https://github.com/nexu-io/open-design) | Apache-2.0；高速演进、Windows/CLI/MCP/插件丰富 | `EXTERNAL_HOST_ADAPTER` | 官方 CLI/API/MCP、DESIGN.md/插件/skill/design-system 映射、宿主 UX 方法 | 不整仓并入、不成为产品 SSOT、不读取其私有 DB |
| [Penpot](https://github.com/penpot/penpot) + official MCP | MPL-2.0；成熟协作设计；MCP 可读写 | `EDITABLE_UI_BAKEOFF` | 官方 Plugin API/MCP、tokens/components/结构读写 | MCP 可执行代码必须沙箱/权限门；不把 Penpot 变数据库 |
| [OpenPencil](https://github.com/open-pencil/open-pencil) | MIT；active development、有 rough edges | `EDITABLE_UI_BAKEOFF` | 本地 `.fig/.pen`、headless Vue SDK、结构化编辑能力 | 不因 MIT 就默认主宿主，不 vendoring 编辑器 |
| [CLI-Anything](https://github.com/HKUDS/CLI-Anything) | Apache-2.0；18 demos/测试方法完整，Windows 依赖 Git Bash/WSL | `ABSORB_HARNESS_METHOD` | 七阶段 harness、capability/test/readback/rollback 方法；首批 2 个工具 | 不自动生成后直接宣称 E3，不允许任意 shell 写用户目录 |

### 5.2 媒体/3D 行业互操作

| 上游/标准 | 许可/状态 | 最终裁决 | DESIGN-LAB 用途 |
|---|---|---|---|
| [OpenAssetIO](https://github.com/OpenAssetIO/OpenAssetIO) | Apache-2.0；ASWF；Windows 支持 | `ABSORB_SPEC + OPTIONAL_LIBRARY` | 用稳定 entity reference 取代硬编码路径；发布、解析、版本与关系的 host/manager 桥，不当数据库 |
| [OpenTimelineIO](https://github.com/AcademySoftwareFoundation/OpenTimelineIO) | BSD-3-Clause；ASWF；adapter 已从 core 分离 | `OPTIONAL_DOMAIN_DEP` | 动效/视频 Design IR 的时间线交换；adapter 独立锁版本 |
| [OpenColorIO](https://github.com/AcademySoftwareFoundation/OpenColorIO) | BSD-3-Clause；成熟影视色彩管理 | `OPTIONAL_DOMAIN_DEP` | 色彩空间、LUT、ACES 与 preflight；不信任外部 config/LUT |
| [MaterialX](https://github.com/AcademySoftwareFoundation/MaterialX) | Apache-2.0；ASWF | `OPTIONAL_DOMAIN_DEP` | 3D 材质/外观交换；最低修复版 `>=1.39.3`，限制递归 import |
| [OpenUSD](https://github.com/PixarAnimationStudios/OpenUSD) | Apache-2.0 | `REFERENCE + CONDITIONAL_ADAPTER` | 复杂 3D scene/hierarchy/variants；有真实 Blender/USD 场景才启用 |
| [glTF](https://github.com/KhronosGroup/glTF) | 开放规范 | `DELIVERY_PROFILE` | 轻量 3D 交付/预览；保留源 scene 与材质/纹理 provenance |

### 5.3 重建与视觉模型

| 组件 | 当前裁决 | 资格化要求 |
|---|---|---|
| VTracer | `KEEP_ACTIVE_E2_CANDIDATE` | 已有非零二进制 hash；仍需固定 fixture、prerelease 风险、结构/人工质量读回 |
| SAM 2 | `DISABLE_UNTIL_QUALIFIED` | Apache-2.0；锁代码与 checkpoint，验证 hash、Windows/WSL、显存、分割黄金集 |
| BiRefNet | `DISABLE_UNTIL_QUALIFIED` | MIT；锁具体 checkpoint 及其 model card/训练数据声明，前景/抠图黄金集 |
| PaddleOCR | `DISABLE_UNTIL_QUALIFIED` | Apache-2.0；代码与具体模型权重分开记录；中英字体/布局/旋转/小字集 |
| GroundingDINO | `DISABLE_UNTIL_QUALIFIED` | Apache-2.0；锁代码、text backbone 与 checkpoint；开放词汇框评测 |
| LayerD | `QUARANTINE_IDENTITY/WEIGHTS` | 当前 source/版本/权重身份与 checksum 未闭合；不得默认启用 |
| StarVector | `CONDITIONAL_SANDBOX` | Apache-2.0；当前示例使用 `trust_remote_code=True`，须离线 sandbox、代码审计、8GB 实测与 SVG 安全清洗 |
| OmniParser | `QUARANTINE_LICENSE_CONFLICT` | 当前 mixed license/AGPL 权重、商业使用 denied；不得进入商业 runtime |

零 checksum、`UNQUALIFIED_*`、许可冲突、模型不存在或硬件不足时，runtime resolver 必须 fail closed；不能 fallback 到“看起来类似”的模型后仍报告成功。

## 6. 关键合同

### 6.1 `DesignIR/v2`

至少覆盖：canvas/frame、layer/group、text/font、vector/path、raster/link、component/instance、constraint/layout、token/style、asset reference、color space、timeline、3D scene/material reference、interaction、rights 与 provenance。Design IR 是宿主中立交换层，不是新画布存储格式。

### 6.2 `AssetReference/v1`

吸收 OpenAssetIO 思路：使用稳定 entity reference、trait、version intent、resolved location 与 publish relationship。物理路径只在 runtime resolution 出现，不写入 portable Design IR；WORK 只管理外部路径 profile，不拥有设计资产。

### 6.3 `HumanGate/v2`

人工门按风险和生命周期，而非 UI mode 决定：

- Direction gate：目标、受众、品牌/参考、rights；
- Quality gate：视觉判断、可访问性、反 AI 痕迹、专业 Jury；
- Rights gate：字体、图片、模型、商标、第三方素材与生成权利；
- Production gate：可编辑性、preflight、BOM、交付范围；
- Release gate：最终验收、签名、版本与回滚。

`production` 可以减少低风险交互，不能把所有 gate 设为空。自动通过必须由预先批准的 policy 和低风险证据决定，并保留 receipt。

### 6.4 `KnowledgeCandidate/v1`

只允许经 rights 检查和人工批准的 Method/Jury correction/Production lesson 输出到 ArcheAxis；包含 source/artifact/evidence hash、DESIGN exact SHA、license/rights、candidate type、supersedes 和撤销入口。原始商业资产、客户 brief 和未授权素材默认不外溢。

## 7. 最终任务 DAG

### DLR-000 — 安装本包并重建 Current State

- 优先级/状态：`P0 / TODO`
- 动作：执行时读取 remote/local SHA、branch、dirty、CI、Release、宿主/模型版本；把本包设为唯一 current 前向包；修复 `generate_project_status.py` 和所有 current projections。
- 生成字段：source SHA、origin SHA、dirty digest、generator version/hash、generated/expiry、evidence floor、subject artifacts。
- 验收：clean 同树重跑字节稳定；HEAD 变化或 report subject 不同使 gate 失败；README/ROADMAP 不复制动态计数。

### DLR-010 — 根合同自包含、MiniGame 与知识出口纠偏

- 优先级/状态：`P0 / TODO`
- 依赖：DLR-000。
- 动作：根规则内含启动必需定位/owner/SSOT/E0-E5/dirty/权限/路径/提交边界；外链 WORK 仅作可选联邦参考。
- 修正：MiniGame 为 `game-visual domain fixture`；原始设计资产默认不外溢，但受审 KnowledgeCandidate 可提交 ArcheAxis。
- 验收：单独克隆 DESIGN 不读取 WORK 也能正确执行；旧名/旧产品身份只在 history，活动 verifier 不误报。

### DLR-020 — 第三方指令与能力索引 P0 隔离

- 优先级/状态：`P0 / TODO`
- 依赖：DLR-010。
- 动作：第三方 `AGENTS/CLAUDE/cursorrules/SKILL/install/affiliate` 作为 inert source blobs 保存；不进入根指令、prompt、tool discovery 或能力计数。
- Capability index 只接受显式 `capability.manifest.*`，且必须有 owner、consumer、schema、tests、source、license、hash、evidence level。
- 验收：恶意 fixture 不能改变执行身份/命令/提交/网络；README/LICENSE/requirements 不计能力；quarantine 内容无法自动激活。

### DLR-030 — Human Gate fail closed

- 优先级/状态：`P0 / TODO`
- 依赖：DLR-010。
- 动作：删除 production 空 approval；将 Direction/Quality/Rights/Production/Release gate 编译为状态机与 policy；UI 只呈现状态，不定义真值。
- 必测：guided/copilot/director/method/production、低/中/高风险、缺 rights、jury reject、过期 approval、重复 approval、撤销。
- 验收：商业 production 无法绕过必需 gate；API/CLI/宿主直接调用也无法绕过；拒绝与撤销有回滚/责任人。

### DLR-040 — 开源 Active 面、许可与能力库减法

- 优先级/状态：`P0 / TODO`
- 依赖：DLR-020。
- 范围：162 quarantine、vendored source roots、active 6 sources、历史 skill/方法、2424 级索引与 adapter registry。
- 状态：`ACTIVE_CODE / ACTIVE_METHOD / ADAPTER / REFERENCE / QUARANTINE / REMOVE_ACTIVE`。
- 立即退出 active：affiliate、非设计电商运营、AI Product OS、第三方控制/安装指令、无 consumer/license/hash/test 的 prompt 堆积。
- 验收：source tree hash 重算；NOTICE/SBOM/rights 完整；accepted evidence 不因删除或计数变化虚增；物理删除另开批次并带恢复清单。

### DLR-050 — 模型注册与重建真值 P0

- 优先级/状态：`P0 / TODO`
- 依赖：DLR-000、DLR-020。
- 动作：所有 `UNQUALIFIED_*` 自动 `defaultEnabled:false`；zero hash 使 verifier 失败；代码、权重、config、tokenizer/backbone、模型许可分别登记。
- 重建阶段：ingest→analysis→layer/text/vector candidates→editable assembly→host readback→jury/preflight；每阶段可中断、可替换、可回退。
- 命名：在 `RECONSTRUCTION_CAPABILITY` 绑定 exact evidence 前，对外仅称 `vector reconstruction candidate pipeline`，不得称 pixel-perfect。
- 验收：黄金集包含 UI screenshot、logo/icon、海报/排版、复杂照片/透明边缘、低分辨率/压缩噪声；结构可编辑性、OCR、视觉差异、延迟/VRAM、失败率与人工评价齐全。

### DLR-060 — Design IR v2 与行业互操作基础

- 优先级/状态：`P1 / TODO`
- 依赖：DLR-030。
- 动作：演进 Design IR；实现 AssetReference/OpenAssetIO mapping，物理路径 runtime resolve；保留未知宿主字段和 provenance。
- 兼容：为 OpenTimelineIO、OpenColorIO、MaterialX、USD/glTF 定义 optional domain extensions，不把全部库设为核心依赖。
- 验收：未知字段 round-trip；跨 Windows 路径恢复；asset version/publish/relationship 可读回；Design IR 不丢 font/color/timeline/material rights。

### DLR-070 — Open Design 当前版本 E3 重验

- 优先级/状态：`P0 / BLOCKED_RUNTIME`
- 依赖：DLR-010、DLR-030、DLR-040。
- 流程：锁安装版/tag/commit→doctor→只读能力枚举→plan→批准注册→真实 brief→artifact/editable source→provenance/readback→失败/恢复→卸载/rollback。
- 只用官方 CLI/API/MCP/plugin；动态端口、namespace、私有 DB 不写进核心。
- 验收：runtime ID、artifact hash、版本、失败、回滚和 host readback 齐全；上游升级必须重新兼容测试，旧 E3 不自动继承。

### DLR-080 — OpenPencil/Penpot 可编辑宿主单选

- 优先级/状态：`P1 / CONDITIONAL`
- 依赖：DLR-060、DLR-070。
- 同一三个 brief 比较：结构读写、components/tokens、constraints/auto-layout、`.fig/.pen/SVG/PDF/HTML-CSS`、离线、Windows、MCP/SDK 权限、备份、性能、许可与退出。
- 安全：Penpot MCP 的代码执行置于专用文件/最小权限/timeout；OpenPencil 的 active-development rough edges 进入风险矩阵。
- 裁决仅选一个 `PRIMARY_EDITABLE_UI_ADAPTER`，另一个 reference/fallback；不 vendoring 两套编辑器。
- 验收：源文件重开可编辑，文字/层级/组件/约束可读回；截图相似不等于通过。

### DLR-090 — CLI-Anything 方法吸收与两工具真实闭环

- 优先级/状态：`P1 / TODO`
- 依赖：DLR-020、DLR-030、DLR-060。
- 吸收：七阶段 source analysis→command design→implementation→tests→docs→refine→evaluation 的方法和 harness contract，不复制全部生成仓库。
- 首批只选两个高价值工具：优先 Blender + Krita/Inkscape；选择由当前安装与真实 brief 决定。
- 验收：Brief→Design IR→ToolActionPlan→approval→execution→native editable artifact→close/reopen readback→quality/preflight→rollback；任意 shell、用户目录和未批准写入被拒。

### DLR-100 — 五黄金案例与人工 Jury 产品门

- 优先级/状态：`P0 / TODO`
- 依赖：DLR-030、DLR-070；若 DLR-070 blocker，则用已可用正式宿主，不降低门槛。
- 案例：品牌系统、UI/UX、电商/营销、平面/出版或包装、动效/3D 至少五类；每类有 brief、参考、rights、editable deliverable、reject 样本。
- Jury：盲评 A/B、评分 rubric、分歧、复审和明确 REJECT；12 Evidence Cards 由真人校准，VLM 只作辅助。
- 指标：迭代、延迟、token、成本、编辑时间、通过率、结构可编辑性、preflight defects 和 Pareto。
- 验收：至少一个真实失败触发 gate 并修复；黄金集冻结为 regression assets；authoritative accepts 只能由人审收据增加。

### DLR-110 — 专业生产工具与可编辑交付

- 优先级/状态：`P1 / BLOCKED_RUNTIME/CONDITIONAL`
- Adobe：仅用户安装新版本后重验。Photoshop 要求图层组、可编辑文字、蒙版、调整层、链接对象、关闭重开；Illustrator 要求未保存文档安全与 `.ai`/PDF/SVG 读回。
- Figma/Penpot：官方 API/MCP/plugin，使用专用测试文件；不写私人空间。
- Eagle：专用测试资料库和官方 API/MCP；不触碰个人库。
- Blender/FFmpeg/Inkscape：scene/timeline/vector source、颜色、字体、出血、分辨率、codec/preflight 与 readback。
- 验收：每个 host/version/scenario 独立 E0-E3；无安装/账号/安全测试库则保持 blocker；旧版本证据不继承。

### DLR-120 — 色彩、时间线、3D/材质 Domain Packs

- 优先级/状态：`P1 / CONDITIONAL`
- 依赖：DLR-060、DLR-100。
- Color：OpenColorIO/ACES config、输入/工作/输出色彩空间、LUT provenance、显示与交付 preflight。
- Timeline：OpenTimelineIO core 与明确 adapters；source media、clip/effect/transition/timebase、导出/回读。
- 3D：MaterialX `>=1.39.3`、USD 或 glTF；scene/material/texture/color space/rights 与 Blender readback。
- 启用规则：只有对应黄金案例证明缺口才安装依赖；每个 Domain Pack 独立 optional extra。
- 验收：不可信 config/MTLX/媒体/scene 有沙箱、大小/深度/路径限制；递归 import DoS fixture；交换后语义与视觉均人工复核。

### DLR-130 — 生成式图像 runtime 单选

- 优先级/状态：`P2 / CONDITIONAL`
- 依赖：DLR-100 证明局部编辑/生成存在真实缺口。
- 候选：Krita AI Diffusion 或 InvokeAI；比较蒙版/局部编辑/ControlNet、batch、参数可重复、VRAM、Windows、license、offline、API、provenance 与 editable handoff。
- 外置：模型权重、安装器、缓存和用户素材不进入仓库；ComfyUI/H3 保持冻结，除非 Owner 另行解冻。
- 验收：只选一个 runtime；失败/卸载后 DESIGN 基线仍独立工作。

### DLR-140 — ArcheAxis `KnowledgeCandidate` 双向接口

- 优先级/状态：`P1 / TODO`
- 依赖：DLR-030、DLR-100；ArcheAxis 接收门。
- 读取：只通过版本化查询消费 verified design knowledge，不直连 ArcheAxis DB。
- 写回：Method/Jury correction/Production failure 先进入 DESIGN staging，经 rights 和人审后提交 candidate；ArcheAxis 不可用时 DESIGN 独立运行。
- 验收：幂等、拒绝、争议、撤销、supersede 和离线队列可读回；原始客户资产不外溢。

### DLR-150 — E4/E5、独立复审与发布收敛

- 优先级/状态：`P2 / TODO`
- 依赖：本期批准的 DLR-010～140。
- 门禁：canonical/Python/MiniGame fixture、host/tool E3、人工 Jury、rights、production preflight、SBOM/NOTICE、Windows 安装/恢复、exact-SHA CI。
- 发布包：editable sources、preview、BOM、rights、quality、preflight、provenance、rollback；不能只给 PNG/视频。
- 验收：独立复审后才提升 E4/E5；capability projection 与 evidence record/exact SHA 同时更新；其余保持 E0/E1/BLOCKED。

## 8. 执行波次

| 波次 | 任务 | 放行条件 |
|---|---|---|
| Truth/Safety | DLR-000、010、020、030、050 | current 状态真实；指令隔离；人工门与模型 fail closed |
| Subtraction | DLR-040 | Active 面与许可收敛，不再以数量衡量 |
| Core IR | DLR-060 | 路径/资产/未知字段/行业扩展合同冻结 |
| Real Host | DLR-070、080（单选）、090 | 至少一个宿主和两个工具有真实可编辑读回 |
| Quality | DLR-100、110 | 五黄金案例、Jury、专业工具/诚实 blocker |
| Domain | DLR-120、130（按需） | 只为真实缺口启用依赖 |
| Federation/Release | DLR-140、150 | 知识候选和 E4/E5 可验证 |

三项目整体顺序是：WORK-LAB 先短期治理冻结，ArcheAxis 作为主线闭合知识/学习真值，然后 DESIGN-LAB 完成第一条商业黄金闭环。DESIGN 的 P0 安全/真值任务可先执行，但不得与另外两仓同时全面重写。

## 9. 强制证据包

每个 Adapter/模型/黄金案例至少交付：

1. exact repo SHA、host/tool/model version 与不可变 upstream revision；
2. fixture/source/brief/rights hash；
3. plan、approval、actions、exit/status、timeout；
4. native editable artifact 与 close/reopen readback hash；
5. preview、结构 diff、视觉/人工 Jury、quality/preflight；
6. failure、cancel、retry、rollback 和恢复后 hash；
7. SPDX、model/weight/data license、NOTICE、SBOM；
8. OS/GPU/VRAM/latency/cost；
9. E0-E5 证据层和有效期；
10. KnowledgeCandidate/外部资产的数据边界。

## 10. 最终完成定义

DESIGN-LAB 本轮只有在以下条件同时成立后才可称为第一条商业闭环完成：

- current reports 全部绑定 exact SHA 且 stale 自动失败；
- 根规则单仓自包含，MiniGame 和知识出口边界正确；
- 第三方指令、affiliate、README/LICENSE/installer 不进入控制链或能力计数；
- production 无法绕过 Direction/Quality/Rights/Production/Release 人工门；
- unqualified/zero-hash/许可冲突模型默认禁用；
- 至少一个正式宿主和两个专业工具完成原生可编辑 close/reopen/readback/rollback；
- 五黄金案例有真人 Jury、真实 REJECT、修复与回归资产；
- 输出含 editable sources、BOM、rights、quality、preflight、provenance 和 rollback；
- OpenAssetIO/OTIO/OCIO/MaterialX 等只在真实 Domain Pack 按需启用；
- 各软件/版本/场景独立 E0-E5，公开声明不超过最弱证据；
- 经人审和 rights 检查的知识候选可提交 ArcheAxis，原始商业资产不外溢。

## 11. 明确禁止

- 禁止把 DESIGN-LAB 改成 Open Design 分支、第二画布、通用 Agent/聊天/知识 OS。
- 禁止把 `production` 理解为“无人审”。
- 禁止把 2424/648/497 等数量、VLM 自评、像素相似度或 schema pass 当商业质量。
- 禁止让零 checksum、未审权重、mixed/AGPL 商业冲突模型进入默认 runtime。
- 禁止 Agent 任意 shell、写用户个人 Eagle/Figma/Penpot/Adobe 空间或私有目录。
- 禁止把旧 Adobe/ComfyUI/H3 E3 继承给新版本或整个工具链。
- 禁止在没有提炼物、反向依赖、恢复 commit 和 Owner 批准时物理删除 vendored 历史。
- 禁止把原始客户 brief、资产、字体、凭据或模型权重提交 Git。

## 12. 官方调研来源

- [Open Design](https://github.com/nexu-io/open-design)
- [Penpot](https://github.com/penpot/penpot) 与 [官方 MCP](https://github.com/penpot/penpot/tree/develop/mcp)
- [OpenPencil](https://github.com/open-pencil/open-pencil)
- [CLI-Anything](https://github.com/HKUDS/CLI-Anything)
- [OpenAssetIO](https://github.com/OpenAssetIO/OpenAssetIO)
- [OpenTimelineIO](https://github.com/AcademySoftwareFoundation/OpenTimelineIO)
- [OpenColorIO](https://github.com/AcademySoftwareFoundation/OpenColorIO)
- [MaterialX](https://github.com/AcademySoftwareFoundation/MaterialX)
- [OpenUSD](https://github.com/PixarAnimationStudios/OpenUSD)
- [glTF](https://github.com/KhronosGroup/glTF)
- [SAM 2](https://github.com/facebookresearch/sam2)
- [BiRefNet](https://github.com/ZhengPeng7/BiRefNet)
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- [GroundingDINO](https://github.com/IDEA-Research/GroundingDINO)
- [StarVector](https://github.com/joanrod/star-vector)

研究时间点为 2026-08-25；执行时必须锁不可变 commit/tag、逐项复核权重与数据许可，且不得以 `latest` 作为供应链证据。
