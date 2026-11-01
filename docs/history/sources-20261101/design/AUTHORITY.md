# DESIGN-LAB TOP-LEVEL AUTHORITY

**Authority ID:** `DL-AUTHORITY-2026-09-18-R2`  
**Status:** `TOP_LEVEL_CURRENT`  
**Repository:** `DTALEX66/DESIGN-LAB`  
**Effective date:** `2026-09-18`

> 本文件是 DESIGN-LAB 所有人类、GPT、Codex、DeepSeek、Hermes、CI/Agent 在审计、规划和修改项目时的第一权威入口。

## 2026-10-28 OWNER ADOPTION — 外部软件自动化解冻、移植包吸收、派生物清理与分支收口

本条根据 owner 2026-10-28 直接指令生效，优先于下文 2026-10-23 / 10-20 / 10-19 / 10-09 的冲突条款；Authority 稳定 ID 保留，
修订号 `AUTOMATION-20261028-R1`。Owner 原话：**「取消冻结的自动化任务  （D:\All projects\Record\新建文件夹     把这里的
内容吃透）」「前端也同步上去自动化的菜单导航等」「并行执行 项目体积清理与规范化  执行合并迁移清理等相关执行，任何过时的
陈旧的冗余的，该归档的归档 包括目录子文件夹等」**，以及选项面板内的两句范围答复（清理＝派生物＋仓库内历史归档合并＋PR #277
合并与分支收口；包＝**全部吸收融入本项目  和原先冻结的自动化任务进行合并**）。逐字转录与解释见
`docs/taskpacks/20261028-automation/OWNER-DECISION-2026-10-28.md`；投递的 9 个原件逐字节登记在
`docs/history/record-archive-2026-10-28-design-automation/ARCHIVE-MANIFEST.json`，规范本地根
`.project-local/record-archive-2026-10-28-design-automation/`。

1. **`外部软件自动化` 不再是冻结项**。下文 2026-10-23 采纳条款第 4 条与第 3 条里"外部软件自动操作属未来能力"、
   `authority-index.json` `desktopKbAdoption.stillFrozen` 中的 `EXTERNAL_SOFTWARE_AUTOMATION`，
   在本条生效的范围内被取代。这与 2026-10-19 已确立的分层工具策略不矛盾
   （`官方 API/SDK → 原生插件 → MCP → 脚本/CLI → 受控 UI 自动化` 本来就是本项目的能力面）。
2. **解冻的是能力类，不是逐次宿主操作**。每一次真启动专业软件、每一次写原生文档的动作仍走 Human Gate；
   默认状态必须是"未探测"（`NOT_PROBED`），不是"可用"。`production` 模式不得把这个 gate 设为空。
3. **交付形态未变**：本项目是专业设计知识管理、跨媒介创意方案与模型应用辅助系统，生成可交外部软件实施的专业材料；
   不建第二套 Agent／模型网关／画布／3D 编辑器／剪辑时间线，也不接管制作落地与成品交付。
   吸收外来自动化包＝在本项目内建立版本化公共合同（登记、只读投影、有界桥接客户端），**不是**把它的 runtime
   当成本项目的第二运行时。
4. **外来指令体与权利未判定素材按 inert 处置**。包内 21 份 `SKILL.md`、prompt 注册表与
   `pip install` / `npm install -g` 字样不进入根指令、prompt、工具发现或能力计数；
   `ppt-master/templates/brands/**` 那 21 个真实公司名模板与各上游组件的许可归属由 Rights gate 裁定；
   整套材料源自商业软件 JZXZ 1.1.27（含反编译 `.il.txt` 证据，上游未授予再分发许可），只登记不宣称已获授权。
5. **本包在本项目内的证据等级上限是 E1/E2**：9 个桥接器只证明"能握手并列工具"（543 条，逐条
   `nativeToolCalled:false`），包内 evidence 目录下的那份跨目录复验记录（**属包内文件，不是本仓库路径**）
   自写 `"physicalSecondComputerTested": false`，
   Grasshopper 的 HTTP URL 本轮未连通。因此不得据此声明真实宿主 E3、真人 E4 或 release。
   `windows` 桌面 UI 自动化连接器已登记但**未启用**，启用需 owner 另给明确授权。
6. **派生物清理与归档合并被授权**：`.project-local/` 内可再生的缓存/临时件按审计清单删除；
   仓库内过时件按"原字节不动、只换指针与取代关系"归档合并；PR #277 合并与分支收口由 owner 本条授权，
   且只在承载全部字节的 head 的 PR run 读回 success 之后执行。
7. **一条都没放松的其他边界**：手机端仍是排除项；三方素材与字库仍在范围外；E 盘不动；模型不锁死但默认
   fail-closed、`UNKNOWN` 不写成合格、云端选项必须披露离开本机的数据、本轮不部署模型也不自行下载权重；
   编号仍由用户填写或显式选 `UNUSED`；验收与签字仍只接受具名真人；候选导出仍是读回不是发送；AAOS 仍只是
   未来合同；release、安装态分发、真实宿主 E3、真人 E4、ComfyUI、MiniMax H3 继续冻结；
   `currentExecution` 原 34 项仍 `FROZEN_DEFERRED`；`DESIGN.md` 在 owner 真实测试前不进入已批准状态。

