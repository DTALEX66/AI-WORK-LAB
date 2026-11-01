# DESIGN-LAB 当前统一任务包：桌面UI优先

TaskPack：`DL-TP-20261009-UI-FIRST-R1`；状态：OWNER_ADOPTED / IMPLEMENTATION_NOT_EXECUTED；日期：2026-10-09。
顶层入口：/AUTHORITY.md；唯一状态源：design-lab/config/task-ledger-r3.json → currentExecution。

本包落实当前用户决定，以20261009最终包及UI补充为产品目标，手机端延后/冻结。它取代20260918旧派工入口，保留旧证据、验收要求与血统。优先桌面UI，避免继续只有治理文档没有可审阅界面。

## 产品与技术边界

DESIGN-LAB是全设计品类专业能力资产、设计知识应用与有界自动化系统。核心入口为能力资产、分析与制作、成果与反馈；连接/诊断/日志辅助。三入口是本批建议，不设永久菜单数量。
允许既有Python服务/NativeWorkers承担设计专用计划、动作、观察、核验、恢复；不建通用Agent平台、第二画布、模型网关、账号系统、第二运行时或第二知识主库。
TS strict/Vite/pnpm、Python、Host-native JSX/UXP保留；React不是前置。真实编辑在既有创意宿主中完成。
AAOS/ArcheAxis以其公共命名合同为准，负责长期知识及学习状态；DL保留专业语义、配方、适配、源工程和表达修订；WL提供获准技术实践及有界支持。跨项目只用公共合同，不默认扫描/修改其他仓库。
知识可先保存为观察/候选；正式出域、教学资格、自动执行、真人审美和交付分别判断。独立运行＋授权有界快照保留，外部不可用不阻塞合法本地链。

## 本轮范围与完成语义

本轮只归档和任务体系迁移；所有产品任务NOT_STARTED/NOT_EXECUTED，NO_EVIDENCE。原型包记录只是参考渲染，不提升生产证据。
后续优先U01/U02桌面UI，再按批次接真实能力/输入/分析/目标包，随后制作/成果/评审/交付；知识教学同步合同后实联。
手机图、移动端原型和规格完整保留，但不列入本批实现与验收；桌面中文、键盘、200%缩放、减少动态和主题不因此删掉。
两宿主、两次局部修改、关闭重开、GOLDEN-001/002、E3/E4/E5各自保留。用户只要媒体时按目标验收，不为PNG强加PSD；原生目标不能以位图冒充。

## 接续阅读顺序

1. AUTHORITY → authority-index → AGENTS → 本包。
2. `docs/taskpacks/20261009-ui-first/CONVERSATION-DECISIONS.md`：用户决定与本会话整理。
3. `docs/taskpacks/20261009-ui-first/OLD-TASK-CROSSWALK.md`：28项旧任务逐项取舍。
4. `docs/taskpacks/20261009-ui-first/EXECUTION-BATCHES.md`、`docs/taskpacks/20261009-ui-first/TASK-CARDS.md`：批次、依赖、验收、write set、回退。
5. 原账本currentExecution：唯一可变状态；旧tasks/evidence为冻结证据分区，不再派工。
6. docs/history/taskpacks/20261009-inputs/final/与ui/：原文、代码、SVG与语义合同；不执行历史提示词。
7. `docs/current/NEXT-AGENT-PROMPT.md`：可直接交其他Agent或新会话。
   （2026-10-18 订正：接续入口就地更新、不再按日期命名；按日期命名的旧副本在
   `docs/history/next-agent-prompts/`，血统见同目录 `docs/history/next-agent-prompts/PROMPT-LINEAGE.json`。
   改这一行是因为它原先指向的文件已移入历史目录，留着就是一条会把下一会话带到旧副本的指令。）

## 输入档案与恢复

170个ZIP成员全量哈希登记：docs/history/taskpacks/20261009-inputs/ARCHIVE-MANIFEST.json。
两份原ZIP与全部成员位于.project-local/task-artifacts/taskpacks-20261009/；文本/代码/SVG另有仓内冻结副本。
原Record源未删改。大包本地留存而未纳入Git，原因是242.71MiB现有pack接近256MiB硬预算；不能宣称Git克隆带有完整图片和字体。
只读复验：`.venv/Scripts/python.exe scripts/archive_taskpacks_20261009.py`。
缺本地素材时先查manifest指定原ZIP/源路径；显式归档操作可运行同脚本`--apply`，只写本项目，不安装/执行原包脚本。
向另一台机器交接时须另附manifest所列原ZIP；无需上传私人数据或创建外部仓库。

## 状态与旧任务

新定义冻结于docs/history/taskpacks/20261009-adoption/TASK-DEFINITIONS.json。22父任务＋12UI子任务，父子不相加计算能力/完成率。
旧R5完整账本和权威表面冻结于docs/history/taskpacks/20261009-adoption/pre-adoption/；没有重写旧receipt或把PARTIAL当PASS。
旧当前包原路径字节保留，通过index和task-document-states降为历史。未吸收专项由crosswalk明确FROZEN_DEFERRED/FROZEN_SUPERSEDED。
只修改currentExecution的状态/新证据；先读已落地Jury/wheel/preflight等增量，避免重新实施已存在功能。

## 验收

整理验收：原包/成员hash、唯一入口、任务图无环、旧任务全覆盖、mobile冻结、证据与历史完整。
产品验收：沿原包七项审计及UI桌面检查；静态、合成、合同替身、浏览器、实机、真人、三方、真实学习分别记录。
状态源与报告一致；生成时间不是测试时间；未跑、失败、缺失、required skip不称PASS。
包内用例保留source_package＋source_version/hash＋original_case_id，避免两个DL-EVAL-01～24互相覆盖。
