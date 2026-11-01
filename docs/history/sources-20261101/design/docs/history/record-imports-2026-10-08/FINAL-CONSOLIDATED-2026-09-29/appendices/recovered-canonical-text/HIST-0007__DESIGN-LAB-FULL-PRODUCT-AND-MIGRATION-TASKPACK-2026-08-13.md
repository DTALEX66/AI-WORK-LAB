# DESIGN-LAB 最终全量产品、架构与迁移任务包

**版本：** R3（外置资料库与本地迁移落实版）  
**日期：** 2026-08-13  
**远端事实基线：** `DTALEX66/DESIGN-LAB` / `main` / `f8664ee24ea7d373d6a1a0056387fef47d3f99ab`  
**仓库身份：** 已从 `OPEN-DESIGN-Assistance` 直接重命名为 `DESIGN-LAB`  
**本地身份：** 用户确认已改为 `D:\All projects\DESIGN-LAB`；本审计环境不可读取该 Windows 路径  
**外置原始资料库：** `D:\All projects\Design assets`（用户已建立；不进入 Git）  
**实施策略：** audit → branch → small controlled changes → local evidence → explicit review → optional publish

> 本任务包中的 `D:\All projects\Design assets` 是用户控制的外置原始资料库。
> 本审计环境未读取该路径，也没有复制、上传、索引其原始内容；所有涉及它的工作
> 必须在用户本机按本任务包的只读、显式子目录选择和权利治理规则执行。

---

## A. 最终结论：项目到底是什么

### A1. 唯一身份

```text
英文正式名：DESIGN-LAB
中文正式名：设计实验室
技术 ID：design-lab
云端：DTALEX66/DESIGN-LAB
本地：D:\All projects\DESIGN-LAB
```

`OPEN-DESIGN-Assistance`、`Open Design Assistance`、`opendesign-assistance`、`Design Intelligence Layer`、`Design Intelligence Capability Kit` 全部退出活动产品命名。它们只允许出现在：

1. `project-memory/history/` 和 `reports/history/` 的不可篡改历史；
2. 明确标注的第三方 Host Adapter（如 Open Design）；
3. 外部来源、兼容性或 Git 历史引用。

### A2. 最终产品定义

> **DESIGN-LAB（设计实验室）是一个面向职业视觉设计的、AI 原生、平台中立的设计智能与生产能力实验室。它把设计研究、合规知识、设计方法、领域能力、视觉质量、专业工具适配、生产预检、可编辑交付和证据体系，组织为可组合、可执行、可验证、可回滚的设计能力闭环。**

**视觉设计是第一主线**，不是一个附加 Domain Pack。优先范围：

```text
品牌视觉 / 平面与编辑 / UI·UX / 电商视觉 / 包装
空间与展陈 / 3D / 动效 / 视频视觉 / 游戏视觉与交互界面
```

研究资料、开源资产、模型、Agent、Host 和工具均是能力来源或执行对象；它们不是产品身份。

### A3. 不是二选一：资料库还是前后端产品？

DESIGN-LAB 既不是静态资料库，也不应变成第二个通用设计软件前端。它是一个**产品化的设计能力系统**：

```text
研究/开源资料                    = 受治理的知识与证据底座
可测试的 Method / Rubric / Pack   = 可复用专业能力
Host / Agent / Tool Adapters      = 在现有工作界面中执行能力
Preflight / Handoff / Evidence    = 商业生产闭环
```

当前采用 **host-native first**：设计师在已接入的宿主（当前为 Open Design 参考入口，未来可为 Adobe/Figma/Blender/ComfyUI 等）中工作；DESIGN-LAB 提供合同、方法、质量门、可编辑交付和适配器。不得为此重建第二画布、聊天客户端、模型网关或通用 SaaS 后端。

若未来需要可视化，只允许建设轻量的 **Lab Review Surface**：展示 Brief、方向、质量评分、预检、证据、适配器可用性和交付状态。它不是设计编辑器，不托管用户帐号/模型/画布，不与宿主竞争。

---

## B. 高标准审计：当前真实缺陷

