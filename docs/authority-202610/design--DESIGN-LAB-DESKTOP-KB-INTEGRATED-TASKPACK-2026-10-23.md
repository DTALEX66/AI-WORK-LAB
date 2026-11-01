# DESIGN-LAB 桌面知识库与方案助手 一体化任务包

- 包编号：`DL-TP-20261023-DESKTOP-KB-R1`
- 采纳日期：2026-10-23（owner 会话内指令，见 `docs/taskpacks/20261023-ui-kb/OWNER-DECISION-2026-10-23.md`）
- 来源包：`docs/taskpacks/20261023-ui-kb/SOURCE-MANIFEST.json`（17 名成员逐字节入仓，ZIP 原件摘要与本地规范副本一并登记）
- 落仓时观察 HEAD：`efa5a8afb7e9b04bd05c7b6ad96f9872d46e4823`（作者包内基线为 `2d6ede51cd0f49e9b99c27f09924a0db29843b89`，那是作者观察时点，不是本包落仓时点）
- 唯一交付面：桌面端。手机端是排除项。

## 0. 本包取代什么，不取代什么

取代：`DL-TP-20261019-DIRECTION-R1` 作为**唯一派工入口**的身份。该包原字节不动，降为前继血统（`docs/taskpacks/DESIGN-LAB-DIRECTION-ALIGNMENT-2026-10-19.md` 的定态改为 SUPERSEDED/LINEAGE，并在 `authority-index.json` 的 `taskpackClassificationRule.lineage` 里登记）。`DL-TP-20261009-UI-FIRST-R1` 与 `DL-TP-20260914-DEEPSEEK-AUTHORITY-R1`、R5 血统同样保持血统身份，不复活旧派工。

不取代：owner 2026-10-20 的定点解冻清单与范围收口（`unfreezeAdoption` 逐条继续有效），以及下面第 3 节逐字重述的边界。

不改变的账本事实：`currentExecution` 原有 **34 项**父/子任务**仍全部 `FROZEN_DEFERRED`**。本包不是对这 34 项的解冻，而是新增一段派工：同一个 `currentExecution` 里新派工 **16 项**（`DL-KB-01`…`DL-KB-16`），定义逐字落在 `docs/history/taskpacks/20261023-adoption/TASK-DEFINITIONS.json`，状态只写在 `design-lab/config/task-ledger-r3.json`。新段落与旧段落共用同一个 `currentExecution`、同一份唯一账本，不建第二账本、不建第二状态源。

## 1. owner 逐字指令（2026-10-23）

> 读取分析，按照这个执行（前端UI有新规划），并且归档到统一项目里，更新覆盖替换到权威和规划里

随后（同会话）：

> 先分析拆解，加入到优先到任务台账里，梳理本对话所有内容，给我完整提示词，我去开启新会话

指令效力解释：前端 UI 从「本轮不动一行」变为**当前主交付面**；归档、权威与规划的覆盖替换、台账派工是同一指令的组成部分。指令**没有**取消第 3 节任何边界，**没有**授权 release、装机分发、真实宿主 E3、真人 E4、外部软件自动化、AAOS 联调或模型部署。

## 2. 定位（本包采纳的产品定义）

DESIGN-LAB 是覆盖品牌、平面、UI/UX、3D、2D/3D 动效、粒子、视频与音频的**专业设计知识管理、创意方案与模型应用辅助系统**。它整理与更新设计规范、审美方法、叙事与视听语言、提示词、模型与软件使用指南及实践案例；按用户的内容、目标、参考资料与所选工具组合，给出有依据的分析、重构方向、专业方案、脚本分镜、声音设计、提示词、参数建议与外部执行说明。

用户决定采用、修改、试用或放弃；外部软件、Agent 与模型实施制作。本项目不承担制作落地、成品交付与发布，不建第二套 Agent、模型网关、画布、3D 编辑器或剪辑时间线。生成交接脚本不等于运行该脚本。

可验证价值：**知识找得到、依据看得懂、方案有专业内容、输入能适配目标工具、材料可以带走、旧版本可追溯、用户反馈能用于修正方法**。没有外部结果时只写「方案已提供／未验证」。

## 3. 不变边界（逐字重述，不得再被反复请示）

