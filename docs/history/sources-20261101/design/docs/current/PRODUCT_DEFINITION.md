# 当前产品定义修订（2026-10-23）

Authority修订`DESKTOP-KB-20261023-R1`；以`docs/taskpacks/20261023-ui-kb/OWNER-DECISION-2026-10-23.md`为准，与下文2026-10-20 / 2026-10-19冲突的派工条款由本节替代。当前唯一integrated TaskPack是`docs/taskpacks/DESIGN-LAB-DESKTOP-KB-INTEGRATED-TASKPACK-2026-10-23.md`（`DL-TP-20261023-DESKTOP-KB-R1`）。
定位按 owner 今日采纳的措辞落定：DESIGN-LAB 是覆盖品牌、平面、UI/UX、3D、2D/3D 动效、粒子、视频与音频的**专业设计知识管理、创意方案与模型应用辅助系统**；它整理与更新设计规范、审美方法、叙事与视听语言、提示词、模型与软件使用指南及实践案例，按用户的内容、目标、参考资料与所选工具组合给出有依据的分析、重构方向、专业方案、脚本分镜、声音设计、提示词、参数建议与外部执行说明。**用户决定采用与放弃，外部软件实施制作**；本项目不承担制作落地、成品交付与发布，不建第二套 Agent、模型网关、画布、3D 编辑器或剪辑时间线。可验证价值是：知识找得到、依据看得懂、方案有专业内容、输入能适配目标工具、材料可以带走、旧版本可追溯、用户反馈能用于修正方法。
本节只做三件事：
1. **桌面 UI 与知识库进入当前派工。** 三个日常入口——设计辅助／知识与提示词库／我的方案——外加设置；`currentExecution` 新增 `DL-KB-01`…`DL-KB-16`（定义原件`docs/history/taskpacks/20261023-adoption/TASK-DEFINITIONS.json`），批次 K0…K8 即执行顺序：知识条目与中文检索 → 中立方案与目标档案/导出 → 一个方案助手模型的真实接入 → 内容方法与反馈。每个纵切都必须同时有真实前端、API、持久化、重启读回与错误态；只有文档修订不算功能完成，只有界面画出来也不算。
2. **旧冻结段没有被解冻。** `currentExecution` 其余 34 项仍 `FROZEN_DEFERRED`；release、安装态分发、真实宿主 E3、真人 E4、ComfyUI、MiniMax H3 与外部软件自动操作继续冻结（**这一项中"外部软件自动操作"已由 owner 2026-10-28「取消冻结的自动化任务」解冻进入派工**，见 `docs/taskpacks/20261028-automation/OWNER-DECISION-2026-10-28.md`；解冻的是能力类，逐次真启动宿主与写原生文档仍走 Human Gate，默认状态 `NOT_PROBED`，本轮证据等级上限 E1/E2），解冻任何一项仍需 owner 新的明确授权。两个数字由`scripts/verify_documented_counts.py`分别现数，不可互换。
3. **边界一条没放松。** 手机端仍是排除项（`mobile` 字段仍是 schema const `FROZEN_DEFERRED`）；字体库与第三方素材权利判定仍在范围外；模型不锁死但默认 fail-closed，`UNKNOWN` 不写成合格，云端选项必须披露离开本机的数据，**本轮不部署模型也不自行下载权重**；`source.job_id` / `operation_id` 仍由用户填写或显式选择「不使用」；验收与签字仍只接受具名真人；候选导出仍是读回不是发送（`outbound=NOT_CONNECTED`）；AAOS 仍只是未来合同；E 盘不动。既有 `executed=false` 合同不得为"通过"而解除——真实推理要走新的运行记录与版本演进，选择成功、连接成功、返回文本、内容可用四件事分别验证。

下面 2026-10-20 一节是当日原文，保留不改写：它的"定点解冻三段"与"范围收口"继续成立，今天没有撤销任何一段；今天改变的是派工面——桌面 UI 从"按需给可审阅界面"升级为当前主交付段。

---

# 当前产品定义修订（2026-10-20）