Authority §17 变化依据：owner intent 落仓于上文裁决件；reason=外部软件自动化解冻、外来移植包按摘要吸收、
派生物清理与 PR 收口获授权；superseded=2026-10-23 条款中"外部软件自动操作属未来能力/继续冻结"的这一项、
以及活动阅读面上"本轮不做自动化"的表述；impact=同步 AUTHORITY.md、authority-index.json（新增
`automationAdoption`）、AGENTS.md、PRODUCT_DEFINITION.md 与 `docs/current/NEXT-AGENT-PROMPT.md`，
冻结原件与历史证据字节不改写，re-pin 见 `docs/history/taskpacks/20261009-adoption/AUTHORITY-PIN-CHANGE.json`
revisions[] 末条。

## 2026-10-23 OWNER ADOPTION — 桌面 UI 与知识库进入当前派工

本条根据 owner 2026-10-23 直接指令生效，优先于下文 2026-10-20 / 10-19 / 10-09 的冲突条款；Authority 稳定 ID 保留，
修订号 `DESKTOP-KB-20261023-R1`。Owner 原话：**「读取分析，按照这个执行（前端UI有新规划），并且归档到统一项目里，
更新覆盖替换到权威和规划里」「先分析拆解，加入到优先到任务台账里」**。逐字转录与解释见
`docs/taskpacks/20261023-ui-kb/OWNER-DECISION-2026-10-23.md`；来源投递包 17 名成员逐字节入仓，摘要与 ZIP 原件登记在
`docs/taskpacks/20261023-ui-kb/SOURCE-MANIFEST.json` 与 `docs/history/record-archive-2026-10-23/ARCHIVE-MANIFEST.json`。

1. **当前唯一 integrated TaskPack** 改为 `docs/taskpacks/DESIGN-LAB-DESKTOP-KB-INTEGRATED-TASKPACK-2026-10-23.md`
   （`DL-TP-20261023-DESKTOP-KB-R1`）；`DL-TP-20261019-DIRECTION-R1` 降为 `SUPERSEDED / LINEAGE`，原字节与其中对定位、
   范围、冻结面的裁定继续有效，只停止"唯一派工入口"这一身份。
2. **桌面 UI 进入当前派工**：三个日常入口——设计辅助／知识与提示词库／我的方案——外加设置；不换栈，仍在
   `apps/workbench` 的 Vanilla TypeScript + Vite 与 `src/design_lab` 的 Python 服务上。`DL-KB-01`…`DL-KB-16` 是唯一新增
   派工段，按批次 K0…K8 顺序执行：知识管理与中文检索 → 中立方案与目标档案/导出 → 一个方案助手模型的真实接入 →
   内容方法与反馈。
3. **定位按本包采纳**：面向职业设计的**专业设计知识管理、跨媒介创意方案与模型应用辅助系统**，覆盖平面/品牌/UIUX/
   3D/2D 动效/粒子/视频/音频/短剧/漫剧/小说/广告/说唱。本项目生成可交外部软件实施的专业材料，不负责制作落地与成品
   交付，不建第二套 Agent／模型网关／画布／3D 编辑器／剪辑时间线；外部软件自动操作属未来能力。
   （本句是 2026-10-23 当日原文，保留不改写；其中"外部软件自动操作属未来能力"已由上文 2026-10-28
   采纳条款在**能力类**层面取代——它现在进入当前派工，但逐次宿主操作、真启动与写原生文档仍走 Human Gate，
   默认状态是 `NOT_PROBED`。）
4. **一条都没放松**：手机端仍是排除项；三方素材与字库仍在范围外；模型不锁死但默认 fail-closed、显式选择只是被记录、
   `UNKNOWN` 不写成合格、云端选项必须披露离开本机的数据、**本轮不部署模型也不自行下载权重**；编号仍由用户填写或显式
   选择"不使用"；验收与签字仍只接受具名真人；候选导出仍是读回不是发送；AAOS 仍只是未来合同而非依赖或门；E 盘不动；
   release、安装态分发、真实宿主 E3、真人 E4、ComfyUI、MiniMax H3 继续冻结，`currentExecution` 原 34 项不在本条解冻。
5. **既有 `executed=false` 合同不得为"通过"而解除**：真实推理必须走新的运行记录与版本演进，选择成功、连接成功、
   返回文本、内容可用四件事分别验证；新登记的界面必须映射真实 API，不以效果图宣称接通。