- 「再说一遍 不做手机端 只做桌面端」——手机端是**排除项**，不是待办、不是缺口、不是待排期。桌面自适应布局（`apps/workbench/style.css` 媒体查询）不等于手机交付。
- 「三方素材和字库不在本项目范围内」——字体库与第三方素材的权利判定不作为缺口或开工前提。既有边界不变：不默认上传客户素材、不持有用户素材库。
- 「不锁死 做好菜单导航和接口 用户自行选择本地或者是云端模型」——默认值 fail-closed 与「用户能不能选」是两件事；显式选择是一次被记录的动作，不改合格状态、不把 `UNKNOWN` 写成合格、不宣称推理已验证；云端选项必须写明哪些数据离开本机。
- 「编号问题留出可填写位置，用户自行填写或者选择用没用」——外部 `source.job_id` / `operation_id` 由界面提供填写位并允许显式选择「不使用」（字面量 `UNUSED`）；代理不得自行铸造标识并当作来源证据。
- 「E盘不动」——E 盘受保护，无精确授权不得访问。
- 「现在都没有真实测试过呢 怎么批准」——验收仍是具名真人；本机与云端都不例外。导出仍是读回，不是发送。
- 「设计规范按照网上最专业的先收入库里 后期落地我自行测试」——`DESIGN.md` 在 owner 真实测试前不进入已批准状态；逐条配色归属与品牌蓝裁定是挂起项，不是阻塞项。
- 继续冻结：release、安装态分发、真实宿主 E3、真人 E4、ComfyUI、MiniMax H3；`currentExecution` 原 34 项。

## 4. 六个任务维度与四条旅程（不得为每个品类造一个子软件）

维度：来源与目的 / 作品形式 / 表现手法 / 执行工具 / 模型及入口 / 使用渠道。「粒子」「3D」是手法，「小说」是来源，「短剧」是形式，可交叉。暂未确定工具时先给通用方案，推荐最多两条候选路线并说明理由与限制。

- 旅程 A：灵感参考 → 观察与推断分离的拆解 → 可借鉴方法 → 用户自己的内容 → 重构方向 → 面向所选工具的提示与步骤。反推提供可用描述，不宣称还原原始提示词。
- 旅程 B：开发中的产品 → 定位/受众/卖点 → 共享品牌表达 → UI/UX、VI、宣传物料、镜头与声音方案 → 分别交外部工具。项目负责方案，不承诺实现界面或交付品牌成品。
- 旅程 C：小说/广告/漫画/说唱等内容 → 叙事分析 → 创意脚本 → 分镜与声音设计 → 所选软件/Agent/模型的执行材料。长篇必须声明已读章节范围与未知范围。
- 旅程 D：导入规范/提示词/指南/案例 → 分类去重与来源登记 → 编辑、比较、版本保存 → 搜索与引用 → 用户试用 → 自愿反馈 → 修正方法。模型离线时常用知识管理必须仍可用。

## 5. 落仓时实测的现状差异（不是继承包内叙述）

下列读数是本轮在同一台机器、同一份字节上跑出来的，来源件 §5.30 有原始日志行：

| 断言 | 实测读数 | 由谁量出 |
|---|---|---|
| 路由合同账本 | 68 行：BOUND_SCHEMA 54，SCHEMA_LESS 14 | `design-lab/scripts/verify_contract_bindings.py` |
| live 载荷比对 | 35 条绑定，failures=0 | `design-lab/scripts/verify_route_payload_contracts.py` |
| 前端调用对账 | calls=109 routes=66 matched=55 backend_only=11 dynamic=3 special=1 | `design-lab/scripts/verify_workbench_route_calls.py` |
| 路由表条目 | `ROUTE_VIEWS` 21 条（`apps/workbench/shell.ts:277-303`） | `scripts/verify_documented_counts.py` 现数 |
| 能力库 | `src/design_lab/analysis/capability_library.py` 是**只读投影**，没有写入面 | 代码读回 |
| 提示词装配 | `prompt_intelligence.py` 不调用任何模型 | 代码读回 |
| 提示词结果 | `prompt_results.py` 存储层仍要求 `executed=false` | 代码读回＋合同 |
| 模型选择 | `model_selection.py` 只记录选择，不证明运行 | 代码读回 |

结论：知识条目**没有**可写面，检索**没有**中文验收，目标档案（软件×模型×入口）**不存在**，导出只有候选导出，方案助手模型**未接入**。本包的派工就是从这四条空白出发。