| 优先级 | 已审计事实 | 风险 | 必须修复 |
| --- | --- | --- | --- |
| P0 | 云端仓库已改名，但 `README.md`、`opendesign-assistance/`、Manifest、Schema、脚本和活动 SSOT 仍使用旧身份 | 外部名与机器/文档语义断裂；后续贡献继续漂移 | 全量内部身份迁移，不可只改 GitHub 名 |
| P0 | `primaryRuntime`、`fiveNeutralities`、`rightsNeutral`、Open Design-first verifier 仍是活动契约 | “平台中立”与“Open Design 中心”相互矛盾 | 改为 Neutrality Policy + Rights Governed；宿主选择移至本地/项目 profile |
| P0 | MiniGame 顶部边界已改为游戏 UI/视觉 fixture，但约 22 个文件仍有合集平台、IAA、广告位、发行或内容包语义；manifest 仍为 `platformRole: launch-game` | 冻结设计 fixture 被测试和文档重新推成活动游戏产品 | 建立游戏视觉 fixture 合同与反漂移测试，清除活动产品语义 |
| P1 | 旧 V4/V42/FINAL 文件仍被当成活动 SSOT；现有 E3 证据绑定旧路径/树 | 名称迁移后会错误复用旧验证结论 | 历史化旧证据并为新树重新取证 |
| P1 | 当前总验证器可在快照下给出 `467/467`，但本审计环境的 Python 测试缺少 `jsonschema`，5 项环境错误；main exact-SHA CI 无可读证据 | 不可宣称新树或 main 已经完整验证 | 建立完整 venv、exact-SHA CI 和新 evidence index |
| P1 | `design-system/` 仍混有 Open Design-first 主入口语义；现有旧插件/`open-design.json` 兼容描述符没有明确隔离 | 删除会破坏上游兼容，保留又污染内核 | Canonical core 与 host projection 分层，精确 allowlist |
| P1 | 资料和开源内容目前偏目录聚合，缺 Source/License/Derivation/Benchmark 的统一对象链 | 版权、版本、AI 参考物和可用性失控 | 建立受治理知识资产流水线 |
| P2 | H3 与 ComfyUI 尚无项目合同、依赖清单、权限边界和实际证据 | 容易被误宣为已可用集成 | 分别建立 E0/E1 adapter；禁止暗中下载、联网或执行 |
| P2 | 视觉质量、生产预检、工具适配已经有资产但仍以旧产品语言组织 | 能力难被新用户理解和调用 | 围绕视觉工作闭环重编目录和入口 |

**审计计数（此基线）：** `opendesign-assistance/` 约 426 个文件；旧身份/旧运行时关键词命中约 183 个文件；`minigame-runtime/` 约 315 个文件。计数用作迁移进度，不作为独立功能数量。

### B1. 本地迁移分支落实状态（不等于已发布）

| 工作项 | 本地状态 | 证据与边界 |
| --- | --- | --- |
| `DL-MIG-010` 身份目录 | 已落实 | `opendesign-assistance/` 已迁为 `design-lab/`；历史文件迁入 `project-memory/history/pre-design-lab/`。 |
| `DL-POS-001` / `DL-ARC-001` | 已落实 | 当前 SSOT、Manifest 和 Schema 使用 `DESIGN-LAB/design-lab`；不设默认 Host/Agent/Model。 |
| `DL-GV-001..003` | 已落实 | `minigame-runtime` 改为游戏视觉 fixture；广告/变现/发布逻辑清除，边界测试已加入。 |
| `DL-KNW-000` | 已落实 | `Design assets` 被明确列为外置原件真源；`.gitignore` 忽略本地知识缓存；禁止子模块、软链接和复制原件。 |
| `DL-KNW-001` 基础工具 | 已落实至 E1 | `ingest_design_materials.py` 仅对用户明确选择的外置子目录只读登记，输出 SourceRecord 和候选卡，不复制原件。实际资料尚未读取。 |
| `DL-ADP-001` | 已落实至 E0 | Adobe、ComfyUI、MiniMax H3 仅有受治理 Adapter 合同；没有安装、凭据、API 调用或 E3 运行声明。 |
| `DL-CI-001..003` | 已落实于本地 | 单一 `DESIGN-LAB Verify` 工作流替换旧路径工作流，含身份、原始资产、fixture 与测试门。 |