Authority §17 变化依据：owner intent 落仓于上文裁决件；reason=前端 UI 新规划入派工、方案包归档、权威与规划覆盖替换；
superseded=`DL-TP-20261019-DIRECTION-R1` 的唯一派工入口身份，以及活动阅读面上"本轮只做文档、不动前端"的表述；
impact=同步 AUTHORITY.md、authority-index.json、AGENTS.md、PRODUCT_DEFINITION.md、NEXT-AGENT-PROMPT.md、
task-document-states、唯一账本 `currentExecution` 与其定义原件，冻结原件与历史证据字节不改写，re-pin 见
`docs/history/taskpacks/20261009-adoption/AUTHORITY-PIN-CHANGE.json` revisions[] 末条（checks 仍为 10）。

## 2026-10-20 OWNER ADOPTION — 定点解冻与范围收口

本条根据 owner 2026-10-20 直接指令生效，优先于下文 2026-10-19 / 2026-10-09 的冲突条款；Authority 稳定 ID 保留，
修订号 `UNFREEZE-20261020-R1`。Owner 原话：**「1 可以做」「大模型可以 但为什么要锁死呢？不锁死 做好菜单导航和接口
用户自行选择本地或者是云端模型」「编号问题留出可填写位置，用户自行填写或者选择用没用」「三方素材和字库不在本项目
范围内」「现在都没有真实测试过呢 怎么批准 …设计规范按照网上最专业的先收入库里 后期落地我自行测试」
「手机端不是冻结 是不做了」「E盘不动」**。逐字转录与解释见
`docs/taskpacks/20261020-unfreeze/OWNER-DECISION-2026-10-20.md`（会话内指令，无外部包、无源哈希，不得虚构）。

1. **定点解冻（产品实施）**：下文 2026-10-19 的"本轮不实施产品功能"在且仅在三段上被取代——
   **Prompt Intelligence 入口**（提示词生成与反推可调用）、**候选导出出口**（把 `src/` 内零调用者的
   `export_payload` / `to_v1_projection` 接到真实调用方）、**模型选择接口**（菜单导航 + 接口，用户自选本地或云端）。
   `currentExecution` 其余 34 项仍 `FROZEN_DEFERRED`；release、安装态分发、真实宿主 E3、真人 E4、ComfyUI/H3 继续冻结，
   解冻仍需 owner 新的明确授权。
2. **模型选择的读法**：不锁死取消的是"把用户挡在选择之外"，**不是**取消 fail-closed 的默认值。
   `AGENTS.md` 的 `UNQUALIFIED_*` 默认 `defaultEnabled: false` 与零 checksum/许可冲突/模型缺失/硬件不足必须 fail closed
   不变；用户的显式选择是一次被记录的用户动作，不改变合格状态、不把 `UNKNOWN` 写成合格、不宣称推理已验证；
   云端选项必须写明哪些数据离开本机。选择面呈现"可选 + 现状 + 后果"，合格判定仍只在真实取证后由 owner 验收。
3. **编号交给用户**：`source.job_id` / `operation_id` 由界面提供可填写位置并允许显式选择"不使用"；
   代理不得自行铸造标识并当作来源证据展示。
4. **三方素材与字库移出范围**：字体库与第三方素材的权利判定不再是缺口、待办或阻塞依赖；不变的是既有边界
   （不默认上传客户素材、不持有用户素材库、E 盘受保护）。活面若仍列为缺口，按本条改写。
5. **设计合同批准权后置**：`DESIGN.md` 在 owner 真实测试前不进入已批准状态；先把业界最专业的设计规范收入库内作参考。
   逐条配色归属与品牌蓝裁定因 owner「我现在看不见」而挂起，**不是开工前提**，不得反复请示。
6. 手机端重申为**排除项**（非冻结、非待办、非缺口）；AAOS 仍不是依赖或门，只保留标准、通用、版本化公共接入接口。

Authority §17 变化依据：owner intent 落仓于`docs/taskpacks/20261020-unfreeze/OWNER-DECISION-2026-10-20.md`；
reason=三段产品实施定点解冻与范围收口；superseded=2026-10-19 条款中"不实施产品功能"的普遍禁止、
以及把字体、三方素材权利判定当作项目缺口的活面表述；impact=同步 AUTHORITY.md、authority-index.json、
AGENTS.md、PRODUCT_DEFINITION.md、NEXT-AGENT-PROMPT.md 五面，冻结原件与历史证据字节不改写，re-pin 见
`docs/history/taskpacks/20261009-adoption/AUTHORITY-PIN-CHANGE.json` revisions[] 末条（checks 仍为 10）。

## 2026-10-19 OWNER DIRECTION ADOPTION — VISUAL DESIGN LAB