## 6. 派工表（16 项，唯一优先级轴）

优先级用既有词汇 `UI_FIRST` / `UI_SUPPORT` / `FOLLOWUP` 表达，批次前缀 `K*` 的顺序即执行顺序；不新增第二优先级轴。逐项定义（标题、依赖、验收轴、可写面、来源成员）逐字位于 `docs/history/taskpacks/20261023-adoption/TASK-DEFINITIONS.json`，采纳后逐字节冻结；状态只写在 `design-lab/config/task-ledger-r3.json` 的 `currentExecution.tasks`。

| 项 | 批次 | 优先 | 内容（一个纵切＝前端＋API＋持久化＋重启读回＋错误态） | 实现依赖 |
|---|---|---|---|---|
| DL-KB-01 | K0 | UI_FIRST | 本包包内材料落仓、权威与规划覆盖替换、台账加入与门禁同步 | — |
| DL-KB-02 | K1 | UI_FIRST | 知识条目可写面：新增/读取/列表，复用 Source/Method/Capability 合同，一个权威写入点 | — |
| DL-KB-03 | K1-UI | UI_FIRST | 「知识与提示词库」屏：搜索为主视觉，标签与列表，详情按需，新增/编辑/导入真实可发现 | 02 |
| DL-KB-04 | K1-contract | UI_SUPPORT | 中文检索：FTS5 与两字以下回退（「分镜」「粒子」），无结果必须说明，不伪造相关条目 | 02 |
| DL-KB-05 | K2 | UI_SUPPORT | 修订与并发：追加修订、旧版摘要不变、`expectedRevision` 前置条件冲突提示、推荐版本≠latest | 02 |
| DL-KB-06 | K2-UI | UI_FIRST | 三主入口外壳：设计辅助／知识与提示词库／我的方案＋设置；导航派生、路由表、截图与审计清单同步 | 01 |
| DL-KB-07 | K3 | UI_SUPPORT | 中立方案对象：复用 Brief/Direction/PromptResult 的引用，不新造第二存储 | 02 |
| DL-KB-08 | K3-UI | UI_FIRST | 「设计辅助」初始态与方案详情屏：一个状态下最多一个主要动作，「已保存」不画成「已生成」 | 07 |
| DL-KB-09 | K4 | UI_SUPPORT | 目标档案（软件×模型×入口）：首批约 4 个有官方依据；未知只能导出标明未验证的规划材料 | — |
| DL-KB-10 | K4-UI | UI_SUPPORT | 目标组合选择面板：先软件后模型，切换保留创意方向，不展示虚构评分 | 09 |
| DL-KB-11 | K5 | UI_SUPPORT | 三形态导出（Markdown/TXT、分镜 CSV、JSON）信息一致，含版本与未执行声明，导出不改 `sent`/`executed` | 07、09 |
| DL-KB-12 | K5-UI | UI_SUPPORT | 「我的方案」屏：最近、继续编辑、复制一份、历史对比、保留上次筛选 | 05、07 |
| DL-KB-13 | K6 | UI_SUPPORT | 轻量与性能**先量后改**：首屏 JS gzip、1,000 条本地搜索 p95、1280×800／1440×900／1920×1080 与 125%／150% | 06 |
| DL-KB-14 | K6-UI | UI_FIRST | 状态与错误面：空态、保存失败、附件未解析、模型不可用、目标不兼容、旧版本查看、离线仍可检索编辑复制 | 02、09 |
| DL-KB-15 | K7 | FOLLOWUP | 方案助手模型真实接入的**前置对账**：端点绑定、失败态、真实运行记录、数据发送范围披露；既有 `executed=false` 不翻义 | 09、11 |
| DL-KB-16 | K8 | FOLLOWUP | 可选外部结果反馈：用户手动附结果、时间码与维度结论；不自动训练、不自动资格认证 | 11 |

`DL-KB-15`/`DL-KB-16` 排后是 owner 2026-10-23 包内第 17 节的原序（先真实知识库与手动方案闭环，再目标适配，再模型，再反馈），不是延期借口。

## 7. 验收定义