本表仅描述未提交本地分支；不构成远端 `main`、发布、真实工具集成或商业可用声明。

---

## C. 用户、工作流与可用闭环

### C1. 五类用户，不做五套产品

| 用户 | 进入方式 | DESIGN-LAB 提供的关键价值 | 人必须决定的节点 |
| --- | --- | --- | --- |
| 职业设计师 | 在宿主项目中选择 Domain Pack | 专业方法、质量检查、可编辑交付 | 方向、版式、风格与交付放行 |
| 创意总监/大师 | 建立 Brief、评审方向与方法卡 | 设计判断显性化、匿名方法研究、Jury | 审美标准和最终认可 |
| 品牌/电商/空间从业者 | 选择行业场景与生产规格 | 商业目标、视觉系统、预检 | 商业约束、预算、物料与生产决策 |
| 新手 | Guided Brief + 基础 Rubric | 从灵感到规范化方向的渐进引导 | 参考物授权、方向选择、学习确认 |
| Agent/开发者 | 调用 Schema/Adapter Contract | 受控执行、读回、证据与回滚 | 范围、授权和异常处理 |

### C2. 统一视觉设计闭环

```text
01 Brief & Business Intent
   → 02 Rights / Source / Reference intake
   → 03 Research + Reference DNA + Design Method
   → 04 2–3 genuinely different Directions
   → 05 Human locks direction
   → 06 Design System / Tokens / Layout / Asset contracts
   → 07 Host or Tool Adapter executes editable work
   → 08 Visual Quality Jury + deterministic checks
   → 09 Production Preflight
   → 10 Editable Handoff + BOM + Provenance + rollback
   → 11 Evidence / benchmark / human review feedback
```

任何自动化都不得跳过步骤 02、05、08、09、10 的授权/人工判断。没有获批参考物、没有质量读回、没有预检或没有交付证据的输出，最多称为草案，不得称为可生产设计。

---

## D. 六大能力域与对象模型

### D1. 能力域

```text
01 Design Intelligence
   Brief理解、商业目标、Reference DNA、方向生成、设计系统、Critique/Refinement
02 Professional Visual Domains
   Brand、Graphic、UIUX、E-commerce、Editorial、Packaging、Spatial、Exhibition、3D、Motion、Video、Game Visual
03 Visual Quality
   去 AI 味、构图、版式、比例、层级、材质、光影、颜色、可读性、商业感、一致性
04 Creative Toolchain
   Host / Agent / Adobe / Figma / Blender / ComfyUI / FFmpeg / Media Model adapters
05 Production & Handoff
   规格、字体、色彩、分辨率、出血、格式、源文件、BOM、包、版本、回滚
06 Research & Evidence
   Sources、licenses、methods、benchmarks、evals、E0–E5、human jury、production validation
```

### D2. 核心对象（唯一可交换语言）

```text
Brief                    商业目标、受众、渠道、约束、验收标准
ReferenceSet             来源、权利、用途、hash、提取特征
ResearchFinding          可引用研究结论，不能直接冒充设计规则
MethodCard               可复用设计方法；禁止以在世创作者名义模仿
Direction                互相区分的视觉方向及其理由
DesignSystem             tokens、type、grid、components、asset contracts
DomainPack               专业领域的流程、模板、Rubric、Preflight
Artifact                 可编辑源文件/导出文件/派生产物
ToolRun                  可审计的 Adapter 执行记录、版本、参数、输出
QualityAssessment        Rubric 评分、缺陷、人工结论、精修建议
PreflightReport          可生产检查结果和阻断项
HandoffPackage           源文件、BOM、许可、版本、回滚、交付清单
EvidenceRecord           E0–E5、bound tree SHA、责任人、时间、读回
```

所有 adapter 的输入输出必须能映射到这些对象；不得以 Prompt 文本、私有聊天记录或不带版本的截图充当唯一事实。

---

## E. 资料、开源资源和版权治理

### E0. 外置设计资料库是原始资产真源