本条根据 owner 2026-10-19 直接指令生效，优先于下文 2026-10-09 / 0918 的冲突条款；Authority 稳定 ID 保留，修订号 `DIRECTION-20261019-R1`。
Owner 原话：**其他任务冻结，以这份任务为当前权威与闭环目标（更新项目内的权威和规划），未来能力暂时冻结和延期延后**。
当前唯一 integrated TaskPack：`docs/taskpacks/DESIGN-LAB-DIRECTION-ALIGNMENT-2026-10-19.md`（`DL-TP-20261019-DIRECTION-R1`）。2026-10-09 UI-FIRST 包降为 `SUPERSEDED / LINEAGE`；其 `currentExecution` 34 项任务全部 `FROZEN_DEFERRED`，不再派工；原字节、定义、历史证据保留。
（上文"当前唯一 integrated TaskPack"与"不再派工"是 2026-10-19 当日原文，保留不改写。2026-10-23 起当前入口是
`DL-TP-20261023-DESKTOP-KB-R1`，本包降为血统；"不再派工"仍只对那 34 项成立——owner 同日在 `currentExecution`
加入了 16 项新派工，两者不是同一批任务，不得互相顶替。）
正式定位：面向职业视觉设计的 AI 原生、平台中立的**专业视觉智能与可复用设计能力系统**。产品本体是视觉智能 + 审美能力工程化 + 设计能力库 + 设计软件自动化 + 受控知识回流。六大能力域：Visual Intelligence / Aesthetic Analysis / Prompt Intelligence / Design Capability Library / Creative Tool Automation / Knowledge Candidate & Evaluation。
永久非目标：第二画布或通用编辑器、以全流程设计文件制作交付为产品本体、通用 Agent Runtime / 聊天客户端 / 模型网关 / 跨项目调度器；不接管 WORK-LAB 通用治理，不取代 AAOS 正式知识真源，不把热门资源或模型输出直接认定为合格能力或可信知识。
模型策略：本地/云端/混合，可替换、按能力与隐私/成本/延迟路由；模型输出是候选判断。工具策略：官方 API/SDK → 原生插件 → MCP → 脚本/CLI → 受控 UI 自动化；握手、HTTP 200、退出码或截图不等于真实任务验证。
本轮只做权威/规划对齐、冲突矩阵、能力映射、技术可行性矩阵、最小真实闭环规划与按范围测试；**不实施产品功能**。文档修订 ≠ 规划完成 ≠ 代码实现 ≠ 真实运行 ≠ 人工验收 ≠ AAOS 接收。
（本句是 2026-10-19 规划轮的原文，保留不改写；其中"不实施产品功能"的普遍禁止已由上文 2026-10-20 采纳条款在
Prompt Intelligence 入口、候选导出出口、模型选择接口三段上取消，其余仍按本句执行。）
未执行且继续冻结：release、安装态分发、真实宿主 E3、真人 E4、ComfyUI/H3。AAOS 已从冻结清单移出——它不是本项目依赖或门（owner 2026-10-19）。项目目标（owner 2026-10-19）：DESIGN-LAB 按**独立可运行、全链路可跑通**的项目标准推进——视觉输入 → 分析/提示词生成或反推 → 可验证输出或合格工具调用 → 用户/授权 Agent 验收 → 知识候选在本项目内留存。AAOS 不是本项目的依赖、闸门或待排期联调项；保留的是标准、通用、版本化的公共接入接口（Schema/API/Manifest 合同与 `KnowledgeCandidate` 出口），外部知识系统能通过合同连接，但本项目不等待其联调结果才宣布闭环成立。手机端已从范围移除（owner 2026-10-19 授权：「再说一遍 不做手机端 只做桌面端」「授权给你 去掉手机端」）：它不是待办、不是能力缺口、也不是待排期项；恢复需 owner 新的明确授权。
Authority §17 变化依据：owner intent 落仓于 `docs/taskpacks/20261019-direction/OWNER-DECISION-2026-10-19.md`；reason=定位纠正与全域冻结；superseded=2026-10-09 UI-FIRST 派工入口及其当前任务派工；impact=索引/根规则/产品定义/边界/路线图/manifest/task-document-states/唯一账本状态同步，旧文件与证据冻结。

## 2026-10-09 OWNER ADOPTION — UI FIRST（2026-10-19 起降为前继记录）