1. 每个 `DL-KB-*` 项要报完成，必须给出：exact SHA、原始命令与退出码、关键产物路径与其 sha256、真实前端界面在该 SHA 上的读回、以及**未执行项清单**。局部测试不得称全量审计。
2. 数据面：写入后**重启进程再读回**；重启读回不是同进程内存读回。字段缺失写未知，不以链接存在认定已核验。
3. 检索面：中文两字词、英文型号词、无结果三种都要有真实断言。英文通过不得宣布中文可用（SQLite FTS5 trigram 对不足三个 Unicode 字符不命中）。
4. 界面面：几何与可达性由既有浏览器门禁实测；「已保存／方案已提供／用户选用／外部未验证」四种状态必须能被界面区分，且断言的是**已渲染**的界面，不是挂载了但没显示的组件。
5. 复制与正式认可是两件事：试用复制不得被审批、署名或反馈阻塞；`标为验证可用` 仍只接受具名真人。
6. 模型面：选择成功、连接成功、返回文本、内容可用四件事分别验证；文本成功不得推出图片或音频能力。

## 8. 明确不做

第二账本、第二运行时、换前端框架、自动操作外部软件、自动派发、成片自动生产、跨项目上下文共享、AAOS 传输与接收回读、手机端、字体库与第三方素材权利管理、虚构「最强榜」与百分制评分、把「收录」写成「已吸收」、把候选导出说成已发送、把 E2 说成 E3。

开源池（flatnotes／Langfuse／Promptfoo／FTS5／Docling／OTIO）目前是**研究参考或候选**，未安装、未 vendoring；真吸收时才登记 exact revision、许可、所取模块、目的地、改动、测试与退出路径。

## 9. 收尾仪式与本包必须同步的门禁

改权威与台账要一起动的面（漏一个就是下一会话的假现状）：

- `scripts/verify_top_level_authority.py` 的 `R2_RELEASE_HASHES`：`AUTHORITY.md` 与 `.project/governance/authority-index.json` 字节变了就必须重钉，并在 `docs/history/taskpacks/20261009-adoption/AUTHORITY-PIN-CHANGE.json` 追加一条 revision（owner 意图／原因／被取代／影响／跑的闸），不得静默换钉。
- `design-lab/config/task-document-states.json`：新任务包＝`CURRENT`/`DISPATCH_ENTRY`（有且仅有一个），方向包降 `SUPERSEDED`/`LINEAGE`，`docs/taskpacks/20261023-ui-kb/**` 需要前缀规则，否则 `no-undeclared-task-document` 红。
- `scripts/verify_documented_counts.py`：`frozen_current_tasks()` 原设计是「任何一项离开冻结就拒绝报数」。owner 2026-10-23 已把这件事记成决定，因此改为**两个分开的实测数**——仍冻结的 34 项，和新派工的项数；两处各自钉住自己的句子。
- `src/design_lab/governance/current_execution.py` 的报告行与 `design-lab/tests/test_current_execution.py` 的计数断言：不得再写死 34。
- 新增路由必须同一改动里付齐：合同账本行＋schema（`repo_resource`＋`pyproject` force-include＋打包面守卫）＋live 载荷用例＋前端调用可被 `verify_workbench_route_calls.py` 解析。
- 新增界面必须同一改动里进入 `ROUTE_VIEWS`、`renderRoute`、截图清单 `PAGES` 与各审计的 `ROUTES`；`DESIGN.md` 的「导航 {n} 项」是实测句，导航数一变它就红。
- 投影与登记件：内容提交 → `scripts/generate_archive_record_register.py` → `scripts/generate_current_reports.py` → `--check` 双绿 → 投影提交 → `verify_design_lab.py` → 推 `main` 与备份分支 → 在该 exact SHA 逐作业逐步读 CI。

## 10. 证据等级声明

本包交付是 E1（结构与合同的静态可证）＋对既有 E2 受控运行读数的引用。**不是** E3、不是 E4、不是 release。包内 12/13 两份 JSON 是作者的自查（scope 明写 artifact consistency only），不作为本仓库的验收证据。`docs/history/` 与 `design-lab/evidence/` 的既往读数按旧时点保留，不因新规划升格。

## 11. 交回下一轮提示词

每一轮结束必须就地更新 `docs/current/NEXT-AGENT-PROMPT.md`（唯一接续入口，不按日期铸新文件），并把下一轮可直接粘贴的提示词交回 owner。提示词里只写实测基线，边界逐字重述，不继承本轮的推测。
