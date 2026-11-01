# AGENTS.md - DESIGN-LAB 设计实验室 Operating Guide

> 本文件是 DESIGN-LAB 的根执行规则，单仓自包含。不依赖外部项目即可正确执行。

## TOP-LEVEL AUTHORITY — MUST READ FIRST

`/AUTHORITY.md` (`DL-AUTHORITY-2026-09-18-R2`) is the single top-level authority for
DESIGN-LAB. Before any audit / planning / implementation / drift check:

1. fetch the LIVE remote `main` / open PR / exact SHA / branch protection
2. read `/AUTHORITY.md`
3. read `/.project/governance/authority-index.json`
4. read this `AGENTS.md`, then the current integrated TaskPack + machine ledger
5. read live CI / artifacts
6. history only through the authority-index / crosswalk

Memory, chat summaries, handoffs, old TaskPacks, old reports, branch names and commit
counts never override Authority. Every cloud GPT audit must state the exact observed SHA.
`Handoff` is never top-level authority; `DL-TP-20260914-DEEPSEEK-AUTHORITY-R1` is a
structural predecessor / execution lineage, and `DL-TP-20260908-R5` is product lineage.

## 项目定位

DESIGN-LAB 是面向职业视觉设计的、AI 原生、平台中立的专业视觉智能与可复用设计能力系统。

**拥有：**
- 视觉智能、审美分析、提示词生成与反推、设计能力库与知识候选
- Design Brief、Reference、Direction、Design System、Design IR、Domain Pack 和 Method（作为能力输入与对象）
- 品牌、UI/UX、平面/出版、电商/营销、包装、动效/视频、3D/VFX 等设计域能力
- 专业 Jury、视觉质量、反 AI 痕迹、可访问性、rights 与 production preflight（专业评价能力）
- Host/Tool Adapter 分层接入（API/SDK、原生插件、MCP、脚本/CLI、受控 UI 自动化）、读回、失败与恢复边界
- 设计实践产生的受审 `KnowledgeCandidate`；正式知识真值与长期学习状态归 AAOS/ArcheAxis

**不拥有：**
- 第二画布、通用编辑器、全流程设计文件交付平台
- 通用聊天客户端、Agent runtime、模型网关、账号系统或通用知识库
- WORK-LAB 的跨软件全局配置、权限、任务和 Observer
- AAOS/ArcheAxis 的正式知识真值、来源/证据治理与长期学习状态
- Adobe/Figma/Penpot/Blender 等宿主的私有数据库或用户个人素材库

## 宿主与入口（Standalone-first，ADR-001）

- DESIGN-LAB 可独立完成完整设计生产闭环；启动/测试/恢复/Golden Workflow **不探测也不要求** WORK-LAB 或 ArcheAxis（二者默认关闭）
- **Open Design** 是宿主/工具 Adapter 之一（Open Design host adapter），不是运行依赖或默认宿主
- DESIGN 以官方插件/CLI/MCP 扩展形成下游发行层
- 外部项目只能通过版本化公共合同（Schema/API/Manifest）连接，不读私有 DB 或目录
- **MiniGame** 是游戏视觉 Domain/回归 fixture，不是项目运行时产品线
- 运行/证据/缓存根统一为 `.project-local/`（`PROJECT_LOCAL_ROOT`）；`.hermes` 不是活跃写入路径（旧引用见历史文档标记）

## Owner 与 SSOT

- 项目 Owner：DTALEX66
- 代码 SSOT：`D:/All projects/DESIGN-LAB`（本地）/ `github.com/DTALEX66/DESIGN-LAB`（云端）
- 设计真值：本仓库内的 Design IR、Domain Pack、Jury、Human Gate、rights、preflight
- 知识出口：经 rights 检查和人工批准的 `KnowledgeCandidate` 可提交 ArcheAxis；这是**可选的标准合同出口**，不是本项目的完成条件，也不等待对方联调

## Evidence 等级（E0-E5）