本条根据owner当前直接请求生效，优先于下文20260918/0927的冲突条款；Authority稳定ID保留，修订号UI-FIRST-20261009-R1。
（以下两句是 2026-10-09 当日原文，保留不改写；当前入口见上文 §17 与本节标题——2026-10-19 起本包为前继记录；本段的「手机端本轮不做」已被 §17 的范围条款取代：手机端是排除项，不是待排期项。）当时唯一integrated TaskPack：`docs/taskpacks/DESIGN-LAB-UI-FIRST-INTEGRATED-TASKPACK-2026-10-09.md`（`DL-TP-20261009-UI-FIRST-R1`），现由 `DL-TP-20261019-DIRECTION-R1` 取代。旧20260918包与R5/DeepSeek血统停止派工，原字节及证据保留。
新目标以20261009最终包＋UI补充为准；手机端本轮不做，FROZEN_DEFERRED；桌面UI先行。当前定义与解释见PRODUCT_DEFINITION、docs/taskpacks/20261009-ui-first/CONVERSATION-DECISIONS.md及新包。
允许现有Python/NativeWorkers的设计专用规划/执行/核验/恢复；仍禁止通用Agent平台、第二运行时/画布/模型网关。能力资产/分析制作/成果反馈是主旅程，旧Workbench技术路径保留，不锁永久菜单数量。
唯一可变状态仍在design-lab/config/task-ledger-r3.json；currentExecution为当前派工区，原R5 tasks/evidence冻结证据区。旧生成器/部署副本须显示这个区分，禁止旧任务复活。
当前整理仅建立任务体系，不实施UI/宿主、不提升E3/E4/E5。旧安全/数据边界/真实证据/Human Gate/双宿主/Golden守卫保留。
未来安装/付费/跨仓/宿主副作用/公开发布/commit/push/merge仍由接收会话实际授权判断。
Authority §17变化依据：owner intent落仓于docs/taskpacks/20261009-ui-first/CONVERSATION-DECISIONS.md；reason=新任务采纳/UI优先；superseded=旧派工入口与冲突导航/目标条款；impact=索引/根规则/manifest/唯一账本/报告/校验同步，旧文件与证据冻结。
**2026-10-12 状态更正**：本行原记 `repository commit=NOT_EXECUTED, live CI=NOT_EXECUTED`，且下一行称
"尚未提交/推送"。两条**当时为真，现已失效**——归档、权威、索引、账本与回执字节已提交、已推送并快进并入 `main`。
保留原句并标注时点，是因为它记录了 2026-10-09 的真实状态；直接删掉会让后来者以为这段变更从未被提交过。
**当前 SHA 与 CI 结论一律自读**（`git rev-parse HEAD` / `gh run list`），不要沿用本文任何数字。
仍未执行：release、安装态分发、真实宿主 E3、真人 E4、手机端。（本行是 2026-10-12 当时的读数，保留不改写；其中「手机端」已于 2026-10-19 按 owner 授权移出范围，见上文 §17。）

---

以下正文保留为既有Authority及历史快照；冲突之处由上面的owner条款替代。

## 0. 云端审计强制启动顺序

每次“审计云端 / 重新审计 / 全量审计 / 检查漂移”必须先读**实时远端仓库**：

1. `/AUTHORITY.md`
2. `/.project/governance/authority-index.json`
3. `/AGENTS.md`
4. Authority Index 指定的当前 Product/Boundary/Architecture 文档
5. 当前 TaskPack 与机器 Ledger
6. GitHub 实时 `main`、Open PR/head、exact SHA、branch protection
7. 最新 CI jobs / artifacts
8. `reports/current/**`（仅在 freshness 校验后）
9. 历史 crosswalk/history（只用于解释血统，不用于覆盖当前权威）

Memory、聊天摘要、handoff、旧 TaskPack、旧 report、branch 名称、commit 数量，都不能单独成为当前 Authority。

每份云端审计必须写明实际读取的 exact SHA。

## 1. 项目身份

DESIGN-LAB 是 **AI-native、Agent-platform-neutral、host-native 的职业视觉设计智能与生产能力层**。

拥有：Brief、ReferenceSet、Research/Methods、Direction、Design System、Design IR、Domain Pack、Quality/Critique/Jury、rights/preflight、Host/Tool/Generator Adapter、editable delivery、BOM、provenance、readback、rollback、evidence。

不拥有：第二 Photoshop/Figma/Blender、通用聊天、通用 Agent Runtime/Model Gateway、WORK-LAB 全局治理、ArcheAxis 长期知识真值、宿主私有数据库。

Open Design = 可选 Host Adapter；MiniGame = game-visual fixture/domain，不是产品线。

## 2. 产品完成语义

能力必须分轴记录：

`CONTRACT / BACKEND / FRONTEND / PERSISTENCE / HOST_OR_GENERATOR / READBACK / QUALITY / RIGHTS / PREFLIGHT / DELIVERY / EVIDENCE`

Backend-only 只能叫 `BACKEND_IMPLEMENTED`，不得叫 `PRODUCT_COMPLETE`。

默认研发单位：

`Workbench -> Contract/API -> Python Design Engine -> State -> Host/Generator -> Readback -> Quality -> Preflight/Handoff`

除真实 blocker 外，不允许连续多个产品 Wave 只扩治理/后端而没有用户可见设计进展。

## 3. 前端权威

DESIGN-LAB **有前端**：`apps/workbench/`。

Workbench 是用户可见设计控制面：Projects、Brief、References、Research、Directions、Design System、Create/Production、Versions、Review/Jury、Preflight、Handoff、Evidence。

它不是第二通用画布。真正原生编辑仍在 Photoshop、Illustrator、Figma、Blender 等专业 Host。

前端技术权威：TypeScript；目标为 strict TypeScript + Vite + pnpm + browser E2E。React/Vue/Electron/Tauri/Avalonia 只有明确需求 + ADR 才可引入。Raw RIR/Patch/Styles JSON 归 Advanced/Developer Mode。