Authority修订`UNFREEZE-20261020-R1`；以`docs/taskpacks/20261020-unfreeze/OWNER-DECISION-2026-10-20.md`为准，与下文2026-10-19冲突的派工条款由本节替代。
定位不变：面向职业视觉设计的AI原生、平台中立的**专业视觉智能与可复用设计能力系统**；六大能力域与最小真实闭环五步（视觉输入 → 分析/提示词生成或反推 → 可验证输出或合格工具调用 → 用户/授权 Agent 验收 → 知识候选在本项目内留存）不变。
本节只做三件事：
1. **定点解冻产品实施**，范围仅三段——**Prompt Intelligence 入口**（提示词生成与反推可被用户与Agent调用。2026-10-22 实测：装配与反推两条读回已接通，产出的两份文档现在都落库为可寻址的追加式修订（`GET …/prompt-results`），并有一条具名人工签署绑定它判过的那份摘要（`POST …/prompt-results/<id>/review`）；仍未接的是真实推理执行——`model.executed` 恒为 `false`、反推的观测仍由操作者粘贴；桌面面板同日接上（2026-10-22：`#/prompts` 列出库里存下的结果，逐行给出摘要尾号与签署状态，未署名时在本页拒发，署名后读回 ACCEPTED，这条走查已进入出厂浏览器链路的 `browser-e2e-summary.json`），owner 同日裁定推理执行仍不接、只做契约与错误路径）、**`KnowledgeCandidate` 导出出口**（把实施前在 `src/` 内零调用者的 `export_payload` / `to_v1_projection` 接到真实调用方，使导出成为可寻址动作；2026-10-20 服务端与 CLI 落地，2026-10-21 界面侧落地——`#/records` 知识面板每条候选一行一个「读回导出文档（不发送）」按钮，被合同挡住的那些行是禁用的且按钮自己说明原因，该控件已进入出厂浏览器链路；出站传输仍是 `NOT_CONNECTED`，所以这是读回不是发送）、**模型选择接口**（菜单导航 + 接口，用户自行选择本地或云端模型。2026-10-21 实测：`GET /api/models` 并列给出 14 条模型与 9 条 provider 端点，`join.key` 为 `null`（两边没有共同字段，端点行的 `model_ref` 为空），`QUALIFIED_LOCAL=0`；选择已被记录，但"可选"不等于"已合格"，也不等于"能执行"）。`currentExecution` 其余 34 项仍 `FROZEN_DEFERRED`；release、安装态分发、真实宿主 E3、真人 E4、ComfyUI 与 MiniMax H3 继续冻结。
2. **模型不锁死，但默认值仍 fail closed**。用户显式选择是一次被记录的用户动作：它不改变模型的合格状态、不把 `UNKNOWN` 写成合格、不宣称推理已验证；每个云端选项必须写明哪些数据离开本机。选择面展示"可选 + 现状 + 后果"，合格判定只在真实取证后由 owner 验收。
3. **范围收口**。字体库与第三方素材的权利判定移出本项目范围，不再作为缺口、待办或开工前提（不默认上传客户素材、不持有用户素材库、E 盘受保护这些边界不变）。`source.job_id` / `operation_id` 改为界面可填写并允许显式选择"不使用"，代理不得自行铸造标识冒充来源证据。`DESIGN.md` 在 owner 真实测试前不进入已批准状态，先把业界最专业的设计规范收入库内作参考（2026-10-21 已登记：`packages/capabilities/standards/INDUSTRY_SPEC_REGISTER.md`——按"可吸收 / 只可引用 / 今日未能核验"三档记录出处、版本与许可原话，取不到的字段一律留 UNKNOWN，不抄任何正文）；逐条配色归属与品牌蓝裁定挂起，不是阻塞项。手机端仍为排除项，AAOS 仍非依赖或门。

---

# 当前产品定义修订（2026-10-19）