```text
D:\All projects\Design assets
  = 原始设计资料、图片、视频、音频、字体、PSD/AI/INDD/BLEND、参考项目、采购素材等的本地真源

D:\All projects\DESIGN-LAB
  = 可复用设计能力、来源索引、结构化提取、方法卡、质量规则、转换脚本、Schema 与证据
```

`Design assets` 不作为 Git 子模块、软链接、复制目录、默认扫描根或运行时依赖提交。DESIGN-LAB 不读取/写入其中的凭据、私有客户资料或未获授权内容。转换只能在用户明确选择的子目录上本地执行，默认只读。

| 留在 `Design assets` | 进入 DESIGN-LAB Git |
| --- | --- |
| 原始图片/视频/音频、PSD/AI/INDD/BLEND、字体、模型权重、大体积 PDF、客户源文件 | SourceRecord、内容 hash、许可证/权利状态、受限摘要、结构化 KnowledgeCard、MethodCard、Token、Rubric、BenchmarkCase、转换脚本与统计索引 |
| 原始文件本体和本地转换缓存 | 不复制原始大文件，不保存绝对本地路径，不保存密钥/账号/客户隐私 |

新增任务 `DL-KNW-000 External Asset Library Registration`：建立**不含原始文件**的本地路径别名和忽略规则；`DL-KNW-001` 必须从 `Design assets` 的经批准资料生成 SourceRecord/KnowledgeCard，而不是把目录整体加入仓库。

### E1. 资料不是“下载后放进仓库”

新增中立知识资产层：

```text
design-lab/knowledge/
├─ sources/              # SourceRecord：来源、抓取日期、许可证、允许用途、hash
├─ curated/              # 已人工筛选、可在许可内使用的内容
├─ derived/              # 从来源抽取的结构化特征；必须回链来源
├─ methods/              # MethodCard，不保存受限制原作的可替代复刻物
├─ standards/            # 公开标准、内部适配注解、版本
└─ registries/           # source / license / font / model / asset indexes

design-lab/research/
├─ style-lineages/
├─ visual-benchmarks/
├─ domain-studies/
└─ experiment-records/
```

每份进入项目的开源/公开资料最少有 `SourceRecord`：来源或外置资料库别名、原始作者、许可证或权利状态、适用用途、取得日期、版本或内容 hash、是否可再分发、是否可作模型输入、是否可商用、人工审核人。未知权利默认 `reference-only`，不得进入可发布资产或训练/微调流程。

### E2. 大师质感与风格边界

允许研究构图、字重关系、节奏、留白、材料、色彩策略、灯光、叙事和版式方法；输出为可归因的 `MethodCard`/`Style DNA`。不以具体在世创作者名字作为仿制目标，不收集或发布侵犯版权/肖像/商标的复制资产。

### E3. 知识进入产品的门

```text
candidate source
 → Rights review
 → SourceRecord
 → local bounded extraction from an explicitly selected `Design assets` subdirectory
 → AI candidate card (outside Git cache)
 → human curation
 → MethodCard or BenchmarkCase
 → domain rubric / test fixture
 → evidence-bound capability
```

转换规则：先以 SHA-256 去重；文本按有意义的段落/页面分块；图像/视频只保存经人工审核的描述、视觉特征和权利信息；设计源文件只提取允许的结构/元数据；原始文件和完整 OCR/转码缓存留在外置资料库或其忽略缓存。研究资料不因“开源”“网上可见”自动获得生产可用资格。

---

## F. 技术架构与目录（目标树）