## 4. 后端权威

Python 继续负责 orchestration、runtime/state、creative/design services、providers、reconstruction、QA/preflight、CLI/HTTP、analysis。

优先扩展 `src/design_lab/` 与 `src/design_lab/creative/`，禁止创建平行 v2 runtime，也不进行 Rust/C#/Go/Java 全仓重写。

## 5. Host/Tool 权威

Adapter 生命周期：`probe -> prepare -> execute -> observe/readback -> failure/recovery -> rollback`。

Adobe 继续使用 host-native JSX/UXP。静态 Adapter 存在只能证明 E1，不等于真实 Host E3。

## 6. Evidence 权威

- E0 DECLARED
- E1 STRUCTURAL
- E2 CONTROLLED_RUNTIME
- E3 REAL_WORKFLOW
- E4 INDEPENDENT_ACCEPTANCE
- E5 RELEASED/REPEATABLE

历史证据不能自动提升新的 SHA/Host/Adapter/Tool 版本。

## 7. 仓库责任

- `apps/`：runnable frontend
- `src/design_lab/`：Python runtime
- `packages/`：可复用能力/协议
- `integrations/`：Host/Tool/Model/Agent 边界
- `design-lab/`：内容/config/schema/domain/eval/production/template/test，**不是第二 Runtime**
- `fixtures/`：fixture/regression
- `research/`：intake/research
- `vendor/`：审阅后的最小第三方来源
- `docs/`：current authority + history
- `reports/`：projection/evidence index，低于 live code/CI
- `scripts/`：repo tooling
- `.project/`：tracked policy/governance
- `.project-local/`：唯一 active runtime/state/cache/artifact/log root

`.hermes` 不是 DESIGN-LAB 活跃写入根。禁止为了目录好看做全仓暴力搬迁。

## 8. 语言权威

- Python >=3.11：backend/runtime/QA/provider/reconstruction/CLI
- Canonical CI 可用 Python 3.12
- TypeScript：Workbench/Web/IPC/MCP client
- Host-native JS/JSX/UXP：宿主自动化
- JSON/JSON Schema：跨语言 contract truth
- SQL/SQLite：local state
- Shell/PowerShell：thin launcher
- Rust：NOT_PRIMARY，仅 benchmark + ADR 后的有界性能 helper

当前 Ruff 事实：`CONFIGURED_NOT_ENFORCED`。下层文档中仍写 `DECLARED_NOT_ENFORCED` 的单句属于 stale wording，应修正但不改变本 Authority。

## 9. REUSE / Source / Rights

原则：REUSE-FIRST / OPEN-SOURCE-FIRST / PLUGIN-FIRST / LOCAL-FIRST WHEN POSSIBLE。

第三方来源最终必须进入：`ABSORBED / REFERENCE_ONLY / REJECTED / DEFERRED`。

登记不等于吸收。ABSORBED 必须有 source/revision/license/mapping/destination/implementation/tests/evidence/rollback。Unknown rights 不得 production-certify。

## 10. Branch 权威

收口后 `main` 是唯一长期正式代码真值。FINAL/AUTHORITY/R4/MIGRATION 等 branch 名称没有天然权威。

历史 diverged branch 按语义分类：`ABSORBED / PARTIAL_ABSORBED / REIMPLEMENT / SUPERSEDED / HISTORICAL_ONLY / REJECTED / ACTIVE_RESIDUAL`。

禁止因为 unique commits 直接 whole-merge 旧 R4 governance、directory migration 或 UXP branch。

Merge/delete/release/force-push 仍属于 owner-authorized destructive actions。

## 11. 历史记录权威

所有审计必须服从 `/.project/governance/authority-index.json`：

`CURRENT / CURRENT_BUT_DRIFTED / PROJECTION / SUPERSEDED / HISTORICAL / REFERENCE / NON_AUTHORITATIVE`

**Handoff 永远不是顶层 Authority。** 它只记录时间点执行状态，后续 merge/branch/CI 可立即使它过时。

PR #120 的 UCR 收口交接（原件已按 owner 2026-10-19 指令删除；分类结论与它独有的事实汇总在 `docs/history/archive-2026-10-19/AGGREGATED-RECORD-2026-10-19.md`，逐份 blob/字节/恢复命令登记在 `docs/history/archive-2026-10-19/REMOVALS.json`，可用 `git show <restoreAt>:<原路径>` 还原原始字节）明确分类为 `HISTORICAL_EXECUTION_RECORD`；即使文件自己写“tracked 权威交接”，也不得覆盖本 Authority。

未来 GPT 不得因为某个旧文档更详细，就拿它重建当前架构。

## 12. 执行血统

顶层 Authority：本文件。

保留血统：
- `DL-TP-20260908-R5`：产品血统
- `DL-TP-20260914-DEEPSEEK-AUTHORITY-R1`：结构/治理前序
- `DL-TP-20260917-BRANCH-CONVERGENCE-R1`：分支收口前序