Authority修订`DIRECTION-20261019-R1`；以owner 2026-10-19方向调整任务包为准，旧定义冲突条款由本节替代。
DESIGN-LAB（设计实验室 / Visual Design Lab）是面向职业视觉设计的AI原生、平台中立的**专业视觉智能与可复用设计能力系统**。它把视觉知识、审美判断、设计方法、参考图分析、提示词工程和成功/失败案例，转化为可检索、可组合、可测试、可版本化、可部署的能力；支持用户和Agent进行专业视觉分析、提示词生成与反推、设计能力检索，并通过API、MCP、原生插件、脚本或受控UI自动化调用设计软件。经用户或获授权Agent验收的知识形成候选，再按AAOS正式流程提交审核。
产品本体是视觉智能＋审美能力工程化＋设计能力库＋设计软件自动化＋受控知识回流。六大能力域：Visual Intelligence / Aesthetic Analysis / Prompt Intelligence / Design Capability Library / Creative Tool Automation / Knowledge Candidate & Evaluation。
不是第二画布或通用编辑器，不以全流程设计文件制作交付为产品本体；不是通用Agent Runtime、聊天客户端、模型网关或跨项目调度器。原生宿主负责画布内实际编辑。
模型本地/云端/混合可替换；工具按官方API/SDK → 原生插件 → MCP → 脚本/CLI → 受控UI自动化分层；握手、HTTP 200、退出码或截图不等于真实任务验证。
WORK-LAB保留通用工作流/全局配置/权限预算/跨项目协调/监测/维护；AAOS保留正式知识真值、来源/证据治理、审核与长期学习。DESIGN-LAB只提交知识候选并读取AAOS状态。
2026-10-09 UI-FIRST派工已降为前继；`currentExecution` 34项全部`FROZEN_DEFERRED`。本轮只做权威/规划对齐、映射、可行性矩阵、最小真实闭环规划与按范围测试，不实施产品功能。发布/安装、真实宿主E3、真人E4、AAOS联调、ComfyUI/H3继续冻结或延后。手机端已从范围移除（owner 2026-10-19 授权：「再说一遍 不做手机端 只做桌面端」「授权给你 去掉手机端」）：它不是待办、不是能力缺口、也不是待排期项；恢复需 owner 新的明确授权。
完整定义见`docs/taskpacks/DESIGN-LAB-DIRECTION-ALIGNMENT-2026-10-19.md`与`docs/taskpacks/20261019-direction/source/TASKPACK.md`。

---

以下2026-10-09定义保留为前继记录；冲突条款不再负责当前派工。

# 当前产品定义修订（2026-10-09）

Authority修订UI-FIRST-20261009-R1；以新包＋owner决定为准，旧定义冲突条款由本节替代。
DESIGN-LAB面向全设计品类的专业能力资产、知识应用与有界自动化，接受文字/截图/文件/多图/音视频，按实际覆盖提供分析、目标生成包、操作方案或原生产物。
当前优先桌面UI的能力资产、分析与制作、成果与反馈；不以项目看板/审批大厅为中心。旧Project对象与apps/workbench技术路径保留；简单任务不强迫完整项目流程。
允许已有设计专用执行/观察/核验/恢复；不建通用Agent、第二运行时/画布/知识主库。
长期知识及学习状态归AAOS/ArcheAxis公共合同；DL保留专业判断、配方、适配、源工程、教学生产和表达修订；WL按许可提供实践和有界支持。独立运行与有界授权快照保留。
手机端已移出范围：不做、不派工、不记为缺口。全品类是目标，不是已支持声明。当前实现证据和操作授权分别判断。

---

以下前继定义保留其适用语义，冲突条款不再负责当前派工。

# PRODUCT_DEFINITION — DESIGN-LAB（设计实验室）

- 版本：`1.1`｜状态：`ACTIVE`｜SSOT 角色：Authority 下的当前产品定义
- 顶层权威：`/AUTHORITY.md`（`DL-AUTHORITY-2026-09-18-R2`）
- 当前唯一任务包：`docs/taskpacks/DESIGN-LAB-DIRECTION-ALIGNMENT-2026-10-19.md`；其他任务全部 `FROZEN_DEFERRED`，不再派工
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