```text
DESIGN-LAB/
├─ design-lab/
│  ├─ core/                    # objects, contracts, policy
│  ├─ intelligence/            # intake, direction, system, critique
│  ├─ atoms/                   # small testable capabilities
│  ├─ bundles/                 # public composites
│  ├─ scenarios/               # end-to-end visual design cases
│  ├─ domain-packs/            # professional domains
│  ├─ quality/                 # rubrics, juries, visual regression
│  ├─ production/              # preflight, handoff, provenance, rollback
│  ├─ knowledge/               # governed sources and methods
│  ├─ research/                # benchmarks and experiments
│  ├─ evals/                   # test fixtures and evidence indexes
│  ├─ schemas/                 # neutral JSON schemas
│  ├─ config/                  # checked-in neutral registries
│  ├─ scripts/                 # deterministic generators/verifiers
│  ├─ templates/
│  ├─ assets/
│  └─ adapters/
│     ├─ agents/{hermes,codex}/
│     ├─ hosts/open-design/
│     └─ creative-tools/
│        ├─ adobe/
│        ├─ figma/
│        ├─ blender/
│        ├─ penpot/
│        ├─ ffmpeg/
│        ├─ comfyui/
│        └─ minimax-h3/
├─ design-system/              # neutral reusable design protocol assets only
├─ minigame-runtime/           # frozen game-visual fixture; not product
├─ project-memory/
├─ reports/
└─ README.md
```

Canonical product manifest becomes `design-lab/config/product-manifest.json` with namespace `design-lab/product-manifest/v1`. Product contract must never contain `primaryRuntime`. Runtime choice belongs to an ignored local profile or a per-project user-approved configuration.

### F1. Host compatibility without product pollution

The existing `open-design.json` filename and upstream `$schema` can remain only where it is a literal Open Design payload. Every such file must be marked `hostAdapter: open-design`; its canonical capability must have a neutral manifest or registry reference. Open Design-specific install, doctor, scaffold and runtime code moves below `design-lab/adapters/hosts/open-design/`.

No global rename may alter an upstream contract merely because the string contains “Open Design”. Conversely, no active core document may use that name as its default product identity.

---

## G. Adapter architecture and tool roadmap

### G1. Common adapter contract

```text
AdapterRecord
  id / type(host|agent|tool|model) / mode
  supportedObjects / capabilityScope / versions
  requiredPermissions / secretHandling / networkPolicy
  rightsDependencies / installPolicy / rollback
  evidenceLevel / lastVerified / boundTreeSha
```

Allowed modes: `in-process`、`process-isolated`、`external-cli`、`external-local-api`、`external-provider-api`、`none`。所有外部适配器默认不执行；须经项目选择、明确授权和可回读证据才可运行。

### G2. Agent 与 Host

- Hermes、Codex 等：`agent` adapter，只做任务协调与受控工具调用；不拥有产品身份，不读写凭据。
- Open Design：当前的 reference Host Adapter；本地使用者可选用，不能再写入全局 default runtime。
- Figma、Penpot、Blender：按真实可调用契约各自建立 adapter，不复制它们的编辑器。
- Adobe：`creative-tools/adobe/`，Photoshop 为 MVP；命令应可逆、能读回、修改可编辑文件。鼠标/视觉自动化仅是人工观察下的最后兜底。

### G3. MiniMax H3