本轮统一剩余任务入口（落仓后）：
`docs/taskpacks/DESIGN-LAB-FINAL-AUTHORITY-CONVERGENCE-TASKPACK-2026-09-18.md`

旧任务 ID 必须经 crosswalk/current-capability 映射后才可执行。

## 13. Authority 建立时的云端已核实基线

实时读取到：`main@0e9f687ca306226f984f9ac49d222c0d8ff8a1e5`。

已核实：
- PR #116 已 MERGED；旧 head `fc4aa0f775c102d18365c386fe712b42fd9d018a` 不再是当前产品真值
- PR #120 已 MERGED 到当前 main
- main 已 protected
- main 当前 required checks 包含 Python、MiniGame、generated-artifact、license/secret、Open Design structural；**未包含 DeepSeek Authority gate**
- Canonical Verify `35289564056` / #182 对 `0e9f687ca306226f984f9ac49d222c0d8ff8a1e5` = SUCCESS
- run #182 Actions artifacts = 0
- 当前 main 尚无 `/AUTHORITY.md`
- 当前 `AGENTS.md` 仍把 2026-09-14 DeepSeek 包写为 current DeepSeek authority
- 当前 `apps/workbench/` 仍只有 `index.html / main.ts / style.css`
- 建立 Authority 时实时远端 branch 数 = 28（仅 snapshot，永远不得作为静态权威）

以后必须重新实时读取这些动态事实。

### 13.1 动态事实的最新 live 读回（不是 Authority 变更，是对 §13 快照的刷新）

> §13 是 **Authority 建立时**的历史快照，保留原文不改写。以下为**重新实时读取**的结果，
> 用于避免读者把 §13 的旧值当成当前事实。动态事实**永远以每次审计的 live 读回为准**。

- 观察时间：`2026-09-27`；观察 exact SHA：`634071f3c8ffa87e08fa1386f49c185ff6fa36d8`（`main` = `origin/main`）
- main required checks = **9 项**（`gh api /repos/DTALEX66/DESIGN-LAB/branches/main/protection` 实读）：
  Python gate、MiniGame node gate、Generated-artifact clean-tree gate、License & secret hygiene gate、
  Open Design host adapter gate、Top-level Authority consistency gate、Workbench strict-TS product gate、
  Workbench browser E2E、DeepSeek authority gate chain
  （相对 §13 的变化：**已包含** DeepSeek Authority gate，并新增 Workbench strict-TS 与 Workbench browser E2E）
- 远端分支数 = **1**（仅 `main`）；open PR = **0**（§13 建立时为 28）
- `apps/workbench/` = **10 个文件**（§13 建立时仅 `index.html / main.ts / style.css`）
- 最近合并：PR #173（`2026-09-27T14:40:41Z`）→ #172 → #171 → #170 → #169
- 以上仅为该时刻读数；下一次审计必须重新 live-read。

## 14. 已关闭且禁止无证据重开的事项

当前 main 已核实：
- ACTIVE `ARCHITECTURE.md` 已对齐当前真实目录
- product-manifest version 已对齐 `0.1.0-alpha.0`
- Product Definition / Boundary 路径已修
- `/api/task-preflight` 已使用 URL parser + 正确 `.runtime` import
- FA-03 report-truth、FA-05 zero-spill 已在 UCR 收口并应以 regression guard 维护
- current-report truth 已改向 input/tree-digest 语义

这些属于 `CLOSED_WITH_REGRESSION_GUARD`，不得继续当成待实现 P0 重做。

## 15. 当前剩余工作

### P0 — Authority/防漂移 [CLOSED_WITH_REGRESSION_GUARD 2026-09-20]
> 全部 9 项已在 main 落地（逐项证据见下），不得再作为待实现 P0 重做。
> 守卫：`scripts/verify_top_level_authority.py`（CI `canonical-verify.yml` 第 116 行）+ main required check
> `Top-level Authority consistency gate (DL-AUTHORITY-2026-09-18-R2)`。
1. 落仓 `/AUTHORITY.md` — CLOSED（本文件；R2 byte-pin `49e21069…`）
2. 落仓 authority-index — CLOSED（`.project/governance/authority-index.json`）
3. 修改 `AGENTS.md`，Authority 强制第一读 — CLOSED（`AGENTS.md` MUST READ FIRST；verifier check `agents-authority-first` PASS）
4. 落仓统一最终 TaskPack — CLOSED（`docs/taskpacks/DESIGN-LAB-FINAL-AUTHORITY-CONVERGENCE-TASKPACK-2026-09-18.md`）
5. 分类/冻结所有 active-looking 历史文档/TaskPack/Handoff — CLOSED（index `historicalGlobs` + `historicalSpecific` + `taskpackClassificationRule`）
6. 将 PR #120 Handoff 首屏明确标为 HISTORICAL/NON_AUTHORITATIVE — CLOSED（原件首屏 banner；该文档已按 owner 2026-10-19 指令删除，恢复句柄见 `docs/history/archive-2026-10-19/REMOVALS.json`）
7. 接入现有 authority-chain，不建第二 ledger — CLOSED（`scripts/deepseek_authority_chain.py` + `reports/current/DEEPSEEK-AUTHORITY-CHAIN.json`）
8. 新增 Authority/index consistency verifier — CLOSED（`scripts/verify_top_level_authority.py`，10 checks）
9. main required checks 加入 Authority gate — CLOSED（gh 读回 main protection：含 `Top-level Authority consistency gate (DL-AUTHORITY-2026-09-18-R2)`；该门禁落地时为 7 项，截至 §13.1 观察时点为 9 项）