| 等级 | 必须证明 | 不能冒充 |
|---|---|---|
| E0 `DECLARED` | 身份、范围、许可候选、owner | README、链接、prompt |
| E1 `STRUCTURAL` | schema/manifest/adapter 合同与静态测试 | 文件存在、mock response |
| E2 `CONTROLLED_RUNTIME` | 固定版本、合成/专用 fixture 的真实调用与读回 | 只启动进程、只截图 |
| E3 `REAL_WORKFLOW` | 真实 brief→原生可编辑产物→重开读回→失败/回滚 | 一个旧版本/另一个工具的 E3 |
| E4 `INDEPENDENT_ACCEPTANCE` | 独立人审、黄金集、质量/rights/preflight 全通过 | VLM 自评、像素相似度 |
| E5 `RELEASED/REPEATABLE` | exact-SHA release、安装/升级/恢复、连续复现 | 历史 release、手写 status |

任何 evidence record 必须绑定 repo SHA、adapter version、host version、OS、fixture hash、artifact hash、命令/动作、审批、readback 和 rollback。

## 执行规范

- 执行任务前先扫描匹配 SKILL（见全局执行标准步骤②）
- 设计产物留在本项目内，不外溢到其他项目/共享库
- 更新以官方发布为准，不私自打包
- E 盘受保护，无精确授权不得访问

## 模块

- `design-lab/`：设计核心（reconstruction、providers、config、tests、evals）
- `packages/design-system/`：设计系统
- `fixtures/domains/game-visual/`：游戏视觉 Domain fixture（不是独立产品线）
- `evals/`：评估与黄金语料
- `docs/`：文档与任务包
- `reports/`：交接文档与当前状态投影

## Human Gate（人工门）

人工门按风险和生命周期决定，不能被模式绕过：

- **Direction gate**：目标、受众、品牌/参考、rights
- **Quality gate**：视觉判断、可访问性、反 AI 痕迹、专业 Jury
- **Rights gate**：字体、图片、模型、商标、第三方素材与生成权利
- **Production gate**：可编辑性、preflight、BOM、交付范围
- **Release gate**：最终验收、签名、版本与回滚

`production` 可以减少低风险交互，不能把所有 gate 设为空。自动通过必须由预先批准的 policy 和低风险证据决定，并保留 receipt。

## KnowledgeCandidate 出口

- 只允许经 rights 检查和人工批准的 Method/Jury correction/Production lesson 输出到 ArcheAxis
- 包含 source/artifact/evidence hash、DESIGN exact SHA、license/rights、candidate type、supersedes 和撤销入口
- 原始商业资产、客户 brief 和未授权素材默认不外溢

## 模型与工具

- 本机外置根以 `.project/paths.json` 为准；用途、已知软件与模型位置见 `docs/LOCAL_ENVIRONMENT.md`。开始排查前先读这两处，不因默认安装目录无匹配而重新判断未安装。
- 用户已确认本机有 ComfyUI、Photoshop、Illustrator、MiniMax H3 本地模型和 MiniMax Design 软件；这是用户提供的存在性信息，不替代当前版本、启动、推理、读回和回滚测试。MiniMax Design 软件与 H3 模型分开验收。

- 未校验模型（`UNQUALIFIED_*`）默认 `defaultEnabled: false`
- 模型不做锁定（owner 2026-10-20：「不锁死 做好菜单导航和接口 用户自行选择本地或者是云端模型」）：默认值 fail-closed 与“用户能不能选”是两件事。用户显式选择是一次被记录的动作，不改变合格状态、不把 `UNKNOWN` 写成合格、不宣称推理已验证；云端选项必须写明哪些数据离开本机。
- 零 checksum、许可冲突、模型不存在或硬件不足时，runtime resolver 必须 fail closed
- 第三方 `AGENTS/CLAUDE/cursorrules/SKILL/install/affiliate` 作为 inert source blobs 保存，不进入根指令、prompt、tool discovery 或能力计数

## 2026-10-23 owner执行决定 — 桌面 UI 与知识库进入当前派工