`model-minimax-h3` 是**媒体生成模型 adapter**，只能服务视频/动效/声音/多模态视觉实验，不是聊天模型、通用推理器或主编排器。根据 [MiniMax H3 官方公告](https://minimaxi.com/blog/minimax-h3)，它适合以受权的文本/图像/视频/音频输入生成视听产物；当前项目只允许建立 E0 声明合同。实施时重新锁定 [官方 API 文档](https://platform.minimaxi.com/docs/api-reference/api-overview) 中实际可用的型号、端点、费用、地区、版本和许可证；不能预填或猜测这些值。

必要文件：

```text
adapters/creative-tools/minimax-h3/
├─ adapter.manifest.json       # E0 until official contract is pinned
├─ media-generation.schema.json
├─ rights-and-provider-policy.md
├─ evidence/README.md
└─ tests/contract-fixtures/
```

密钥只在用户本机环境配置；禁止入库、UI、日志、报告和截图。本地 RTX 3060 Ti 8G 不承诺 H3 本地推理，须以官方权重/硬件条件和实际测试决定。

### G4. ComfyUI

`tool-comfyui-local` 是用户自有的 `external-local-api` 工具，不是 DESIGN-LAB 服务。ComfyUI 的工作流可用 JSON 表示并通过本地 API 执行，[官方工作流说明](https://docs.comfy.org/development/core-concepts/workflow) 和 [开发概览](https://docs.comfy.org/development/overview) 是唯一接口依据。

```text
approved MediaGenerationRequest
 → pinned ComfyUI workflow JSON
 → user-started loopback-only ComfyUI
 → prompt_id / output readback
 → artifact + dependency lock + quality/preflight + evidence
```

硬约束：不自动安装 ComfyUI/模型/custom node；不 vendoring；不管理常驻进程；不暴露公网；不下载或执行未知工作流/节点；不新增后端或编辑器。每个 workflow 必须锁定 ComfyUI 版本、所有节点/模型的来源与 hash、许可证、输入/输出、审批和 rollback 版本。

### G5. H3 × ComfyUI bridge

两者先独立存在。只有官方权重/接口或审查通过的节点可证实、许可证清晰、可复现本地 loopback workflow、依赖锁定、E3 执行与人工视觉审核都通过时，才能新建 bridge。否则不得说“已集成 H3 ComfyUI”。

---

## H. MiniGame：游戏视觉设计 Fixture 的精确改造

### H1. 新合同

```text
minigame-runtime = Game Visual Design Fixture / Runtime Reference

允许：HUD、UI、图标、皮肤、交互反馈、场景氛围、动态视觉、资产规范、
      跨端可视化回归、可运行视觉 fixture 的安全/构建/测试维护。
禁止：小游戏合集平台、独立产品线、发行渠道、广告/IAA/变现、运营、
      新玩法系统、内容包扩张、发布/增长路线图。
```

### H2. 必须逐项收口

1. `README.md`：删除“合集分类目录”、AppID/广告位、发布、发行命令和“新平台定位”；保留仅用于 fixture 的预览/回归命令。
2. `games/find-anomaly/elevator-console/game.manifest.json`：把 `platformRole: launch-game`、`monetization`、`nextContentPackCandidate`、产品化 description 换成 `fixtureRole: game-visual-design-reference`、可验证视觉目标、允许的 build fixtures。
3. 旧平台、变现、抖音 release、内容包文档：移入 `minigame-runtime/docs/history/`，或标为不可执行历史资料；活动索引禁止链接为当前路线。
4. `AGENTS.md`：取消“独立游戏产品”职责，改为冻结游戏视觉 fixture 维护边界。
5. 测试：删除保护“合集平台”措辞的断言；新增 `minigame_visual_fixture_boundary_test`，对关键活动路径禁止 `launch-game`、`IAA`、`adSlots`、`release`、`monetization`、`nextContentPack`、`平台运营`。
6. 多端 build 仍保留，但定义为“视觉工作在 H5/Canvas/WebView 的兼容和回归读回”，不是可发行产物。

这不是删除 MiniGame，而是把其已有运行时价值收敛为游戏视觉设计的证据资产。

---

## I. 活动 SSOT、任务 ID、术语与报告

活动 SSOT：

```text
project-memory/
├─ PRODUCT_DEFINITION.md
├─ ARCHITECTURE.md
├─ BOUNDARY_CONTRACT.md
├─ ROADMAP.md
├─ OBJECT_MODEL.md
├─ USER_MODES.md
├─ NEUTRALITY_POLICY.md
├─ EVIDENCE_POLICY.md
├─ ADAPTER_POLICY.md
└─ history/
```

任务前缀固定：

```text
DL-POS  positioning       DL-ARC  architecture
DL-CORE core              DL-INT  intelligence
DL-DOM  domain            DL-QLT  quality
DL-ADP  generic adapter   DL-ADB  Adobe
DL-H3   MiniMax H3        DL-CFY  ComfyUI
DL-PRD  production        DL-KNW  knowledge governance
DL-EVD  evidence
DL-MIG  migration         DL-GV   game visual fixture
```

旧 V4/V42 ID、原 SHA、测试记录、reports 必须原样归档，不能修改文字来伪造新名称下的历史。新报告必须包含 `boundTreeSha`、生成时间、执行环境、工具版本、输入 hash、结果与人工审批人。

---

## J. 分阶段实施任务包

### J0. Freeze / preparation（阻断一切广泛改动）

| ID | 工作 | Done 条件 |
| --- | --- | --- |
| DL-MIG-000 | 记录 `main@f8664ee…`、clean worktree、原路径清单、回滚点 | 基线可独立 readback；无直接 main 写入 |
| DL-MIG-001 | 建立迁移分支和变更批次清单 | 每批有目标、影响、验证、回滚 |
| DL-MIG-002 | 建立术语 allowlist/denylist | 旧名只在 history/source/host adapter 精确位置出现 |

### J1. 先清除产品漂移

| ID | 工作 | Done 条件 |
| --- | --- | --- |
| DL-GV-001 | MiniGame 游戏视觉 fixture 合同 | 活动 README/manifest/AGENTS 一致 |
| DL-GV-002 | 归档旧平台/IAA/发行内容 | 活动目录无产品化语义；历史仍可追溯 |
| DL-GV-003 | 防漂移测试和 CI gate | 新玩法/广告/平台扩张 PR 被 fail-closed 拒绝 |
| DL-POS-001 | 写入九份稳定 SSOT | 不再引用 V42/old name 作为活动权威 |
| DL-POS-002 | 根 README 与产品地图 | 一屏说明“视觉设计实验室、host-native、非第二前端” |

### J2. 内部身份与核心重构

| ID | 工作 | Done 条件 |
| --- | --- | --- |
| DL-MIG-010 | `git mv opendesign-assistance design-lab` | Git history 可追踪；无丢失文件 |
| DL-ARC-001 | 新 Manifest/Schema namespace | `design-lab/product-manifest/v1` 通过 schema |
| DL-ARC-002 | Neutrality + Rights policy | 无 `primaryRuntime` / `rightsNeutral` / `fiveNeutralities` |
| DL-MIG-011 | scripts/index/verifier rename | `verify_design_lab.py`、`generate_capability_indexes.py` 成为唯一活动入口 |
| DL-MIG-012 | Open Design host projection | 原上游 payload 可继续被验证，且不污染 core |
| DL-MIG-013 | V4/V42/history report migration | 历史文件可读、活动入口唯一、链接不坏 |

### J3. 视觉能力产品化

| ID | 工作 | Done 条件 |
| --- | --- | --- |
| DL-CORE-001 | 11 个核心对象和 schema | Schema fixtures + round-trip tests |
| DL-INT-001 | Brief → Direction → Design System contract | 至少三条跨领域 scenario 可追溯 |
| DL-DOM-001 | 视觉领域 taxonomy 和 pack contract | 领域不会污染 core；每包有 rubric/preflight |
| DL-QLT-001 | Visual Quality Jury V1 | 含反 AI 味、布局、材质、可读性、商业适配、人审 |
| DL-PRD-001 | Handoff/Preflight V1 | 颜色/字体/尺寸/格式/源文件/许可证/BOM/回滚完备 |
| DL-KNW-000 | 外置资料库登记 | `D:\All projects\Design assets` 仅作为本地原始真源；无 Git 复制/软链接/绝对路径泄漏 |
| DL-KNW-001 | 资料与开源治理 | SourceRecord、license registry、derivation trace 可验证 |

### J4. 工具适配器（只建设可验证合同）

| ID | 工作 | Done 条件 |
| --- | --- | --- |
| DL-ADP-001 | Adapter Registry V3 | host/agent/tool/model 无默认绑定；每项可回滚 |
| DL-ADB-PS-001 | Photoshop MVP | 可逆的可编辑文档操作与 E3 读回 |
| DL-CFY-001 | ComfyUI E0/E1 | loopback 与禁止自动安装检查通过 |
| DL-H3-001 | MiniMax H3 E0 | 无虚构 API/权重；权利/证据合同完备 |
| DL-H3-002 | H3 provider qualification | 仅在官方契约可核验后执行 |
| DL-CFY-002 | 受批准 workflow E3 | 手动启动 ComfyUI、依赖锁定、输出可复现 |
| DL-H3-003 | H3–Comfy bridge feasibility | 四项前置齐全才评审；否则保持未启用 |

### J5. 证据、CI 与交付

| ID | 工作 | Done 条件 |
| --- | --- | --- |
| DL-EVD-001 | 新树 evidence index/SBOM | 所有 E 级绑定新树 SHA；历史 E3 不误用 |
| DL-CI-001 | identity-boundary gate | 主动路径旧名命中即 fail；Host/history allowlist 例外精确 |
| DL-CI-002 | schema/unit/fixture gate | 已安装完整 venv 后测试；不把环境缺依赖当通过 |
| DL-CI-003 | MiniGame boundary gate | 反平台化/反广告断言必过 |
| DL-CI-004 | release exact-SHA gate | CI run、artifact、SHA 回读一致 |
| DL-REL-001 | 人工可视与生产验收 | UI/UX、平面、3D、游戏视觉各至少一个有效案例 |

---

## K. 验收、CI 和防漂移规则

```text
Identity gate        产品 ID / Namespace / folder / docs / scripts / CI 均为 design-lab
Legacy allowlist     Open Design 仅限 host adapter、history、source
No default binding   产品 manifest 无默认 host / agent / model
Rights gate          每个 source/model/workflow/font/asset 有权利状态
Adapter gate         未达到 E3 不得写“已集成”
Comfy gate           loopback-only；无自动安装/下载/外网端口
Game visual gate     禁止 IAA/广告/发行/平台/新玩法或内容包扩张
Quality gate         Rubric + 人审，不用单张 AI 图作为通过证据
Production gate      可编辑源、预检、BOM、许可证、回滚包
Evidence gate        boundTreeSha + exact command + environment + readback
Release gate         exact-SHA CI + human approval + clean worktree
```

默认状态是 fail-closed。为兼容旧 host contract 的例外必须有文件级 allowlist、理由、责任人、到期/复查日期；不能使用宽泛的 `**/*open-design*` 忽略规则。

---

## L. 实施/发布规则和回滚

1. 本次仓库重命名已经完成；禁止再建同名副本、再 rename 或把 MiniGame 回迁 WORK-LAB。
2. 一切代码变化在迁移分支完成；按 J 节的批次顺序合并，禁止一个“大爆炸”重命名提交。
3. 每一批必须有 `git diff --check`、受影响验证、链接检查、旧名扫描和回滚 SHA。
4. 不读取/提交 API key、OAuth、cookie、私有 app config、真实 AppID 或广告位；不以测试名义绕过这一限制。
5. 未获得明确授权时，不 commit、push、开 PR、merge、改 ruleset 或 release。
6. 若任一 identity/compatibility/evidence gate 失败，回退到本批起点；不重写 Git 历史、不删除历史证据。

---

## M. Definition of Done

只有同时满足下面全部条件，才可宣布“DESIGN-LAB 完成迁移并进入视觉设计主线”：

- GitHub、origin、本地目录、根 README、manifest、schema、脚本和 CI 均使用 `DESIGN-LAB/design-lab`。
- 核心不含 Open Design-first、默认 Agent、默认模型或默认 Host；Open Design 是可验证的 Host Adapter。
- 视觉设计闭环和六能力域有稳定 SSOT、对象 schema、scenario、quality/preflight/handoff/evidence。
- 开源资料都经过 Source/License/Derivation 治理；大师质感只以方法研究表达。
- MiniGame 仅为游戏视觉/交互 Fixture，所有活动平台、广告、发行、运营和内容扩张语义已被清除并由测试防回归。
- Adobe Photoshop MVP、ComfyUI、MiniMax H3 的证据等级如实记录；H3–Comfy bridge 未满足条件时明确为未启用。
- 新树的 unit/schema/fixture、MiniGame、Host compatibility、CI exact-SHA、人工视觉评审和生产交付证据全部可读回。
- 没有未经用户授权的提交、推送、PR、合并、发布或凭据访问。

**当前状态：** 身份、MiniGame fixture、外置资料库治理、Adapter E0 合同和本地 CI 门已在迁移分支落实并经本地验证。尚未提交、推送、创建 PR、合并或发布；下一批只能在用户明确授权后，按 `DL-KNW-001` 的人工资料审核与 `DL-ADB-PS-001 / DL-CFY-001 / DL-H3-001` 的逐项 E3 取证推进。