### P0 — Frontend [CLOSED_WITH_REGRESSION_GUARD 2026-09-20]
> 守卫：main required check `Workbench strict-TS product gate (taskpack 12.2/12.3/12.4/12.5)` + `git diff --exit-code -- apps/workbench/build` + `design-lab/scripts/verify_workbench_packaging.py`。
- strict TypeScript product workspace — CLOSED（D003：`apps/workbench/main.ts` strict TS）
- pnpm 单一产品依赖真值 — CLOSED（`pnpm-workspace.yaml` + `pnpm-lock.yaml`）
- Vite build — CLOSED（`apps/workbench/build/main.js`，构建产物受 `git diff --exit-code` 守卫）
- browser E2E — CLOSED（`workbench-browser-e2e` job + `design-lab/tests/e2e/browser_design_layer_e2e.mjs`；P0-G 已加入证据 JSON 与 artifact 上传）
- 独立 Workbench CI gate — CLOSED（main protection 含 Workbench strict-TS gate；截至 §13.1 观察时点 required checks 共 9 项）
- built resources 正确 package — CLOSED（pyproject force-include + P0-H wheel 隔离安装态完整纵切验证）
- 默认 UI 不再 JSON-centric — CLOSED_WITH_REGRESSION_GUARD（Workbench 面板/选择器交互；**残留**：无人工视觉验收记录，属 E4）

### P0 — 第一条全栈设计 Vertical Slice [CLOSED_WITH_REGRESSION_GUARD 2026-09-20]
`Project -> Brief -> Reference -> Direction -> DesignSystem` 已贯通 Workbench/API/Python backend/state/readback/evidence：
E-SLICE-01（PR #123/#124）+ 不变量修复（Reference 资产校验、DB 级单选择不变量、`constraints` 对称序列化、`active_binding` 跟随当前 chosen、方向级 partial unique index）。
守卫：`design-lab/tests/test_design_layer_http.py`（18 用例）、浏览器 E2E、`verify_workbench_packaging.py`。
**残留**：Reference → DesignIR → 可编辑产物链路未接入；真实 Host E3 / 人工 E4 未做（见下 P1）。

### P1 — Native production / quality / delivery
- DesignSystem -> DesignIR -> Photoshop/Illustrator
- editable artifact/readback/patch/recovery
- Automated Quality 与 Human Jury 分离
- Rights/Preflight/Handoff
- real Host E3
- independent/human E4

### P1 — CI/Evidence
- 如需要 artifact proof，必须真实 upload/query/download/hash — 部分 CLOSED（`workbench-browser-e2e` 已真实上传浏览器 E2 证据 JSON + 失败截图：固定 SHA 的 `upload-artifact` + `if-no-files-found: error`）；其余 release claim 仍须逐项证明
- run #182 无 artifact，不能冒充 artifact readback — 保留（记录性事实，非待办项）
- 修 LANGUAGE-POLICY 中残留 `DECLARED_NOT_ENFORCED` 单句 — CLOSED（tracked `docs/architecture/LANGUAGE-POLICY.md` 已无该串；`verify_top_level_authority.py` stale-wording check 守卫）
- Ruff 是否真正 enforce 单独决策，不重开全语言迁移 — OPEN（决策未做）
- Workbench gate 建成后加入 required checks — CLOSED（main protection 已含 Workbench strict-TS gate；截至 §13.1 观察时点 required checks 共 9 项）

### P1 — Branch cleanup
实时重读 branch。合并后的 UCR 短分支与旧 candidate 进入 cleanup candidate；旧 S2/S3 继续 semantic residual/equivalence 检查。远端删除仍需 owner 授权。

## 16. 未来 GPT 云端审计协议

1. fetch live main
2. fetch open PR/head
3. fetch AUTHORITY
4. fetch authority-index
5. fetch AGENTS
6. fetch current TaskPack/Ledger
7. fetch latest CI/artifacts
8. fetch branch protection
9. compare to Authority
10. history only via index/crosswalk
11. report exact SHA(s)
12. never memory-only current state

## 17. Authority 修改规则

修改本 Authority 必须有：owner intent、reason、superseded rule、impact note、repository commit、authority-index update、必要 CI/readback。

**END — DL-AUTHORITY-2026-09-18-R2**