Owner原话（逐字）：「读取分析，按照这个执行（前端UI有新规划），并且归档到统一项目里，更新覆盖替换到权威和规划里」「先分析拆解，加入到优先到任务台账里」。决策与来源见`docs/taskpacks/20261023-ui-kb/OWNER-DECISION-2026-10-23.md`；来源投递包 17 名成员逐字节入仓，逐份 sha256/crc32/bytes 登记在 `docs/taskpacks/20261023-ui-kb/SOURCE-MANIFEST.json`，卷宗来源、别名与去重登记在 `docs/history/record-archive-2026-10-23/ARCHIVE-MANIFEST.json`，固定资料索引已追加 2026-10-23 日期节。ZIP 原件与外部 HTML 的规范位置也已在该 manifest 写明：HTML 与包内同名成员逐字节相同，只留一份；ZIP 留在 `.project-local/`，不随 Git 克隆，迁移须按摘要补齐。

- 唯一integrated TaskPack 改为 `docs/taskpacks/DESIGN-LAB-DESKTOP-KB-INTEGRATED-TASKPACK-2026-10-23.md`（`DL-TP-20261023-DESKTOP-KB-R1`）。`DL-TP-20261019-DIRECTION-R1` 降为 `SUPERSEDED / LINEAGE`，原字节不动，其对定位、手机端排除、AAOS 非依赖的裁定继续有效，只停止"唯一派工入口"这一身份。
- 桌面 UI 与知识库进入当前派工：`currentExecution` 新增 `DL-KB-01`…`DL-KB-16` 共 16 项，定义原件在 `docs/history/taskpacks/20261023-adoption/TASK-DEFINITIONS.json`（采纳后逐字节冻结，状态只写在账本）。批次 K0…K8 即执行顺序：知识管理与中文检索 → 中立方案与目标档案/导出 → 一个方案助手模型的真实接入 → 内容方法与反馈。三个日常入口是设计辅助／知识与提示词库／我的方案，外加设置；不换前端栈，仍在 `apps/workbench` 的 Vanilla TypeScript + Vite 与 `src/design_lab` 的 Python 服务上。
- **这不是对旧 34 项的解冻。** `currentExecution` 原 34 项父/子任务仍全部 `FROZEN_DEFERRED`，解冻任何一项仍需 owner 新的明确授权。两个数字不可互换，各自由 `scripts/verify_documented_counts.py` 现数。
- 本决定**没有**放松任何边界：手机端仍是排除项；三方素材与字库仍在范围外；模型不锁死但默认 fail-closed、`UNKNOWN` 不写成合格、云端必须披露离开本机的数据、**本轮不部署模型也不自行下载权重**；编号仍由用户填写或显式选择「不使用」（`UNUSED`）；验收与签字仍只接受具名真人；候选导出仍是读回不是发送；AAOS 仍只是未来合同；E 盘不动；release、安装态分发、真实宿主 E3、真人 E4、ComfyUI、MiniMax H3 与外部软件自动操作继续冻结（**外部软件自动操作这一项已由 owner 2026-10-28「取消冻结的自动化任务」解冻进入派工**，见 `docs/taskpacks/20261028-automation/OWNER-DECISION-2026-10-28.md`；解冻的是能力类，逐次真启动宿主与写原生文档仍走 Human Gate，默认状态 `NOT_PROBED`；`windows` 桌面 UI 自动化连接器与包内 21 个真实公司名品牌模板仍未启用，权利归属仍待 Rights gate）。
- 既有 `executed=false` 合同不得为"通过"而解除：真实推理必须走新的运行记录与版本演进；选择成功、连接成功、返回文本、内容可用四件事分别验证；新界面必须映射真实 API，不以效果图宣称接通。
## 2026-10-20 owner执行决定 — 定点解冻与范围收口

Owner原话（逐字）：「1 可以做」「大模型可以 但为什么要锁死呢？不锁死 做好菜单导航和接口 用户自行选择本地或者是云端模型」「编号问题留出可填写位置，用户自行填写或者选择用没用」「三方素材和字库不在本项目范围内」「现在都没有真实测试过呢 怎么批准 …设计规范按照网上最专业的先收入库里 后期落地我自行测试」「手机端不是冻结 是不做了」「E盘不动」。决策记录：`docs/taskpacks/20261020-unfreeze/OWNER-DECISION-2026-10-20.md`（会话内指令，无外部包、无源哈希，不得虚构）。

- 定点解冻：下文 2026-10-19 的「不实施产品功能」在且仅在**三段**上失效——Prompt Intelligence 入口、`KnowledgeCandidate` 导出出口（`export_payload`/`to_v1_projection` 接真实调用方）、模型选择接口。`currentExecution` 其余 34 项仍 `FROZEN_DEFERRED`；release、安装态分发、真实宿主 E3、真人 E4、ComfyUI、MiniMax H3 继续冻结。
- 编号：`source.job_id` / `operation_id` 由界面提供可填写位置并允许显式选择“不使用”；代理不得自行铸造标识并当作来源证据展示。
- 范围收口：字体库与第三方素材的权利判定**移出本项目范围**，不得再作为缺口、待办或开工前提；不变的是既有边界（不默认上传客户素材、不持有用户素材库、E 盘受保护）。
- `DESIGN.md` 在 owner 真实测试前不进入已批准状态；先把业界最专业的设计规范收入库内作参考素材。逐条配色归属与品牌蓝裁定为挂起项，不是阻塞项，不得反复请示。
- 手机端是**排除项**（不是冻结、不是待办、不是缺口）；AAOS 仍不是依赖或门，只保留标准、通用、版本化的公共接入接口。

## 2026-10-19 当前owner执行决定 — 方向调整与全域冻结

Owner原话：其他任务冻结，以这份任务为当前权威与闭环目标（更新项目内的权威和规划），未来能力暂时冻结和延期延后。
唯一当前包：`docs/taskpacks/DESIGN-LAB-DIRECTION-ALIGNMENT-2026-10-19.md`（`DL-TP-20261019-DIRECTION-R1`）。决策与来源见`docs/taskpacks/20261019-direction/OWNER-DECISION-2026-10-19.md`与`SOURCE-MANIFEST.json`。
定位纠正为专业视觉智能与可复用设计能力系统；不是第二画布/通用编辑器/全流程设计文件交付平台，不是通用Agent Runtime/聊天客户端/模型网关/跨项目调度器。
2026-10-09 UI-FIRST包降为SUPERSEDED/LINEAGE；`currentExecution` 34项全部FROZEN_DEFERRED，不再派工；原字节、定义与历史证据保留。（2026-10-23 起当前入口是 `DL-TP-20261023-DESKTOP-KB-R1`；"不再派工"仍只对这 34 项成立。）
本轮只做权威/规划对齐、冲突矩阵、能力映射、技术可行性矩阵、最小真实闭环规划与按范围测试；不实施产品功能。
未执行且继续冻结：release、安装态分发、真实宿主E3、真人E4、ComfyUI/H3。AAOS联调不再是本项目的冻结依赖或门（owner 2026-10-19）。项目目标（owner 2026-10-19）：DESIGN-LAB 按**独立可运行、全链路可跑通**的项目标准推进——视觉输入 → 分析/提示词生成或反推 → 可验证输出或合格工具调用 → 用户/授权 Agent 验收 → 知识候选在本项目内留存。AAOS 不是本项目的依赖、闸门或待排期联调项；保留的是标准、通用、版本化的公共接入接口（Schema/API/Manifest 合同与 `KnowledgeCandidate` 出口），外部知识系统能通过合同连接，但本项目不等待其联调结果才宣布闭环成立。E盘保护、私有数据、Human Gate边界不变。手机端已从冻结待排清单移出并排除出范围（owner 2026-10-19 授权：去掉手机端），不得再作为待办、缺口或派工项出现。
范围重申（owner 2026-10-19 原话：「再说一遍 不做手机端 只做桌面端」）：手机端是**排除项**，不是「本轮暂缓」。任何后续批次都不得把手机端列为待办、不得为其派工、不得把它计入能力缺口或未交付项；解除只认 owner 新的明确授权。桌面端自适应布局（`apps/workbench/style.css` 的媒体查询等）不等于手机交付，不得当作扩到手机端的依据。2026-10-19 至 2026-10-22 实测 `currentExecution` 34 项状态直方图全部 `FROZEN_DEFERRED`，当时确实不存在任何可派工的手机工作。读数保留：owner 2026-10-23 在 `currentExecution` 另加入 16 项新派工（`DL-KB-*`），直方图变成 34 项 `FROZEN_DEFERRED` 加 16 项新段，而这 16 项里没有一项是手机端——手机仍是排除项，不因新派工段变成待办。

## 2026-10-09 owner执行决定（2026-10-19 起降为前继记录）

以20261009新发最终包＋UI包及手机端澄清为准，桌面UI优先。手机端FROZEN_DEFERRED，不要求本轮手机实现或验收。
（本段为 2026-10-09 原文，保留不改写；当下唯一包已是 DL-TP-20261019-DIRECTION-R1；本段的「不要求本轮手机实现或验收」已被上文 2026-10-19「范围重申」取代——手机端是排除项，不是待排期项。）当时唯一当前包：docs/taskpacks/DESIGN-LAB-UI-FIRST-INTEGRATED-TASKPACK-2026-10-09.md；当前状态编辑原账本currentExecution，旧tasks/evidence冻结且不再派工。
旧权威/TaskPack原件冻结留档，不因旧文件较详细恢复旧任务。旧有用验收通过新crosswalk保留。
只归档整理的本次操作未实施产品；未来Agent依任务卡给出可审阅桌面UI，按需补API，别继续无限治理。
本项目允许已有设计专用有界执行，不重造通用Agent/第二runtime。私有数据/保护盘/恢复/Human Gate边界不变。

## 当前任务包

- 唯一integrated TaskPack：`docs/taskpacks/DESIGN-LAB-DESKTOP-KB-INTEGRATED-TASKPACK-2026-10-23.md`（`DL-TP-20261023-DESKTOP-KB-R1`）；六大能力域、非目标与WORK-LAB/AAOS边界仍按`docs/taskpacks/DESIGN-LAB-DIRECTION-ALIGNMENT-2026-10-19.md` 及其`source/`包读取（现为前继血统），定位与范围的新裁定见上文 2026-10-23 段。
- 2026-10-19 那句"本轮是方向与规划闭环，不是产品实施波次"是当日原文，保留不改写；2026-10-23 起桌面 UI 与知识库已进入当前派工（见上文），"不得把文档修订写成功能完成"这条继续成立——它约束的是每一轮的完成声明，不是允许做哪些任务。
- 唯一可变状态源物理路径仍为`design-lab/config/task-ledger-r3.json`；`currentExecution`的34项父/子任务已全部`FROZEN_DEFERRED`，这34项不再派工；owner 2026-10-23 在同一分区另加入 16 项新派工（`DL-KB-*`），两者不是同一批任务，不得互相顶替；`tasks/evidence`为冻结R5证据区。schemaVersion保持r5-v1作为兼容信封，扩展字段有机器合同。解冻需新的owner明确授权。
- 2026-10-09 UI-FIRST包与20261009任务卡保留为前继记录；旧W00–W17工作分组只用于映射，不构成第二账本，不新增任务编号。
- 冻结新任务定义：当前绑定的是 `docs/history/taskpacks/20261023-adoption/TASK-DEFINITIONS.json`（owner 2026-10-23 采纳；它逐字携带 20261009 的 34 项定义并另加 16 项新派工。账本 `currentExecution.source` 只钉当前绑定的这一份的 sha256，20261009 原件仍在原位、字节未改，作为被携带定义的出处）；旧28项映射及21件任务文档/58项结构记录普查见该目录OLD-TASK-CROSSWALK.json、OLD-DOCUMENT-CENSUS.json。仅作映射/输入，不是第二账本。
- 旧20260918统一包、DeepSeek/R5任务定义原字节留在原位置，已在authority-index与task-document-states取代/冻结；正确恢复/安全/证据/Human Gate/双宿主/Golden验收并入新任务。不凭旧DONE重新宣称当前完成。
- 原始输入：`docs/history/taskpacks/20261009-inputs/ARCHIVE-MANIFEST.json`记录2原ZIP/170成员；文本/代码/SVG逐字节入档，大包/字体/位图完整存本项目`.project-local/task-artifacts/taskpacks-20261009/`（Git忽略）。不能声称Git克隆带完整视觉参考；跨机器交接须附原ZIP。
- 对话决定、旧任务取舍、批次与任务卡在`docs/taskpacks/20261009-ui-first/`；**接续入口只有一个**：`docs/current/NEXT-AGENT-PROMPT.md`（就地更新，不是独立Authority）。
  2026-10-18 之前它按日期命名，于是每轮都要铸新文件、搬一次指针，旧副本合法地留在`docs/current/`里——那正是"旧路径反复出现"的机制，已废止。历史提示词移入`docs/history/next-agent-prompts/`，逐份登记在该目录的`docs/history/next-agent-prompts/PROMPT-LINEAGE.json`。
- 当前报告仍由`scripts/generate_current_reports.py`生成；TASK_PROGRESS与PROJECT_STATUS显示当前派工区，旧证据读回保留历史身份。生成不等于执行测试；真实宿主/真人/三方/学习/发布分别记。
- 任务文档定态登记仍为`design-lab/config/task-document-states.json`，并由`verify_task_document_states.py`与现有aggregate fail-closed检查；恰好一个DISPATCH_ENTRY等于index.currentIntegrated。
- 原Record导入档案继续保留在`docs/history/record-imports-2026-10-08/`及其manifest；不批量搬迁或修改冻结原件。跨项目素材、系统数据、E/F盘均不因旧包或本轮任务整理获得访问授权。
- 20261009 owner追加授权Record中本项目资料完整归档、去重、提炼和索引。找资料先读`docs/RECORD-ARCHIVE-INDEX.md`；2026-10-09 关键信息提炼已归档到`docs/history/archive-2026-10-19/current-records/ARCHIVE-KEY-INFORMATION-2026-10-09.md`；机器来源/成员/hash/canonical登记位于`docs/history/record-archive-2026-10-09/ARCHIVE-MANIFEST.json`。相关原ZIP、素材和递归成员已保存在本项目，按hash复用既有副本/内容对象；旧manifest的EXTERNAL-ONLY是旧时点，不能再据其判断素材未归档。共享作品集/三项目容器只作惰性参考，不提升当前任务或许可。大对象在`.project-local/`且不随Git克隆，迁移须按manifest带齐；原Record不删改，既有冻结路径不删除。
- 后续新增资料必须同步来源、hash、版本/定态、别名和canonical位置，并更新固定资料索引指向最新完整清单；不能只复制文件、不登记。过时内容先更新精简阅读面和取代关系，不重写冻结原件。
- **2026-10-12 状态更正（本条取代上面 20261009 那句"本地未提交、勿宣称远端已同步"）**：归档、权威、
  索引、唯一账本与全部回执字节**已提交并已推送**到 `qoder/designlab-backup-consistency-20261007`，
  并已快进并入 `main`。当时那句是事实，现在不是；留着会让下一会话**错误地不信任远端**，
  从而重复劳动或误判同步状态。当前真实 SHA 一律用 `git rev-parse HEAD` 自读，不要抄本文任何数字。
  仍然**未**执行的是：release、安装态分发、真实宿主 E3、真人 E4、手机端（FROZEN_DEFERRED）——此处的「手机端」为 2026-10-12 当时读数，2026-10-19 已按 owner 授权移出范围，不再是待执行项。
  这些边界不因已推送而改变。
