# 下一会话提示词（唯一入口）

> **本文件就地更新，不要再按日期新铸一份。**
> 2026-10-18 之前它按日期命名（`NEXT-AGENT-PROMPT-<日期>.md`），于是每轮都要铸新文件、搬一次指针，
> 旧副本合法地留在 `docs/current/` 里，`AGENTS.md` 再逐个罗列——那就是"旧路径反复出现"的机制。
> 现在只有一个文件名；改状态就改这一个文件，并同步下面两行。
> 历史条目在 `docs/history/next-agent-prompts/`，逐份登记于 `docs/history/next-agent-prompts/PROMPT-LINEAGE.json`。
> `verify_task_document_states.py` 的 `entry-not-dated-again` 会在有人重新铸日期副本时直接失败。

- **updatedAt**: 2026-10-28
- **writtenAtSha**: 自己读 `git rev-parse HEAD`（不要抄任何文档里的数字；本文件也不例外）

## 0. 这份文件是什么

不是 Authority，不是第二状态源。它只回答两件事：**现在真实状态是什么（怎么自己读）**，以及**下一刀该切哪里**。
任何与本文件冲突的事实，以 `/AUTHORITY.md`、`.project/governance/authority-index.json`、
唯一任务包和账本 `currentExecution` 为准。

## 1. 读的顺序（不可变）

1. `git rev-parse HEAD`、`git status --porcelain`、`gh pr list`、`gh run list --branch main --limit 1`
2. `/AUTHORITY.md`
3. `.project/governance/authority-index.json`
4. 根 `AGENTS.md`
5. 唯一当前包 `docs/taskpacks/DESIGN-LAB-DESKTOP-KB-INTEGRATED-TASKPACK-2026-10-23.md`（`DL-TP-20261023-DESKTOP-KB-R1`；2026-10-19 方向包已降为血统，仍读它对定位与边界的裁定）
6. `design-lab/config/task-ledger-r3.json` 的 `currentExecution`
7. 本文件

历史只经 `authority-index` / crosswalk 进入；记忆、聊天摘要、旧交接**都不覆盖 Authority**。

## 2. 先核对，再动手

```bash
git rev-parse HEAD && git status --porcelain && git log --oneline -5
gh pr list
gh run list --branch main --limit 1
python scripts/verify_top_level_authority.py                 # 10 项，含 6 个 SHA 钉
python design-lab/scripts/verify_task_document_states.py     # 13 项
```

**别抄本文件的数字当事实。** 上一轮的红灯里有一次就是"文档说已同步、实际没有"。

## 3. 2026-10-19 的方向调整（本轮唯一的权威变化）

Owner 原话（逐字）：

> 其他任务冻结，以这份任务为当前权威与闭环目标（更新项目内的权威和规划），未来能力暂时冻结和延期延后

落仓结果：

- 正式定位：**面向职业视觉设计的 AI 原生、平台中立的专业视觉智能与可复用设计能力系统**。
  产品本体 = 视觉智能 + 审美能力工程化 + 设计能力库 + 设计软件自动化 + 受控知识回流。
- 六大能力域：Visual Intelligence / Aesthetic Analysis / Prompt Intelligence /
  Design Capability Library / Creative Tool Automation / Knowledge Candidate & Evaluation。
- 永久非目标：第二画布或通用编辑器；以全流程设计文件制作交付为产品本体；
  通用 Agent Runtime / 聊天客户端 / 模型网关 / 跨项目调度器；接管 WORK-LAB 通用治理；
  取代 AAOS 正式知识真源；把热门资源或模型输出直接认定为合格能力/可信知识；默认外传客户素材。
- `docs/taskpacks/DESIGN-LAB-UI-FIRST-INTEGRATED-TASKPACK-2026-10-09.md` 降为 `SUPERSEDED / LINEAGE`；
  `currentExecution` 的 **34 项父/子任务全部 `FROZEN_DEFERRED`**，这 34 项不再派工；原字节、任务定义与证据保留。（2026-10-23 起 owner 在同一分区另加入 16 项新派工，见 §2.0.1——「不再派工」只对那 34 项成立，不是"账本里没有可做的活"。）
- 本轮**只做**权威/规划对齐、冲突矩阵、能力映射、技术可行性矩阵、最小真实闭环规划与按范围测试；
  **不实施产品功能**。解冻任何未来能力都需要 owner 明确授权。
  （2026-10-20 更新：这条普遍禁止已被 owner 后续直接指令在**三段**上取消，见下文 §2.0。
  2026-10-23 更新：桌面 UI 与知识库进入当前派工，见 §2.0.1；原句保留，因为它记录 2026-10-19 那一轮的效力范围。）

## 2.0 当前授权面（2026-10-20 定点解冻）

逐字原话与解释见 `docs/taskpacks/20261020-unfreeze/OWNER-DECISION-2026-10-20.md`；机器面读
`.project/governance/authority-index.json` 的 `unfreezeAdoption`。**只放行三段产品实施**：

1. **Prompt Intelligence 入口** —— 提示词生成与反推成为可调用面（服务 façade、CLI、HTTP 路由、工作台面板）。
   实施前的基线实测（2026-10-19）：`prompt` 在 `src/design_lab/http_service.py`、`src/design_lab/cli.py`、
   `apps/workbench/shell.ts` 三处 0 命中，只作为产品声明存在于边界合同与方向包。
   落地后按同一量法重新实测（2026-10-20，小写 `prompt` 子串出现次数）：`http_service.py` 8 处、`cli.py` 21 处、`apps/workbench/shell.ts` 41 处。承载模块是 `src/design_lab/prompt_intelligence.py`，入口为两条写路由（`POST …/prompts`、`POST …/assets/<id>/prompt-reversal`）、CLI `prompt generate|reverse` 与工作台 `#/prompts`。本句不再是缺口。
2. **`KnowledgeCandidate` 导出出口** —— 把 `export_payload` / `to_v1_projection`（`src/` 内原本零调用者）
   接到真实调用方，让"导出"成为可寻址动作；`outbound.transport` 仍是 `NOT_CONNECTED`，不得因为加了出口就宣称已发送。落地状态（2026-10-20）：调用方是 `KnowledgeReview.export_document`，入口为 `GET …/knowledge-candidates/<id>/export` 与 CLI `export-candidate`，信封自己写 `design-lab/assurance-knowledge-candidate-export-envelope/v1` 并有 schema 与 live 载荷用例绑定。界面侧同日补上第三级（2026-10-21，`#/records` 的知识面板）：每条候选一行一个 `读回导出文档（不发送）` 按钮，被合同挡住的那些行是禁用的且按钮自己说明原因，面板把信封版本、两份投影、编号回显（USER_SUPPLIED 与 EXPLICITLY_UNUSED 分开）、freshness 与 outbound 三事实原样上屏。按钮文字带"不发送"是有意的：只写「导出」会被读成已经交付。
3. **模型选择接口** —— 不锁死：菜单导航 + 接口，用户自行选择本地或云端模型。
   fail-closed 的**默认值**规则不变（`UNQUALIFIED_*` 默认 `defaultEnabled: false`；零 checksum、许可冲突、
   模型不存在、硬件不足时 resolver 仍拒绝）。用户的显式选择是被记录的用户动作，不改变合格状态、
   不把 `UNKNOWN` 写成合格、不宣称推理已验证；云端项必须写明哪些数据离开本机。

仍不做：release、安装态分发、真实宿主 E3、真人 E4、ComfyUI、MiniMax H3 验收；`currentExecution`
其余 34 项仍 `FROZEN_DEFERRED`（`scripts/verify_documented_counts.py` 实测；这条闸门从 2026-10-23 起把"仍冻结"与"已派工"当成两个分母分别现数，所以悄悄动一项旧任务会让那四处 34 的句子同时红，而不是让闸门拒绝报数——保护是测量，不是沉默）。
新落地的范围收口：**字体库与第三方素材的权利判定移出本项目范围**，不得再列为缺口或开工前提；
`source.job_id` / `operation_id` 改为界面可填写 + 可显式选择"不使用"，代理不得自行铸造标识冒充来源证据；
`DESIGN.md` 在 owner 真实测试前不进已批准状态，逐条配色归属与品牌蓝裁定**挂起不是阻塞**，不要再反复请示。业界规范入库这一步已落地一半（2026-10-21）：`packages/capabilities/standards/INDUSTRY_SPEC_REGISTER.md` 按「可吸收 / 只可引用 / 今日未能核验」三档登记 11 条外部规范的出处、版本与许可原话，取不到的字段一律留 UNKNOWN——WCAG 3.0 草案已在第二轮直接取到（页面原话「W3C Working Draft 10 September 2026」，许可为 W3C 文档使用规则；它是方向不是判据，本项目现行判据仍是 WCAG 2.2 AA）；PDF/UA-1 与 IEC 61966-2-1 两条仍取不到出版方页面（ISO 目录 403、pdfa.org 全站 403/404、IEC 那个编号实测返回 CISPR 25:2008），版次只有二手线索，登记件里原样标为未核验——下一位要重取，而不是补一个日期顶上。

## 2.0.1 当前授权面（2026-10-23 桌面 UI 与知识库进入派工）

owner 原话（逐字）：**「读取分析，按照这个执行（前端UI是新规划——见 §2.0.1 末的原文引用），并且归档到统一项目里，
更新覆盖替换到权威和规划里」「先分析拆解，加入到优先到任务台账里」**。裁决件
`docs/taskpacks/20261023-ui-kb/OWNER-DECISION-2026-10-23.md`；机器面读
`.project/governance/authority-index.json` 的 `desktopKbAdoption`。唯一当前包是
`docs/taskpacks/DESIGN-LAB-DESKTOP-KB-INTEGRATED-TASKPACK-2026-10-23.md`（`DL-TP-20261023-DESKTOP-KB-R1`）。

**台账读数（2026-10-24 第四轮收尾时现数，不是抄来的）**：`currentExecution` 现有 50 行，其中
仍冻结 **34 项**（`DL-FINAL-T01…T22` 与 `DL-UI-U01…U12`，一行都没被解冻），当前可派工 **16 项**
（`DL-KB-01…DL-KB-16`）。第四轮收口后的状态是 `DONE 6`（`DL-KB-01/03/04/06/07/08`——这是账本的 DONE，
证据等级仍是 E1/E2，真人验收未发生）、`PARTIAL 2`（`DL-KB-02/05`）、`NOT_STARTED 8`（`DL-KB-09…16`）。
`currentExecution.evidence` 249 条全部 PASS：236 条前三轮 + 13 条本轮回执（KB-07 两条、KB-08 十一条），
逐条 `artifact_sha256` 绑定受跟踪工件；其中 1 条 `delivery` 回执
（`kb-01-delivery-ci-clean-checkout-20261024`，绑 `3c6ca491` 的干净检出 CI）。
`DL-KB-01` 的干净克隆条款已由 CI 兑现：main run `40036696250` 在 `3c6ca491` 上 success（11 个作业
success、Branch light 按规则跳过），`RECORD_REGISTER_GATE=PASS checks=5 problems=0` 在全新 Linux
checkout 上复算登记册摘要，EOL 未被规范化；同 SHA 的分支 run `40036704582` 也 success。
本机九门在收口树（`249` 条证据、`DONE 6`）上全部 exit 0。证据包 `kb-20261023/` 现有 86 个受跟踪文件；
`evidence-index.json` 仍是第一刀在 `7f5e68d7` 的 47 份索引，**不是全量清单**——第二轮起的回执
以账本 `artifact_sha256` 为准。定义原件
`docs/history/taskpacks/20261023-adoption/TASK-DEFINITIONS.json`，账本按 sha256 钉它，采纳后逐字节冻结。

**台账读数（2026-10-24 第八轮收口时现数，取代上面第七轮那一段的"当下"身份）**：`currentExecution`
仍 50 行、34 项 `FROZEN_DEFERRED` 一行没解冻；直方图 **`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`**——
`DL-KB-02` 升上 DONE，因为 A5 那句"模型服务关闭时仍可写入、检索、编辑与复制"这一轮**被直接量了**：
`test_knowledge_library.py` 读 AST 扫模型／供应商／网络方向的 import（按点号分段比对，并用一条
种进去的假 import 证明这把尺会响），先断言 `model_selection` 表行数为 0，再建条目、检索、修订、读回。
四个动词里"复制"原先**在界面上不存在**，所以这轮先补 `kb-copy-body`（剪贴板被拒时退化成
全选只读的 `as-copy-fallback`），再让 Chromium 真读回剪贴板并与**创建路由的应答**逐字节比。
浏览器走查 10 件→**11 件全真**，各阶段发请求数仍 `[0,0,1,1]`（两次本地拒答确实没发请求）。
`currentExecution.evidence` 现数 **279** 条、全部 PASS，本轮新增 2 条绑 `72710b7f04b9`。
路由面 **88 条**（48 GET + 40 POST）不变、账本 90 行（50 GET／39 POST／1 GET+POST）、
载荷比对 **57 条绑定** `failures=0`；写侧扫描
`rows=40 walked=39 written=39 read_backs=48 refused=0 excluded=1`。三把浏览器尺在同一批字节上重跑：
对比度 50 个面 `checked=14002 belowAA=0 unparsable=0 controlMisses=0`（design-lab/dark 与
ui2026/light 各一遍）、几何 112 个面（1440/1280/1536/1920）`docOverflowX=0 clipped=0 stray=0`、
路由级 UI 审计 clean。**两把静态尺的读数与上一轮一字不差，这不是尺坏了**：它们只走到
`#/knowledge` 列表、从不点开条目，新控件在详情面板里，落在行走路径之外——这块界面的证据来自
走查与 `appshell.mjs`，不来自这两把尺（细节见审计件 §5.40）。
本机 `VERIFY_DESIGN_LAB=OK total=76 failed=0`；体积 `build/main.js` 605,670 字节 / gzip
**158,722** 字节（同一把尺，第七轮记录 158,477），`DL-KB-13` 的 150 KB 裁定仍在 owner 手上。
**下一刀已经看清，不需要新路由**：方案的参考选择器只给得出 5 种类型里的 2 种
（`ASSET`、`KNOWLEDGE`），`BRIEF`／`DIRECTION`／`PROMPT_RESULT` 服务收得下、界面上选不到，
而 `/api/projects/<id>/briefs`、`/directions`、`/prompt-results` 三条读路由都已存在且各有合同行。

**台账读数（2026-10-26 第二十六轮收口时现数**：直方图仍 **`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`**，
`evidence` 303→**306**（三条：`kb-13-theme-geometry-palette-table-derived-20261026`、
`kb-13-single-accent-graded-as-paint-20261026`、
`kb-06-field-refusal-adjacency-graded-on-its-referent-20261026`），旧 34 项一项未解冻。
**推送后按字节读到的 CI（head_sha `1a7ddd52`，PR #277）**：`VERIFY_DESIGN_LAB=OK total=76 failed=0`、
`PYTHON_TESTS_UNION=OK expected=3380 distinct=3380 ran=3380 duplicates=0 missing=0 unexpected=0`、
`BROWSER_E2E ran=41 skipped=0 failed=0`，作业级 rollup 是 `11 pass / 13 skipping / 0 fail`。
上一轮欠的红都在这一轮结清：`AUTHORITY_CHAIN=DRIFT`（账本加行后重生成链）与
`RECORD_REGISTER_GATE=FAIL row 5`（登记件钉的是**已提交** blob，所以卷宗追加必须等一次跟随提交才能重绑）
都各自用一次"代码提交→记录提交→重绑提交"结清；`BROWSER_E2E_NO_SKIP_VIOLATION: skipped
test_the_refusal_state_is_named_in_the_receipt` 是这一轮新造的，根因见下面第④条。

**本轮四件，每件都有改前/改后实测。** ① **几何那把尺的色板表不再是手抄的**：`PALETTES` 从
`apps/workbench/shell.ts` 现读（mjs 与 python 各自独立解析同一份声明），断言"渲染出的集合＝声明的集合"，
解析不出 4 项直接红；珍珠白因此第一次被这道门量到，判据是**与默认面逐位等值**而不是我发明的数
（`09_DESIGN.md:9` 只给六个颜色值，没给导航轨宽度），实测 `1440/1920/960/768/700` 全等、`findings=[]`。
植入第一版是错的（只把表名改掉、条目还在，什么都没证明），改成遮 `schemes:` 才真的让拒绝响。
② **包里那支单一强调色第一次有"代价"**：样式表里消费 `var(--accent*)` 的属性是
background/border-color/border-left/box-shadow/outline/stroke/fill/border-right/border-bottom，
`color:` 是 **0 处**——所以 WCAG 1.4.3 只在"墨压在强调色底上"这一层咬它。同一把算式下
纸白墨压 `#356B92`=**5.72:1**、压 hover `#2558DB`=**6.00:1**、强调色当字墨压珍珠白=**5.08:1**，
而**深墨 `#17212B` 压 `#356B92` 只有 2.85:1**：§5.52 摆给 owner 的两个方向不是"都有代价"，
是一个达标、一个直接造出 AA 违规。shipped 的三条强调色底规则本来就写 `color:#fff`，现在这条被钉住
（换成深墨、或新写 `color:var(--accent)`，各有植入用例定罪）。`brandBluePaints` 珍珠白下 **106**
（分母＝182 个 宽度×路由 对，与 §5.52 那个 21 不可互换），包给的值一字未改、enforce 阈值一字未动。
③ **「错误紧邻字段」量错了对象**：审计取 `host.querySelector(...)`＝宿主里第一个控件，于是表单末尾
的提示被拿去跟开头的「需求」文本域比，`dy=1199px`、`errorAdjacent=0/8`。这一句同时是尺子的错和产品的错，
两边都改：产品用 `showFieldRefusal(control, message)` 写 `data-for` 并把同一个节点移到该字段所在行之后
（清空时移回原槽，静态版面一字节未动），闸门按 `data-for` 认对象、无主的消息另记 `errorUnowned`
（不混进被断言的数，防止靠重新分类把人口缩小），并逐个造出该表单自己的拒绝。现读
`errors=8 errorAdjacent=8 errorNamed=8 errorUnowned=0`，三条被点名的拒绝各 **24px**（那正是这一行自己的下边距）。
④ **一条"读上一次跑的件"的测试，在 no-skip 作业里必然红**：`_run_gate` 每个方法各跑一次浏览器，
而写默认面工件的类按字母序排在后面，所以干净检出上那份文件根本不存在→`skipTest`→CI 判违规。
改成自己调用生产者并按环境记忆化（一个进程一次测量），既去掉 skip 也去掉重复的整轮浏览器。

**我自己这轮的四次仪器/流程失误（它们是下一轮的陷阱）。** a) 第一条回执的 `subject_sha` 绑在**上一个**提交上，
即不含被它测量的代码——做法是先提交代码、再出回执；b) 提交信息里手抄 `5.94:1`（hover 那支），
脚本派生是 `6.00:1`，是我算错——在下一条提交信息里更正，不 amend 已存在的历史；c) record 脚本先读工件
后跑闸门，于是把**上一次跑**的读数当成本轮结论——改成先跑后读，并因此暴露人口本身在两次连续跑里不等
（8 与 4；差别在后面的面板态里那条提示还在不在屏上），**被断言的是等式与逐条造出的案例，不是计数**；
d) 一次插入没重出锚点，把 `console.error(` 的前半行吃掉，靠回读文件才发现——锚点式插入必须重出锚点。

**下一刀按此顺序。** ① `knowledge+refusal` 那一族**已经造出来了，原因与我上一轮写的相反**：
不是"揭示动作没渲染"，而是**闸门一直在点这个路由上不存在的 id**——`knowledgeFormPanel` 的 create 前缀是
`kb-new`（字段真名 `kb-new-title` 一族），而它的提交按钮与状态区**连 id 都没写**。
现已改成选择器（线＝`#kb-form [role=status]`、清空＝`#kb-new-title`、触发＝`#kb-form .primary-btn`），
先点 `#kb-new` 揭示，`CT_REFUSAL_PROVED count=4`（两族 × 两宽度）。量的结果是**12 条计数消息**：
点名对象的 8 条全部贴在字段上（`errorNamed=8=errorNamedAdjacent`），
另 **4 条是知识表单的复合消息**——一句同时点名"标题、一句话用途、正文"三个字段，
实测离最近控件 **82px**，谈不上贴在哪一个旁边。**这条因此是"字段级已达标、表级复合句未达标并已量出"**，
下一刀要做的就是把它按字段拆开（校验器按字段返回问题、每个字段旁各说各话），
并顺手给那个只靠 class 定位的状态区补稳定 id（辅助技术现在也指不出它）。
**注意定罪面已经挪位**：判的是"消息 ↔ 它点名的字段"，并且新加一条反向断言 `errors > errorNamed`，
即那 4 条复合消息必须还在被数到——把它们从人口里摘掉来买绿会直接红。
② 让人口稳定：每个面板态自己造一次拒绝，而不是依赖前一个态遗留的消息；
③ 提示词读回的**界面翻页线索**（服务端默认 100，包里写 50，这个分歧要么按包取 50 要么请 owner 裁），
④ 剩下 7 条无界列表路由，⑤ 五份 CSS 花括号扫描器收敛（逐个证明输出集不丢），
⑥ 附件 `width/height/media_type` 写入时物化（单独一刀，带迁移＋precheck＋合同行；成本实测 59% 在 path+stat、
30.5% 在两次图像解码，分页一毫秒都不会少）。**还有一件本轮量出来但没修的债**：卷宗里的 `<file>:<N>`
行号指针已腐到不能用一次性重写来救（toast 节点被引在 `shell.ts:5794`，现读 `id: 'toast'` 在 **9857** 行，
差 4063；另有相当一部分写成裸基名，按仓库相对路径根本解析不到），而 `scripts/` 下**没有任何行号指针闸门**——
要做就先做"指针→判据片段"的显式表，别上一把会误报的通用尺。
**owner 未裁照旧，都不代做**：150 KB 上限、顶栏是否吸顶、标题阶梯、勾选框标签算不算违反「标签放输入上方」、
hover 墨色，以及强调色最终收敛到哪一支（现在两支的 AA 代价都有了数）。
**边界不动（逐字）**：桌面端 only（手机是排除项）、不部署模型、不宣称推理已验证、导出是读回不是发送、
签字只认具名真人、编号用 UNUSED 或用户自填、E 盘不动、旧 34 项仍 `FROZEN_DEFERRED`、
release／安装态分发／真实宿主 E3／真人 E4／ComfyUI／MiniMax H3／外部软件自动化／AAOS 联调继续冻结、
不得靠改断言或删接口或把失败改成演示成功来通过、`.codebuddy/` 与 `.cursor/` 永不暂存。

**台账读数（2026-10-26 owner 审计摄入，7 条，逐条对回字节后的当下身份）**：第 **1** 条（P1 源码包不能
重建安装包）已修并结清——见卷宗 §5.71 与回执 `dl-final-t05-sdist-wheel-roundtrip-20261026`。
第 **4** 条（`doctor --task` 确定性崩溃）见 §5.72 与 `dl-final-t04-doctor-task-unboundlocal-20261026`。
第 **2、3、5、6、7(a)、7(b)** 条**已修并各自带反证**，见 §5.73／§5.74 与那两节下的六枚回执：知识后继分叉（两条路线
共用一个 `_supersedes_guard`、`BEGIN IMMEDIATE`、状态 SQL 里新增 `knowledge_entry_one_successor` 触发器；
五枚新用例在修复前提交上判红，含并发跑出 `['wrote','wrote']`）；正文阶段无人管辖（`api()` 把头部与正文
放进同一个 try，三条用例带看门狗；反证跑先谎报过一次 `rc=0`，成因是**我的跑法硬编码返回 0**且没断言
"换源码真的改了 bundle"）；知识表单一句合并提示改成**一字段一条**、落在该字段自己的 `.field-row` 内
（`.two-col` 是两列栅格，"行之后"会落进右列），浏览器尺新增 `walkKnowledgeFieldRefusals()`，
**并且删掉了 `errors > errorNamed` 这条要求缺陷继续存在的断言**；审计回执覆写（反证跑写自己的
`-enforce-red.json`，两份回执各带 `report.run` 身份，另有静态尺定罪"改了配置却没写自己文件名的
`_run_gate`"，人口探针用 `grep -rnE "assertNotEqual\(.*,\s*0" design-lab/tests/*.py`＝**11 处／8 模块**，
只有对比闸的反证会写回执；我第一版那条 `grep "assertNotEqual(code, 0)"` **匹配不到跨行调用**，
所以它的"只命中一处"不算证据，见 §5.73 的更正）；会话关联出处（链接写一次，答复改读库里那行的
`source_system`，矛盾的重新链接直接拒绝；可达性由 126 个文件的表面人口**断言**而非由话说，
所以本轮等级只是模块级 E2）；仓外报告路径打印崩溃（新增 `scripts/report_paths.py`）。
第 **7** 条剩余两项**未结**，但两句身份不一样——旧版本写"未结且不是工程缺口"，把混合面整块推给了 owner，
这里按 `UNBOUNDED_REGISTER`（`design-lab/tests/test_workbench_weight.py:266`）的逐路由理由分开。
**CSV 安全模式＝待 owner 决策**（§5.73 逐字：「属于待决策项，不是工程缺口」，等一句话而不是等我的实现）。
**容量**那半是 **8 条无界路由**（`LISTROWS list_routes=18 bounded=10 without_limit=8`，
每个不封页的路由都带 `client_calls` 与理由；这个数现在由 `scripts/verify_documented_counts.py` 直接数那张表，
不再靠散文里的算术——本轮散文写的是"其余 7 条"而表里是 8 条，闸一加上去就红了）：
`_list_design_systems` 由四名注册表天然有界，**没有活**；`_list_or_read_assets` 成本在每行重校验
（实测 200×47,160 B 时服务端 199.59 ms，path+stat 59.0%、两次图像解码 30.5%、hash 2.4%），**分页修不了**，
真修法是写入时物化 `width/height/media_type`，那是带迁移＋precheck＋合同行的 state-schema 单独一刀；
`_list_projects`（逐项目汇总）与 `_list_token_documents`（空值语义须保列表）是**修法各不同的工程项**；
`_list_jury` 与 `_list_research` 标着 `NOT MEASURED`，**先补数再谈修法**；
只有 `_list_rights`（Human Gate 面——"一页把行藏起来就是把决定藏起来"）与 `_list_knowledge_candidates`
（导出是读回——截断即误报曾经 offered 过什么）落到 owner：**要不要封页是产品裁定，不是我能替 owner 写的代码**。
**本轮还修掉了一处 CI 红**：`5d603fe6` 的 PR run 唯一失败是漂移登记面少一对——`d2dbeefc` 给
`test_doctor.py` 加用例，使一条哈希它的旧记录变旧；补钉并 65→**66**，成因为什么红、逐名 delta 都写在测试注释里。
**本轮自造的两处红也已结清（卷宗 §5.76／§5.77）**：① 收尾脚本只暂存 `git status` 里 ` M` 的路径，新写的回执是
`??`，于是账本行进仓、它指的文件留在工作树——本地永远看不出（文件就在盘上），干净 checkout 里 `[Errno 2]`；
run 40338742258（head `4dc59349`）逐字 `VERIFY_DESIGN_LAB=FAIL total=77 failed=2`。修法把 `??` 纳入暂存集，
并给 `test_evidence_artifact_presence` 加两条：全量扫一遍账本，外加一枚"指一个不在索引里的工件必须被定罪"的
植入（`.project-local/**` 的豁免不许被扩成红）。② 触发器兜底的拒绝话术不点名后继，现在应用层校验与
`sqlite3.IntegrityError` 兜底共用 `_superseded_detail()`；用例**刻意把 `_supersedes_guard` 置空**逼触发器接管，
同一用例在修改前的 `ac97cc71` 上判红、在修复后的字节上 `Ran 27 tests in 3.246s OK`。
**§5.75 的 CI 账（逐字取作业自己的日志）**：run 40334885313（event=pull_request，head `768f3fac`）
`conclusion=success`，10 个非 skipped 作业全绿，`PYTHON_TESTS_UNION=OK expected=3412 distinct=3412 ran=3412 duplicates=0 missing=0 unexpected=0`、`BROWSER_E2E ran=44 skipped=0 failed=0`；相对 run 40315188651
（head `5d603fe6`）读到的 **3397** 净增 **15** 条。**这条只覆盖 `768f3fac` 那批字节**——§5.77 的代码改动在其后，
所以承载本轮全部字节的那个 head 的 run 必须单独读回（§5.76 末句留的就是这个前指），不要借用前一次的绿。
**§5.78 收口面自审（卷宗最后一节）**：三处 § 引用是本轮自己写错的，已按"读目标而不是回忆"改正——
`§5.67`→**§5.66**（`LISTROWS` 表在那节，§5.67 是几何色板表；上一轮那条"已验证"的改正本身也指错了）、
"§5.72 记下的 3397"→run 40315188651 日志里那一行逐字、`§5.76`→**§5.73**（CSV/容量归 owner 那句只在 §5.73）。
`UNBOUNDED_REGISTER` 是 8 条而散文还写"其余 7 条"、类文档还写"Nine of eighteen"——现在
`scripts/verify_documented_counts.py` 的 `unbounded_routes()` 直接数那张表（文本切，不 import：这条闸跑在
没有 Pillow 的 node 作业步骤里，§5.57 的约束），本提示词那句必须逐字等于 `**8 条无界路由**` 才过；
先红 `DOCUMENTED_COUNTS=FAIL claims=21 failed=1`（`prose says nothing, measurement says 8`）、散文跟上后
`PASS claims=21`，类文档那句数字被删掉而不是换一个新数。**那个 head 读到了：`5580f184`（承载 §5.77 的代码
与本轮指针改正的第一批字节）run 40346676032（PR）`conclusion=success`**，逐字
`PYTHON_TESTS_SHARDS_START shards=3 expected_tests=3415`、三片 `exit=0`（1094/1101/1220）、
`PYTHON_TESTS_UNION=OK expected=3415 distinct=3415 ran=3415 duplicates=0 missing=0 unexpected=0`、
`VERIFY_DESIGN_LAB=OK total=77 failed=0`、`BROWSER_E2E ran=44 skipped=0 failed=0`——相对 3412 净增 **3** 条
（`53cdc7eb` 两条"工件必须在索引里"＋`7b9a4f37` 一条兜底话术）。同 head 的 push run 40346664251 只跑轻闸
（11 个重作业 `skipped`），所以这条 PR run 才是能引的那一条。**owner 点名的 `83448333` 两个 run 也逐字节读完了，
答案是那个 head 上从来没有过套间结论**：PR run 40328675340 被后续推送 cancel（`Python gate`／
`Workbench browser E2E`／`CI artifact proof` 三个作业 `cancelled`，其余 8 个 success），push run 40328665473
只有轻闸——按本仓规矩 cancelled 不算通过，不存在"就地修到它绿"这一步，那一格的账由 `5580f184` 这条补上。
**承载 `2048cf2e`＋§5.78＋登记件重绑＋投影刷新的那一个 head 也已经读回**：`8190527d` 的 PR run 40350069509
`conclusion=success`（10 个作业全绿，逐字 `expected_tests=3415`、`PYTHON_TESTS_UNION=OK … ran=3415`、
`VERIFY_DESIGN_LAB=OK total=77 failed=0`、`BROWSER_E2E ran=44 skipped=0 failed=0`；同 head 的 push run
40350057037 success 但只跑轻闸）。人口仍是 3415 是预期的——这几提交只加登记件、回执与散文，没加断言。
**同一条规矩对本句所在提交继续成立**：本句之后的那个 head 的 run 不在本轮宣称里，由下一轮读回；
`main` 无分支保护，PR #277 合不合入是 owner 的决定，本轮没有合。
**§5.79：那之后同一条浏览器尺自己红了一次，红在闸的读法上。** `cf30ee05` 的 PR run 40352855984 `failure`，
唯一红作业 `Workbench browser E2E`，逐字 `BROWSER_E2E ran=44 skipped=0 failed=1`，条名
`test_design_layer_slice_in_real_browser`，而定罪行 `E2E_ASSISTANT_PLAN_DUPLICATE … answer={"revision":1,
"id":"aplan-b5d27f…"} writes=5/5` 说明服务已写、写入计数已进一位，**被读出来的却是提交前的提示语**——
`shell.ts:6236` 的确认文案由 `afterWrite()` 在页面 POST promise settle 之后才写，闸拿到响应就 `innerText()`，
读到的是渲染没跟上的一帧（与 §5.55 的补间中间帧同族）。已把闸改成**先等它该看到的那句话**
（谓词与断言原有条件逐字相同：`已复制为新的方案` ＋那个 id，25 s 到不了就 `confirmationRendered=false` 交回断言，
所以这条尺仍然会红，只是不再把"没等到"误报成"没写"）。本机：`Ran 2 tests in 22.235s OK`、
`node --check` 干净、`test_e2e_script_is_lint_clean` 过、漂移钉 66 对未动；**但本机那份
`browser-e2e-summary.json` 没有 `assistant` 字段，证明不了四态那一段在本机被走过**——逐段结论要从 CI 的
`E2E step:` 序列里读；绿跑不打印那段序列（包装脚本只在失败时回显子进程 stdout），所以证明是「每一步失败都 exit 15 ＋ 子进程 0 退出且摘要 `result=PASS`」。**承载这次闸改动的 head 已读回**：`751df4a0` 的 PR run 40357134311 `success`，逐字 `PYTHON_TESTS_UNION=OK expected=3415 … ran=3415`、`VERIFY_DESIGN_LAB=OK total=77 failed=0`、`BROWSER_E2E ran=44 skipped=0 failed=0`；同 head push run 40357121752 只跑轻闸。本句所在 head 的 run 仍由下一轮读回。
**§5.80 对抗性审计（本轮自己）**：把刚修的那把闸打回红一次——`shell.ts:6236` 的确认措辞改成`复制完成 ` 后 `vite build`，同一条尺 `Ran 2 tests in 31.842s FAILED (failures=1)`，定罪行带`confirmationRendered=false` 且 `answer={"revision":1,"id":"aplan-ddb0c767…"}`、`writes=5/5`；复原按 sha256 校验后 `Ran 2 tests in 10.741s OK`、工作树干净。**所以 §5.79 的修法不是将闸改松，闸也确实会红**。另外三条自我纠正：§5.73／§5.74 的 6 处 `path:line` 已逐处读到内容并认账（含两条 `assertNotEqual` 的跨行/退出码形状）；提示词里 36 个 `§5.NN` 全部解析、悬挂 0；提交 `c46ef4b6` 曾宣称登记闸 PASS 而那条命令其实被 `| tail -1` 掩掉退出码没跑成——不加管道重跑才成立，教训是**自证的命令也不能走管道**。 §5.80 还把新计数闸朝**人口**方向反证了一遍：往 `UNBOUNDED_REGISTER` 里植一条假路由（8→9、散文不动）就 `DOCUMENTED_COUNTS=FAIL claims=21 failed=1`（exit 1），按 sha256 还原后 `PASS`（exit 0）——所以它咬的是人口，不是那句抄来的话。
**§5.81（2026-10-27）STITCH 画板基准包登记 + 外壳第一次照画板改。** owner 问「为什么还是网页的」，查出两处漏：
① **包到了三天没登记**——`D:\All projects\Record\stitch_design_lab.zip`（5,115,919 B，sha256 `ae76e90307bfcc429b5b11e13502e2a739ad69f7a3bc96a5a86f0cdc941eee03`，
2026-10-24 19:31，**14 块画板** = 每块 `code.html`+`screen.png`，解包 31 文件 / 5,678,932 B）此前在 `docs/`、
`design-lab/config`、`reports/` 里 **0 次命中**；② **我的检索面漏了投递目录**，把"我没搜到"写成了"它不存在"
（同一卷宗 §5.73 刚为同类错误被追正）。现已登记：`docs/history/record-archive-2026-10-27-stitch-boards/ARCHIVE-MANIFEST.json`
（逐成员 name/bytes/CRC32/SHA-256，摘要从 ZIP 内字节算）+ 固定资料索引 2026-10-27 日期节，
**插在生成登记件那节标题之前**（那节标题到 EOF 归生成器）。原件与解包副本的 canonical 位置
`.project-local/record-archive-2026-10-27/`，不随克隆走，迁移按摘要补齐。
**画板与现界面的第一条差异是骨架不是配色**：14/14 块画板左栏都是「设计辅助／知识与提示词库／我的方案」+ 左下设置，
08 原文逐字「只保留三个日常导航」，而现界面 24 项 4 组。已做（`cbaee463`，PR run 40509435322 success）：
默认只露那三项 + 设置沉底、折叠时藏组标题、加「全部功能／收起次要入口」；**一条路由都没删**——
`.app-nav-item` 条数是浏览器 E2E 与 DESIGN.md「导航 N 项」的现数对象；当前路由被折叠会自动展开。
屏幕一补了画板的本地事实（`8895bea6`）：「清空 · N 字」「Shift+Return 换行」「已关联 N 项参考」，
**两个计数在 `renderReferences()` 里重算**，因为载入已存方案（`shell.ts:6089`）与保存后清空（6236/6250）
是程序改 `value`、不触发 input 事件。**两处故意不照抄**：画板「2 / 8 附件」的 8 不是合同上限，不报 `N / 8`；
画板标题「这次想设计什么？」与按钮「整理设计方向」与 08 原话「你想完成什么设计？」「整理方案」不一致，
**以包内文本为权威**（画板是生成物，不是第二份规格）。
**§5.82（2026-10-27 第二轮）把上一轮欠的两条缺陷与一条画板差异一起结清**：折叠改的是导航的几何，
却不发 `scroll`/`resize`，所以溢出提示仍停在折叠态的读数——UI 审计闸在 `3a2b6565` 上量到
`1217px of nav hidden with no cue`（1280x500）与抽屉里 `873px`，`fe2cd160` 让折叠自己负责刷新提示
（`syncNavCue` 因此改成提升的函数声明，挂载那次折叠才调得到它）；新增的守卫步
`the rail users actually see is the folded one` 量的是 `#app-sidebar .nav`，**并且被打回过一次真的红**
（把折叠改成什么都不隐藏，`E2E_NAV_FOLD_INERT … closed=total=23`，rc=13），它同时断言 `.app-nav` 在路由页不可见，
所以 §5.81 那种"改了没人看的壳"再也过不了闸。交付类型按画板做成胶囊行（`0e3e5b5f`），
词表仍全部来自服务：未读回时一个胶囊都不画、读回后一个都不预选。
**收口顺序（本轮新钉，取代"想起来再重算"）**：文档与账本改完 → **先提交** → `generate_archive_record_register.py`
→ `deepseek_authority_chain.py`（不带 `--check`，它把 `ledger.evidence_receipts` 记成一个字段，**每落一条回执都要重生成一次**）
→ `generate_current_reports.py` → 跑闸（`verify_archive_record_register.py`、`verify_authority_gates.py --zero-spill`、
`verify_projection_freshness.py`、`verify_documented_counts.py`）→ 再提交 → 推送 → 读 CI。
登记件、权威链、现行投影都是**被绑定字节的派生物**，顺序错了就会出现本轮那样：每个闸在本地都各自绿过一次，
CI 在承载全部字节的 head 上把它们一次跑红（§5.83 记了三条：登记件旧、权威链旧、复制种子竞态）。
**下一轮接着做的顺序**：① 已完成——状态主人是被勾选的那颗 `radio`，`<select>` 整个删除，不留第二台账；
基数按合同（`output_type` 单值）而不是画板那句"多选"，要做多选得改那份闭合的读回 schema，那是 owner／合同决定；
② 附件 tile 的名称/大小——**不是"没有数据"，是投影没带出来**：库里 `f.path` 与 `f.byte_size` 都在
（`src/design_lab/native_assets.py:25,37` 就 SELECT 了它们），而 workbench 读的那一行 `AssetRecord`
（`apps/workbench/contracts.ts:37-47`）只有 id/kind/version/media_type/width/height/rights/sha256。
所以这一步是**加宽那份读回投影并补它的路由合同行**，不是新数据源；在加宽之前，tile 只能显示
`media_type · W×H`，画板那行「2.4 MB · 字体排印样张」不能照抄；
③ **缩略图需要开静态资源路由并放宽 CSP，是 owner 的安全决定，不要顺手做**；
③.5 **浏览器标签页没有图标**（实测：冷启动／旧工作台／路由页三面 `link[rel~="icon"]` 全是 `NONE`，
`§5.83` 末段）。做法不是往 `index.html` 里手贴一份 SVG——那会造出第二份没有出处的图形字节。
要由 `design-lab/scripts/render_brand_asset.py` 从**同一份被跟踪的矢量**派生 favicon 字节、
用同一族 `begin sha256=` 记号钉进 `index.html`，并让 `--check` 同时覆盖 CSS 与 favicon 两处，
`test_workbench_brand_asset.py` 跟着扩一条"两处字节同源"的断言；④ 画板顶栏那三个 Windows 窗口按钮
在浏览器标签里没有真实现，**不画装饰件**，真窗口壳属交付形态变更（要 owner 解除 release／安装态分发冻结）。
**新增待 owner 裁（界面这一支的交付形态，全部不是工程缺口）**：左栏收口是否进一步扩到路由清单本身（会动 DESIGN.md 的「导航 N 项」与那把闸）；
画板顶栏那三个 Windows 窗口控制件要不要真做（=桌面壳/安装态分发，需解除 release 冻结）；缩略图（静态资源路由 + CSP 放宽）；
**输出类型是否允许多选**（画板那句是"多选胶囊"，合同 `output_type` 是单值——现做的一组 radio 是照合同来的，改多选要改那份闭合的读回 schema）；
**浏览器标签页图标**（三面实测 `link[rel~="icon"]` 全为 `NONE`；补法见 §5.83 末段，要先定"第二份图形字节"的出处规矩）；
以及"STITCH 那套是否成为默认配色"（现行裁定是新配色只做可选主题、默认不动）。 **本轮重读 CI 的结论（§5.84）**：承载本轮全部字节的 head `19ffd0d1` 的 PR run 40537819918
`conclusion=success`，10 个非 skipped 作业全绿，逐字 `PYTHON_TESTS_UNION=OK expected=3415 … ran=3415`、
`VERIFY_DESIGN_LAB=OK total=77 failed=0`、`BROWSER_E2E ran=44 skipped=0 failed=0`。
更早 `924af2fb` 的 run 只剩两条红（权威链旧 + 它从测试面的那次复现），`5388b62f` 的 run 四条红里
三条都是同一个"派生物没跟着字节重算"，只有浏览器 E2E 那条是真的测试竞态，并在 `924af2fb` 单独转绿。
**下一轮起手不要重跑套件**：`307cc6e5` 是本文件最后一次收口时 `git rev-parse HEAD` 的读数，它的 PR run 40553954732
已读回 `conclusion=success`（10 success + 2 skipped，逐字读数见 §5.84）；**只剩一件事**——
自己 `git rev-parse HEAD` 取当下 head，读它那条 PR run：绿就收，红就按 §5.83 那三条的查法查明根因；
`3a2b6565`…`5e52fa97` 没有各自的 run，别把它们说成"每个 SHA 都单独验过"。
（本段是 2026-10-27 收口时的指针，保留原文；本轮之后的 head 与读数见下文 §5.85 末段。）
旧 34 项状态一字未改：这些证据挂在语义主人
`DL-KB-02`／`DL-KB-06`／`DL-FINAL-T04` 下，`state` 仍是 `FROZEN_DEFERRED`——审计授权的是修缺陷，
不是把那些任务重新派工。

**§5.85（2026-10-28）自动化解冻、包吸收、派生物清理与附件 tile 的真缺陷。**

本轮 owner 三条指令逐字：「取消冻结的自动化任务  （D:\All projects\Record\新建文件夹     把这里的内容吃透）」
「前端也同步上去自动化的菜单导航等」「并行执行 项目体积清理与规范化  执行合并迁移清理等相关执行，任何过时的
陈旧的冗余的，该归档的归档 包括目录子文件夹等」；范围答复逐字：清理＝只清派生物＋仓库内历史归档合并＋
PR #277 合并与分支收口；包＝「全部吸收融入本项目  和原先冻结的自动化任务进行合并」。
裁决件 `docs/taskpacks/20261028-automation/OWNER-DECISION-2026-10-28.md`；权威修订 `AUTOMATION-20261028-R1`
（`AUTHORITY.md 00126066…→e31fb1fa…`、`authority-index.json 9a0e1a58…→7ffe85d1…`，
`AUTHORITY-PIN-CHANGE.json` 第 11 条 revision，纯插入）。

**逐字节实测（本轮现算，不是抄包）**：ZIP `371,678,561 B` / sha256 `d0daeb54ea13b4996368970368483dc0046f6cfe8df7753ddfc287c4e62a9ca4`、
29,382 成员、解包 662,244,361 B；包自带 MANIFEST 29,380 行逐成员重算 **matched=29380 mismatch=0 missing=0**，
未列 2 条＝它 `excluded[]` 自述的自身与 `evidence/relocation.json`；8 个散件与包内同名成员逐字节相同；
11 个连接器 id 与 543 条已列工具（9 个握手过，逐条 `nativeToolCalled:false`）从被钉住的 ZIP 提进受跟踪登记件。
独立抽查 5 个最大成员（194,652,336 B / 0.492 s）5/5 相符——所以 2.6 s 跑完 29,380 条是真数不是空转。

**清理账**：`.project-local/` 10,457.5 MiB → 2,099 MiB，释放 **8,359.4 MiB（79.93%）**、27,970 条目；
两个陈旧 worktree 先按内容比对确认是更旧草稿（手机端仍写 `FROZEN_DEFERRED`，HEAD 已是排除项）才移除。
保留清单与理由写在 `docs/audits/DESIGN-LAB-DERIVATIVE-CLEANUP-2026-10-28.md`：`projects/`（持久作品）、
`record-archive-2026-10-23/-27/-28`（受跟踪 manifest 点名要能按摘要补回的 owner 原件）、
`task-artifacts/`（254 条冻结区回执指它）、`cache/vendor`（37 个 lock 源唯一本地持有）、
`task-runtime/playwright/npm-cache`（删了五把浏览器闸会静默 SKIP 而不是判红）。
**第一遍清理在写完账目之前崩在只读的 `.git/objects` 上**，那一段字节没有逐条记录——这条如实写在审计件里。

**附件 tile 的前提被实测改写**：简报说"库里 f.path 与 f.byte_size 已在，是投影没带出来"。实测是
`/api/projects/<id>/assets` **今天就在发 `byte_size`**（`src/design_lab/image_assets.py:84`），
而 `apps/workbench/contracts.ts:37` 的 `AssetRecord` **多声明了两个路由从不发的字段** `kind`/`version_no`；
删掉幽灵字段后 `tsc` 自己定罪两处调用点——真浏览器里参考选择器画 `undefined · img-…`、`#/intake` 画 `vundefined`。
**名称没有数据可发**：`image_assets.py:144`/`native_tasks.py:172`/`bundle_store.py:121` 写的是发布常量
（`reference.png`/`reference.jpg`/`native.<ext>`/`delivery.zip`），不是用户起的名字；
且 `assistance_plan.py:367` 明确拒绝 reference 带多余键。所以 tile 显示 `media_type · W×H · 大小` +
各来源已读回的标题，"要不要给参考加一句人写的标题"是合同决定，不是我能替 owner 加的字段。

**自动化菜单已上线**：次级入口 `#/automation`（`shell.ts:9955` 的 `B10_NAV` 从 `ROUTE_VIEWS` 派生，
`shell.ts:9985` 折叠时按 `NAV_DAILY_VIEWS` 隐藏非日常项），读 `GET /api/automation-connectors`。
真 Chromium 渲染实测：11 行、KPI `11 / 0 / 0 / 0`、`windows` 行写「owner 明确不启用 · 包内证据：未握手 ·
权利 OUT_OF_SCOPE_THIS_ROUND」、`consoleErrors=0`、`1440 == 1440` 无横向溢出。
11 个连接器按 `declared` 进 `integrations/adapter-registry.json`（30→41，`ADAPTER_REGISTRY=PASS`），
状态词只用 `NOT_PROBED`/未启用，屏上没有任何启动动作。

**本轮自己造又自己结清的红（下一轮别再犯）**：① 新决定文件没在 `task-document-states.json` 声明定态，
CI 抓到 `no-undeclared-task-document`（`VERIFY_DESIGN_LAB=FAIL total=77 failed=1` at `737307f3`），
而我本地只跑了四条闸——**改受跟踪文件必须先跑聚合，不是先跑相关闸**；
② `inert_contract_survey.py --check` 因新增产品文件过时（`productFiles 226→227`），本地聚合抓到；
③ 前端一旦真调用该路由，先前挂的 `BACKEND_ONLY` 豁免就成了反向谎报
（`STALE_BACKEND_ONLY`，闸两个方向都查）；④ `same_named_project_adapters` 会把 `adapter-delivery-*`
自己那行也 join 进来→恒真，已排除并加断言；⑤ 回执 `exit_code` 被我写成字符串，成因是**看格式化回显而不是原文件**，
`verify_task_ledger_contract.py` 判红 `'0' is not of type 'integer'`；
⑥ 重绑导入行时把 `evolvedBy` 写成裸 sha（它是 `{commit, subject}` 对象，直接把校验器 `AttributeError` 崩掉），
又把 `repoSha256AfterImport` 写成裸 hex（既有每行都带 `sha256:` 前缀，于是 crc 与 size 都对、只有摘要不对）；
⑦ **`scripts/run_structure_contracts.py` 不在聚合那 77 条里**：本地聚合 `VERIFY_DESIGN_LAB=OK total=77 failed=0`
而 CI 的 `Early structure contracts` 步骤红——`test_workbench_css_single_definition.py` 钉着
`el('ul', { class: 'list'` 的调用数 73，新增一屏变 74。**推送前的本地检查必须包含这一步**，
抬数按该钉的既有惯例：具名说出新增的那个容器，并说明为什么空态不占一个列表。

**§5.86（2026-10-28 续）CI 的两个新红：一个是我写的登记行，一个是闸门量了没画出来的字。**
本轮最终 head 的 PR run **40694692860** 收口读数（逐字从作业日志取，不是 wrapper 状态）：
`conclusion=failure`，11 个作业 **9 success / 2 failure / 2 skipped**，红的是
`Python gate (V3 verifiers + unit tests)` 与 `Workbench browser E2E`。两条独立成因，都在这一节里结清。

**成因 A 是我自己造的，且 CI 与本地读数一致。** 我加的 11 行 `adapter-delivery-*` 被两个既有契约拒绝：
① `hostAdapter` 在 `design-lab/schemas/adapter-contract.schema.json` 里**不是 required**，出现时必须是
`minLength:1` 的字符串，而我写成 `null`（30 条既有行里只有 1 条带这个键）——修法是**删掉这个键**，
不是给它补一个编造的主机名；② 本仓的大工具守卫
`design-lab/tests/test_oda4_0206_adapters.py::test_large_tools_process_isolated` 断言
`"Blender" in tool` 的行必须 `status == "missing"`（注释原文 "honest: not proven"），我的行写的是
`declared`。**我没有改断言，我把行的声明降级到它该说的词**：Blender 行现在是 `missing` + `fallback: none yet`，
其余 10 行仍是 `declared`（`declared`/`missing` 都不是可用性词，`runtime`/`structural` 才是）。
同轮我自己写的 `test_automation_connectors.py` 也被这条改动判红过一次——它原先断言 11 行**全** `declared`，
而那正是与守卫矛盾的说法，现在它断言规则（状态 ∈ {declared, missing}、禁止可用性词）并单独钉住
Blender 必须是 `missing`。读数：`test_oda4_0206_adapters` 10/10 OK，`test_automation_connectors` 11/11 OK，
`DOCUMENTED_COUNTS=PASS claims=21 route_views=25 cli=24 adapters=41 routes=89`（**8 条无界路由** 逐字不变），
`STRUCTURE_CONTRACTS=PASS tests=31 failures=0 errors=0`。

**成因 B 是闸门的盲区，我加的那一项只是第一个被它照到的页面。** `Workbench E2E` 报
`CT_FAIL: 14 text run(s) below WCAG 2.1 AA contrast`，全部是 `span :: 项目`，`fg=rgb(245, 247, 252)`、`got=1.5`。
逐条查下来（本地真 Chromium + 真环回服务复现，非猜测）：`.nav{overflow:auto}` 是侧栏唯一滚动容器
（`sidebarTop=0`、`navTop=817`），`scrollIntoView` 把当前项滚到底之后，**「项目」这一项被滚出了 `.nav` 自己的框**——
标签 rect `[55,20,32,21]` 对上 nav 框 `[18,125,243,616]`，`elementFromPoint` 在那一点返回的是 `div.brand`。
也就是说这个像素上**一个字都没画**，而闸门仍拿祖先栈里那层 `a=0.86` 的半透明侧栏渐变去合成它，于是判了一条看不见的 1.5:1。
基线 `58abdc69` 在同一台 Linux runner 上 `LOWCONTRAST=0`，所以这不是平台差，是**一条一直存在、被我 +1 个导航项推进到可达位置的量测缺陷**。
修法在闸门而不界面：`audit_workbench_contrast.mjs` 现在先做**裁剪判定**再入人口——某元素的框与某个真会裁剪它的祖先
（`overflow` 非 visible；`position:fixed` 后代除非法则获得包含块，否则会误删搜索面板这类固定层）完全不交，
就不进 `checked`，计为 `clippedOutOfScroller` 并**逐个报名**（`CLIPPED_OUT <route> <节点> by <裁剪者>`，绿了也打印）。
这同它已有的 `display:none` / `collapsed` / `obscured` 三档跳过是一类决定，WCAG 1.4.3 管的是看得见的字。
两侧都钉住：新植入 `#ct-clipped`（零高 `overflow:hidden` 宿主里的白字白底，**必须被排除**）与既有
`#ct-control`（同一份颜色、开在明处，**必须仍然被判红**），再加一条反空集断言——排除数不得达到人口的一半，
`checked` 仍须 ≥500。本地读数：`checked 52,138 → 48,819`（减 3,319，全部点名，除植入项外只有
`nav.nav.nav-open.has-scroll-more` 的导航标签），`productFails 14 → 0`，
`Ran 2 tests ... OK`。**须如实说的比较缺陷**：52,138/48,819 是本机 Windows 一次运行内由回执自己的字段推出来的
（旧代码把被排除项也计入 `checked`），而"14→0"的另一半是 CI Linux 的读数，两个数不同平台；
CI 对新 head 的 `BROWSER_E2E` 读数由下一轮自己取，不要抄本节任何一个数字。

**本轮自己造的第三个错（没进 CI，但值得记）**：用 heredoc 生成 Python 测试源码时 `\n` 被折叠成真换行，
写出来的 `self.assertEqual(..., '...run:\n%s')` 成了未闭合字符串。`ast.parse` 在运行前抓住了它。
教训沿用既有那条：**生成源码要落文件再改，别把转义寄望于 shell**。

**§5.87（2026-10-28 续）安装态真正读得到登记表：上一轮那句"可接受的降级"被实测否掉了。**
owner 说"持续推进 不要再问了"，所以按上一轮写下的下一轮第①项开工，做完并证明了三方读数。

**先说追正**：§5.86 的"下一轮按此顺序"里写 `现在装好的 wheel 会诚实报 registry_state=MISSING，这是可接受的降级`。
这句的判断是错的。实测（把本轮改动前的树 build 成 wheel、装进干净 venv、直接调用投影）：
`registry_state=MISSING pack_state=MISSING connectors=0 project_adapters=0`——不是一行少一个字段，
是**整张表空了**，而这一页存在的唯一理由就是"把已登记的连接器摆出来"。空表在任何读者眼里都等于"没有登记"，
那是对仓库的假陈述。成因与 `domain_packs.py` 当年一样：模块把自己往上第三层当仓库根，
装在 wheel 里那就是解释器自己的 `Lib`。

**做了什么**：① `src/design_lab/automation_connectors.py` 改用 `runtime/state_resources.repo_resource()`
（打包优先、其次本 checkout，并且只有当这个模块真的是 checkout 里的那份才回退，所以安装态永远不会
去敲邻居项目的门），`build(root=...)` 的植入根保留给缺失态用例；② `pyproject.toml` 加两条
force-include（`integrations/adapter-registry.json`、
`docs/history/record-archive-2026-10-28-design-automation/ARCHIVE-MANIFEST.json`，都落到
`design_lab/resources/repo/…`），sdist 的 `only-include` 同步补上那条 docs 根；
③ `design-lab/tests/test_standalone_chain_http.py` 新增一条**内容**断言并在 CI 的 clean-wheel 作业里
以 `layout=installed` 跑（该作业本来就用 `DL_LAUNCH_INSTALLED=1` 走这条链）。这条断言之所以必要，
是因为这个路由两种情况都回 200：状态码分不开"包装了这个记录"和"什么都没找到但如实说了"。

**三方读数（同一份测试文件，只换被测工件）**：
`AUTOMATION_READBACK layout=source registry=READ pack=READ connectors=11 adapters=41` → OK；
装在**改动前** wheel 里 → `FAILED (failures=1) AssertionError: 'MISSING' != 'READ'`（这就是它能红）；
装在**改动后** wheel 里 → `AUTOMATION_READBACK layout=installed registry=READ pack=READ
connectors=11 adapters=41` → OK。wheel 体积 `1,254,358 → 1,272,996 B`（+18,638）。
`SDIST_PACKAGING=OK wheel_sources=73 covered=73 missing=0 sdist_roots=18 mode=build`——
即从发布出去的源码包能重建出带这两条记录的 wheel，这正是 2026-10-26 那次审计点名过的旧缺口。

**顺带把一个工具盲区补上，并因此暴露一条既存真相**：`design-lab/scripts/audit_repo_root_reads.py`
原先写明"根先存进变量就不追"，而我的模块正是这个拼法，所以它一直看不见自己该看见的东西。
现在 `root_names_of()` 会追模块内任何位置的根绑定（含 `x = a or ROOT` 传递闭包），
`string_constants_of()` 会解 `NAME = Path('…')` 常量，`is_shipped()` 也不再只按 `design-lab/` 前缀比对
（只认一个前缀的工具，对 `integrations/…`、`docs/…` 永远只能说"没打包"，它的绿就不是证据）。
**加严之后 live 报告从 paths=1 变 paths=2**：新冒出来那条是
`adapters/illustrator_com.py → integrations/hosts/adobe/illustrator/reconstruction-assemble.jsx`，
和 Photoshop 那条同类、字节本来就在 `design_lab/resources/adobe/` 打包着——即它**一直是既存事实**，
只是旧检测器看不见。处置是把它并进那条豁免名单并写明理由（不是删断言），并把正对照从"计数"改成
"具名对"：`CONTROL evidence=4 hits=4 / CONTROL=OK every pre-fix reader was found`，
其中两条就是我自己这份改动前字节，用 `git show aa65fc70:` 取真字节，证明加强后的检测器确实能看见
当初藏住这个缺陷的拼法。

**没做的事**：没有安装态分发、没有 release；wheel 只是被构建并被证明读得到，没有被发布。
`probed_by_design_lab=0 / enabled=0 / native_tool_calls_executed=0` 在两条断言里都继续被钉成 0。

**§5.88（2026-10-28 续）浏览器标签图标：从同一个被跟踪矢量派生，不新画第二个图形。**
`index.html` 原先没有任何 `link[rel="icon"]`（实测三个面都报 NONE），所以标签页画的是浏览器的通用文档图标，
而侧栏画的是 owner 的标志——同一个产品在两个相邻像素面上不是同一个品牌。这一刀把它接上。

**派生而不是新画**：`design-lab/scripts/render_brand_asset.py` 现在能从
`apps/workbench/brand/design-mark.svg` 组出图标，相对源文件**只改两件事**，而且两件事都是从源里读出来的数：
① 墨色从 `#17212B` 翻成 `#EEF2F5`（标签页的 chrome 可能是亮也可能是暗，字形不能跟着背景一起消失）；
② 插一个 `<rect>` 当底板，`x/y/width/height` 直接取被跟踪的 `viewBox`，`rx` 取短边的三分之一——
就是 48px 导轨方块 `border-radius:16px` 用的那个比例。`<path d=…>` 逐字节不动。
字节以 `data:image/svg+xml;base64` 内联进 `index.html` 里一段 `<!-- brand-favicon:begin sha256=… -->` 管理区，
因为 `workbench.py` 只发三条固定路径且 CSP 是 `img-src data:`——加一条 favicon 路由要同时放宽两处，
那是 owner 的安全裁定，不是方便。**这条理由现在是一条断言，不是一句注释**（`test_the_icon_adds_no_served_path_and_no_csp_change`）。

**`--check` 现在同时管 CSS 与 favicon**，并且会把图标从源重算一遍逐字节比：
只换图标载荷、只改摘要声明、整页没有管理区，三种腐法各有具名红。
顺带把这条刀在**做之前**的状态留成一个永久用例：`--sync-favicon` 存在之前，
`--check` 对一个没有图标的页面照样打印 `BRAND_ASSET=OK`，因为它只读样式表——
一个不读某个面的检查，报的"覆盖"就是谎。

**读数**：`BRAND_FAVICON=SYNCED bytes=7701 -> 9494 region=inserted`；
`BRAND_ASSET=OK svg=1110B paths=2 encodings=2 default=paper light_flips=2 favicon=1194B composed_from_source=yes`；
`design-lab/tests/test_workbench_brand_asset.py` → `Ran 24 tests OK`（新增 8 条，全部能红）；
真 Chromium 对**服务出去的那一页**读回 `{"link":true,"type":"image/svg+xml","dataUri":true,"bytes":1618,
"loaded":true,"naturalWidth":160,"naturalHeight":156}`，并在 16/32/48 三档 × 亮/暗两种工具条底色下截图看过：
16px 亮底时暗块与浅色 D 都立得住，暗底时方块与 chrome 融成一片、由浅色字形独自承重——两种都读得清，
这正是翻墨色的目的。**渲染件没有入仓，这里要如实说**：两张判定用的 PNG 一度被提交，随后在同一轮里退回`git rm --cached`。原因是 `DL-AST-001`：受跟踪的二进制必须带 `asset-sidecar/v1`，而 `redistributable:false` 的二进制还要带**具名人工批准的、未过期的** exception；品牌标志自己的 sidecar 写的就是 `redistributable:false`，它的一次 Chromium 渲染继承这个属性，而**本轮会话不能替 owner 签这份批准**。所以六张图留在 `.project-local/`（不随克隆），回执里以 sha256+bytes 点名，谁都能重跑探针再导出同一批图；这条同时记下：**往仓库加二进制之前先读资产治理规则**，我加了两个文件却只跑了 counts/path-refs/structure 三把便宜闸，没重跑 77 项聚合与 license coverage，于是 CI 替我发现了它。

**一处要如实记下的自造缺陷**：新用例第一次跑就红，成因是我拼接的正则把结尾写成 `);"` 而不是 `");`——
它在 CSS 里找一个不存在的顺序。修法是抽出 `_css_encodings()` 一处读，别在两个类里各写一份正则；
**但旧类那份没能并过来**（锚点转义又不匹配，第二次踩同一个 heredoc 教训），所以今天仓里是两个读者读同一件事，
helper 的 docstring 已把这句话写在那里，不再声称"一处读"。
**同一轮里第二个自造缺陷**：§5.87 那次替换把 `**下一轮按此顺序**：` 这个锚点本身吃掉了
（替换串以锚点开头，替换文本里没有再吐出它），列表因此裸奔了一段——这正是记忆里
"anchored insert must re-emit the anchor"点名的老坑，第三次踩。本节这次替换前先核对了锚点计数，
补回后列表重新挂回它的小标题下（该短语在 §5.87 的引文里还出现一次，所以计数不是证据，读上下文才是）。

**下一轮按此顺序**：① ~~把 `integrations/adapter-registry.json` 与本轮登记件纳入 wheel 的 force-include 并在干净 venv 里证明~~ —— **已由 §5.87 做完**（安装态 `registry=READ pack=READ connectors=11`，改动前工件同一条断言红在 `'MISSING' != 'READ'`；"可接受的降级"那句判断作废）；② LAYER 2 仓库内历史归档合并（`docs/audits` 842 个受跟踪文件是最大面），
按"冻结原件原字节不动、只换指针与取代关系"执行并重绑登记件/权威链/投影；
③ 若 owner 授权探测，才做第一次真 probe 并把读数写成新回执——**默认仍是 NOT_PROBED**；
④ 提示词读回的界面翻页线索、其余 8 条无界路由、五份 CSS 花括号扫描器收敛、附件 `width/height/media_type`
写入时物化（带迁移＋precheck＋合同行）这些旧账照原顺序。
⑤ ~~浏览器标签图标~~ —— **已由 §5.88 做完**（`--sync-favicon` 派生 + `--check` 双覆盖 + 8 条可红用例 + 真 Chromium 16/32/48 看过，两张判定渲染随回执入仓）；
⑥ ~~首屏双列（最近方案进右列）**未做**，动 `flex-wrap` 后必须重量常驻页脚与窄窗行框~~ ——
**已由 §5.89 做完**（改的是默认路由 `''` 那一面，不是早已双列的 `#/assistant`；右列真读
`?limit=5` 的方案列表，三条"没读到"与一条"读到 0 条"分开写；本轮没有新增 `flex-wrap`，
页脚与窄窗仍按那句要求重量了，读数在 §5.89）。
本轮四刀里 ①③④ 已交（① 是把前提证伪后改的字面：`byte_size` 本来就在发，页面读的是从未发出的字段），② 与 ④ 中的双列一屏见上条 ⑤⑥，均为 NOT_STARTED，不是缺口被抹平。

**逐字基线**（本轮最终 head 的 CI 读数由下一轮自己读，不要抄这里的数字）：
`PYTHON_TESTS_UNION=OK expected=3415 …` 是 `58abdc69`/`766f48d2` 时代的人口，本轮新增 11 条自动化用例后
人口会变，**必须重取**；`VERIFY_DESIGN_LAB=OK total=77 failed=0`；`BROWSER_E2E ran=44 skipped=0 failed=0`；
`DOCUMENTED_COUNTS=PASS claims=21 route_views=25 cli=24 adapters=41 routes=89`，**8 条无界路由** 这句必须逐字保持。

**边界逐字不变**：只做桌面端，手机端是**排除项**；三方素材与字库在项目范围外；E 盘不动；
不部署模型、不自行下载权重、不宣称推理已验证；`UNKNOWN` 不写成合格；云端选项必须披露离开本机的数据；
编号由用户填写或显式选 `UNUSED`；验收与签字只认具名真人；候选导出是读回不是发送；
AAOS 不是依赖、门或待排期联调项；release、安装态分发、真实宿主 E3、真人 E4、ComfyUI、MiniMax H3 继续冻结；
旧 34 项仍 `FROZEN_DEFERRED`；**`windows` 桌面 UI 自动化连接器未启用，启用需 owner 另给明确授权**；
包内 21 个真实公司名品牌模板与各上游组件许可归属仍待 Rights gate；21 份 `SKILL.md` 与 install 字样是惰性素材，
不进指令面、prompt、工具发现或能力计数；不得靠改断言、删接口、硬改能力标记或把失败改成演示成功来通过；
`.codebuddy/` 与 `.cursor/` 永不暂存；**#277 的合并与分支收口由 owner 2026-10-28 明确授权并已在本轮执行**，
之后任何新的合并、推送、发布仍分别判断授权。

**§5.89（2026-10-28 续）首屏双列：最近方案进右列——先把"哪一屏"量出来再动手。**
owner 那一刀的原文是"首屏双列（最近方案进右列）"，入口记为未做。但仓里 `#/assistant` **早就是**
双列且方案在右列（`.split as-split` 由 `2d9372fb` 于 2026-10-24 引入，`git log -S` 核过，早于这条
"未做"的读数），所以照字面再改一遍就是重复施工。真 Chromium 对照两面才定下主语：默认路由 `''`
（应用打开时的第一面，遗留工作台）的 `.grid` 只有 01 导入与 02 读回预览，两栏 512/692 各剩约
250px 空白，右栏那块是一个从未导入过东西的棋盘占位，03 执行历史在 900px 折叠线以下。**这一刀改的是
那一面**，回执 `dl-kb-06-first-screen-two-columns-recent-plans-right-20261028`。

**改法**：`.grid` 的两个面板包进左 `.col`（导入 → 读回预览仍上下相邻），右 `.col` 是新的
最近方案面板（eyebrow `RECENT PLANS`，**不占 01–05 编号**——那条序列是导入→读回→记录→产物→
设计层，方案列不在其中）。CSS 只加 `.grid>.col{display:grid;gap:inherit;align-content:start;min-width:0}`
与 `.plan-line`：`gap` 用 `inherit` 而不是再写一遍数值（列间距是 `.grid` 的财产，写两份下次只改到
一份），所以债闸读数一字未动（`literal_px` 仍 526、`literal_colors` 仍 26）。新列读
`GET /api/projects/{id}/assistance-plans?limit=5`——**有界**，`「8 条无界路由」` 那句逐字未动，
`DOCUMENTED_COUNTS=PASS claims=21 route_views=25 cli=24 adapters=41 routes=89`。

**说法是三条不是一条**：未选项目 / 读被拒 / 响应缺 `plans` 字段各有一句，只说"这一列没读到"；
只有服务真发回 0 条才说"这个项目共 0 条"。排序写成"服务按写入时间倒序发回"，因为
`assistance_plan.py::AssistancePlans.list` 自己就是 `ORDER BY r.created_at DESC` 取每计划的最新
修订——"最近"是服务的读数，页面不替它下结论；`total/returned/一页之外` 三个数逐字挂在读回上。
第二个读者出现时，方案列表信封的 TS 形状不能留两份：`AssistancePlanRow`/`AssistancePlanListView`
从 `shell.ts` 的局部声明**移进** `contracts.ts`，`shell.ts` 改从 `contracts.js` 导入。

**证伪**：新增 `design-lab/tests/test_workbench_first_screen_columns.py`（14 条，其中 8 条植入
各自定罪：第三个面板被直接加进 `.grid`、方案面板被搬进左列、id 丢失、`.grid>.col` 出现第二份
或被改写死长度、`.plan-line` 被降级、未读态说成"没有方案记录"、初始句两处写手漂移、目的地不在
`ROUTE_VIEWS` 里、读回失去界限、信封长出第二份声明）。几何那半在 overflow 闸里加 `firstScreen`
读数（列数/轨道数/是否并排/面板是否真在第二列/那句话是否真被画出来/文档是否变宽），
`_assert_first_screen_columns` 在三套主题下都读它，并配 6 个植入方向证明它不是无条件通过。
**这条断言在上线前被真实运行判红过一次**：第一版写死"折叠线上必须说没读过"，而闸的夹具在交互步骤
里建了一条真方案，首屏读到的是 1 条不是 0 条——改成与状态无关的一致性检查（画出行数 N 就必须印
"读到 N 条"，没有行才允许说没读到），它才既管得住谎也管得住自己的假设。

**读数**：`tsc --noEmit` 干净、`vite build` 632344B（服务出去的字节与工作树逐字节同摘要
`aff3697ca5c9e609515c3c73cbbe5dd6b99ef60a932c1313d67a6171469cbb7a`）、unit/appshell/shape-notice
全过（seam 仍 62 处且每处有报告）；`test_workbench_css_single_definition` 17 OK（`.plan-line` 与
`.plan-line small` 不算重复定义）、`test_workbench_route_calls` 23 OK、`test_workbench_weight`
22 OK、`STRUCTURE_CONTRACTS=PASS tests=31`（这一步不在聚合那 77 条里）、
`Ran 5 tests in 406.417s OK`（overflow 闸，三套主题各一次真 Chromium，报告
`dcefafc669ed3f5b1e6bf54a1f109e8ef492463aa03aefd3aae0a20ba8307392`）、
`Ran 32 tests in 303.413s OK`（对比度闸：新行的正文与 `--muted` 小字三套配色都过——**本地是
Windows，云上 Linux 的读数仍要由承载本 head 的 PR run 自己说**）、`VERIFY_DESIGN_LAB=OK total=77
failed=0`（在记录入仓前跑的，收口后须复跑）。

**看过**：播种 7 条真方案（`limit=5` 所以必然出现"还有 2 条在这一页之外"），1440/1280/1100 三档
两列并排、方案面板在第二列、底边 862/862/882 均在 900 折叠线内；700 档（≤760 媒体查询）自动落回
一列；每档 `docScrollWidth` 等于视口宽、`consoleErrors=0`；点「在设计辅助中查看全部方案」确实换到
`#/assistant` 并读到 7 行。**页脚这条按 owner 的要求重量了**：本轮**没有新增 `flex-wrap`**，
量到的事实是——首屏那面 `.sidebar-footer` 画的是 `0×0`（B10 侧栏在遗留工作台路由不画），随内容
下移的是 `body > footer`（静态、非吸附，1440 档实测 `y=3090`、700 档 `y=4659` 且 `wrap` 生效时
仍是一行）；改动前的同一点没量过，所以这里只报改后读数，不给差值。侧栏页脚与导航切线的 6px
底线仍由 overflow 闸在三种主题下量着。渲染件按 `DL-AST-001` 不入仓（品牌标志 sidecar 写着
`redistributable:false`，本轮会话不能替 owner 签那份具名批准），九张图以 sha256+bytes 在回执里点名。

**顺手抓到并修掉的一处旧缺陷**：起手 `git status` 露出 `apps/workbench/brand/index-synthetic.html`
——`test_workbench_brand_asset.py` 的夹具每次运行往**受跟踪素材目录**写文件且从不删，派生投影还把
它登记成证据主体路径（`reports/current/PROJECT_STATUS.json`、`CLOUD_BASELINE.json`、
`current-report-index.json` 都点名一个 clone 里不存在的文件）。这正是"存在不等于交付"那一类：
记录指向的东西必须按 `git ls-files` 核，不是按 `Path.exists()`。夹具改到忽略根并跑完即删
（`8a4f37771e4e06a161fa95120e55a7100991e27a`），24 条仍全绿。

**这一刀自己造了一条 CI 红，成因如实写在这里。** PR #279 第一条 run（40747812300）的 Python gate
红一条：`test_workbench_native_ui…test_list_responses_and_errors_cannot_overwrite_newer_refresh`
（`function='refresh'`，success 与 error 两个方向都红），raise site 是 bundle 里
`recentPlans` 的 `TypeError: Cannot read properties of undefined (reading 'length')`。
根因是**我用错工具**：`shapeFieldMissing` 报的是 `apiOrEmpty` 那道 seam 自己补过的字段（它读
`SHAPE_MISSING` 符号），而这一列走的是 `api()`，不做形状归一化——于是一个 200 但没有 `plans`
数组的答复绕过所有检查，直接撞上 `data.plans.length`。类型注解读不到运行时。修法换成运行时真检查
`Array.isArray(data?.plans)`，说"未读回：响应里没有 plans 数组"，并新增
`assert_guard_precedes_dereference` 钉住"守卫必须在读之前"（没有守卫 / 守卫在读后 / 整列不再读
信封，三种各自定罪）。**流程上的缺口才是这条红真正要记的东西**：推送前我跑了 css-single-def、
route-calls、weight、structure-contracts、debt、counts、overflow、contrast 八处，唯独没跑
**直接驱动被我改动的 `refresh()`** 的那个 vm 合同套件。把一次读加进共享函数之前，先 grep 谁在
驱动这个函数，把那些套件写进推送前清单。修后复跑：native_ui 15 OK、first_screen_columns 16 OK、
tsc 干净、unit/appshell/shape-notice 全过，四档几何与折叠线读数与修复前逐字一致。

**这条刀的 CI 读回（承载 head `81c46439` 的 PR run 40752513010，`conclusion=success`，
12 个作业 10 success / 2 skipped / 0 failed）**，逐字：
`PYTHON_TESTS_UNION=OK expected=3453 distinct=3453 ran=3453 duplicates=0 missing=0 unexpected=0`、
`VERIFY_DESIGN_LAB=OK total=77 failed=0`、`BROWSER_E2E ran=46 skipped=0 failed=0`、
`STRUCTURE_CONTRACTS=PASS tests=31 failures=0 errors=0`、`LICENSE_COVERAGE=OK (source headers +
binary sidecars complete)`、`RECORD_REGISTER_GATE=PASS checks=5 pathish_named=21 problems=0`、
`VERIFY_PROJECTION_FRESHNESS=OK records=14 verified=21 receipts=7 excluded=0 findings=0`、
`AUTHORITY_GATES=PASS gates=7 failed=none`、`WORKBENCH_WEIGHT_GATE=OK remote=0 bundle_gzip=167038`、
`WORKBENCH PACKAGING: all 5 Build-Output-Truth / packaging checks passed`。
人口从 3451 涨到 3453 就是守卫顺序那两条新用例，`missing=0 unexpected=0` 说明新模块被分片发现且没重复。
回执 `dl-final-t04-pr-run-read-at-81c46439-20261028`，账本 `currentExecution.evidence` 335 → 336。
`DOCUMENTED_COUNTS` / overflow / contrast 三处 CI 不单独打印判定行（它们跑在聚合里），
回执里如实写 `ABSENT`，不拿本地读数冒充云上读数。
**收口 head `67639cc9`（只含派生记录的那次重切）自己也过了全矩阵**：PR run 40755717217
`conclusion=success`，12 作业 10 success / 2 skipped / 0 failed——本轮到此结清，下一轮不必再为
这一刀重跑 CI。另记一次自己造的噪音：本地 union 里 `test_projection_freshness` 两条红
（`test_it_writes_no_tracked_file`、`test_the_gate_passes_and_prints_its_verdict_last`），
成因是我在 union 还在跑的时候并发跑了重生成脚本，读的一方看到写的一方留下的脏树；
安静树上一条命令复跑 `Ran 25 tests OK` 证伪了"这是产品缺陷"那个读法——**归因要有复跑，不要有推断**。

### 5.90 LAYER 2 的可执行那一半：跨波次指针登记（承载 head `32ac0bd5`）

owner 目标 ② 那句"冻结原件原字节、只换指针与取代关系"在两个面上成立度完全不同，上一轮只现数了
`docs/audits` 那一半（结论：待裁）。这一轮做另一半：`docs/history/**` 六波归档清单之间的**指针与取代关系**。

**现数（全部由 `python design-lab/scripts/verify_record_archive_crosswave.py --check` 复算，登记件在
`design-lab/config/record-archive-crosswave.json`；下面这组数**已被 §5.91 取代**——那一版只普查了
`docs/history/` 下的六份清单，第八份之后的正确读数是 8 清单 / 566 行 / 510 摘要 / 49 跨波次）**：
6 份清单 / 391 条成员行 / 340 个不同摘要 /
**48 个被两个及以上波次同时声称**，其中 **34 个**在 clone 里有受跟踪副本、**14 个**没有字节
（大对象按 `AGENTS.md` 留在 `.project-local/`，登记件单独成节并写明"不是不存在，也不是通过"）。
扫描面 643 个受跟踪 `docs/history` 文件。**摘的一律是 blob 摘要**（`git cat-file blob HEAD:<path>`），
不是工作树字节——`core.autocrlf=true` 让两者不同，记工作树就是把登记件绑在自己机器上。

**这一刀量出来的两条反直觉读数，比"做了什么"更值得传下去**：
① **34 行 in-clone 的 `canonicalPaths` 每一条都只有一个路径（>1 的有 0 条）**，且每一行恰好被 **2**
个波次声称（没有 3 个及以上的）。所以 `docs/history` 里根本不存在"同一份字节有两份受跟踪副本"，
重复的是**声称**不是**文件**——这一半同样没有可折叠的字节，能写的只有关系。这与上一轮 `docs/audits`
那个结论是同一个形状，两次独立现数都指向：**这个仓的历史归档问题不是体积问题，是可读性问题。**
② **6 波里只有 1 波带 `supersedes`**（r2 任务包那份，且它写的是三段结构而不是一个 bool），其余 5 波为
`null`。所以"取代关系"本来就不是普遍缺失的字段，登记件把它原样带出、不替 owner 补写——
把 5 个 `null` 填成"取代了某某"就是编造来源。

**证伪（同模块 13 条，6 个植入方向）**：丢登记件必须失败而不是空集通过；只认一种清单形状必须漏到
被定罪；成员行不带摘要不能算一条声称；34+14≠48 的分裂必须被拒；把包记成 owner 盘上的绝对路径必须被拒；
普查"看不见东西"时人口地板必须开火，而且**地板开火时 `--write` 必须拒绝落盘**——这一条是先写下才想到的：
一个能在自己瞎掉的时候把半个登记件写进仓的脚本，会把"没有读数"洗成"读数就是这样"。
每条 `canonicalPaths` 都被测试重新哈希回它被记的那个摘要，这是登记件唯一的价值所在。

**边界**：一个冻结字节都没动（回执里那条断言是从 `git show --name-only 32ac0bd5` 现读的：4 个路径，
落在 `docs/history/` 下 0 个）。这不是"历史归档已合并"。旧 34 项仍 `FROZEN_DEFERRED`，`docs/audits`
那一半仍待 owner 裁，release/E3/E4/真宿主/手机端/E 盘一律不动。

**这一刀自己发了一条 CI 红，读数与归因逐字写在回执
`dl-kb-06-ci-red-orphaned-crosswave-gate-run-20261028` 里**：承载 `32ac0bd5` 的 PR run 40763980787
`conclusion=failure`，12 个作业 **9 success / 2 skipped / 1 failed**，红的是
`STRUCTURE_CONTRACTS=FAIL tests=31 failures=1 errors=0` 那一步的
`test_gate_reachability.ReadOnlyModeTests.test_every_read_only_form_is_invoked_or_declared_with_its_measured_verdict`，
断言行 `AssertionError: Lists differ: ['verify_record_archive_crosswave.py'] != []`。
**根因**：我写了一个声明 `--check` 的新闸，却没有把它接到任何 CI 步骤上——这个仓里有一条专门管这件事的测试
（"一个没人调用的 `--check` 只是纸面闸门"）。同一条 by-name 规则**没有**报警，因为我自己那份新测试提到了这个脚本，
所以抓住它的只有"模式级"那条规则。这也是为什么**不能靠加豁免修**：豁免等于登记"这闸在 CI 里不可要求"，
而它其实有一个干净、便宜、只依赖标准库的家——就在隔壁那条 `Archive-wave record register gate` 后面。
修法：`.github/workflows/canonical-verify.yml` 的 `top-authority-gate` 作业加一步
`python design-lab/scripts/verify_record_archive_crosswave.py --check`，本地按 CI 原样复跑
`scripts/run_structure_contracts.py` 读回 `STRUCTURE_CONTRACTS=PASS tests=31 failures=0 errors=0`。

**两轮连续两条 CI 红是同一个形状，这条比红本身更该传下去**：我跑的都是**给我这次改动打分的那些闸**，
没跑**我这次改动会扰动的全仓不变量**。上一轮是驱动共享函数的那个 vm 合同套件，这一轮是审计闸门的那条测试。
推送前清单应该是后者——尤其这四条治理级测试：`test_gate_reachability`、`test_path_ref_gate`、
`test_documented_counts`（经 `verify_documented_counts.py`）、以及任何按 `glob==EXPECTED` 钉人口的清单测试。
另记两条诚实的边界：这条红停在 Early structure contracts 那一步，所以**这一轮 union 根本没跑**，
人口 3453 → 3466 仍只是预测，要等修好的 head 读回；我在本地起了整轮 union 复现，跑到 40 分钟仍未出读数，
而且中途我改了 `canonical-verify.yml`（正是那条测试要读的文件），那份读数的树已经不是我起步的树，
**判为不可引用后停掉了进程**，没有拿它当证据，也没有拿"本地没红"当"云上会绿"。

**修好之后的 CI 读回（承载 head `e0455c3b` 的 PR run 40772321348，`conclusion=success`，
12 个作业 10 success / 2 skipped / 0 failed）**，逐字取自 `gh run view --log`：
`CROSSWAVE=OK manifests=6 distinct=340 crossWave=48 inClone=34 outsideClone=14 tracked=643`
（**这条就是本次新接上的那一步真在 CI 里跑过**——同一份读数在本地与 Linux 干净检出上逐字相同）、
`STRUCTURE_CONTRACTS=PASS tests=31 failures=0 errors=0`、
`PYTHON_TESTS_UNION=OK expected=3466 distinct=3466 ran=3466 duplicates=0 missing=0 unexpected=0`
（上一段那个 3453 → 3466 的预测在这里被云上读数证实，`missing=0 unexpected=0` 说明新模块被分片发现且没重复）、
`RECORD_REGISTER_GATE=PASS checks=5 pathish_named=21 problems=0`、`PATH_REF_GATE=PASS checks=10 failed=[]`、
`VERIFY_DESIGN_LAB=OK total=77 failed=0`、`BROWSER_E2E ran=46 skipped=0 failed=0`、
`AUTHORITY_GATES=PASS gates=7 failed=none`、`VERIFY_PROJECTION_FRESHNESS=OK records=14 verified=21
receipts=7 excluded=0 findings=0`、`WORKBENCH_WEIGHT_GATE=OK remote=0 bundle_gzip=167038`、
`WORKBENCH PACKAGING: all 5 Build-Output-Truth / packaging checks passed`、
`LICENSE_COVERAGE=OK (source headers + binary sidecars complete)`。
`DOCUMENTED_COUNTS` 与 `TASK_DOC_STATE_GATE` 两处 CI 不单独打印判定行（它们跑在聚合里），回执里如实写
`ABSENT`，不拿本地读数冒充云上读数。回执 `dl-final-t04-pr-run-read-at-e0455c3b-20261028`，
账本 `currentExecution.evidence` 338 → 339。

### 5.91 追正：§5.90 那份普查漏了两波，它漏的正是它自己要防的那类缺陷（承载 head `622c157c`）

收口之后我没有把 §5.90 当成"做完"，而是问了一句它最容易被问倒的话：**"六份清单"是这仓里全部，还是我
记得的那六份？** 现数回答是八份——`docs/taskpacks/20261019-direction/SOURCE-MANIFEST.json` 与
`docs/taskpacks/20261023-ui-kb/SOURCE-MANIFEST.json` 这两波住在冻结家族 `docs/history/` 之外，
`MANIFESTS` 是手写的六条，于是整波没被打开过。补全后的两组读数（各自从两个提交里的登记件读出，差值是
对两份产物做算术不是回忆）：

| | 6 波（`f9689fa7`） | 8 波（`622c157c`） | 差 |
|---|---|---|---|
| 清单 | 6 | 8 | +2 |
| 成员行 | 391 | 566 | +175 |
| 不同摘要 | 340 | 510 | +170 |
| 跨波次 | 48 | **49** | **+1** |
| 有字节在 clone | 34 | 35 | +1 |
| 扫描面 | 643 | 1625 | +982 |

**漏的不只是数字，是一条真实关系**：`docs/taskpacks/20261023-ui-kb/source/`
`DESIGN-LAB_今日完整需求与可行性方案_20261023.html`（59,898 字节）同时被 2026-10-23 的归档清单与
20261023 任务包的来源清单登记为同一份字节——这正是 `AGENTS.md` 里"HTML 与包内同名成员逐字节相同，
只留一份"那句话的摘要级证据。在此之前它只是散文，谁也证不了；能证它的那份普查恰好没打开那个文件。

**第二次自打脸，值得单独记**：我做这个核查用的第一版探针自己也是错的——它只认顶层 `members` 键，
对着登记件的 340 报出 152。同一个缺陷类低了一层的复现。所以修法不是"我把六改成都对了"，而是
**取消手写人口**：`discover_manifests()` 从 `git ls-files -z -- docs` 现数，
与声明的 tuple 两个方向不一致各自拒绝（`MANIFEST_NOT_CENSUSED` / `MANIFEST_DECLARED_BUT_ABSENT`），
测试里两个方向各种植一次，再加一条正对照断言"声明必须等于 git 现数，且 `docs/taskpacks` 出现在根里"。
`members_of()` 补第三种形状，`PATH_KEYS` 补 `landingPath`/`name`；地板按新读数重设
（1625/510/49 → 1200/450/40），注释里写明被取代的那组数是被范围限制出来的。测试 13 → 16 条。
回执 `dl-kb-06-crosswave-census-scope-corrected-20261028`（含 before/after/delta 与那条新配对的逐字出处），
账本 339 → 340。**一个冻结字节仍然没动，49 行里 `canonicalPaths`>1 的仍是 0 行，每行仍恰好被 2 波声称。**

**教训只有一句**：登记"覆盖范围"的那句话，必须是机器数出来的，不能是我按目录想出来的。

**补两条 CI 逐字读数（两把尺子，不是我说一致就一致）**：承载 `f9689fa7` 的 PR run 40776458027
`conclusion=success`（12 作业 10 success / 2 skipped / 0 failed），那一步的 CROSSWAVE 行还是六波旧数
`manifests=6 distinct=340 crossWave=48 inClone=34 outsideClone=14 tracked=643`；承载补全后普查的
`feb23a11` 的 PR run 40779786064 同样 `conclusion=success`（10/2/0），同一行读成
`CROSSWAVE=OK manifests=8 distinct=510 crossWave=49 inClone=35 outsideClone=14 tracked=1625`，
`PYTHON_TESTS_UNION=OK expected=3466 distinct=3466 ran=3466 duplicates=0 missing=0 unexpected=0`、
`VERIFY_PROJECTION_FRESHNESS=OK records=14 verified=21 receipts=7 excluded=0 findings=0`、
`STRUCTURE_CONTRACTS=PASS tests=31 failures=0 errors=0`。两行差集就是上表那六个 delta，
在 Linux 干净检出上复现——**被漏掉的两波是仓的属性，不是我这台机器上的目录树现象**。
回执：`dl-final-t04-pr-run-read-at-f9689fa7-20261028`、`dl-final-t04-pr-run-read-at-feb23a11-20261028`，
账本 340 → 342。

**下一轮按此顺序**：⓪ 先读承载本轮最后那条"只含派生记录"的 head 的 PR run 全矩阵并逐字记账
（本节写到这里时它还在跑，本轮不替它预填绿；用 `gh run list --branch <工作分支> --limit 2
--json databaseId,headSha,status,conclusion,event` 点名那个 SHA，别看旧 run）；
① `docs/audits` 的字节去重仍**待 owner 裁**，工程上没有第二件可做的事——现数：
842 个受跟踪文件 / 8,141,995 字节（按 blob 计，不按工作树），其中逐字节相同的只有 77 组 / 牵涉 256 个文件 /
冗余 179 份 / **545,455 字节**；全仓被文本点名的 `docs/audits` 路径共 27 条（25 条解析到受跟踪文件，2 条不解析），
点名者有 28 个文件在 `docs/audits` 之外，而**这 179 份重复里没有任何一份被点名**（按文件名取交集为 0），
且 73/77 组的重复是**同一个冻结导入包内部**的形状
（`DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/` 的 `harness/tmp-*`、`ui-kit/` 与 `ui-originals/` 两份、
`hermes-legacy` 的 `.staging-*` 目录与 `runtime/` 合同副本）。
所以要动的只能是"删 179 份重复、省 0.52 MiB"这个决定本身，而它直接撞那条"原字节不动、不批量搬迁或修改冻结原件"。
现数脚本与读数留在 `.project-local/task-runtime/twocol/measure_layer2.py` 与
`layer2-measure.json`（不随克隆），谁要复核一条命令就能重跑；`docs/history` 的指针层已由 §5.90 落完、
普查面由 §5.91 补全到全部 8 份清单（人口改由 `git ls-files` 现数，新增一波会先红
`MANIFEST_NOT_CENSUSED`，不再靠人记目录）；后续只在新增归档波次时重跑
`verify_record_archive_crosswave.py --write` 并按哈希链重切一次；
② 其余 8 条无界路由、五份 CSS 花括号扫描器收敛、附件 `width/height/media_type` 写入时物化
（带迁移＋precheck＋合同行）、提示词读回的界面翻页线索，照原顺序；
③ owner 原本四刀**至此全部交完**（① 磁贴名称/大小、③ 浏览器标签图标、④ 首屏双列已落，
② 缩略图与静态资源路由＋CSP 放宽仍是 owner 的安全决定，不顺手做）；
④ 真宿主第一次 probe 仍默认 `NOT_PROBED`，要 owner 明确授权探测才做。

**台账读数（2026-10-26 第二十五轮收口时现数，取代上面第二十四轮那一段的"当下"身份）**：本轮把上一轮欠的三件事全部落到"有实测读数"而不是"已实现"。① **精确 SHA 的 CI 矩阵读通了**：run 40211581088（PR，head `f9683930`）`conclusion=success`，10 个非 skipped 作业全绿，逐字 `PYTHON_TESTS_UNION=OK expected=3363 distinct=3363 ran=3363 duplicates=0 missing=0 unexpected=0`、`BROWSER_E2E ran=27 skipped=0 failed=0`。§5.59 那句"CI 已绿"曾被 §5.61 追正——它引的是换 logo **之前**的 SHA，教训写进记忆：**结清一轮的 CI 账必须点名叫到承载该变更的那个 SHA**。② **增强面对量过**：把 `.ambient` 的动画冻在关键帧每一档（0/3000/6000/9000/12000ms）后用同一个 `MEASURE` 谓词逐档量，`CT_MOTION_PASS poses=5 routes=24 checked=34170 belowAA=0 distinctTransforms=4`；四个不同变换（不是五个）恰因 0% 与 100% 同声明停靠点，这一条同时是"尺子在动"的反证。③ **`errors=0` 原来是空集**，且有两个不同成因：`.error[role=alert]` 那族（`#as-form-error`）选择器一直覆盖，缺的是**没人让界面拒绝一次**；`p.view-hint` 那族（知识/评审/权利/研究的 outcome 行）连 `role` 都没有，既是尺子盲区也是**读屏盲区**。现在闸门**自己点一次**空表单造出真失败（`CT_REFUSAL_PROVED … role=alert`），词表从 `shell.ts` 现数 6 个前缀经 `CT_REFUSAL_WORDS` 传入，**空词表时闸门拒绝开跑**；`RefusalPopulationIsGraded` 三条断言里有一条在它该红的时候红过（旧回执没有 `+refusal` 行）。

**造出拒绝态的下一步就抓到一支不达标的红字**：珍珠白的 `--color-error` 继承 `:root` 为炭黑面选的 `#F05252`，压白 3.48:1、压 `#F4F6F8` 3.21:1，8 条 run 报红。修法是**重指到同仓已有的实测值** `--uif-light-danger #ab384d`（6.17 / 5.69 / 5.20），不新造红（包只逐字给了六个值，不含错误色），默认炭黑一字节不动。教训：**一个永不出现的状态永远不会失败**，所以"绿"必须先问"这一项被画出来过吗"。

**粒子层零依赖落地**（按 owner 既有裁法"参考它的结构源代码进行复制"，不装 GSAP/tsparticles）：24 颗、只用两种品牌墨、`canvas` 挂进 `.app` 第一个子节点并占 `--layer-canvas-ambient`（实测 computed `zIndex:-2`），**在文字之下**所以不会覆盖字形；`?motion=enhanced&particles=static` 画**固定种子的一帧**（同时是包要求的低性能回退），`particles=live` 才动，`prefers-reduced-motion` 整层不挂。`data-motion` 与这块 canvas 现在都由**产品自己**产出——闸门走的是真实 URL（`/workbench?motion=enhanced&particles=static`），并且**挂不上就红**。`ui-layering.json` 的表被这条新规则**逼着同步**（`TABLE-SELECTOR-DRIFT` 先红了一次：表说 ambient 用这层，样式表现在有两个消费者），随后 `usedBy 1→2` 与 purpose 一起补上。bundle 现读 616351 字节 / gzip9 162258。聚合复跑：`VERIFY_DESIGN_LAB=OK total=76 failed=0`。

**两条被实测改写的台账说法**：①"唯一强调色 `#356B92` 待落"是**早已在仓**（stitch/light 块四个 token 全指它），不该再占施工单；②"`_list_prompt_results` 套 `PAGE_LIMIT` 是最成熟一刀"被**否掉后又真做完了**——`prompt-result-readback-v1.schema.json` 是 `additionalProperties:false` 闭集，所以这一刀**必须带上 schema**：六个信封键进 `properties`+`required`，`readback(project_id, offset, limit)` 默认 100/上限 200，**所有计数与 `newest`/`state`/`reviews` 在切片前取**（分页不可能把 400 条读成 100 条），`reviews` 明确永不翻页（截断签收记录＝隐藏决定），路由声明 `path_only` 后 `?limit=0/201/ten`、`?offset=-1` 各回具名 400，同轮从 `UNBOUNDED_REGISTER` 摘牌（现读 `list_routes=18 bounded=10 without_limit=8`）。`contracts.ts` 里没有这支读回的类型（先查后动），所以没碰任何 `.ts`。

**下一轮入口（按此顺序，别重做已完成的）**：⓪ 写"仓外路径"的测试**不要用 `tempfile`**——本仓 CI runner 把
`TMPDIR` 设在工作区里面，那条红（run 40331019135，head `fc9c8b0d`，Python gate 分片 2/3 两条 FAIL）
正是这么来的；要从 checkout 自己位置推，
并把前提写成断言。另外 push run 只跑轻闸（11 个重作业 `skipped`），套件结论只在 PR run 上，而推新 head 会把它
cancel 掉——结清一轮要在最终 head 上等它跑完；① 界面上的翻页 affordance——服务端默认页已是 100，前端调用点仍不传 `limit/offset`，要做的是"还有 N 条"这条可见线索（包明文：长列表分页或窗口化，初始最多 50 行——**注意包给的初始界是 50，本轮沿用的是本仓既有 PAGE 常量的 100**，两者不是一回事，要收口就按包的 50 或让 owner 裁定，别默认自己赢了）；② `particles=live` 的**动画过程**未做逐帧认证，只证了确定首帧；③ `audit_workbench_theme_geometry.mjs:56` 那份**硬编码**色板表仍缺 `stitch`，改它要把几何结论一起重读；④ 其余 **8 条无界路由**理由已逐条登记，不要套同一修法；⑤ 五份手写 CSS 花括号扫描器的收敛（每份豁免面不同，要逐个证明覆盖不丢）。

**边界逐字重述（一条没动）**：只做**桌面端**，手机端是**排除项**——不是待办、不是缺口、不派工；**不部署模型、不自行下载权重**，不宣称推理已验证，选择成功／连接成功／返回文本／内容可用**四件事分别验**；候选**导出是读回不是发送**；验收与签字**只认具名真人**；编号由用户填写或显式选 `UNUSED`，代理不得自行铸造标识当来源证据；**E 盘不动**；旧 **34 项仍 `FROZEN_DEFERRED`**，解冻任何一项都要 owner 新的明确授权；release、安装态分发、真实宿主 E3、真人 E4、ComfyUI、MiniMax H3、外部软件自动化、AAOS 联调**继续冻结**；**不得靠改断言、删接口、硬改能力标记或把失败改成演示成功来通过**；新包配色做成可选主题、不覆盖既有配色，已实测地板值不改；不擅自升级框架或改全局配置；`.codebuddy/` 与 `.cursor/` **永不暂存**。

**仍只等 owner 的事（不重复请示，只登记）**：`150KB` 上限是改写成"画像＋指标＋推导"（本机回环建议 CPU 预算：boot 主线程 JS ≤300ms、0 long task；若将来走网络＋gzip 则 JS ≤150KB 且关键路径总量 ≤170KB）还是维持原数并据此砍内容——本轮实测关键路径 gzip 合计约 202 KiB、bundle 单口径约 158 KiB，而回环服务**不 gzip**（`transferSize` 即全额），冷启动 `load` 93ms、0 long task；勾选框/radio 标签算不算违反「标签放输入上方」（实测同排样本如 `1440:preflight label vs input#jury-approve dy=-17px`）；品牌蓝 `#316CFF` 压白字 4.45:1 那条老裁定。真人视觉验收、模型调用、`DESIGN.md` 批准仍归 owner。

**台账读数（2026-10-25 第二十四轮收口时现数，取代上面第二十三轮那一段的"当下"身份）**：`currentExecution` 仍 50 行、直方图 **34 项 `FROZEN_DEFERRED`／`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`**，`evidence` 现数 **295→297**——两条新回执 `kb-13-motion-band-graded-to-pack-sentence-20261025`（轴 `unit`）与 `kb-06-enhanced-motion-layer-opt-in-20261025`（轴 `implementation`），`subject_sha` 都是 **`ada3ddd9`**（`feat(ui): put every transition inside the pack band, and give the opt-in motion layer a home`：`style.css`、`main.ts`、新增 `motion.ts`、`test_workbench_contrast_gate.py`、`build/main.js` 全在这一个提交里）。**本轮补的是卷宗 §5.60 与这条接续**；写这段时账本那两行与两枚回执 JSON 仍在工作树未提交，`git status --porcelain` 自己读，别抄这里。**owner 的新裁定逐字**：「界面去找动效交互 STITCH 更多是静态页面 一比一复刻完成后 找牛逼的组件库 加入更多动画动效粒子等UI组件库」——它只**新增**一个动效层，不放松任何既有边界；包内静态面那两句（`docs/taskpacks/20261023-ui-kb/source/09_DESIGN.md:5` 动效强度约 1/10、`:21`「仅必要的120–180ms opacity/transform 过渡；减少动态效果时移除」）对静态复刻面继续成立，动效层是叠加的、默认关闭的。**数字面**：`style.css` **20** 条 `transition` 声明、**16 条越界**——10 条没有属性表（等价 `transition-property:all`），被补间的非允许属性有 `background`、`border-color`、`box-shadow`、`filter`、SVG 几何属性 `r`，越时长读数 220ms×4、200ms×2、280ms×2、550ms×1；带本身是从样式表自身定义读出来的 `--motion-fast=120ms`／`--motion-base=180ms`／`--motion-slow=280ms`，尺子解析 token 后判数字而不是判字符串。**改法**：14 条收成只补间 `transform`（toast 为 `opacity,transform`，drawer 保留 `visibility 0s linear` 作为无障碍树离场的离散伴侣），5 处颜色/几何补间被删除（`button` 底色、`.stage-nav-btn` 边框底色、`.version-ring-node` 的 `r`、`.seg button` 的 `all`、`.graph-stage circle.node-dot` 的 `all`——后者保留 transform 180ms），drawer 由 .28s、`.review-inner` 由 .55s 收到 `--motion-base`。**这不是砍内容**，包内「不能为了轻量化删除必要内容」不受影响。**三枚例外是具名登记不是跳过**：`.ui-motion-fast/-base/-slow`（`all`，slow=280ms 越带）——UIKIT 的对外导出件、`0.28s` 被 `docs/audits/DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/evidence/W02-UTILITY-VERIFY.json` 钉住（原文 `"ui-motion-slow = 0.28s (--motion-slow)"`），且本产品内零消费者（`build/main.js`、8 个 `apps/workbench/*.ts`、`index.html` grep `ui-motion` 各 0 命中）；登记双向，第四条越界声明即红、登记项在 CSS 里消失也即红。**与 §5.55 同源**：`transition:all` 连墨色一起补间，那次 CI-only AA 红（`1920:target-profiles+combination button#tp-validate.primary-btn 1.06:1(stitch)/2.6:1(ui2026)`）量的是一帧任何规则里都不存在的中间态灰，本轮把这一缺陷类**在整个样式表范围内**关掉。**新尺**在 `design-lab/tests/test_workbench_contrast_gate.py` 的 `MotionBandFollowsThePack`，3 个用例（带内断言／三枚植入缺陷 `background-color 400ms ease`+`.5s ease` 裸简写+`transform 90ms ease` 低于下界／`all` 与墨色属性全站禁用），三枚全部被同一把尺抓到，所以零违规不是空输入；它与既有 `SRC-T07-MOTION-COMPOSITED`（`test_workbench_motion_gate.py` + `tests/e2e/audit_workbench_motion.mjs`，只禁会重排的补间、**主动发布 `transitionAllCount` 而拒绝判红**）是两把尺，谁也不顶谁。**动效层**：`motion.ts` 由 `main.ts` 引入、Vite 打进同一个 `build/main.js`，所以不新增被服务路径、不动 CSP 白名单；四个原语全部只写 `transform`（磁吸 ≤3px、双轴倾斜 ≤4deg、入场只位移**不用 opacity**、数字滚动最终逐字落回页面已发布的原值），用**一个 `pointermove` + 一个 `pointerleave` 的委托**实现（shell 会重渲染路由视图，boot 时逐元素绑监听会在下一次导航静默失效），默认 **static**：只有 URL `?motion=enhanced` 才启用，`prefers-reduced-motion: reduce` 一律退回 static。**构建与读数**：`vite build` 成功，`build/main.js` 610,364→**615,430 字节**，同档 gzip（level 9）
160,246→**161,916**（+1,670）——vite 自报的 164.50 kB 是另一刻度，别混用；`tsc --noEmit` 干净；node 三套
`tests/unit.mjs`（含 bundle 在 vm 下可执行、零顶层 import/export）、`tests/appshell.mjs`、
`tests/shape-notice-coverage.mjs`（61 个 seam 读数）全绿；聚合 `VERIFY_DESIGN_LAB=OK total=76 failed=0`。
**收完补间才发现的第二盲区**：`style.css` 还有 **4 条 `animation` 声明、全部 `infinite`**，而两把动效尺
都只读 `transition:`，谁都不管循环次数。按"选择器的每个 class 是否作为整词出现在 bundle 里"分死活
（子串会把散文 "DESIGN-LAB design **core**" 当成 `.core` 的消费者，第一版就误判过）：**live=1**
即 `.ambient` 的 `floatGlow 12s infinite`，每条路由都挂，也就是包里「无持续循环、自动播放和浮动装饰」
一直在默认界面上被违反；现只在 `:root[data-motion="enhanced"]` 下运行。**dead=3** `dashMove`/`pulse`/
`scanSweep`，宿主零消费者，是死 CSS 不是违规，登记在 `DEAD_LOOPS` 双向钉住（真被挂载就必须作用域化或具名登记）。
**渲染实测已做**（真服务+真 Chromium，`#/assistant`，1440×900）：默认面 `data-motion=null`、`.ambient`
`animation-name:none`、`iteration-count:1`；增强面 `data-motion=enhanced`、`animation-name:floatGlow`、
`iteration-count:infinite`；指针落在可见控件「设计辅助」上（`page.$` 首个匹配是折叠面板里的零尺寸盒，
必须按 rect 挑），静止 `none` → 默认面 hover `matrix(1,0,0,1,2.99,0)`（既有 CSS `translateX(3px)`，不是 JS）
→ 增强面 hover `matrix(1,0,0,1,0.96,0.82)`（委托磁吸），两面墨色恒为 `rgb(245,247,252)`；磁吸宿主 34、
倾斜宿主 10。截图在 `.project-local/task-runtime/motion-probe/shots/`。**自己造出来的新风险要一起交**：
增强面那 12s 浮动是在半透明卡片底（`color-mix(...surface2 74%)`）下方移动 `blur(80px)` 光斑，会改变文字底下的
合成背色——正是 §5.55 那一族"规则里不存在的一帧"；**增强面的对比度至今没量过**，要把它灌进对比度闸门做
逐帧采样才能从风险改成已证。**未测项如实**：真人视觉验收（测量与截图不等于 owner 说"像样"）、
粒子/氛围层**未选型未接入**（GSAP 3.13 gzip 27.2KB 但许可非 MIT；canvas-confetti ISC 4.3KB；
@tsparticles/slim MIT 30.5KB；pixi.js 226KB/lottie-web 76.8KB 不引入；react-bits、magicui 是
React+Tailwind，按 owner「参考它的结构源代码等进行复制」抄源码不装库）、
`scripts/measure_workbench_weight.py` 实测 `budgetDeclared=False`。

**下一轮入口＝动效层落地。** 起手**必须先跑两把动效尺**：`design-lab/tests/test_workbench_contrast_gate.py`（含新类 `MotionBandFollowsThePack` 与 `EnhancedMotionLayerStaysComposited`）与 `design-lab/tests/test_workbench_motion_gate.py`；它们红就先别写样式。待办按此顺序：① **把增强面灌进对比度闸门**——`?motion=enhanced` 下逐帧采样 `.ambient` 光斑在半透明卡片底下移动时的文字对比度，把 §5.60 里那条自造风险从"未量"改成"已证或已修"，这是粒子层开工前的**前置门**，不是并行项；② 粒子/氛围层选型已调研完（见上），按 owner「参考它的结构源代码等进行复制」的路子**抄结构自写**，硬条件四条不变——**离线打包**（`remoteReferences=0` 是已实测前提）、**不得补间文字墨色**、必须在 `prefers-reduced-motion` 下退让、**引入前后都要报 bundle 字节**；若真要装库，GSAP 需先过权利登记（非 MIT），canvas-confetti（ISC 4.3KB）是许可最干净的一条；③ `animation:` 那一半只有新尺管得到，`SRC-T07` 不看循环次数——新增任何 `animation` 前先确认它有没有消费者，死 CSS 进 `DEAD_LOOPS`、活的必须作用域化或具名登记；④ 别把"静态带已修好"写成"动效层已交付"，真人视觉验收仍未发生。

**边界逐字重述（不动）**：只做**桌面端**，手机端是**排除项**——不是待办、不是缺口、不派工；**本轮不部署模型、不自行下载权重**，不宣称推理已验证，选择成功／连接成功／返回文本／内容可用**四件事分别验**；候选**导出是读回不是发送**；验收与签字**只认具名真人**；编号由用户填写或显式选 `UNUSED`，代理不得自行铸造标识当来源证据；**E 盘不动**；旧 **34 项仍 `FROZEN_DEFERRED`**，解冻任何一项都要 owner 新的明确授权；release、安装态分发、真实宿主 E3、真人 E4、ComfyUI、MiniMax H3、外部软件自动化、AAOS 联调**继续冻结**；**不得靠改断言、删接口或把失败改成演示成功来通过**；`.codebuddy/` 与 `.cursor/` **永不暂存**。

**owner 只需要拍一件事**：**150 KB 上限**。两条路——(A) 按行业形态把这一句改写为「画像＋指标＋推导」：本机回环建议用 **CPU 预算**（boot 主线程 JS ≤300ms、0 long task）；若将来走网络＋gzip，则 **JS ≤150KB 且关键路径总量 ≤170KB**。(B) 维持原数，并据此砍内容。现状读数：这把尺自述不发明预算、`budgetDeclared=False`，而本轮新增 5KB 使 JS 单口径离包内那句 150KB 更远，关键路径合计 gzip（bundle+stylesheet+document，level 9）实测 **206,956 字节 = 202.1 KiB**。其余旧未裁项（勾选框标签算不算违反「标签放输入上方」、顶栏吸顶、标题阶梯、hover 墨色）照旧记账，不重复请示。

**台账读数（2026-10-25 第二十三轮收口时现数，取代上面第二十二轮那一段的"当下"身份）**：直方图仍 **`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`**，`evidence` 294→**295**（`kb-06-brand-mark-on-interface-20261025`，轴 `implementation`，`subject_sha=e297f967`）。**owner 点名 `D:/All projects/矢量LOGO` 要求换项目 logo，查出的真实缺口是"品牌件流水线有、消费者没有"**：`design-lab-mark.png` 只被自己的生成脚本与二进制清单引用；AppShell 导航头是纯文字；CSS 里 48px 的 `.brand-mark` 挂在**被注释掉的旧版侧栏**（实测 rect 0×0）；唯一在画的是旧版页头 52px `.mark`。所以换 logo 必须四件一起做：素材入库 + 槽位挂上 + 浅色翻墨 + **把守着位图管线的闸门一起改**（最后这件最容易漏，漏了就留一把永远校验废弃资产的死闸）。**切带不能手解路径，两次都栽在这**：正则抓 `d="..."` 把 17 条抓成 18（多一条空路径，"单标"只剩空的）；按坐标奇偶配 x/y 在 Illustrator 混合绝对/相对命令下无意义 → 产出 `viewBox` 4×4 的不可见图形而数字看着完全正常；改由 Chromium 解析源文件逐条读 `getBBox()`，在 20.97px 间隙切成单标 2 条 / 文字带 15 条（单标框 160.22×155.97）；第三个错是 viewBox 平移符号写反（`left-pad` 写成 `-left+pad`），**同样是渲染暴露的**。接法：导航头文字左侧 22px 单标（文字仍是可访问名，图形 aria-hidden）；`--brand-mark` 同一矢量两枚编码（paper 给炭黑默认、ink 给 ui2026/light 与 stitch/light），因为 background-image 不吃 currentColor，而 CSP `img-src data:` + workbench.py 三条固定路径意味着开资源路由要同时放宽两者——那是 owner 的安全决定不是便利。**两件未验证如实写**：应用自身主题控制器会在启动后重写 `data-palette`（注入值被改回 design-lab），且落地视图未找到可点主题控件（`clicked=null`）→ "浅色翻转渲染正确"已证（强制后 nav 底 255,255,255、字色 53,107,146、深墨压白），"**用户从当前视图一步切到珍珠白**"未证，那是 STITCH 施工单里主题入口的活。新闸第一次运行冤枉了一份正确样式表（`light_flips` 多减 1）→ 读回 CSS 后修检查器而非改 CSS。`verify_projection_freshness` 又抓到我一次：新规则带 4 个字面 px，`DESIGN.md` §4 债句 517→**521** 必须跟改（字面色值那栏工具明写 agent 不得填，未动）。**并结清上一轮欠账**：run `40191207017`（head `bdaf4883`）`conclusion=success`，逐字 `BROWSER_E2E ran=17 skipped=0 failed=0`（含 contrast_gate ran=6、preflight_handoff ran=1）、三分片 exit=0 且 FAIL=0、`PYTHON_TESTS_UNION=OK expected=3352 distinct=3352 ran=3352 duplicates=0 missing=0 unexpected=0`，strict-TS 与 Python gate 均 success——前两轮两条红（PIL 依赖、漂移清单）确认消失。`LOGO.ai` 只按哈希登记不入库（仓库过体积警戒线 + 从 .ai 导出需驱动 Illustrator＝冻结项）。复验：node 三套全过、42 条 CSS 相关 python OK、`LICENSE_COVERAGE=OK`、`BRAND_ASSET=OK paths=2 encodings=2 light_flips=2`、聚合 `VERIFY_DESIGN_LAB=OK total=76 failed=0`。**下一轮顺序不变**：STITCH 施工单 S1（强调色唯一化，重测 AA——那条曾被撤回的债，其"CI 两条红"证据已被 §5.55 证明是补间中间帧）→ S2（过渡只留 opacity/transform，包原句「仅必要的120–180ms opacity/transform」）→ S3（标题阶梯，包参照 42/27/19）→ S4（列表界=50 与附件缩略物化，两条都是包明文要求，不再等 owner）→ S5（错误紧邻：闸门自己造一次真失败）→ S6（按占比减非必要字节，不删功能不换栈）。仍待 owner 的只剩两件：勾选框标签算不算违反「标签放输入上方」、以及 150 KB 是认账减重还是改数。

**台账读数（2026-10-25 第二十二轮收口时现数，取代上面第二十一轮那一段的"当下"身份）**：直方图仍 **`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`**，`evidence` 291→**292**（`DL-KB-13` 一条 `visual_review`；`DL-KB-13` **仍 PARTIAL，两处都不是工程缺口**——150 KB 上限要 owner 裁定、无指导真人任务要真人）。**本轮的判据被 owner 纠正过一次，写下来免得下一轮又用错**：我按"有没有引用"判有用没用，被指出**「有用没用的判定不是有没有引用，是对项目还有没有用」**；改成按职责判（去掉它，项目能证明或能承诺的会不会变少），否则我会删掉 `model_radar.resolve()`——它是「零 checksum／许可冲突／模型不存在／硬件不足必须 fail closed」这条承诺的唯一承担者，它零生产消费者只说明本机没有加载模型的 runtime（模型部署是冻结项）。**落地七件，都有改前/改后实测**：① `GET /api/projects/<32hex>` 未知 id 改前实测 `http.client.RemoteDisconnected`（与"服务挂了"同形）→ 404 `PROJECT_NOT_FOUND`，并把两种 404 分开钉（畸形 id 归路由模式、合法但不存在归 handler）；② `drain_body` 注释承诺"失败即忽略"却无 `try`，超时在 `except` 内再抛出，正是它要防的 10053；③ `MAX_QUERY=200` 声明了没人读 → 真拒绝 `KNOWLEDGE_QUERY_TOO_LONG`，且恰好 200 字符合法（界不是墙）；④ 合同行承诺的 `KNOWLEDGE_OFFSET_INVALID`／`KNOWLEDGE_LIMIT_INVALID` **全仓零测试**，三条一起钉；⑤ **`test_workbench_preflight_handoff_e2e` 本地 2.039s 通过，却不在 no-skip 注册表、也不被任何 workflow 步骤点名——CI 从没跑过这把浏览器尺**；登记前先把它 Windows 专属的 `chrome-win*` glob 换成其余七把尺共用的跨平台发现函数（注册表自己会 `setdefault('E2E_NODE_MODULES', apps/workbench)`，所以登记安全），现 `BROWSER_E2E ran=17 skipped=0 failed=0`；⑥ `test:unit` 直跑已提交 bundle，改 `shell.ts` 后本地"绿"测的是改前字节 → 脚本内先 `vite build`（pnpm 在此不跑 pre/post 钩子），重建后 bundle **零漂移**；⑦ `verify_fresh_clone.py` 问完 `shutil.which('uv')` 又无条件写 `uv is absent`；聚合链用 `sys.executable` 派生子进程，同一提交 `.venv` 下 `failed=0`、裸解释器下 `failed=29`——现拒绝并点名解释器与缺的声明依赖，需求集仍从 `pyproject.toml` 读。**删与迁**：清出 **25 个**无任何 `var()` 读、也无源码/闸门/测试/schema/包内按名断言的自定义属性（27 行、593 字节，`style.css` 121,964→121,371）；**防复发的是把普查闸的人口补全**——既有 CONSUMPTION 检查只看包点名的 `--uif-*`，整族死声明一直在它视野外（覆盖率闸永远只证明它自己携带的那张表），新规则枚举全部声明属性、例外交给既有 `SPEC_PROVENANCE` 判定，不手抄 allowlist。无界列表路由也从"打印一个数"升级成"钉一张登记面"：18 条带列表 GET 里 **9 条无界**，逐条带理由；**新增第十条即红，绑好却不摘牌也即红**。**一条别走错的路**：附件那条（200 张 47,160 B 时服务端 199.59 ms，其中 path+stat **59.0%**、两次图像解码 **30.5%**、hash 仅 **2.4%**）**不该用分页修**——成本来自每行重校验而不是行数，`width/height/media_type` 未落库，真修法是写入时物化，属带迁移/precheck/合同行的 state-schema 单独一刀；截断列表看着像进步而毫秒数一毫秒不会少，还会让"附件多于 N 张"在界面上不可见。**该并而本轮没并**：五份手写 CSS 花括号扫描器——每份豁免清单与断言面不同，合并要逐个证明输出集不丢。**下一刀按此顺序**：① `_list_prompt_results` 套用仓内已有的 `PAGE_LIMIT=100` 信封（最接近可直接落地的一条，`task_queries._envelope` 就是现成结构，别再造第二个主人）；② 附件写入时物化 `width/height/media_type`（先出迁移+precheck+合同行方案再动）；③ 五份 CSS 扫描器收敛，逐个证明覆盖不丢；④ 「错误紧邻字段」仍需闸门先制造一次真实失败态。**我自己这轮的仪器错误四条也入账**（因为它们是下一轮的陷阱）：清扫第一遍把文档/证据里的名字当消费者只删 14 个；普查闸初版复用只匹配 `--uif-*` 的 `declarations()` 造成**恒真即假断言**，植 `--space-dead-99` 才暴露；404 测试连错两次 id 形状（64 位与 `p-` 前缀都不匹配 `([0-9a-f]{32})`），差点把"兄弟模块用词不一致"当结论；**登记时锚点行没重出，等于把 `test_workbench_motion_gate` 从元组删掉**——靠 `git diff` 只显示「+1/0 删除」发现并 AST 复核=8 项。另：删 `--info` 使 `--color-info` 成孤儿，故清扫必须迭代到不动点（第 2、3 遍各 0 删除）；我写的"理由须满 40 字"规则逮到自己写的填充条目。**复测**：聚合 `VERIFY_DESIGN_LAB=OK total=76 failed=0`（清扫后与登记后各一次）；CSS 清扫后对比度 `checked=16258 belowAA=0 controlMisses=0 unparsable=0`；单元 44+110+21+19+21+9 OK；`TEST_SELF_SUFFICIENCY=OK modules=259 violations=0`；`KNOWLEDGE_SEARCH_P95_MS=34.7 budget=300`。上一轮那条"只在远端出现的 AA"已定位为 `transition-property:all` 的补间中间帧（见 §5.55），本轮未动它。owner 未裁项：150 KB 上限、顶栏吸顶、标题阶梯、勾选框标签、hover 墨色，**新增一件**：`_list_prompt_results` 要不要套 `PAGE_LIMIT` 信封（它是登记面里最成熟的一条）。**同轮补记（第二十二轮收尾时推送后 CI 抓的红）**：推送 `1d86e877` 后 `Workbench strict-TS product gate` 红，步骤 `python3 scripts/measure_workbench_weight.py --check`，逐字 `MEASURE_SOURCE_MOVED cannot import the route table: ModuleNotFoundError: No module named 'PIL'`——**造成者是本轮我新加的 DL-KB-13 读数**，它为拿 `ROUTES` 去 `from design_lab.http_service import ROUTES`，链上到达 `image_assets` 并需要 Pillow，而 strict-TS 是 node 作业、不装任何 Python 第三方包；本机 `.venv` 有 Pillow 所以本地绿远端红。**修法不是给 CI 加安装也不是动 workflow**：改回复用本脚本自带的 AST 静态读取（`parse`/`module_tables`），`--check` 回到纯标准库；并拆开一个字段干两件事的通道——`readerError`=读不到路由表（致命），新增 `callSiteError`=规范匹配器不可用（如实报缺失，绝不当成 0；此前 `frontend_calls=0` 被这把尺自己当致命错，会把"这列没测"报成"路由表变了"）；解析出的轻量路由实现 `accepts()` 以兼容规范匹配器 `route_matches`，带 `when=` 的路由（全表仅 `_task_detail_or_events` 一条，非列表路由）无法从文本求值即抛 `ValueError`，调用方本就按 dynamic call shape 处理，不答 True 造成静默过匹配。三把防复发闸：函数体外不得模块级 import 非标准库、客户端列不可用必须点名失败、`when=` 必须拒绝求值。**复验用 CI 的真实条件而非我的 venv**：裸解释器 `list_routes=18 bounded=9 without_limit=9`、NOTE 点名缺失匹配器、`GATE=OK`、exit 0；venv 下同三核心数另加 `frontend_call_sites_scanned=142`。代码 `31862800`，`evidence` 292→**293**（`kb-13-gate-toolchain-coupling-20261025`，轴 `browser`），卷宗 §5.57，直方图不变。**教训写给下一轮**：新增任何读数/尺子时，先问"它跑在哪个作业、那个作业装了什么"——工具依赖面大于环境装机面，产出的就是只在本机成立的绿。**再补记（同轮第二次远端红，红在账本纪律上）**：推送 `d8962779` 后 `Python gate` 分片 1/3 报一条 FAIL —— `test_evidence_artifact_presence...test_tracked_artefacts_of_the_real_ledger_all_read_back`（`outcomes={'FAIL': 1, 'PASS': 1018, 'SKIP': 14}`），而同一矩阵 **`Workbench browser E2E` 绿**（证明 `--check` 纯标准库化与预检套件登记在 Linux 都成立）。这不是产品回归而是纪律生效：本轮给 `test_design_layer_http.py` 加了 404 测试，而冻结记录 `r5-workbench-http-native-ui-reobserved-20261006` 把那个模块当工件哈希，那条 2026-10-06 观察因此比它命名的文件更旧。处置顺序很重要：**先从闸自身重算活清单并与钉住集合双向 diff**（钉 30 对/64、活 31 对/65，唯一差异即此对，无计数位移、无消失、broken=0），再按本文件惯例把这一对带日期理由加入期望集合、总数 pin 64→65 写进变更日志，**旧记录不改写**；把条目从账本删掉或取消"双向精确"才是不诚实做法。改完自检 钉65==活65、new/moves/vanished 全空——编辑该测试模块本身没有让它自绑的记录多出一对（那对早已在清单内，即 2026-10-19 注释所说的"闸门模块让自己的绑定记录变老"）。代码 `9d4a17ca`，`evidence` 293→**294**（`kb-13-drift-inventory-repin-20261025`，轴 `unit`），卷宗 §5.58，直方图不变。**给下一轮的判据**：凡是改了被冻结记录当工件的文件，先跑 `design-lab/scripts/verify_evidence_artifact_presence.py` 现数并与 `test_evidence_artifact_presence.py` 的钉住集合 diff，再收尾——这条闸是设计来抓你的，不是来添乱的。

**台账读数（2026-10-25 第二十一轮收口时现数，取代上面第二十轮那一段的"当下"身份）**：直方图仍 **`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`**，`evidence` 290→**291**（`DL-KB-06` 第 **17** 条，轴记 `visual_review`——顺带更正上面几轮的说法：16→17 是**任务内总序号**，`DL-KB-06` 的 `visual_review` 行只有 8 条，前几轮把它写成"第 16 条 visual_review"是不精确的），状态仍 `DONE`，旧 34 项一项未解冻）。**先更正交接的前提**：读 CI 实况时尖端已经不红了——PR run `40170639181`（head_sha `13df2a9e`）`Workbench browser E2E` 通过，`BROWSER_E2E ran=15 skipped=0 failed=0`；红的是更早的 `40168878523`（head_sha `b5b59927`）。**所以本轮不是把一条红拧成绿**：同一条路径红过两次、绿过一次，差别只在采样时刻落不落在那 200ms 里，绿的那次什么都没修。**根因是量出来的**：四类动作按钮共享规则写 `transition:.2s ease`，简写不带属性表＝`transition-property:all`，启用↔禁用切换把 `color` 与 `background-color` 一起补间。rAF 逐帧采样（1920/stitch-light）读到墨色 `rgb(23,33,43)→118,124,130→187,190,193→226,227,228→251,251,252→255,255,255`，同时背景从实白褪到透明压在 brand 渐变上；`rgb(187,190,193)` 对 `.294` 白纱覆盖的 `rgb(29,79,196)` 按闸门算法合出 **1.97:1**。CI 那两次点名经按通道反解与插值吻合：stitch `rgb(157,161,165)` 对 `#fff↔#17212b` 解出 `t=0.422/0.423/0.425`，ui2026 `rgb(209,213,217)` 对 `#fff↔#152b3d` 解出 `t=0.197/0.198/0.196`，而枚举 `document.styleSheets` 匹配该元素的三条 `color` 声明**全部写白字**——量到的从来不是规则里的颜色。§5.54 那句"我改什么远端读数就跟着变"同时有了答案：那三次改的都是这条补间的端点。**修复只撤中间帧**：`transition` 限定 `transform, border-color, box-shadow`，时长缓动未动，端点值仍是 §5.54 之后那一套；没改阈值、没放宽断言、没跳过该面、没关 enforce、没猜新色值。motion 尺抓不到这类（`color`／`background` 不是布局属性，它只打印 `transitionAllCount` 并拒绝定罪）。**第二件：本应走到该态的循环是空转的**——旧 `openStaleValidationState` 要求每个下拉 ≥3 个 `<option>`，而组合解析成功后 `tp-agent` 只剩空选项、`tp-entry`／`tp-model`／`tp-task-mode` 各只剩一个可用值，五个轴一条都不满足，所以"本地不可复现"是真的但**不是状态不可达，是闸门没去换**。判据改成页面自己写的「唯一对应档案 <key>」：实测 `flux2--api--image-generation → elevenlabs--web-app--music` 且 `mode` 仍 `target`，脏文案「按新目标重新校验」升级为必须出现的断言，走不到即进 `controlBad` 让闸门 exit 1。**修复后实测**：default `checked=8129`、stitch/light 与 ui2026/light 各 `16258`，三者 `belowAA=0 controlMisses=0 unparsable=0`，三处 `STALEROW` 一致 `color=rgb(255,255,255)`；反证实测——还原成不带属性表的简写后静态守卫点名 `all` 变红，同一态采样器重新量到 **7 个**不同墨色、修复后只剩 **1 个**（两枚逐帧日志存 `kb-20261025/kb-06-action-button-ink-ramp-{before,after}-fix-20261025.log`），`test_workbench_contrast_gate` 6 条 `261.082s OK`。**包里仍未满足的五句只登记**：① 单一强调色 `brandBluePaints` 双宽度 **44 处**（第二十轮那句"21 处"是单宽度读数，两数不可互换）；② 标题仍 10 个 `(级别,字号,字重)` 组合、`h1` 同时 26/17px、`h3` 可小于 `h4`；③ **`errorNodes=0` 是因为闸门还没制造过一次真实失败态**，这句既不能记满足也不能记已测；④ 带标签控件 494→**532**、在上方 416→**434**、旁置 78→**98**，增量已核到行（新 `combination-after-change` 在 1440/1920 各 `labelled=19/labelAbove=9/旁置=10`，合计 +38/+18/+20；`LABEL-SIDEBY` 打印样例上限 10 条，98 来自 `labelled−labelAbove` 不是数样例）；⑤ hover 态仍不在静息尺对象内。**下一刀已指名**：先让闸门制造一次真失败（保存失败／目标不兼容／模型不可用三选二可造），才有资格谈「错误紧邻字段」；标题阶梯要一次裁定（包参照文档 42/27/19px）。owner 未裁照旧：150 KB 上限、顶栏吸顶、勾选框标签是否纳入「标签在上方」、hover 墨色跟不跟着翻。

**台账读数（2026-10-25 第二十轮收口时现数，取代上面第十九轮那一段的"当下"身份）**：直方图仍 **`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`**，`evidence` 仍 **290**（本轮只架尺子，未动样式）。包的「标签放输入上方」与「标题层级」第一次在已渲染文档上有数：带标签控件 **494**、标签在上方 **416**，其余全部是复选框／单选行与一个紧凑选择器（可逐条点名），所以那句只登记不断言——包的话针对"输入"，勾选框标签在框旁是常规写法。**尺子先错过一次**：界面用 `<label>` 包裹控件，量 wrapper 会把 240 个正确标注的字段判成并排（7/247），改成量标签自身文本节点的 Range 联合框才是 208/247，"闸门外报一条大债"与"闸门对象选错"长得一模一样，这条已写进注释。**「错误紧邻字段」本轮没测到**：`errorNodes=0`，静息态没有已渲染的错误实例——要量它得先让闸门制造一次真实失败态，那是下一刀的前置，不是绿灯。**标题层级是量出来的未满足**：读到 10 个 `(级别,字号,字重)` 组合，`h1` 同时 26px 与 17px，`h3` 有 13/15/16 而 `h4` 是 14/16——第三级比第四级更小，不是单调阶梯；包里没写 px，收敛成一套阶梯需要一次设计裁定，本轮不替包猜。本轮新增的是**覆盖断言**（`labelled>=200`、`headingLadder>=5`），防"选择器坏掉→0 违规→被读成通过"。单一强调色仍是登记债（21 处），owner 未裁的三件照旧记账：150 KB 上限、顶栏吸顶、以及这一轮的标题阶梯与勾选框标签。

**台账读数（2026-10-25 第十九轮收口时现数，取代上面第十八轮那一段的"当下"身份）**：直方图仍 **`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`**，`evidence` 仍 **290**（本轮是撤回，不新增债账）。第十八轮那句"单一强调色已归零"只在 Windows 的 Chromium 上成立：同一提交在 CI 的 Linux runner 上报 2 条真红，`1920:target-profiles+combination button#tp-validate.primary-btn 2.86:1 need>=4.5:1 fg=rgb(222,224,227)`。按该读数反推，那一刻压住字的底比 `#356B92` 更亮（白字也只有约 3.79:1），所以我**没有**再猜一个本地验证不了的色值去追远程那一次读数：三处 brand 渐变恢复原状，`brandBluePaints` 从 enforce 移出、改为**持续打印的登记债**，测试断言改成"这条仍在测量且非零"。**包里「单一低饱和强调色 #356B92」当前是未满足**，实测 21 处深蓝仍在，需一次配色裁定（同 hue 深阶当填充 vs 按钮文字改深色并放弃强调色当填充）——与既有的"品牌蓝压不住白字"是同一约束在第三套配色上的重现，不是新 bug。`:not(:disabled)` 那条修复保留（它抓回的是两平台一致的既有缺陷）。**流程收获两条，进收尾清单**：① 账本加行后必须重生成 `deepseek_authority_chain`；② 76 项聚合门禁不含单元套件——`--uif-font-micro` 抬到 12px 与 20261009 包登记的 11 冲突出在单元套件里，已用这条尺自带的 `DOCUMENTED_DEVIATIONS` 正式登记理由与撤回条件。下一刀仍按已指名的顺序：「字段密度／标题层级」要先定分母；`.app-nav button:hover` 的静息态之外仍未测；owner 未裁的两件（150 KB 上限、顶栏吸顶）继续记账不代做。

**台账读数（2026-10-25 第十八轮收口时现数，取代上面第十七轮那一段的"当下"身份）**：直方图仍 **`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`**，`evidence` 289→**290**（`DL-KB-06` 第 **16** 条 `visual_review`，状态仍 DONE）。这一轮把包里那句「**单一低饱和强调色 #356B92**」变成可数的反面命题：屏幕上还有没有第二支蓝。尺子读的是已渲染的色（painted 元素的 background-color／background-image／border-top-color 里出现 `rgb(29,79,196)` 或 `rgb(42,99,216)` 即计入），所以 token 从哪条规则流过来都躲不掉。珍珠白下第一次量到 **21 处**仍是 brand 那对深蓝（能力详情的「使用此能力」、`#research-submit`、`#preflight-run`、`#jury-submit`），压平到包里那一支之后 **0 处**，同一次跑 `belowAA=0`——白字压 `#356B92` 是尺子的读数，不是我算出来的。
  **这一刀把自己造出来的缺陷让尺子抓回来了**：压平第一版没写 `:not(:disabled)`，我的特异性压过 `button:disabled`，于是 13px 次级墨落在强调色底上报 **1.06:1**、产品级红 **29** 条——那正是 2026-10-09 用「平涂次级底＋虚线边＋可读次级墨」量掉的同一个问题。根因写进注释：**高特异性规则顺手覆盖掉一个为无障碍而写的状态**。同时修了尺子自己的账：`belowAA` 以前扣的是「每枚植入控制是否被报出」的布尔数，长页面同名折叠控制的多枚道具行会被算成产品债，现在按实际控制行数扣，`controlMisses` 仍要求每枚都被报出。
  **CI 这一轮教的是套件的边界**：`8fef3f18` 的 PR run 红三件，本地 76 项聚合一条都没抓到——因为聚合不含单元套件，也不含权威链。三件全部本地复现后处理：账本加行后必须重生成 `deepseek_authority_chain`；`--uif-font-micro` 抬到 12px 与 20261009 包登记的 micro=11 冲突，用这条尺自带的 `DOCUMENTED_DEVIATIONS` 登记「拒绝哪一值＋测量理由＋撤回条件」，不删检查也不偷偷对齐；第三条是第一条的连带。**下一轮起收尾必须跑单元套件，不只跑闸门包。**
  包里剩下的：「字段密度」与「标题层级」要先定分母才能写成数；`.app-nav button:hover` 这类 hover 态仍读那对 brand token，但对比度尺目前只量静息态 painted 面，所以那处不改也不宣称已合规——改它要先决定 hover 的墨色跟不跟着翻，这是一条需要 owner 拍的设计裁定。owner 未裁的两件照旧记账：`DL-KB-13` 的 150 KB 上限，与长屏顶栏是否吸顶。

**台账读数（2026-10-25 第十七轮收口时现数，取代上面第十六轮那一段的"当下"身份）**：直方图仍 **`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`**，`evidence` 288→**289**（`DL-KB-06` 第 **15** 条 `visual_review`，状态仍 DONE）。这一轮把包里最后一句还没对象的"**避免大面积渐变**"变成面积读数：一个 painted 元素的 `background-image` 含渐变、且它与视口的**可见交集**超过 25%，就计入。用可见面积而不是布局面积——长列表卡的布局高度能量到视口的 90 倍，照布局算会把一条 24px 高、95% 已滚出屏幕的高光判成违规，那是尺子在打自己造出来的靶子。
  第一次量（stitch／light，width 1440）：渐变 painted run **656** 条，可见面积过阈值 **42** 处，三类来源：`.panel` 的底（单卡可见占比 28–75%）、`.panel::before` 的整卡高光、`.grid-bg` 的 `inset:0` 装饰网格（整屏 100%）。改法的出处是包自己的参照 HTML：`section{background:#fff;border:1px solid var(--line)}`——平涂白卡压珍珠白画布，卡内无渐变无高光。所以三处都写在 `[data-palette="stitch"][data-scheme="light"]` 里，默认炭黑一字节不动；这一改同时把上一段那条「长文字与列表实底」做得更彻底（面板底与卡内高光本就是正文底下的两层可变底）。
  改完读数：同一条单宽度扫描上渐变 run 656→**489**、过阈值 42→**0**（原文留在 `kb-06-gradient-single-width-remeasure-20261025.log`，所以这是同分母的比较）；回执所绑的 1440+1920 双宽度那次是 run **978**、过阈值 **0**，两个数各记各的不互换。AA 仍 `belowAA=0`（重跑的读数，不是推测），几何 stitch 主题 `clipped/stray/tiny/spec` 全 0，两条静态 CSS 尺与 design-debt 扫描一字未变（本轮没有新增字面 px）。**这条同样会咬**：默认炭黑在同一条 enforce 下现在报**两条**红——`长文字与列表实底` 与 `避免大面积渐变`，测试断言两者同时出现，所以珍珠白的 0 不是靠连默认配色一起改掉换来的。
  **剩下两句为什么还没做**：「单一低饱和强调色／避免霓虹」要动主按钮的两停 brand 渐变，这条一改就必须连 AA 重测（珍珠白下应当是平涂 `#356B92`），已排在下一刀；「字段密度／标题层级」要先定分母（按哪一列算密度、什么算一级标题），没定分母就写不成数，硬写就是把猜测写成通过。owner 未裁的两件继续记账不代做：`DL-KB-13` 的 150 KB 上限，与长屏上顶栏是否吸顶。

**台账读数（2026-10-25 第十六轮收口时现数，取代上面第十五轮那一段的"当下"身份）**：直方图仍 **`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`**，`evidence` 287→**288**（`DL-KB-06` 13→**14** 条 `visual_review`，状态仍 DONE）。这一轮把 owner 那句"一比一复刻 STITCH 界面设计"从**颜色**推到**数字规则**：包 `09_DESIGN.md` 与 `08_STITCH完整提示词.txt` 写的元数据至少 12px、圆角输入/按钮 6–10px、玻璃只给顶栏/导航/临时面板、长文字与列表实底，现在由对比度闸门在**同一次渲染**上量（`CT_SPEC` 段），跟 AA 用同一批面。第一次量的债（修复前那次是 width 1440 **单宽度**扫描；下面改完的读数是 1440+1920 **双宽度**，两处分母不能互换）：小于 12px **119** 处、列表行与文字按钮压在半透明白上 **23** 处、表单控件圆角超过 10px **474** 个；玻璃这条一测就在名单内——全 UI 只有 `aside#app-sidebar.sidebar` + `header.topbar` 两处 `backdrop-filter`。
  改法按裁定分两半：12px 地板**全局**抬（1 个 token 与 7 条规则，颜色一字节没动，`--accent-hover`／`--border-strong` 这些已实测的地板值也没动），实底与半径**只加在** `[data-palette="stitch"][data-scheme="light"]` 的作用域里。改完的读数：`below12=0 translucentTextHosts=0 formRadiusOver10=0 glassOffAllowlist=0 unparsableAlpha=0`；AA 仍 `belowAA=0`，几何四个主题 `clipped/stray/tiny/spec` 全 0。
  **断言会咬，而且是被证明的**：同一条 enforce 在默认炭黑配色下必须红，`test_the_pack_number_assertion_refuses_a_theme_it_was_not_applied_to` 断言红里出现`SPEC-VIOLATION 长文字与列表实底`，同时断言该配色 `below12=0`——后半句证明 12px 是全局抬的，不是只在珍珠白里改。两条静态尺也被这次改动当场抓到，并按它们自己写好的补救路径同步：design-debt 扫描器把字面 px 从 516 读成 **517**（`DESIGN.md` §4 改的是扫描器读数，不是手点），single-definition 把 `.primary-btn`／`.soft-btn`／`select` 三条收进 SANCTIONED 并带理由。
  **只登记不断言的三件，写清楚免得下轮当成已通过**：控件高度实测 14 处低于 36px、主动作在 41–47px，而包写的是「约 36–40px」；名单外还有 1818 个 painted 控件（双宽度合计）保持各自半径，因为同一句把面板写成 12–16px、包自己的 HTML 用 20px 的 `.status`；正文带宽读数 3196/15602。**下一刀已指名**：包里还要「单一低饱和强调色」与「避免大面积渐变」，而主按钮现在仍是两停 brand 渐变，珍珠白下不是平涂的 `#356B92`——这条必须连 AA 一起重测才好说，本轮不拿算出来的比值当通过。owner 未裁的两件继续记账不代做：`DL-KB-13` 的 150 KB 上限，与长屏上顶栏是否吸顶。

**台账读数（2026-10-25 第十五轮收口时现数，取代上面第十四轮那一段的"当下"身份）**：直方图仍
**`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`**，`evidence` 286→**287**
（`DL-KB-06` 12→13 条 `visual_review`，仍 DONE）。这一轮开始做 owner 那句
**"一比一复刻 STITCH 界面设计"**，落成第一件实物：`08_STITCH完整提示词.txt` 视觉段逐字给的六个值
（`#356B92`／`#17212B`／`#566472`／`#F4F6F8`／`#FFFFFF`／`#D8DFE5`）做成**第三套可选色板**
`?palette=stitch`，**浅色一侧 only**（包没写暗色值，自造就是把复刻变成猜），默认那套按 token 逐条
证明没被改（`--color-bg #060A14`／`--color-primary #316CFF`／`--color-text #F5F7FC`）。
**这套颜色第一次量就被自己的闸门判红**：珍珠白画布上淡底药丸配白墨，12px 粗体状态词
`1.83:1 / 2.2:1`，`LOWCONTRAST` **405** 行、exit 1；控制跑逐字留在
`kb-06-stitch-pill-ink-control.log`。修的是**角色不是阈值**（`--tag-ink` 取包的正文色、
info 药丸保持中性淡底），修完 stitch/light 下 **58 面／15,772 run `belowAA=0`**（与默认色板同一批
测量对象，只差配色）、几何 **132 面**全零。顺带挖出一个可达性缺陷：`readThemeChoice()` 硬比两个色板名，
第三套在菜单和 CSS 里都在、**就是进不去**——现在问 `PALETTES` 这张表，
`test_workbench_stitch_palette.py`（7 条）钉住六个值、"默认不被覆盖"、"声明的 scheme 必须有 CSS 规则"
与这个写法不许回潮。体积 bundle 609,452→**609,950**、gzip 159,775→**160,052**（+277），
`DL-KB-13` 的 150 KB 上限仍等 owner 裁，本轮不删内容凑数。**这是量，不是批**：
设计批准仍等 owner 真机测试，`DESIGN.md` 不进已批准状态。
**下一刀接着做复刻对照**：包里的"屏幕一…屏幕六"逐个与渲染屏对表，量标题层级、字段密度、
按钮唯一主动作、玻璃只给顶栏/导航/临时面板这几条能不能落在可断言的数字上；
owner 未裁的两件（顶栏吸顶、体积上限）继续记账不代做。

**台账读数（2026-10-25 第十四轮收口时现数，取代上面第十三轮那一段的"当下"身份）**：直方图仍
**`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`**，`evidence` 285→**286**
（`DL-KB-16` 3→4 条，状态仍 `PARTIAL`——它差的仍是具名真人，不是界面）。
这一刀补上闭环最后一环的那一态：**反馈块要先写一条才有内容**，两把尺以前走到方案详情就停。
闸门取服务给的结果词第一个、填两条必填、**记录人写「审计脚手架（合成，不是真人签署）」**
（这一格会进历史，不能读起来像真人签署），等 `#as-fb-history` 出行且状态句不再说"正在读回"，
`state` 从那行文字读出来而不是硬写。读数：对比度 56→**58** 面／15,772 run `belowAA=0`，
几何 128→**132** 面，四宽度反馈态全 `state=read`、几何计数全 0。
**一次崩溃按事实记了账**：这批改动落地前有一次整模块跑在 `w=1536` 死在
`locator.click: Timeout 30000ms`（等 `#as-list .as-plan-open`，当时那一屏没有可点的行）——
闸门没把这件事说出来而是把进程弄崩了。现在先数行、数不到就把 `#as-list-meta` 原话引用进报告；
**之后两次完整跑都干净，所以这不叫修好**：原因没确定，改的是"下一次它会自报"。
下一轮如果又看到 `assistant+plan-detail 的方案清单里没有可点开的行`，那条引号里的原话就是起点。
六类"点开才有"的面至此都有具名行；剩下的打磨主线是 owner 的**一比一复刻 STITCH**：
把渲染屏与 `docs/taskpacks/20261023-ui-kb/source/`（含 `08_STITCH完整提示词.txt`）逐屏对照量偏差并修，
以及 owner 未裁的两件——**顶栏在长屏滚走要不要吸顶**（§5.44／5.47 两次量到 `notInView=3`）、
`DL-KB-13` 的 150 KB 体积上限。

**台账读数（2026-10-25 第十三轮收口时现数，取代上面第十二轮那一段的"当下"身份）**：直方图仍
**`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`**，`evidence` 284→**285**（`DL-KB-12` 2→3 条，仍 DONE）。
这一刀量的是一块**以前根本不存在于任何尺子里**的态：`DL-KB-12` 的验收说"对照页比的是两份真实修订"，
而那块面板要 ① 这份方案有第二个修订 ② 有人按下"对照" 才会画出来——两把尺以前两件事都不做，
所以十二行并排的内容从未被量过（不是"量了没问题"，是"没量"）。现在种子走界面用的同一条
`POST …/revisions`（带 `expected_revision`）写 r2，打开 `#as-compare`、选 r1／r2、点对照，
等 `#as-compare-body` ≥12 行且状态句不再是"正在读回"；**`state` 取自那行文字而不是硬写 `read`**，
硬写会让将来一次被拒的读回被判成成功。读数：对比度 54→**56** 面／15,270 run `belowAA=0`，
几何 124→**128** 面，四宽度对照态全 `state=read`、`clipped/stray/tiny/occluded/docOverflowX=0`
（**1280 这一档也干净**，两栏长中文最容易在这儿挤断）；`notInView=3` 与 §5.44 同因，仍只记账不改布局。
CI：`1947eb3e`（第十二轮那批）push run success、PR 矩阵当时仍在跑；本轮这批字节推上去后逐作业读数照旧回看。
**"点开／选中才量"至此覆盖六处具名面板态**（条目详情、方案详情、两案对照、目标组合、全局搜索、证据投影），
同类的最后一个缺口是**反馈块写入后的读回态**（它也在方案详情里，需要一个 POST 才有内容）。

**台账读数（2026-10-25 第十二轮收口时现数，取代上面第十一轮那一段的"当下"身份）**：直方图仍
**`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`**，`evidence` 283→**284**（`DL-KB-10` 3→4 条，仍 DONE）。
这一刀把 `#/target-profiles` 从"只量没选目标那一屏"改成**量选中之后那一态**：
两栏真相与四档 `support_state` 药丸是选了之后才画的，而 `08_STITCH完整提示词.txt` 第 13 行对这一面
说的话正是"先选软件／Agent，再看到该入口可用的模型／模式……显示官方支持与本项目未测试的区别"
（逐字核过）。判据用界面自己写的状态位 `#tp-combination.dataset.mode === 'target'`，
**不是**"有没有字"——一次诚实的空回答同样有字。读数：对比度 52→**54** 面／14,764 run `belowAA=0`，
几何 120→**124** 面，四宽度组合态全 `state=read`，`clipped/stray/tiny/occluded/docOverflowX` 均 0，
`notInView=0`（顺带把 §5.44 那条顶栏观察的边界说清：那是长设计辅助屏特有，不是全站现象）。
**这一刀没有量出新缺陷**，所以只留覆盖面与一条回执，不写"修好了什么"。
CI 侧本轮已确认两个 SHA 的 PR 矩阵全作业 success：`e6521525`（5.43 那批字节）与 `64b72310`（5.44 那批）。
**"点开／选中才量"这套做法现在四处成型**（条目详情、方案详情、目标组合、原有的全局搜索与证据投影），
共同四步：种子或选择 → 等界面自己写的状态位 → 量成具名行 → 过同一个计数入口，
并由测试要求"每个宽度都在"＋"报了＝算了"（`OV_SUMMARY interactions=` 等于带 `+` 的行数）。
**还剩两格没被尺子开进去**：我的方案的两案对照态、反馈块写入后的读回态；
另外 owner 侧未决的顶栏是否吸顶已记在 §5.44，等裁定，不擅自补规格里没有的要求。

**台账读数（2026-10-25 第十一轮收口时现数，取代上面第十轮那一段的"当下"身份）**：`currentExecution`
仍 50 行、34 项 `FROZEN_DEFERRED` 未解冻；直方图不变 **`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`**；
`evidence` 282→**283**（`DL-KB-08` 13→14 条 browser 回执，状态仍 DONE）。这一刀把第十轮自己列的
清单往前推了两格：**几何尺现在也会点开方案详情**（`assistant+plan-detail`，四个宽度各一行，
全部 `state=read`），116→**120** 个几何面，`docOverflowX=0 clipped=0 stray=0 tiny=0 occluded=0`。
过程中先掉进自己的坑并补了牙齿，两条都值得下一轮记住：
① **"报告里有这行"与"闸门算了这行"不是一件事**——第一版把面板行塞进 `report.routes` 就没管计数器，
   clip／stray／occlusion 会打印出来然后被忽略；现在两个面板都过同一个 `absorbPanel` 入口，
   闸门的测试另加一条硬断言：`OV_SUMMARY interactions=` 的数量必须等于报告里带 `+` 的行数。
② **"不在屏上"不等于"被盖住"**——新行报的 `occluded=3` 其实是顶栏三个入口的中心点在视口上方
   约 1.8k 像素处（`top≈-1814`，视口高 900），而探测块自己的注释早就写了这两句不是一回事。
   现在分出 `notInView` 并带上中心点／视口／上下边，`occluded` 只留给真被别的元素盖住的情况，
   仍然进 `specProblems` 判红。**要不要把顶栏吸顶不是工程决定**：采纳包里
   `02_完整产品方案.md` 只在"玻璃用在哪儿"那句提到顶栏，没有任何一条要求常驻可见，
   所以这条按实测现象记账，留给 owner，不擅自 `position:sticky` 去补规格里没有的要求。
体积与上一轮同（这批字节没动 `shell.ts`／`style.css`）：609,452 B／gzip 159,775 B。
**还没被尺子碰过的"点开才有"的面**：目标组合面板的展开态、我的方案里两案对照态、反馈块写入后的读回态；
做法已经现成（种子 → 点开 → 等真实状态 → 量成具名行 → 进同一个计数入口 → 补"报了必须等于算了"）。
`DL-KB-13`／`DL-KB-16`／`DL-KB-15` 三格账不变。

**台账读数（2026-10-25 第十轮收口时现数，取代上面第九轮那一段的"当下"身份）**：`currentExecution`
仍 50 行、34 项 `FROZEN_DEFERRED` 一行没解冻；直方图不变 **`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`**；
`evidence` 281→**282**（`DL-KB-03` 10→11 条，状态仍 DONE）。这一轮做的是 §5.40／§5.41 连着两轮
自己写下的覆盖盲区：**两把静态尺从不点开知识条目详情**。做法照方案详情的先例——服务写一条合成条目
（`created_by` 写明"合成，不是真人"，随临时状态目录丢弃），点开，等 `kb-copy-body`／判断表单／正文
都画上才量，量成具名状态 `knowledge+entry-detail`，两个宽度和四个宽度各一份；
两份闸门测试现在**要求这个状态在每个宽度都出现在报告里**，"少量一块面板"从此是一次红而不是一次安静的绿。
**它第一次跑就量出一个真缺陷**：点开详情时指针还压在刚点开那行的标题上，量到的是 `.kb-open:hover`
的墨色 `--accent`（品牌蓝 `#316CFF`）——在这块表面上 **4.08:1**，16px 粗体按 AA 要 4.5:1，
深浅两套主题各红一次（控制跑逐字读数在回执 `kb-03-contrast-prefix-control.log`）。
改的是字色选择不是品牌：三条 hover 墨色改走 `--secondary`（本项目为"小号有色文字"准备的按主题那支），
`--accent` 一个字没动——**闸门量出缺陷不等于拿到改品牌的许可**，那仍是要 owner 裁的账。
量的面确实变大：对比度 50→**52** 面、`checked` 14,002→**14,278** run，`belowAA=0`；
几何 112→**116** 面，`docOverflowX=0 clipped=0 stray=0 tiny=0`，四个宽度的详情都报 `state=read`。
本机 `VERIFY_DESIGN_LAB=OK total=76 failed=0`；`DL-KB-13`／`DL-KB-16`／`DL-KB-15` 三格账没变，
分别是 owner 的体积裁定＋3 位真人、具名真人签字、本机推理前置。
**下一刀仍是打磨与审计**：把同一套"点开才量"的做法推向剩下的面板
（我的方案详情已有，目标组合与反馈面板的展开态还没被静态尺量过），并按 owner 本轮指令
把渲染屏与 `docs/taskpacks/20261023-ui-kb/source/` 归档的 Stitch 参考屏逐屏对照量偏差。

**台账读数（2026-10-24 第九轮收口时现数，取代上面第八轮那一段的"当下"身份）**：`currentExecution`
仍 50 行、34 项 `FROZEN_DEFERRED` 一行没解冻；直方图不变——**`DONE 13`／`PARTIAL 2`／
`NOT_STARTED 1`**，本轮没有可升的行（剩下两格要 owner 与真人，见审计件 §5.40）。本轮把**闭环第一环**
接上：服务收五种 `REFERENCE_KINDS`，方案参考选择器只列两组，所以项目自己的 brief／方向／提示词结果
是"API 引得到、界面选不到"。三条读路由本来就有合同行，所以这一刀没加路由：路由面仍 **88 条**、
账本 90 行、载荷比对 57 条。选择器现在是五组 `<optgroup>`，`Promise.all` 读三份项目内清单，
`next_cursor` 非 null 时明说还有更早的没读到。牙齿有两处：一条 Python 测试把界面
`REFERENCE_KIND_LABELS` 的键与 `REFERENCE_KINDS` 逐一比对并要求每种都有 `referenceGroup('KIND'…)`
——**上一轮 KNOWLEDGE 就是栽在这种"每侧自洽、中间断了"的跨侧缺口上**；另一处是门禁自己报的旧账
`STALE_BACKEND_ONLY GET …/directions`，删的是豁免不是断言。浏览器走查 11 件→**12 件**
（`pickerOffersBothSources` 改名 `pickerOffersAllFiveKinds`，新增 `planCitesEveryKind`：一次保存里
挂上四种引用，要求服务回 `revision >= 1` 与摘要，页面只发类型和编号）。顺手修掉一个一直存在的
悬挂 promise：首屏 `loadKnowledgeChoices()` 没有 `catch`，库被拒时留下未处理的 rejection，
而屏上还挂着"库里还没有条目"——那是把失败说成了关于库的事实。三把尺在收口字节上重跑：
对比度 50 面 `checked=14002 belowAA=0 unparsable=0 controlMisses=0`、几何 112 面
`docOverflowX=0 clipped=0 stray=0 tiny=0`、UI 审计 `ok=true violations=0`
（宽度 `1280,1920,2048`，它的 `environment.commit` 字段自己记了 `e172e33e964b`）。
**"读数与上一轮一样"两次都不是尺坏了**，两次的原因不同，写在 §5.41：详情面板不在它们的行走路径上，
而 `<option>` 的文字不是被画的文本 run。`evidence` 279→**281**（`DL-KB-08` 11→13 条，状态仍 DONE）。
本机 `VERIFY_DESIGN_LAB=OK total=76 failed=0`；体积 609,452 字节 / gzip **159,775**
（第八轮 158,722），`DL-KB-13` 的 150 KB 裁定仍在 owner 手上。
**本轮 CI 抓到一次我自己的红，读数与口径都变了。** push run `40140333553` success，同 SHA
`5041b8f5` 的 pull_request run `40140337003` failure，逐作业只有一条红
（`Workbench browser E2E (exact-SHA controlled-runtime, no-skip)`）。原因不是产品：那张十二件事实的
字面表是我按驱动的**写入顺序**抄的，而断言左边是 `sorted(...)`——**两边永远不可能相等**，
这条断言从提交那刻起只有一种结果。它本地照绿，因为整段证据断言包在
`if os.environ.get('E2E_REQUIRED') == '1':` 里，那个变量只有 CI 设。
`b90aaf66` 两边都补：条件改成 `E2E_REQUIRED == '1' or summary.is_file()`（required 而无 summary
仍然硬失败），两张清单都包进 `sorted(...)`，并按老规矩双向验——种一个 `'bogusStateName'`
**本地立刻红**。**从今天起"本地 `test_workbench_design_layer_e2e` OK"这句话的含义变了**：
它现在真的包含那十二件；在它之前的每一次本地 OK 验的是驱动侧 `E2E_OK` 与 summary 的 `allAsserted`，
**不是** Python 侧的清单比对。细节与逐字读数见审计件 §5.42。

**下一刀两件事，都是机器能证明的**：① 把两把静态尺**开进**一条知识条目的详情与一份方案详情
（现在它们只走到列表，`§5.40`/`§5.41` 连续两轮把这件事写成覆盖盲区——补它比再加一条走查更值钱）；
② owner 这轮的 standing 指令是"一比一复刻 STITCH 界面设计"，来源在
`docs/taskpacks/20261023-ui-kb/source/`（含 `08_STITCH完整提示词.txt`），要做的是把渲染出的屏与
归档的 Stitch 参考屏逐屏对照、量几何差、修偏差，**不是**照效果图声称接通了什么。

**台账读数（2026-10-24 第七轮收口时现数，取代上面第六轮那一段的"当下"身份）**：`currentExecution`
仍 50 行、34 项 `FROZEN_DEFERRED` 一行没解冻；直方图 **`DONE 12`／`PARTIAL 3`／`NOT_STARTED 1`**——
`DL-KB-05` 升上 DONE，因为 D5 那句话的主语（旧方案）这一轮才真的在产品里走得通：
`REFERENCE_KINDS` 加了 `KNOWLEDGE`，方案能钉住一条知识条目的修订号与摘要，
四个 schema 的 kind 枚举与 Python 元组由一条测试钉在一起。`currentExecution.evidence` 现数
**277** 条、全部 PASS（`DL-KB-05` 一条任务共 8 条回执），本轮新增 2 条绑 `2c47e359`。
路由面 **88 条**不变（这次没加路由）、账本 90 行、载荷比对 57 条绑定；写侧扫描
`rows=40 walked=39 written=39 read_backs=48 refused=0 excluded=1`。浏览器走查从 8 件加到 **10 件全真**
（新增 `pickerOffersBothSources`、`planCitesTheKnowledgeEntry`，各阶段发请求数
`[0,0,1,1]`）。同一轮拆掉一个一直存在的界面缺陷：引用原来在表单里退化成"光 id"、提交时一律贴回
`kind: ASSET`，所以引用了 brief 或知识条目的方案**在界面上点修订就必然被服务拒**
（`ASSISTANCE_PLAN_REFERENCE_ID_MALFORMED`）；现在选择器带类型、给不出的类型原样保留。
本机 `VERIFY_DESIGN_LAB=OK total=76 failed=0`；体积 `build/main.js` 604,992 字节 / gzip
**158,477** 字节（同一把尺，上一轮记录 158,029），`DL-KB-13` 的 150 KB 裁定仍在 owner 手上。

**台账读数（2026-10-24 第六轮收口时现数，取代上面第五轮那一段的"当下"身份）**：`currentExecution` 仍
50 行、34 项 `FROZEN_DEFERRED` 一行没解冻；直方图不变——**`DONE 11`／`PARTIAL 4`／`NOT_STARTED 1`**。
本轮没有把任何一行升上去：`DL-KB-05` 的 D5 现在**造出来了**（判断存储、路由、条目详情里的界面，
`52961f49`），但它仍停在 PARTIAL，理由写在下面第一刀里。`currentExecution.evidence` 现数 **275** 条、
全部 PASS，本轮给 `DL-KB-05` 加了 4 条（判断存储的 unit／implementation／browser，加第一次真点开
一条知识条目的浏览器走查），逐条绑 `52961f49`／`38bb48d8` 的现测字节。
路由面 **88 条**（48 GET + 40 POST）、账本 90 行、载荷比对 **57 条绑定**；写侧扫描
`rows=40 walked=39 written=39 read_backs=48 refused=0 excluded=1`。浏览器三把尺：对比度 50 个面
`checked=14002 belowAA=0 unparsable=0`、几何 112 个面（1440/1280/1536/1920）
`docOverflowX=0 clipped=0 stray=0 detailsExpanded=1200`、路由级 UI 审计 `ok=true hardViolations=0
totalMetrics=54`；表单缺陷修完后前两把尺在同一批字节上重跑，读数不变，回执绑 bundle
`sha256 e27eeacf…`（603,048 字节）。本机 `VERIFY_DESIGN_LAB=OK total=76 failed=0`。体积：
`build/main.js` 603,048 字节 / gzip **158,029** 字节，比上一轮记录的 155,787 高 2,242 字节——
`DL-KB-13` 的 150 KB 裁定仍在 owner 手上，本轮不代做、也不删内容凑数。

**这一轮最该记住的一件事**：`browser_design_layer_e2e.mjs` 第一次在真 Chromium 里**点开一条知识条目**，
当场量到两个一直存在的表单缺陷。「适用场景／边界与反例」留空时 `collect()` 用 `|| undefined` 把键丢掉，
而创建与修订两条路由要的是精确键集合，于是答 `400 INVALID_PROJECT_FIELDS`——用户只看懂一句读不懂的代码，
且只要不填这两格就永远存不进去；许可状态那个 `select` 没有"未选"这一档，词表第一项 `reviewed` 默认中选，
一张没被碰过的新表单打开就在替用户声明"这份许可审过了"，存储按规则拒了
（`KNOWLEDGE_LICENSE_UNKNOWN_CONTRADICTION`）。两条都修了（键永远在、空表单默认 `unknown`），并各留一条
不依赖浏览器的断言。`apps/workbench/tests/appshell.mjs` 在同一批字节上一直是绿的——这句话不是给桩件记分，
是给下一轮定口径：**桩件的绿不能声称浏览器验过，浏览器的红也不能靠桩件抵账**，细节见审计件 §5.38。

**台账读数（2026-10-24 第五轮收口时现数，读的是 `36addfd5` 那批字节，不是当下）**：`currentExecution` 仍是
50 行、34 项 `FROZEN_DEFERRED` 一行没解冻；16 项派工里 **`DONE 11`**（新增 `DL-KB-09/10/11/12/14`）、
**`PARTIAL 4`**（`DL-KB-02/05` 旧账，加 `DL-KB-13` 体积超标与真人无指导任务、`DL-KB-16` 的
`human_review` 只认具名真人）、**`NOT_STARTED 1`**（`DL-KB-15`，前置是 owner 本机可用的推理服务与硬件余量）。
`currentExecution.evidence` 从 249 涨到 **270** 条、全部 PASS，本轮回执 21 条落在
`design-lab/evidence/current-execution/task-artifacts/kb-20261024/`（合计 279,212 字节，单文件最大
117,639 字节，未触发 `large-assets.json` 的 256 KiB 线），逐条绑 `36addfd5` 的现测字节。路由面
**88 条**（48 GET + 40 POST），写侧扫描 `rows=40 walked=39 written=39 read_backs=48 refused=0 excluded=1`，
对比度闸两档主题各 50 个面、`checked=14002 belowAA=0 collapsedOpened=6228 unparsable=0 colourBad=0`，
几何闸扫 `1440,1280,1536,1920`（1536＝1920 在 Windows 125% 下），本机 `VERIFY_DESIGN_LAB=OK total=76
failed=0`。性能基线里有一条**真实超标**：交付方案 §14 定"首屏 JS gzip ≤ 150KB"，实测
`build/main.js` 593,796 字节 / gzip **155,787** 字节——不能靠压缩构建解决（`vite.config.ts` 顶上写明
这个包故意不压缩，原生 UI 契约测试要读函数名与界面文字），也不该删必要内容凑数，所以 `DL-KB-13` 停在
PARTIAL 并把取舍交给 owner（见 §7）。搜索侧达标：1,000 条按真实结构生成的样本、`search p95=28.89ms`
（阈值 300ms）。

**下一刀切哪里（按价值排序，不是按编号）**：
① `DL-KB-13` 的两件人账——owner 对 150KB 上限的裁定（提预算并写明理由，或批准一次按面板拆包的加载
模型改动，后者会动 `vite.config.ts` 那份"单文件不压缩"合同，必须 owner 点头），以及 §14 要求的
3 位目标用户无指导任务。本轮已把决定需要的数补齐：按顶层声明归因后整包覆盖 100%，其中设计辅助
那一面占 **11.61%**、目标组合面板占 **5.56%**，是最大两块——但要说清口径：超出的量按 150,000 字节
读是 5,787 B、按 153,600 B（150 KiB）读是 2,187 B，而这两块加起来是整包的约六分之一，
"拆掉它们就能达标"没有量过，别拿占比当因果；
② 折叠态自己的裁剪行为现在**没人声称**：几何闸与 UI 审计闸这一轮改成"先展开再量"，说的是打开之后
那一屏好不好；闭合面板会不会把内容裁成一个看不见的半成品，是另一把尺子的问题，谁要声称就得新立
一条断言，别把这两件事混成一句"几何已过闸"；
③ 还剩两件机器可证的账：`DL-KB-02` 的 A5 直接断言；以及参考选择器现在只给两类
（`ASSET`／`KNOWLEDGE`），`BRIEF`／`DIRECTION`／`PROMPT_RESULT` 只能在 API 层引用——界面上
引用了这三类的方案能原样保留、但加不进去。把它们并进同一个分组选择器（各用自己的 id 形状
与读回标题）是下一步的界面活，`REFERENCE_ID` 已经把形状都备好了；
③b 上一轮记下的那条边界本轮**关掉了**：`browser_design_layer_e2e.mjs` 里新增
`knowledge detail and judgement walk`，第一次在真 Chromium 里点开一条知识条目。它当场量到两个一直
存在的表单缺陷（`applicability`/`limits` 留空被 `|| undefined` 丢键 → `400 INVALID_PROJECT_FIELDS`；
新表单的许可状态默认中选词表第一项 `reviewed` → `400 KNOWLEDGE_LICENSE_UNKNOWN_CONTRADICTION`），
两条都已修、各有一条不依赖浏览器的断言，细节见审计件 §5.38。**下一轮不要退回"桩件绿了"**：这条
走查之所以有价值，恰恰是因为 DOM 桩件在同一批字节上全绿。仍然没有的是：条目详情面在对比度与几何
两把尺下的读数（那两把尺量的是列表页），要声称就得让门禁真点一次开详情再量。
④ `DL-KB-16` 的 `human_review` 与 `DESIGN.md` 的批准状态，都等 owner 真实测试后由具名真人签。


**四个空白是实测出来的，不是听来的**（同一批字节上）：`capability_library.py` 是只读投影、没有写入面；
`prompt_intelligence.py` 不调用任何模型；`prompt_results.py` 的存储层仍要求 `executed=false`；
`model_selection.py` 只记录选择。路由合同账本 80 行里 BOUND_SCHEMA 66、SCHEMA_LESS 14，
live 载荷比对 47 条绑定（K4 之后 52 条，见 §7 的复测句），前端调用对账 calls=127 / matched=67 / backend_only=11 / dynamic=3 / special=1，
`ROUTE_VIEWS` 23 条（K4 收口时按当下读数更正）。所以第一刀不是"接模型"，是**知识条目可写面 + 中文检索 + 三入口外壳**（批次 K0…K2）。
2026-10-24 复核：这四个空白在第一刀里没有被触碰，读数不变；那一刀改的是知识写入/检索/界面/外壳。

**边界逐字不变**：「再说一遍 不做手机端 只做桌面端」——手机端是排除项，不是待办、缺口或待排期；
「三方素材和字库不在本项目范围内」；「不锁死 做好菜单导航和接口 用户自行选择本地或者是云端模型」——默认值
fail-closed、`UNKNOWN` 不写成合格、不宣称推理已验证、云端选项必须写明哪些数据离开本机，且**本轮不部署模型、
不自行下载权重**；「编号问题留出可填写位置，用户自行填写或者选择用没用」——`UNUSED` 字面量，代理不得自铸标识；
「E盘不动」；release / 安装态分发 / 真实宿主 E3 / 真人 E4 / ComfyUI / MiniMax H3 与那 34 项继续冻结；
签字与验收只接受具名真人；导出仍是读回不是发送；AAOS 只是未来合同。

**这条线之前必须同步的门禁**（漏一个就是下一会话的假现状）：`verify_documented_counts.py` 现在有两个账本分母
（34 冻结 / 16 派工）与 20 条受治句子；`test_current_execution.py` 的计数断言已改为从账本自身取数；
`current_execution.py` 的 `22父任务＋12UI子任务` 硬写行已改成按投影计数；新增路由要同一改动付齐
合同行 + schema 打包三件套 + live 载荷用例 + 前端调用可被对账；新增界面要同一改动进 `ROUTE_VIEWS`、`renderRoute`、
截图 `PAGES` 与各审计 `ROUTES`，并同步 `DESIGN.md` 的「导航 {n} 项」实测句；新增证据包要在
`design-lab/config/large-assets.json` 声明 bundle（单文件 ≥256 KiB 会被拦，而账本 `artifact_sha256`
绑定的工件不能挪进 Git 忽略目录）。

**第一刀（K0/K1 四项）落地后实测**（2026-10-24，全部 E1/E2）：路由 66 → **72**，合同账本 68 → **74** 行
（BOUND_SCHEMA 60 / SCHEMA_LESS 14），live 载荷绑定 35 → **41**，前端调用对账 calls=117 / routes=72 /
matched=61 / backend_only=11 / dynamic=3 / special=1，`ROUTE_VIEWS` 21 → **22**（侧栏 21 个按钮 + 空 hash
工作台），`DESIGN.md` 的「导航 22 项」同步。六条知识路由：`GET /api/knowledge-entries/search`、
`POST /api/knowledge-entries`、`POST /api/knowledge-entries/import`、`POST /api/knowledge-entries/index-rebuild`、
`GET /api/knowledge-entries/(kentry-…)`、`POST /api/knowledge-entries/(kentry-…)/revisions`。
中文检索：`分镜`/`粒子`/`品牌` 在 1,000 条真实 HTTP 语料上走 `SHORT_FALLBACK` 命中，`panasonic` 走
`TRIGRAM`，零结果带解释；p95 单元 26.1 ms、HTTP 30.4 ms（预算 300 ms）。界面四处缺陷（写入口换行、
零结果文案重复、表单无出口、零结果右侧挂旧详情）已修并各有可复跑断言；390px 窄窗底栏 138 → 56px
（`.nav-group` 缺 `flex`），E2E 阈值未放宽。本地并集 3200/3200；CI 先有 run `40009897564` 在 `cf77b2c2`
逐作业全绿，收尾提交后的 run `40013185833`（main）与 `40013198844`（分支）在 `d9a8412b` 同样全绿
（细节见审计 §5.32、§5.33）。下一会话自读 `git rev-parse HEAD`，不要抄这两个 SHA。

**第四刀（K3 两项）已收口，下一刀是 K4。** `DL-KB-07`（中立方案对象 + 一份创意意图）与
`DL-KB-08`（设计辅助初始态 + 方案详情四态）在 `2d9372fb` 实现、`103a6680` 收口：6 条新路由
（输出类型、列表、详情、创建、修订、选用）把 ROUTES 从 72 带到 78（42 GET + 36 POST），合同账本
74 → 80 行（BOUND_SCHEMA 66 / SCHEMA_LESS 14），live 载荷绑定 41 → 47，ROUTE_VIEWS 22 → 23，
`DESIGN.md` 导航 22 → 23；新增五份 plan schema 与一张 state 表。`test_assistance_plan` 18 项、
路由/账本/打包 77 项、工作台 node 30 项（含 `㉔ B10_NAV` 派生断言）与 Python 44 项全绿；浏览器实跑
四态可分、复制与选用互不代劳、空目标被拒并聚焦、手工补创意可行、重载读回一致、无聊天面，
consoleErrors 0；81 张截图绑 `2d9372fb` 的 bundle `ffabee75`，UI audit 0 violations、对比度双 palette、
溢出 1100/900/750/620 四档、a11y 27 屏 0 findings（自动扫描，不是认证），设计债 713 条与助手屏
出现前条数、严重度、文件分布相同，`(file, rule, severity)` 的 713 条多重集完全一致（28 条行号
随 `shell.ts` 增长而位移）——新界面没有新增字面 px 或硬编码颜色。**CI 抓到过一处真缺陷**：首个完整矩阵
（run `40048178001`，`142e7efe`）Python gate 红，`assistance_plan` / `assistance_plan_revision` /
`assistance_plan_choice` 三张新表没进 `project_backup.py` 的 `COUNTER_QUERIES`，备份的静默证明看不见它们；
已在 `dbdee924` 补三行计数并复跑（run `40076707359`：10 作业 success，`Branch light` 与 `CI artifact proof`
按规则跳过；CI 三 shard `3196 PASS / 22 SKIP / 0 FAIL`，本机并集 `3213 PASS / 5 SKIP / 0 FAIL`）。这条不在 76 项闸门里，
住在 `test_backup_watches_written_tables`——**新增 state 表必须在同一改动里补计数行**。该 E2E 自己的 `subjectSha` 写的是 `local`，工件身份
由 `routeInventory.bundleSha256` 与截图 manifest 的 commit 绑定，账本回执里照实记录了这一点。

**DL-KB-05 的 D5 现在可以重新量。** 修订链本身已有真实 HTTP 探针
（`design-lab/scripts/knowledge_revision_probe.py`）：r1 是推荐版本，修订后 r2 成为最新且父摘要不变，
带 `expected_revision=1` 的过期写返回 `409 KNOWLEDGE_ENTRY_REVISION_CONFLICT` 并点名 revision 2，
重启后链一致（`KB_REVISION_OK`）。它停住时写的是"推荐版本回退没有路由、失效来源没有字段，
依赖尚未开工的 `DL-KB-07`"；`DL-KB-07` 现已 DONE，下一轮要先按现行字测量 D5 是否真的被那 6 条
方案路由解锁，再决定 KB-05 能否从 PARTIAL 收口——不要因为依赖项 DONE 就把它读成已证。
K4 是 `DL-KB-09`（目标档案：软件×模型×入口）与 `DL-KB-10`（目标组合选择面板屏）。
**先量现状再动手**：上一轮的教训是"卡片说缺的"经常已经存在一半；`DL-KB-02` 的 A5
（模型服务关闭时仍可写入、检索、编辑与复制）仍然没有直接断言，不要因为五条写路由都在就把它读成已证。

**本轮留下的账**（下一轮同批付或明确记录）：真实中文知识语料仍只有探针合成的那批，不含 owner 的条目；
写入路径的逐屏截图只覆盖新增；1280 宽档侧栏仍要滚动才能看全分组（这是密度事实，不是缺陷；当前项在
100/125/150% 三档实测滚入视口，`fullyInsideNav=true`）；design-review 的 713 条设计债
（`design-lab/evidence/current-execution/task-artifacts/kb-20261023/design-review-20261024/design-debt.json`）
是**未关闭的登记**，`style.css` 683 条里有一部分就是 token 定义，清理属版式轮次，不许写成"已清零"；
a11y 的 0 findings 只是自动扫描（axe 每屏仍拒评若干节点），不是 WCAG 认证；1920 档的播种截图还没采，
第二轮的八张截图是 1440/1280。这些都在同目录 `VISUAL-REVIEW-ROUND2-20261024.md` 的「仍然未证」里，
下一轮不要把它们读成已完成。

本轮同步过的面（都已落盘）：`AUTHORITY.md`、authority index、`AGENTS.md`、
`docs/current/PRODUCT_DEFINITION.md`、`docs/architecture/BOUNDARY_CONTRACT.md`、`docs/current/ROADMAP.md`、
`design-lab/config/product-manifest.json`、`design-lab/config/task-document-states.json`、唯一账本状态、
`.project/manifest.yaml` 的 taskpack 指针、`R2_RELEASE_HASHES`、`AUTHORITY-PIN-CHANGE.json`、`reports/current/**`。

**没有**同步、也不得声称同步的：真实宿主调用、人工验收。（原句还列有"运行时代码、模型路由"——
2026-10-20 定点解冻后，上文「当前授权面」三段的运行时代码与模型选择接口**属于本轮实施范围**，
但"路由到已合格模型"仍然不得声称：合格判定只在真实取证后由 owner 验收。）「AAOS 接收」不再列入本项目同步范围：owner 2026-10-19 定调本项目独立全链路跑通，外部知识系统只通过版本化公共合同连接，其接收状态既不由本项目宣称，也不作为本项目的完成条件。

### 3.1 2026-10-19 归档与删除波（明面已经换了形状）

Owner 两条指令：旧的不许留在明面上；旧的都删除，但先审计、汇总成可追溯记录、并给出替代。已执行完：

- **移动**：228 个跟踪文件 `git mv` 进 `docs/history/archive-2026-10-19/**`（85 份按日期交接、19 个旧任务包、
  `docs/plans|research|superpowers`、UI-CONVERGENCE 证据包 93 件、4 份旧当前面记录、根级 WORK-LAB 交接），
  5 份 reports 交接摘要进 `reports/history/`。逐文件 `原路径→新路径→blob→字节` 在
  `docs/history/archive-2026-10-19/MANIFEST.json`，228/228 复验字节一致。
- **删除**：83 份（68 交接 + 5 按日期提示词 + 10 份 loose reports 交接），共 713,606 字节。
  删前先汇总：`AGGREGATED-RECORD-2026-10-19.md`（每份的标题/自述/结论/只有它记载的事实）+
  `HANDOFF-PROMPT-DIGEST.json`；恢复句柄在 `REMOVALS.json`（blob sha1/sha256/crc32/bytes/restoreAt），
  逐条 `git show <restoreAt>:<path>` 实测过才算登记。
- **明面现状**：`docs/` 不再有 `handoffs/`；`docs/taskpacks/` 只剩 4 个包体 + 2 个来源目录（14 个跟踪文件），
  因为 `authority-index` 与账本仍点名这四件，被钉字节不能改。
- **故意没删**：`handoffs/deepseek-r3-20260906/` 17 件（owner 随包提供的审计输入原件）、`PROMPT-LINEAGE.json`、
  按日期 bundle 目录里的成员。删这些是销毁输入或拆散 bundle，不是清理陈旧材料。
- **指针的替代**：指引面不再点名任何已删文件；需要原件内容时用 `scripts/archive_records.py:read_record(rel)`，
  它按 工作区 → 归档移动 → 删除清单 restoreAt 三层解析，并把来源回写进报告
  （`handoff_read_from: removed-at:<sha>`）。三层都不到即 `RecordUnavailable`，不放行。
- **逐条证据与读数**：`docs/audits/DESIGN-LAB-ARCHIVE-AND-REMOVAL-2026-10-19.md`（§0 结论 `PARTIAL`、命令 + 退出码、§6 六处与 §6.5 一处共七处缺陷、回滚方法）。
- **重钉**：本轮 AUTHORITY.md / authority-index.json / HISTORY-FREEZE-RULES.md 共重钉两次
  （归档改路径一次、删除改指针一次），每次都在 `AUTHORITY-PIN-CHANGE.json` 追加 revision。
- **登记位置**：这五份记录本身（移动清单、移除清单、汇总登记、可读汇总、交付报告）的路径、
  blob SHA-1、字节与 SHA-256 已写入 `docs/RECORD-ARCHIVE-INDEX.md` 的 2026-10-19 一节，
  哈希取自 `git cat-file blob HEAD:<路径>`；找资料先读那个索引，不要回聊天记录里抄。

## 4. 状态是分轴的，不能合成一个"完成"

能力状态至少区分：
`Discovered`、`Reviewed`、`Adapted`、`Installed`、`Loaded/Connected`、`Tested`、
`Qualified`、`Accepted`、`Knowledge Candidate`、`Ingested/Verified in AAOS`。

证据等级仍是 E0–E5：E0 声明 / E1 结构 / E2 受控运行 / E3 真实工作流 /
E4 独立人审 / E5 发布可复现。**文档修订 ≠ 规划完成 ≠ 代码实现 ≠ 真实运行 ≠ 人工验收 ≠ 外部知识系统接收。**最后一轴是对外部系统状态的读数（本项目只写候选、只读回执），不是本项目闭环的前提。

当前实测（重跑命令，别抄结论）：

| 事实 | 复算方式 | 读数 |
|---|---|---|
| 能力证据分布 | `design-lab/config/capability-evidence-current.json` 的 `capabilities` | 50 条：E1=13、E0=37 |
| Provider 证据 | `design-lab/config/provider-capabilities.json` | 全部 E0（未复验运行时） |
| 已批准模型 | `design-lab/config/model-manifest-trust.json#approved` | 空 |
| Adobe/Comfy/Penpot 适配器 | `src/design_lab/adapters/`、`src/design_lab/generators/`、`src/design_lab/interop/penpot.py` | 静态/合同层存在；无当前 SHA 的真实宿主 E3 |
| 历史 ComfyUI/H3 记录 | `docs/current/ROADMAP.md` 的 2026-08-16 `runtime-pass` | 历史记录，未在当前 HEAD 复验；H3/ComfyUI 已冻结 |
| 评测集 | `git ls-files evals; git ls-files design-lab/evals; git ls-files design-lab/evals/reconstruction` | 根 `evals/` **0**；`design-lab/evals/` **63**；其中 `reconstruction` **20**（6 例 golden corpus + 索引）；**无六域级基准** |
| Prompt Intelligence 运行时 | `git grep -l -iE 'class .*Prompt' -- 'src/design_lab/*.py'; git grep -l -iE 'def .*prompt' -- 'src/design_lab/*.py'` | 只命中 `generators/comfy_http.py` 的请求字段；**没有独立运行时模块**（两条口令原本写 `**/*.py`，会漏掉 26 个顶层文件；改成 `*.py` 后读数不变，仍是这个结论） |
| 真实 OCR | `git grep -l -i 'ocr' -- 'src/design_lab/*.py'; git grep -l -i 'tesseract' -- 'src/design_lab/*.py'` | `ocr` 命中 6 个文件（`analysis/decomposition.py`、`analysis/model_cache.py`、`asset_analysis.py`、`http_service.py`、`creative/generative/model_assets.py`、`readiness/model_radar.py`），`tesseract` 0 命中；**没有 OCR 引擎实现**——新增的两个命中是派生入口与路由在"要求操作者提供观测"时提到 OCR，不是引擎。注意本行旧版用 `'src/design_lab/**/*.py'`，该 pathspec 不含 26 个顶层文件，所以旧读数少两个 |
| 运行时规模（HEAD 口径） | `git ls-files src/design_lab \| grep -c '\.py$'` | 112 个 .py：顶层 32 / creative 21 / runtime 17 / assurance 12 / governance 7 / interop 6 / analysis 6 / adapters 4 / readiness 3 / generators 3 / reconstruction 1（2026-10-24 实测；旧的 106 / 顶层 26 早于 `prompt_intelligence.py`、`prompt_results.py`、`model_selection.py`、`knowledge_library.py` 等顶层模块）。本行旧版写作 103 且引用 `'src/design_lab/**/*.py'`——那个 pathspec 只给 80（它匹配不到 `src/design_lab/` 直属文件），数字与命令本来就不成对，现已换成能复现出口令的那一条 |
| 能力包 | `git ls-files packages/capabilities \| wc -l` | 178 个受跟踪文件；atoms 21 个目录 |

## 5. 六大能力域 → 现有实现映射（只用于映射，不新建账本）

六域是**能力视角**，不是新目录、不是新账本、不是新任务编号。实现落在既有模块与既有 W00–W17 工作分组上
（W 分组见 `docs/audits/DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/pack/02_EXECUTION_TASKS.md`）。

| 能力域 | 现有实现（模块/配置） | 现有证据 | 主要缺口 | 既有任务映射 |
|---|---|---|---|---|
| Visual Intelligence | `src/design_lab/analysis/`（decomposition / plan_to_rir / model_cache / model_manifest / capability_library）、`packages/capabilities/reconstruction/`（34 个受跟踪文件）、`design_layer.py` | E1 结构；`design-lab/evals/reconstruction/` 有 6 例 golden corpus；无六域级一致性与字段完整性实测 | 观察/推断/不确定性未分离到可验证输出；无六域基准集 | W04、W05、W13；T09、T10、T11；U04、U05 |
| Aesthetic Analysis | `qa_plane.py`、`quality_record/store`、`human_jury`、`jury_store`、`jury_review.py`、`design-tokens.json` | E1；Jury 记录层存在 | 无盲评一致性、维度区分度、反例覆盖；无 E4 | W06、W08、W09；T12；U06 |
| Prompt Intelligence | 仅 `generators/comfy_http.py` 的请求字段；无独立模块 | E0（结构引用） | 结构化提示词、图像反推、跨模型转换、人工可用性评审全部缺失 | W07、W16；T09、T10；U04 |
| Design Capability Library | `design-lab/config/capability-*.json`、`packages/capabilities/`（atoms 21 / bundles / plugins / quality / standards）、`verify_knowledge_lifecycle.py` | 50 条能力证据 E1=13 / E0=37；资格状态可追溯 | 去重/分类一致性、许可核验的批量实测；`tool-control` 等来源登记债 | W02、W13；T05、T06、T07；U03 |
| Creative Tool Automation | `adapters/photoshop_com.py`、`adapters/illustrator_com.py`、`adapters/spi.py`、`generators/comfy_*.py`、`interop/penpot.py` | E0/E1 为主；ComfyUI 2 条为 2026-08-16 历史 E3，未在当前树复验 | 分层选择、超时/取消、失败模式、恢复/回滚逐项声明与实测 | W07、W10、W16；T13、T14；U05、U06 |
| Knowledge Candidate & Evaluation | `assurance/`（rights / preflight / jury / quality）、`schemas/candidate-knowledge.schema.json`、`knowledge-role-classification.json`、`verify_knowledge_lifecycle.py` | E1；候选字段与生命周期闸存在 | 无 AAOS 接收回读；无真实验收主体/时间/理由 | W08、W17；T16、T18；U09 |

`design-lab/core/` 是**明文冻结的契约参考件**（`docs/architecture/DIRECTORY-AUTHORITY.md`， "must not gain new consumers"）。
不要因为"没人 import"就删它；要动它先改那份文档并给出 ADR。

## 6. 最小真实闭环：已规划，未执行

目标闭环（`docs/taskpacks/DESIGN-LAB-DIRECTION-ALIGNMENT-2026-10-19.md` §10）：

```
固定视觉输入（含 brief/参考图）
  → 分析：观察 / 推断 / 不确定性 分栏输出
  → 结构化提示词（含目标模型/工具与不确定性）
  → 一次合格工具调用或可验证输出（读回 + 失败/恢复记录）
  → 用户或授权 Agent 验收（署名、时间、理由）
  → 知识候选（来源/许可/版本/测试/哈希/撤回）
```

- 最小可执行切片（不需要外部服务）：固定 fixture + 本地确定性分析 + 提示词结构 + 差异/读回工件；
  产物必须能复算，失败与低置信必须显式标注。
- 工具调用段：官方 API/SDK → 原生插件 → MCP → 脚本/CLI → 受控 UI 自动化；
  **当前没有可用的、未冻结的真实宿主**（Adobe E3 / ComfyUI/H3 均需 owner 授权）。AAOS 不属于「宿主」：它是可选的外部知识系统合同对端，本项目不等待它。
- 人工验收段与研究接受段属于 owner 门；不得用 VLM 自评、截图或"AI 说通过"代替。
- 映射：输入/分析 = T09/T10/U04；目标包 = U05；工具调用 = T13（E3，owner-gated）；
  验收 = T12（E4，owner-gated）；知识候选 = T16/T18/U09。
- **五段链路的实测现状（2026-10-19 逐条查过，不是推断）**：
  1. 视觉输入 = 已实现且真跑：`src/design_lab/image_assets.py:21 inspect_image`、POST `/api/projects/{id}/assets`（`http_service.py:203`，2026-10-22 复测），字节入库并按 sha256 复核。
  2. 分析/提示词 = **桥在、调用方已有两个（2026-10-19 起）**：`analysis/decomposition.py:96 Plan.from_ocr` 与 `analysis/plan_to_rir.py:137`（内部调用 `reconstruction/contracts.validate_rir`）都有测试通过，生产入口现有两条——CLI `design-lab analyze`（`cli.py:242`/`cli.py:665`）与 `POST /api/projects/<id>/assets/<img-ID>/analysis`（`http_service.py:206`，2026-10-22 复测），都经 `src/design_lab/asset_analysis.py:AssetAnalysis.derive`。核验口令：`git grep -c AssetAnalysis -- 'src/design_lab/*.py'` → 三个文件各命中。**仍然缺的是合格的 OCR/分析后端**：观测必须由操作者提供，所以该路由在 workbench 调用闸门里登记为 `backend_only`，页面也不自动编排结构。**反向提示词仍然没有运行时模块**——注意旧版用 `grep 'analyz|prompt'` 作证据是假阴性仪器（代码里写的是 `analysis` 不是 `analyz`，而 CLI 的 `analyze` 动词确实命中），别再拿那条口令的 0 命中当"没有入口"。`design-lab/core/providers.py`（不在 `src/design_lab/core/`）只是 39 行能力词汇表。所以这一段既不能声称已实现，也不能靠新建面板冒充。
  3. 工具调用 = 静态合同 E1；本机唯一可离线真跑的是 vtracer（`providers/vtracer_provider.py:7` → 外部工具链 1.0.0-alpha.3，MIT，`commercialUse: ALLOWED`）；`design-action.schema.json` 在 `src/` 内**没有 emitter**，`integrations/hosts/ffmpeg/` 是空目录。
  4. 验收 = E2 有路由有 UI（`/jury/verdict`、`/jury/proposal`、`quality`/`rights` CLI），但 E4 真人判定按铁律不由代理填。
  5. 知识候选 = 存储与路由齐（`assurance/knowledge_feedback.py:202 build_candidate`、`knowledge_candidate` 表、create/review/revoke 三路由），**缺的是从验收判定到候选的发射器**；导出合同也已存在（`design-lab/schemas/assurance-knowledge-candidate-v2.schema.json` 的 `$defs.export`，第 178 行），**不要再新建一份 export schema**——那会让一个边界出现两个权威。
- **独立全链路的真实可跑面（2026-10-24 复测，路由清单以 `http_service.py` 的 `ROUTES` 为准，共 89 条 = 49 GET + 40 POST（2026-10-28 复测：自动化连接器只读投影 `GET /api/automation-connectors` 上线，88→89、GET 48→49；2026-10-24 第七次复测：DL-KB-12 的按修订读取加了 `GET …/assistance-plans/<id>/revisions/<n>` 一条读，上一轮的 KB-11 材料导出也在同一族里。账本 `contract-bindings.json` 是 90 行 = 50 GET + 39 POST + 1 `GET+POST`，因为 `/api/projects` 在 ROUTES 里是 GET 与 POST 两枚、在账本里是一行；所以读侧扫描的分母是 50、写侧是 40，两数不可互换。`ROUTES` 的行号本轮读到 119，别抄数字也别抄行号，自读表））**：
  能靠调用入口真跑通的链是 项目 → 简报 → 参考图入库 → 资产分析派生 RIR（CLI `analyze` + POST `…/assets/<img-ID>/analysis`，live HTTP 已测）→ 原生计划提交 → jury 判定 → rights 记录 → 打包 → **preflight**（POST `…/bundles/<id>/preflight`，2026-10-19 起有 live HTTP 测试；此前所有 preflight 测试都只在进程内调 `preflight_bundle`，路由的默认 profile 与返回形状从未被走过）→ 知识候选创建/审阅/撤回。
  **两个断点没有任何调用入口，不是"还没接"而是没有实现**：(1) Prompt Intelligence——`prompt` 在 `http_service.py`、`cli.py`、`apps/workbench/shell.ts` 三处 0 命中，也没有承载模块，它只作为产品主张出现在 BOUNDARY_CONTRACT 与任务包 §9；(2) 候选导出——`assurance/knowledge_feedback.py:458 export_payload` 与 `:521 to_v1_projection` 在整个 `src/` 内**零调用方**（除各自函数体内那行 `_document(candidate, "…")` 自指标签），出站 `outbound.transport` 在 `knowledge_review.py:337` 硬编码 `NOT_CONNECTED`，该模块第 11 行的注释本身就写明"本仓库没有 ArcheAxis transport"。所以导出段缺的不是接线，是一个真实出口。（本行是 2026-10-19 的诊断，两段已于 2026-10-20 落地，见上头两条的落地状态；照本行去"补第一个调用方"会重复劳动。）
  另两处口径要写清：`quality` 记录只有 CLI（`cli.py:99`），**没有路由**，所以它既不算 matched 也不算 backend_only；`/jury/proposal` 有路由但页面不调（BACKEND_ONLY，理由已登记）。
  **链上走查（2026-10-19 起有了第一条，2026-10-20 把提示词两段接进来，2026-10-22 把提示词结果落库与人工签署接进来）**：`design-lab/tests/test_standalone_chain_http.py` 用一个服务、一个项目，按上一跳真实返回的 id 依次走 **20 跳验收链**——project→asset→brief→direction→design-layer 读回→资产分析派生 reconstruction-ir/v1→目录读回 `GET /api/models`→模型选择 `POST …/model-selection/choose`→提示词组合（prompt-composition/v1，正文里必须出现前面那两跳写入的 brief 与 direction，`model.selected` 必须就是刚记录的那个修订）→提示词反推（prompt-reversal/v1，绑定 asset 那跳返回的 sha256）→**提示词结果读回 `GET …/prompt-results`（两份文档都必须在库里，且存下的 content_sha256 等于产生它那一跳发布的 document_sha256）**→**具名人工签署 `POST …/prompt-results/<id>/review`（签名引用的就是它判过的那份摘要）**→**jury 判定（对着 asset 那一跳返回的 version_id 与 sha256 直接落判，201）**→jury 读回→**rights 决策**→rights 读回（CLEARED）→知识候选（`evidence_sha256` 取自这次被签署的组合，编号一律字面量 `UNUSED`）→人工审阅→候选读回，实测 `project=201 asset=201 brief=201 direction=201 design-layer=200 analysis=201 catalog=200 model-choose=201 prompt-compose=201 prompt-reverse=201 prompt-results=200 prompt-accept=201 jury-verdict=201 jury-readback=200 rights=201 rights-readback=200 candidate=201 review=200 candidate-readback=200 export=200`；另有 **4 跳交付链** `project=201 native=READBACK bundle=201 preflight=200`。此前每个缝各自有测试但没人按顺序走过，"独立全链路"是从逐跳绿灯拼出来的主张；而 2026-10-21 的审计指出更实的一层：那 18 跳证明的是同一台服务器上多个接口能按顺序调用，**不是**同一份专业产物贯穿了分析、验收与留存——现在第 11、12 跳与第 17 跳的 `evidence_sha256` 把这条链钉成了一条身份链。写这条链时发现的两个链事实，都记在测试注释里：jury 的判定对象此前只能靠测试自己往数据库里 publish 版本，从未证明"导入的资产能长出一个可判的 version"；`native_tasks.execute` 只接受字面量 scope `project-native-test`（`native_tasks.py:94`），所以交付段是受控 E2 而不是真实宿主 E3。导出段的调用方已经接上（2026-10-20 同日第二批）：`export_payload`/`to_v1_projection` 在 `src/` 内的零调用者由 `KnowledgeReview.export_document` 终止，入口是 `GET …/knowledge-candidates/<id>/export` 与 CLI `export-candidate`，也正是这条链的第 20 跳（实测 `export=200`，且 `provenance.job_id` 回显 `UNUSED` / `EXPLICITLY_UNUSED`、`v1_projection.source_id` 为 `UNUSED:UNUSED`）；`test_design_layer_http.py:147` 那条 6 跳走查仍止于 design-layer。所以"独立全链路跑通"当前的准确说法是：**20 跳每一跳都有可调入口与 live 证据，含提示词两段的页面入口、结果落库与人工签署、以及导出出口**。仍然不在链上的是三件事，且都不是入口缺失：发送通道（`outbound.transport` 恒为 `NOT_CONNECTED`、`sent_count` 恒为 0，本项目没有 ArcheAxis 传输）、合格后端（`QUALIFIED_LOCAL=0`，owner 2026-10-21 裁定推理执行仍不接）、以及真人 E4 与真实宿主 E3。（2026-10-22 B3 桌面半：原先第四件"桌面端对 `…/prompt-results` 的调用"已经不再是缺口——`apps/workbench/shell.ts` 现在列出存下的结果并可具名签署，`design-lab/tests/e2e/browser_design_layer_e2e.mjs` 第 14 节在真实 Chromium 里走完"生成→读回列表→匿名签字被本地拒→署名后读回 ACCEPTED"，并把这几项事实写进 `browser-e2e-summary.json` 的 `promptLoop`，所以跳过这一节的运行不能被读成 PASS。两条路由随之从 `BACKEND_ONLY` 表里删除——留着会被 `STALE_BACKEND_ONLY` 判红，这正是这张表双向防陈旧的作用。）
- **两处曾经不是工程缺口、而是 owner 决定，现在一条已定、一条仍待裁**：(a) 验收记录里没有 `source.job_id`/`operation_id`，而 `build_candidate` 强制要求它们——owner 2026-10-20 定了做法：「编号问题留出可填写位置，用户自行填写或者选择用没用」。所以界面与接口提供可填写位置并允许显式选择"不使用"，代理仍不得凭空填 provenance。落地状态（2026-10-20）：写入合同已接受字面量 `UNUSED` 代表"显式不使用"（`knowledge_feedback.PROVENANCE_UNUSED`，v2 schema 两处 description 已记名），空白仍 400 且点名被拒字段——"没填"与"声明没有"是两件事；导出信封回读 `provenance.job_id_state ∈ {USER_SUPPLIED, EXPLICITLY_UNUSED}`，v1 投影 `source_id` 原样拼接不做美化。界面侧同日落地（2026-10-20，b0b8be55）：`#/knowledge` 的创建表单里两个编号各自先选「来处」——"我来填写"或"不使用（发送字面量 UNUSED）"，未选时本地就拒绝并说明是"没选"而不是"没有"；选"不使用"只禁用填写框、不清空内容，框里还有字时报自己的冲突而不是静默丢掉；`apps/workbench/tests/appshell.mjs` ㉒ 逐条走过这三态并断言外发体里 `source.operation_id === "UNUSED"` 而同表单填写中的 `job_id` 原样带走——字面量上线，不是界面装饰。合同侧与界面侧现在都不再阻塞。(b) 本机没有合格模型：`readiness/model-radar.json` 14 条里 `QUALIFIED_LOCAL=0` 且全部 `default_enabled: false`，`reconstruction-models.json` 指向的模型根目录不存在，omniparser `commercialUse: DENIED`；磁盘上确有 Qwen2.5-VL-7B GGUF（含 mmproj）但它不在雷达里。要不要把它列为合格本地模型，是许可与资格裁定，不是我能替你定的。界面侧已改读 `GET /api/models`（`src/design_lab/model_catalog.py`）：它把雷达 14 条与 provider-capabilities 9 条端点**并列**给出、`join.key` 保持 null 并写明两边无共同字段，计数全部实测（`qualified_local=0`、`weights_recorded=0`、`default_enabled_true=0`），`selection.transport` 仍是 `NOT_CONNECTED`——所以"可选"不等于"已合格"，也不等于"能发送"。选择也已被记录（2026-10-20 同日第二批）：`model_selection` 表按项目追加修订、触发器拒绝 UPDATE/DELETE，`GET /api/projects/<id>/model-selection` 回读三态 `CHOSEN / DECLINED / NEVER_ASKED`（DECLINED 是操作者显式「不用」，NEVER_ASKED 是没人被问过，两者不得合并），`POST …/model-selection/choose` 写一次选择；快照字段由服务从它校验过的目录行复制，所以命名一个模型带不进任何资格，`MODEL_NOT_IN_CATALOGUE` 拒绝登记外的名字；提示词文档原样带出 `model.selected` 与 `selection_state`，而 `model.executed` 在两份 schema 里都是 const false。三份信封级合同同日补上 schema 并各带一条live 载荷用例（`design-lab/schemas/model-catalog-v1.schema.json`、`model-selection-readback-v1.schema.json`、`assurance-knowledge-candidate-export-envelope-v1.schema.json`，用例在 `design-lab/scripts/verify_route_payload_contracts.py`，账本三行随之从 SCHEMA_LESS 翻成 BOUND_SCHEMA）；未付的版本债由 7 条回到 5 条，剩的是 Adobe 两个 job-spec 与 rights/research/native-runtime 三份读回。（2026-10-22 更新：那三份读回已付——rights/research/native-runtime 各有自己的 schema 与 live 载荷用例，`VERIFY_CONTRACT_BINDINGS` 读数由 `routes=66 bound=26 schema_less=40` 变为 `bound=29 schema_less=37`，`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=13`；未付的只剩 Adobe 两个 job-spec，它们的形状是 adapter 构造的作业文档而不是本服务写的 envelope，付它要在 `photoshop_com.py` / `illustrator_com.py` 的边界上装载 schema，不是再补一份没人读的 schema 文件。）2026-10-22（B2b）：这两条也付了，且按那句要求付——三份契约文件在 `design-lab/schemas/reconstruction/`（adobe-patch-job / photoshop-patch-job / photoshop-native-job），两个 adapter 各自持有一张 `JOB_CONTRACTS` 版本表，`execute()` 在第一次 COM 调用前按 body 里的版本装载并校验，取不到文件或不认识版本都是预检拒绝；手检一条没删。`VERIFY_CONTRACT_BINDINGS` 实测 `routes=68 dispatched=68 bound=33 schema_less=35`，带版本号的未付债清单实测为空（`test_contract_bindings.py` 里那条从"两条 Adobe"改为"空集"，并写明空集才是这里真正的牙齿：新的带版本 SCHEMA_LESS 行照样红）。`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=14 failures=0`。
- **链的桌面可达性，一句话（2026-10-22 直接读 `design-lab/scripts/verify_workbench_route_calls.py` 的 `BACKEND_ONLY` 表得出，不是估计）**：20 跳验收链里 **19 跳在 workbench 有真实调用点**，只剩一跳登记为 `backend_only`：①"资产分析派生 RIR"——本机无合格 OCR/分析后端（`readiness/model-radar.json` 报 `QUALIFIED_LOCAL=0`、全部 `default_enabled:false`），操作者路径是 CLI `design-lab analyze`。原先的 ②`GET …/prompt-results` 与 ③`POST …/prompt-results/<id>/review` 两条豁免已随 B3 桌面面板落地删除（留着会被 `STALE_BACKEND_ONLY` 判红：前端确实开始调用了；同日实测 `VERIFY_WORKBENCH_ROUTE_CALLS=PASS calls=109 routes=66 matched=55 backend_only=11 dynamic=3 special=1`）。这张表是**双向防陈旧**的：路由消失却仍登记会红，前端已经开始调用却仍登记也会红，所以这句总结会跟着表一起失效，不会悄悄过期。owner 待决里"要不要把磁盘上的 Qwen2.5-VL-7B GGUF 列为合格本地模型"正是第①跳能否进页面的前置——缺的是资格裁定，不是代码。
- **精选来源阶梯的第一条 CONSUMED 是量出来的，不是登记出来的（2026-10-22 B5）**：`packages/capabilities/selected-sources.json` 由 `registered_only=8 mapped=2 consumed=0` 变为 `mapped=1 consumed=1`，升上去的是 `SRC-T07-MOTION-COMPOSITED`（`packages/capabilities/standards/MOTION_ACCESSIBILITY.md`）。证据是 `design-lab/tests/e2e/audit_workbench_motion.mjs`：真实 Chromium 逐条点击导航（21 项 → 21 个 location → 22 次扫描），读 CSSOM 与 computed style，实测 9614 条规则、88 个 `@keyframes`、154 个关键帧步进、8995 个元素，布局属性动效 0 条；同一把扫描器必须先判出植入缺陷的 3 条，零才算证据。它刻意不判的也交了出来：`transition: all` 132 处、非布局的其他动画属性 110 处——判据原文只禁布局属性，闸门不自造更严的标准。**这条不是判据变更**：E2 是受控运行时测量，`capabilityState` 仍是 `structural-pass`，宿主 E3 与真人 E4 依旧冻结。它进了 `verify_browser_e2e_ran.py` 的 `TEST_MODULES`，所以在 required 作业里跳过即红；一条 CONSUMED 的判据若靠"没人看"活着，就等于没有。
- **已作废的三条调查结论**（写在这里防止下一会话照它们动手）："export 没有 schema 文件" 与 "plan_to_rir 缺失" 都是错的；前者见上（且 2026-10-20 起信封自己也写了 `design-lab/assurance-knowledge-candidate-export-envelope/v1`，不再只靠正文里的 `status` 认身份），后者是缺调用方而非缺实现。第三条现在也过期了："`plan_to_rir` 无生产调用方" 自 2026-10-19 起不成立（CLI `analyze` + `POST …/assets/<id>/analysis` 两条入口，见 §上一项 2），照旧话去"补第一个调用方"会重复劳动。缺的那一半是**合格后端**，不是调用方。
- 下一轮若获授权，先交付"可审阅的读回面板 + 真实数据源 + 可复现测试"，
  把没建的那一半写在可见文字里，不要把 PLANNED 标成 IMPLEMENTED。
  **2026-10-22 之后的实际剩余面（B2–B5 已全部落地并 CI_VERIFIED @ `f4b727e1`，见审计件 §5.18–§5.21）**：
  ①带版本号的未付契约债清单实测为空（当时余下 32 条 SCHEMA_LESS 都是"信封自己不带 schemaVersion"的选择，不是欠账；2026-10-23 后端 I 把其中设计层一族付成有版本有合同，剩下的条数交 `scripts/verify_documented_counts.py` 现读，不抄本文字）；
  **后端 A/B/D 已落地（审计件 §5.23 与 §5.24）**：`GET /api/projects` 现回 `design-lab/project-list/v1`，
  逐项目给 14 个表面的计数、最晚时间戳与"还没人签"的两个数，合同把 **null=该表面在此检出从未建表**
  与 **0=表在而此项目没有记录** 绑成双向不可互换；能力库的 `counts.qualified` 拆成
  `qualificationVerdicts / qualifiedTrue / qualifiedFalse / qualificationNotAdjudicated`
  （旧字段"读起来像合格数、算的是有判定数"，今天同为 0，将来会分岔）；三条任务读回合成一份
  `design-lab/task-readback/v1`（`surface` 判别 + `limit=100` 与 `truncated`/`next_cursor` 同源 +
  状态词汇读自 `design-lab/config/state-vocabularies.json` + `does_not_say` 点名取消语义），台账那两行
  "recorded debt"随之付掉并更正了两处过期理由。实测读数：
  `VERIFY_CONTRACT_BINDINGS=PASS routes=68 dispatched=68 bound=36 schema_less=32`、
  `VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=17`。D07/D08 经复核**不是缺口**：候选每行已带
  `export_ready/export_blocked_by`，任务记录已带 `cancel.requested` 与 `cancel.acknowledged` 两个布尔——
  两者都有真实写入路径（`job_store.acknowledge_cancel` 在 `CANCEL_REQUESTED` 上置 1 并转 `RECONCILING`，
  `native_tasks._failed` 的派发前被拒路径也置 1），语义是**适配层已确认、仍需读回**，不是宿主已停手；
  界面可显示"已确认取消，仍需读回"，不得画成会自己变绿的进度。（此处上一版写的"没有通往 true 的宿主
  事件"是没打开那两个函数就下的结论，已在 §5.23 原样更正。）
  **A 批欠下的两条 CI 红已在 §5.24 记账并修掉**，其中一条是安装态才会踩的：`PROJECT_ROOT` 是
  `Path(__file__).parents[3]`，在 wheel 里指向解释器的 `Lib`，于是 `/api/projects` 打不开自己的合同、
  启动器回 `status: ERROR`。改走 `repo_resource()` 并给 `pyproject` 补三行 `force-include`，另加一个
  从磁盘枚举 `repo_resource('…')` 字面量的闸门（`design-lab/tests/test_packaged_contract_resources.py`，
  含一条"删掉声明必须判红"的手检）。接入侧要读的字段清单：列表页
  `{schemaVersion, surface:'list', limit, truncated, next_cursor, count, stateVocabulary, tasks, does_not_say}`，
  详情页同信封但 `surface:'task'` 且 `truncated` 恒 false、`next_cursor` 恒 null，事件页 `surface:'events'`
  且**游标是 `event_no` 整数**——`apps/workbench/contracts.ts` 现在把 `next_cursor` 写成 `string | null`，
  对事件页不精确，接入时随信封一起改正（本批不动界面）。
  **本批状态：CI_VERIFIED_EXACT_SHA @ `91186bc7`**（分支与 main 同指此枚；11 个重作业全绿，
  `PYTHON_TESTS_UNION=OK expected=3167 distinct=3167 ran=3167 missing=0 unexpected=0`，
  安装态作业 `Ran 3 tests` 且步骤三条 grep 全过——§5.23 欠的两条红就是在这一枚上转正的）。
  **上一轮点名的"装机面债"已在同日第二十二批（后端 E）付清，别再照旧话重做**（审计件 §5.25）：
  度量换了地方——静态用 AST 从 `http_service.py` 走 import 闭包列出 `PROJECT_ROOT` 拼出来的仓库读取（18 条里 17 条没有 force-include 声明），
  动态把 `design-lab/tests/test_standalone_chain_http.py` 改成能 honour `DL_LAUNCH_INSTALLED=1` 并在 `setUp`
  先验布局（包路径含 `site-packages`、`/api/health` 的 `bundleOrigin=packaged`），在装好的 wheel 上跑整条链。
  **静态单独不够**：`production_preflight.py` / `delivery_bom.py` / `evidence_readback.py` 把同一个根拼成
  `Path(__file__).parents[3]`，清单看不见，是安装态实跑抓出来的——`GET …/design-layer` `500 INTERNAL`、
  `POST …/tasks/<job>/bundle` **`409 NATIVE_BUNDLE_UNVERIFIED`（缺文件伪装成语义判决，最坏的一种）**、
  `POST …/bundles/<id>/preflight` `503 PROJECT_STORE_UNAVAILABLE`（矛头指向用户的数据库）。
  现在 20 处读取改走 `repo_resource()` 并补 20 行 force-include，装机链 **4 条用例全绿**，
  `CHAIN_HOPS … export=200` 与 `DELIVERY_HOPS project=201 native=READBACK bundle=201 preflight=200`；
  装机 GET 面（能用一个真实项目 id 构造的 23 条）2xx 由 14 升到 **17**，`/api/models`、
  `…/prompt-results`、`…/design-layer` 三条拒绝全部转正。植入检查做过：移走
  `resources/repo/design-lab/production/profiles` 后立刻 `FileNotFoundError: packaged repository resource
  missing: production/profiles`，拒绝发生在导入时而不是悄悄回落。
  **CI 里已有永久的一步**：clean-wheel 作业新增 "Walk the acceptance chain against the installed package"，
  断言 `Ran [1-9][0-9]* tests`（不钉死用例数）、`^OK`、无 `skipped`、`CHAIN_HOPS` 与 `DELIVERY_HOPS` 都打印。
  **后端 E 状态：CI_VERIFIED_EXACT_SHA @ `f804af9f`**（main 与备份分支同指此枚；11 个重作业全绿，
  `PYTHON_TESTS_UNION=OK expected=3169 distinct=3169 ran=3169 missing=0 unexpected=0`，新加的装机链步骤
  在该枚为 `success`；打包修正单枚 `2102ba8b` 也独立跑过一遍全绿）。
  审计工具也在库里了：`design-lab/scripts/audit_repo_root_reads.py` 从 `http_service.py` 走 AST import 闭包，
  报告路由可达的仓库根读取及其打包声明状态，`--control` 会从 git 取修复前字节证明检测器还看得见病
  （它曾因为只认 `ast.Call` 而对 `parents[3]` 的 `ast.Subscript` 形式报过假的 "0 remaining"）。
  `design-lab/tests/test_packaged_contract_resources.py` 把这份报告变成闸门，并**把"空群体"本身判红**。
  它的两条盲区写在工具头部注释里，别把它们当已解决：先把根存进变量的两步拼法不追；不同打包前缀的
  合法 packaged-first 读法会被报成 NOT-SHIPPED（现在只有 Adobe 桥那一条，宿主派发仍冻结）。
  **本机那条未结的读数已经结清**（原本记在这里，现由后端 F 修完，见下条与 §5.26）：
  `test_capability_library_clean_install` 两条安装态用例在本机绑定跑里稳定
  `[WinError 206] 文件名或扩展名太长`（解包 wheel 到 `.project-local/task-runtime/python-tests-shard-1/…`
  的深路径，377 个成员里 8 条超 259 字符且探针一条都不读），Linux CI 三次全绿。
  更正一句旧话：`/api/evidence-projection` 在安装包里回 `503 EVIDENCE_LEDGER_ABSENT`，detail 是
  `design-lab/config/task-ledger-r3.json is not in this checkout`，判决仍然正确，但它命名的那个"检出"
  其实是解释器目录 `…/Lib`——上一轮写的"临时根没有台账"说错了对象。
  **上一轮那两条"没测/未修"，同日第二十三批（后端 F）都结清了**（审计件 §5.26）：
  ① 分母先更正——账本是 **51 条** GET 行（2026-10-28 加自动化连接器只读投影 50→51；F 批次当时量到 41；K 批新增方案列表、方案详情与输出类型三条读，K4 再加目标档案的轴、列表、详情三条读，KB-16 再加反馈历史一条读，KB-11 再加材料导出一条读，KB-12 再加按修订读取一条读），不是前两轮写的 37 条（我当时的 `startswith('/api/')` 过滤把
  `/workbench` 与 `workbench.ROUTES` 悄悄滤掉了）。现在 `test_standalone_chain_http` 里新增
  `test_every_ledger_get_route_is_answered_in_this_layout`：用写入路由造出真实资产/简报/方向，再经
  `_deliver_to_preflight()`（从交付腿抽出来共用）拿 job/bundle/version id，把每一行的槽位换成真值调用。
  读数：源码 `routes=39 reads=39 answered=35 verdicts=4` 无未点名 5xx；装机 `reads=38 answered=34
  verdicts=4`，唯一被点名的 5xx 是 `/api/evidence-projection → 503 EVIDENCE_LEDGER_ABSENT`
  （安装态没有可投影的治理检出；同一条在源码检出回 200，两侧名单互换即红，所以这不是豁免是差别）。
  仍未读的 3 条各带原因：`…/native-assets/<id>/verify` 需要先登记的原生资产；候选 export 由同一布局的
  验收链走到 `export=200`；`workbench.ROUTES` 不是 URL。覆盖表**双向**断言，新路由没人写读法就红；
  CI 装机步额外要求日志出现 `GET_SWEEP layout=installed`。
  ② 本机那两条 `[WinError 206]` 修好了：逐成员解包 + 对跳过集合下断言（只许 domain-pack 基准页被跳，
  能力库四个输入不许跳），判据用成员名而非 errno（同一超长路径在 `makedirs` 报 206、在 `open` 报
  `[Errno 2]`，按码过滤会悄悄再坏一次），并加了一条不对称用例证明这条豁免两侧都有效。在 runner 自己的
  深临时根下该模块 `Ran 5 tests / OK / errors=0 skipped=0`。**后端 F 状态：IMPL_LOCAL + TESTED_LOCAL
  @ `74a461f4`**，CI 逐作业读数见 §5.26 末。
  **后端 F 复核后：CI_VERIFIED_EXACT_SHA @ `11e30625`**（main 与备份分支同指此枚；11 个重作业全绿，
  `PYTHON_TESTS_UNION=OK expected=3171 distinct=3171 ran=3171 missing=0 unexpected=0`；CI 装机步骤日志原文
  `GET_SWEEP layout=installed routes=39 reads=38 answered=34 verdicts=4 unmeasured=3`，该步骤要求这行必须出现，
  所以用例被重构成空转时作业不能照绿）。本机绑定重跑 `scripts/run_python_tests_all.py --shards 3 --jobs 1`
  三分片全 `exit=0`（`shard=1/3 outcomes={'PASS': 1104,'SKIP': 2}`），此前稳定复现的两条本机 ERROR 消失——
  这条只能在 Windows 上量，Linux CI 给不了这个证据。
  **写侧的同一把尺子已于同日第二十四批（后端 G）量完**（审计件 §5.27）：`design-lab/tests/`
  `test_installed_write_surface.py` 把账本 **40 条 POST 行**（含 `GET+POST` 那条创建行；G 批次当时是 33，K 批新增方案创建/修订/选用三条写行，K4 新增目标档案草稿与校验两条写行，KB-16 新增外部使用反馈一条写行，KB-05 D5 新增知识判断一条写行）登记成一张按对象依赖顺序排的覆盖表，
  其中 **39 行**逐行真写、每行都用 GET 读回，剩下 1 行按政策点名不走，覆盖表双向断言、槽位缺值即红、5xx 名单按布局分开且必须与实际发生
  完全相等。今日读数取自源码布局：
  `rows=39 walked=38 written=38 read_backs=47 refused=0 excluded=1`（G 批次当时是 `rows=29 walked=28`
  与 34 次读回，K 批与 K4 把方案、目标档案与反馈的写行逐条加了进来，分母跟着动才是对的——写行增加了
  而覆盖表不跟着走，正是"新增了没人证的写面"的形状。装好的 wheel 由 CI 的装机作业拿同一张表再跑一遍，
  本机这一次不替它报数）。这是 §5.25 付清读路径之后写侧被真走到时给出的确认，不是侥幸。唯一不走的行是 `POST …/tasks/<job>/run`：体只有一个 `attempt_id` 而扫描手里就有，
  但 `native_workers.start()` 会 spawn 子进程派发真实宿主，冻结与"不触发真实宿主/模型执行"都在，所以按
  `FROZEN-BY-POLICY` 点名登记，不冒充"构造不出合法体"。**播种把一处误判顶了出来**：把 wheel 里的
  `config/state-vocabularies.json` 移走后 `POST …/tasks/<job>/bundle` 回 **400 INVALID_REQUEST**——
  `TaskReadbackError` 继承 `ValueError`，写侧那几条顺手建同一份信封的路由没像读侧两条那样就地包，于是
  "服务器读不出合同文件"被发成"你的请求不合法"。已按 dispatch 家规在通用 `ValueError` 子句前补一条
  具名子句（`8b83652d`），并加一条不对称用例：删掉该子句必红、恢复必绿，四步实跑已记；批次 D 给两条读路由就地加的那层包装与它产出逐字节相同的拒绝体，已删——一个字节面不留两个主人。两侧读数与 wheel 字节在删包装后重测：源码与装机同值，wheel 1,073,608 字节。**后端 G 状态：IMPL_LOCAL + TESTED_LOCAL @ `3f542016`，复核后 CI_VERIFIED_EXACT_SHA @ `fa0cf178`**（main 与备份分支同指此枚；11 个重作业全绿，CI 装机步日志原文 `POST_SWEEP layout=installed rows=29 walked=28 written=28 read_backs=34 refused=0 excluded=1`，该步骤要求这行与 `POST_SWEEP_WRITTEN`/`POST_SWEEP_EXCLUDED` 都出现且"未点名 5xx"不出现；`PYTHON_TESTS_UNION=OK expected=3177 …missing=0 unexpected=0`，本机三片 exit=0 零 ERROR——但一处中间红要点名：`1ff547bb` 那枚的 Python 作业红在 `test_documented_counts`，因为我重写了计数闸门的**逐字锚句**，而 `verify_design_lab --check` 那 76 项不含这条闸门也不含单元测试；改过受治散文后必须单独跑它，细节与两处修正见 §5.27 末）。级别仍是 E2——这张表量的是"这台装好的服务写不写得进、
  读不读得回"，不是产物好不好。CI 装机步现同时要求 `GET_SWEEP layout=installed` 与 `POST_SWEEP
  layout=installed`（外加 `POST_SWEEP_WRITTEN`/`POST_SWEEP_EXCLUDED` 两行与"没有未点名 5xx"）。
  顺带更正本件里三处没人看守的散文行号：`http_service.py` 的 `ROUTES` 现为 **94** 行（原写 93），
  POST `/assets` 路由现为 **203**（原写 191），POST `…/assets/<img>/analysis` 现为 **206**（原写 195）。
  三处都不是本批改行号改坏的（本批插入在 470 行之后），是更早批次留下的、且**没有任何闸门会读它们**——
  与 §5.25 那次被 `EMITTER_POINTER_NOT_THE_VERSION` 当场抓住的账本指针同一形状，只是散文坏了不会响。
  **同日第二十五批（后端 H）把读侧最后一条"没调用"结清了**（审计件 §5.28）：批次 F 那句
  "`…/native-assets/<id>/verify` 需要先登记的原生资产"是**错的**——交付腿自己就登记了一行
  `{"id": "native-<64hex>", "kind": "psd", "verification": "METADATA_ONLY"}`，`GET …/native-assets`
  当场答出来，只是当时没人去读。现在那条 UNCONSTRUCTED 已换成真调用，扫描分母随之移动：
  源码 `reads=39 answered=35 unmeasured=3` → `reads=40 answered=36 unmeasured=2`，
  装机 `reads=38 answered=34 unmeasured=3` → `reads=39 answered=35 unmeasured=2`；仍有 **2 条**没被这条扫描读到，且都不是洞而是判决：候选 export（同一布局的验收链已走到
  `export=200`，本扫描不重复建候选）与 `workbench.ROUTES`（那行账本记的是模块表名，不是 URL）。
  **这条路由量的是字节**，且已用播种证明不是标签：列表行的 `verification` 是 `METADATA_ONLY`，
  verify 行自己重算摘要后答 `HASH_VERIFIED`；把账本记下的那个 `native.psd` 改成**等长**的字节
  （只查大小也过得去）判决必须变成 `409 NATIVE_ARTIFACT_UNVERIFIED`，改回来必须回到 `HASH_VERIFIED`，
  形状合法但从未登记过的 id 必须 `404 NATIVE_ASSET_NOT_FOUND`；再把 `native_assets.py` 里那行摘要比较
  改成永假，这条用例必须红——实测四步：带比较 OK、去掉比较红、恢复 OK、恢复后再 OK，
  所以这不是"看着像有牙齿"的断言。两侧都跑：源码 6 OK，装好的 wheel 里
  `NATIVE_VERIFY layout=installed clean=HASH_VERIFIED tampered=NATIVE_ARTIFACT_UNVERIFIED
  unknown=NATIVE_ASSET_NOT_FOUND`，写侧扫描读数一字未动。CI 的装机步现同时要求这行整串出现。
  本批未新增打包面债务：这条路由读的是项目自己的资产库字节，不读仓库合同文件，两侧同值即是证据。本节的两个读侧分母（39 条 GET 行、仍有 2 条没被读到）也已交 `scripts/verify_documented_counts.py` 现数（claims 13 → 15，两条各自播种皆红、照实写 PASS），所以它们不能悄悄变陈旧。**后端 H 状态：IMPL_LOCAL + TESTED_LOCAL @ `4454531b`，复核后 CI_VERIFIED_EXACT_SHA @ `51c14f10`（main 与备份分支同指此枚，run `39865099663` = completed success、12 作业无非绿；其代码前枚 `d9976d0c` 同枚全绿，11 个重作业全绿，CI 装机步同一条日志里给全 `GET_SWEEP`/`NATIVE_VERIFY`/`POST_SWEEP` 三行且要求整串出现，`PYTHON_TESTS_UNION=OK expected=3178 …missing=0 unexpected=0`；本机把三个模块放进取数器自己的深 TEMP 重跑 `Ran 17 tests / OK / exit=0`、零 `WinError 206`——本机整轮 union 未跑完就被中止，所以"全套通过"这条只按 CI 那枚报，不冒充本机证据。细节见 §5.28 末）。
  口径也补清：72 是 `ROUTES` 条目数（`/api/projects` 在那里是 GET 与 POST 两枚），账本 74 行 =
  41 GET + 32 POST + 1 `GET+POST`，所以读侧分母 41、写侧分母 33，两个数不可互换。
  **同日第二十六批（后端 I）把设计层这一族从"账本记 SCHEMA_LESS"改成了有合同**（审计件 §5.29）。
  先现数再动手：账本 68 行、`BOUND_SCHEMA` 36 / `SCHEMA_LESS` 32，按"账本的 handler 落在
  `design_layer` 的哪几个方法上"量出这一族 21 行 = 3 已绑 + 18 行未绑；载荷闸门当时 `bindings=17`。四份信封合同全部
  **按实测字节**写（先用真服务把每条路由的字节打出来，再写文档）：
  `design-lab/schemas/design-record-v1.schema.json`（一条记录的信封，读与写共用，`record_kind` 判别）、
  `design-collection-v1.schema.json`（活行列表，`collection` 判别，方向页带游标、token 页**不许**有游标）、
  `design-lineage-v1.schema.json`（版本链，`subject_kind` 判别）、`design-layer-rollup-v1.schema.json`
  （整片读回，`chosen_direction` 与 `active_binding` 只能是 null 或真记录）。被包的形状一律 `$ref`
  不重述：brief 行回 `design-lab/schemas/brief-readback.schema.json` 的 `$defs.brief`，DTCG 文档回
  `design-lab/schemas/interop-dtcg-document.schema.json`，direction / binding / token_document 由新文件
  第一次做主人。服务侧每次都判——`_check_design_record` / `_check_design_collection` /
  `_check_design_lineage` / `_check_design_rollup` 装载自己的合同，不符就 500
  `DESIGN_*_CONTRACT_VIOLATION` 带字段路径，且先比版本再校验。**这条守卫当场咬了我一口**：我把
  `get_design_layer` 包成了双层 `design_layer`，闸门立刻红了七条并指名 `'design_layer' was unexpected`——
  先红的是我的补丁，不是产品。18 行随之翻成 BOUND_SCHEMA（第 18 行是我第一轮按路由名过滤时漏掉的
  `GET /api/design-systems`——换成"账本的 handler 落在 `design_layer` 的哪几个方法上"重新量才找出来），
  emitter 逐行重钉为
  `src/design_lab/design_layer.py:104`、`:105`、`:106`、`:107`（各版本常量自己那行，`BRIEF_READBACK` 的
  `:64` 一字未动），设计层这一族付掉 **18 行**，账本仍有 **15 行**没有合同（2026-10-28 的
  `GET /api/automation-connectors` 按 SCHEMA_LESS 登记，payload 不声明 schemaVersion），
  live 载荷比对现在 **57 条绑定**——每条绑定至少一例真实载荷，多数两例、少数一例或三例（目录读那几行只有一例：`catalog()`
  没有"空目录"这一分支可给）：活梢与被超版、有内容与空项目、
  追加与同幂等键的重放。一条写在账本 reason 里的旧断言被实测字节推翻并点名更正：brief 链那行原写
  "superseded_by 链**加 design_layer_event 行**"，实测文档里根本没有事件行——`_chain()` 读
  `design_layer_event` 只是用 `*-revised` 载荷找回父行，交出的仍是记录；事件 kinds 仍归
  `EVENT_KINDS` 与表 CHECK 管，不由这份 schema 管。打包按三件套付清：四个新 `repo_resource('schemas/…')`
  读取点 + 四行 `pyproject` force-include + `design-lab/tests/test_packaged_contract_resources.py`
  从磁盘枚举；植入检查做过——把装好的包里的
  `resources/repo/design-lab/schemas/design-layer-rollup-v1.schema.json` 移走，装机扫描立刻
  `FileNotFoundError: packaged repository resource missing: schemas/design-layer-rollup-v1.schema.json`
  （抛在 `design_layer.py:114` 的导入期，六条用例全部红在 setUp 之前），装回即 `Ran 6 tests / OK`。
  **两侧扫描的语义与读数一字未动**，这是本批的可复核部分：源码
  `GET_SWEEP layout=source routes=39 reads=40 answered=36 verdicts=4 unmeasured=2`、
  `POST_SWEEP layout=source rows=29 walked=28 written=28 read_backs=34 refused=0 excluded=1`，
  装机 `GET_SWEEP layout=installed routes=39 reads=39 answered=35` 与
  `POST_SWEEP layout=installed` 同值、`NATIVE_VERIFY` 两侧同串；信封是**加在回答上的**，不是改回答。
  前端 0 文件。牙在测试里：`design-lab/tests/test_route_payload_contracts.py` 的绑定清单钉从 17 项
  扩到 35 项，另加五条只针对这一族的种红（判别器说谎、链丢 `root_id`、token 列表凭空长出游标、
  `{}` 冒充"没有选择"、追加与重放键集必须一致），该模块 31 项 OK。  **后端 I 状态：IMPL_LOCAL + TESTED_LOCAL @ `efa5a8af`，复核后 CI_VERIFIED_EXACT_SHA @ `efa5a8af`**（main 与备份分支同指此枚，两次 push run `39943398842` / `39943381425` 均 completed success，12 作业里除 branch-light 那枚按规则 skipped 外全部非绿为零；Python 作业三分片 exit=0、`PYTHON_TESTS_UNION=OK expected=3183 distinct=3183 ran=3183 duplicates=0 missing=0 unexpected=0`（本机 PASS 3161 / SKIP 22），同作业 `VERIFY_CONTRACT_BINDINGS=PASS … bound=54 schema_less=14`、`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=35 failures=0`、`VERIFY_WORKBENCH_ROUTE_CALLS=PASS calls=109 …`、`VERIFY_DESIGN_LAB=OK total=76 failed=0`；清轮安装作业给全三行 `GET_SWEEP layout=installed routes=39 reads=39 answered=35 verdicts=4 unmeasured=2`、`POST_SWEEP layout=installed rows=29 walked=28 written=28 read_backs=34 refused=0 excluded=1`、`NATIVE_VERIFY layout=installed clean=HASH_VERIFIED tampered=NATIVE_ARTIFACT_UNVERIFIED…`。**一处本机差异，第一版归因是错的，这里把两版都留下**：同一枚在本机重跑整轮 union 是 `union-exit=1`，shard 3 报 59 FAIL + 1 ERROR（`PYTHON_TESTS_SHARD_FAILURES shard=3/3 n=60 …`）。**我最初写的是**「集中在机器绑定套件，可能与落 20261023 方案包的并发写有关」——**这句已被实测推翻**：两次静默复跑失败模块与耗时完全一致（`415.7s` / `414.4s`），不是竞态；真因是 `scripts/verify_spill_census.py` 在本机报 `INCOMPLETE`（`rootCensus truncated=true cappedAt=4096`），而本机忽略根实测 `.project-local/task-runtime` 308,833 条、`task-artifacts` 9,153 条、`projects` 472 条，全是历轮运行与测试自己写出来的状态；这条闸拒绝把截断读成干净（本就该如此），依赖它判定的套件跟着红。CI 是干净 checkout，那些根不存在，所以同一枚 CI 三分片 exit=0、`PYTHON_TESTS_UNION=OK expected=3183 …missing=0 unexpected=0`。**"全套通过"这条只按 CI 报**；本机这条不是代码缺陷，也不许用`rm -rf .project-local/task-artifacts/**` 去"修好"——`currentExecution` 的回执按 `artifact_sha256` 绑在那些字节上，删它等于删证据面。要推进只有两条：审计确认后再清根，或 owner 决定把上限调到覆盖真实状态并同步相应句子
  级别仍是 E2：这一批改的是"信封自己说的是不是真的"，不是产物好不好；宿主 E3、真人 E4、release、
  安装态分发、ComfyUI / MiniMax H3 与 `currentExecution` 34 项继续冻结，手机端仍是排除项。
  ②规范登记件的第三轮取证已于同日跑完（见审计件 §5.22）：Apple 与 Fluent 各补到一条服务端可读的面，
  但**这一轮推翻的是本件自己上一轮的读数**——`.../tutorials/data/design/human-interface-guidelines.json`
  本轮直连 **200**（给 `schemaVersion 0.3.0` 与版权年，仍无编辑日期），而上一轮登记为"全族 404"；
  两轮读数都留着，不删旧、不粉饰。仍未结的是两条 C 档：**PDF/UA-1 版次**（ISO/PDF Association 403、NEN 503、
  Beuth→DIN 404、EAN/TBS 与 Wayback 连接失败、BSI 404，只有第三方索引捕获到 Edition 2 / 2014-12 / 17 页，
  按捕获登记不升级为已核验）与 **IEC 61966-2-1 出版记录**（`/publication/2960` 实测是 IEC 60695-4 防火测试，
  编号不可猜；检索与预览面 404/连接失败）。这些是重跑取数，不是判据变更，也不需 owner 批准；
  带版次的符合性断言在取证到位前仍不得写。
  ③真正卡住的只剩 owner 面：合格后端（`QUALIFIED_LOCAL=0`，磁盘上那条 Qwen2.5-VL-7B 是否列为合格是许可裁定）、
  `DESIGN.md` 批准与配色归属（挂起，非前提）、以及 E3/E4/E5 与 34 项 `FROZEN_DEFERRED`。
  代理不得替 owner 填任何一项，也不得把②以外的剩余面当缺口重复派工。

## 7. 只能由 owner 决定的（不要猜，也不要替他填）

- **E3 真实宿主**、**E4 独立人审**、**E5 发布/安装态分发**：均未执行，需明确授权。
- **手机端**：**已从范围移除**（owner 2026-10-19：「再说一遍 不做手机端 只做桌面端」→「授权给你 去掉手机端」）。AUTHORITY.md / AGENTS.md / PRODUCT_DEFINITION / authority-index 的现行条款都已把它从「冻结待排」改为「排除」：不派工、不开路由、不加组件、不做验收、不记为能力缺口或未交付项；恢复需 owner 新的明确授权。机器面留一处说明：账本 `currentExecution.mobile` 由 schema 以 `const: FROZEN_DEFERRED` 钉住、并被 `design-lab/tests/test_current_execution.py` 断言，改这个词属于 schema+测试+UI 状态词的合同变更，不在本次授权内；该值本身的含义就是「手机工作零派工」。桌面端响应式/自适应是交付质量的一部分，不等于手机端，其既有闸门保持不动。
- **解冻 34 项 `FROZEN_DEFERRED` 任务**：需要新的 owner 明确授权；不得自行恢复派工。owner 2026-10-20 放行的是**三段产品实施**（提示词入口、导出出口、模型选择接口），不是账本任务解冻——`currentExecution` 34 项一项未动，`scripts/verify_documented_counts.py` 实测并在四处句子同时看守。
- **已从范围移出，不要再当缺口登记**：字体库与第三方素材的权利判定（owner 2026-10-20：「三方素材和字库不在本项目范围内」）。保留的只是既有数据边界：不默认上传客户素材、不持有用户素材库、E 盘受保护。`DESIGN.md` 的批准、字面配色的逐条归属（存量以 `scripts/design_debt_baseline.py --check` 与
`design-lab/config/ui-off-palette-colours.json` 实测为准，本文件不复述数字）、品牌 `#316CFF` 能否承载白字——owner 原话「我现在看不见」，属**挂起项而非开工前提**，不要为它们反复请示；本轮按「设计规范按照网上最专业的先收入库里」把业界规范作为参考素材入库，落地验收由 owner 自行测试。
- **"保留标准通用的接入接口"具体保留到哪一层（2026-10-19 逐层实测，别把"有合同"读成"能接入"）**：
  官方 API/SDK 层有代码（`adapters/photoshop_com.py`、`adapters/illustrator_com.py`、`adapters/spi.py`、`interop/penpot.py`、`generators/comfy_*.py`），等级以 E0/E1 为主，ComfyUI 的 E2/E3 证据是 2026-08 的、未在当前树复验；
  原生插件层有注册表与清单（`integrations/adapter-registry.json` 41 条（2026-10-28 由 30 增至 41：投递包 11 个连接器登记（10 行 `declared`，Blender 行 `missing`——本仓大工具守卫不允许它读成可用），闸门 `ADAPTER_REGISTRY=PASS`；每一行都写明 DESIGN-LAB 未探测、未启用、未调用任何工具，`adapter-delivery-*` 是这批行的前缀），`integrations/hosts|generators/*/adapter.manifest.json`），闸门 `ADAPTER_REGISTRY=PASS`、`ADAPTER_MATRIX=PASS matrix=9`、`ADAPTER_LOCATOR_AUDIT=PASS`；
  脚本/CLI 层有 24 个子命令（`src/design_lab/cli.py` 的 `add_parser` 实数）；
  **MCP 层只有合同没有服务**——`schemas/contracts/design-control-mcp.schema.json` 与 contract-bindings 那一行在，但 `docs/audits/INERT-CONTRACT-SURVEY-2026-10-08.md` 记它 `state=NO_STATE_COUNTERPART`、`route_references=[]`、`table_readers=[]`、`table_writers=[]`；
  **受控 UI 自动化层在 `src/` 内没有任何模块**（`ui_automation|controlled.ui|accessibility tree|屏幕坐标` 全 0 命中），它只作为策略分层出现在本文件 §上一行。
  所以：owner 要的"标准通用接入接口"在**合同与注册表层是保留的**，MCP 与受控 UI 自动化两层是**已声明未实现**；把后两层做出来属产品实施，在 `currentExecution` 冻结之内，需 owner 授权才动。
- **ComfyUI/H3、外部服务、跨仓库写入、数据外发、E 盘访问**：全部冻结/需授权。**AAOS 不在此列**——owner 2026-10-19：「AAOS 不要管，保留标准通用的接入接口等，本项目按照独立能运行的能全链路跑通的项目」。保留 `schemas/candidate-knowledge.schema.json`、`knowledge-role-classification.json`、`verify_knowledge_lifecycle.py` 这些版本化合同与出口，但不得再把 AAOS 联调当作本项目的前置条件或完成判据。
- **D09 GitHub 必需检查**：需另外授权；先加稳定、绑定实际 SHA 的汇总检查，验证"required + 条件 skip"
  确实会失败，再设为必需。

## 8. 每批的强制序列（按 owner 的效率约束：只跑最小定向闸）

```
改动 → 只复跑相关闸与测试（不跑全量套件，除非 owner 显式授权）
      → 动过账本/被钉文件/索引时：deepseek_authority_chain.py + generate_current_reports.py
      → 动过 Record 导入清单绑定的跟踪文件时：declare_record_evolution.py <路径> --why "…"
      → 提交 → 推工作分支 + 快进 main → 读该 SHA 的 CI 逐作业照抄 → 才允许说"完成"
```

**Record 那一步不是可选项**：清单里有 479 行按 CRC/大小绑定仓库内的跟踪文件（含 `docs/LOCAL_ENVIRONMENT.md`、
`docs/architecture/BOUNDARY_CONTRACT.md` 这类看着像"随便改改"的文档），改一个就红三条
`test_record_import_fidelity`。改前先 `python scripts/record_import_verify.py --head` 看这一行动没动；
红了用 `declare_record_evolution.py` 走登记机制，别改断言。2026-10-19 这一轮就两次踩它：
先是 `BOUNDARY_CONTRACT.md`，后是 `LOCAL_ENVIRONMENT.md`——两次都不是内容缺陷，是清单没跟上。

**"相关闸"这个词两轮都把我带偏了，按下面这句理解**：它不止指给我这次改动打分的那些闸，还包括
**我这次改动会扰动的全仓不变量**。2026-10-28 两条 CI 红同源于此——上一轮漏了驱动被我改动的共享函数的
vm 合同套件，这一轮漏了审计闸门可达性的 `test_gate_reachability`（新写一个带 `--check` 的闸必须同刀
给它一个 CI 步骤，加豁免等于谎报"这闸不可要求"）。代价最小的兜底是把 CI 那几步便宜的检查原样跑一遍，
每条都是现读过的命令与读数：
`python scripts/run_structure_contracts.py`（现读 `modules=3 tests=31`，它按名字枚举
`test_workbench_css_single_definition`、`test_workbench_stage_nav_reachability`、
`test_gate_reachability`——注意它**不含** `test_path_ref_gate`，所以那条要单独跑
`python scripts/verify_path_refs.py`）与 `python scripts/verify_documented_counts.py`。
这四条不能替代全量套件，只是不让"少跑了一个模块"再变成一次云上红。

**本地结论永远不是 CI 结论。** 读 CI 时按作业读，不要只看总结论。
上一轮 owner 明确要求：不要无限跑各类全量测试和大型闸门；需要显式授权时先申请。

## 9. 工具事实（省得再踩）

- **登记册的重钉必须是"文档定稿之后的另一个提交"**（2026-10-24 自己踩过一次）。`scripts/generate_archive_record_register.py` 钉的是 **HEAD 里那份 blob**，不是工作区那一份；把 §5.42 的追加和重钉塞进同一个提交，本地 `RECORD_REGISTER_GATE=PASS`（两边都读旧 blob，自洽），CI 却按新 blob 复算，判 `blob SHA-1 claim … vs …`、`bytes claim 238,875 vs 241,745` 五条 PROBLEM。正确顺序永远是：提交文档 → 重跑生成器 → 另一个提交只带登记册。本地绿的那句"PASS"在当时也是真的，只是它说的是上一个提交——这也是为什么 CI 的逐作业读数不能被本地并集替掉。
- **回执里的 `artifact_path` 一律仓库相对 POSIX 斜杠**（2026-10-25 一晚踩两次）。`str(Path(...))` 在 Windows 上给的是 `design-lab\evidence\…`，`scripts/generate_current_reports.py` 与 `verify_current_execution.py` 都以 `expected a public repository-relative POSIX path` 拒它。写账本前把 `str(path)` 换成 `path.resolve().relative_to(REPO).as_posix()`，并在提交前跑一次投影生成器当探测——它比"aggregate 也红、两条红我还得分别归因"便宜得多。


- **本机 `.venv` 里没有 pytest，但装得上**：
  `uv run --python .venv/Scripts/python.exe --with pytest --no-sync -m pytest <files> -q`。
  这条取代早前"本机没有 pytest，只能用 unittest"的记录（2026-10-19 实测：单文件与 21 项子集都能跑）。
  跑整个 `design-lab/tests` 目录时 capture 阶段会在某个关掉 stdout 的用例上崩掉
  （`ValueError: I/O operation on closed file`，此时 `no tests ran`）——那是本地工装缺陷，不是产品红；
  要么只跑定向子集，要么交给 CI。
- **`Path.write_text` 在 Windows 会把 `\n` 写成 `\r\n`**。本轮补丁脚本因此把三个 `binary` 属性的钉死文件
  （AUTHORITY.md、authority-index.json、HISTORY-FREEZE-RULES.md）和 `cr-at-eol` 子树里的登记表悄悄改成 CRLF，
  而钉死文件不做行尾归一，改动直接进 blob——哈希还跟着更新了，所以门全绿也没发现。
  改这类文件必须 `read_bytes` / `write_bytes` 并按原像形状回落；改完用
  `git diff --numstat` 看行数是否与预期一致，再核 blob 与原像的行尾。
- **新入库的 `scripts/verify_*.py` 本身就是 CI 面改动**：`design-lab/tests/test_gate_reachability.py` 的
  `test_every_orphaned_gate_is_exempted_with_a_reason` 会把「没有任何 workflow、也没有任何测试点名」的
  校验脚本判为孤儿闸并失败——本轮就因此让 `66fdade1` 的 Python 作业变红：
  `STRUCTURE_CONTRACTS=FAIL tests=31 failures=1`，offender 就是刚加的登记校验器。
  合同给的两条正当出口只有：接进 `.github/workflows/canonical-verify.yml`（本轮接在 
  `top-authority-gate` 第 5 步），或按既有豁免面写明理由。所以加闸时必须同一次跑 
  `python scripts/run_structure_contracts.py`（31 项）再谈提交——它不在我原先认定的『小闸门』集合里，
  本地因此一点征兆都没有。改 workflow 后还要 YAML 解析复核与 `named steps` 重名检查。
- **指引面点名已删文件会双门齐红**：`verify_path_refs` 与 `verify_task_document_states` 的
  `guidance-paths-resolve` 都把 `AUTHORITY.md` 里的 `docs/...` 当指令。写"某文件已删除"时不要留它的路径字面量，
  留汇总面/恢复清单的路径。
- **系统 Python 缺 `jsonschema`**；报告生成器必须用 `.venv/Scripts/python.exe scripts/generate_current_reports.py`。
- **账本身份字段今天换了名字，那条唯一的 drift 没有消失，只是换了内容。** 2026-10-23 之前它钉在
  `DL-TP-20261009-UI-FIRST-R1`（设计如此：定义/证据字节不动，只有状态冻结），`.project/manifest.yaml#taskpack`
  写的是 `DL-TP-20261019-DIRECTION-R1`，两边不一致 → `deepseek_authority_chain.py` 稳定产出**恰好 1 条**
  finding。owner 2026-10-23 把派工段重绑到新包，`currentExecution.taskpack` 现在是
  `DL-TP-20261023-DESKTOP-KB-R1`，而 manifest 仍写 `DL-TP-20261019-DIRECTION-R1`（生成器那句 action 原文是
  「reconcile in DLDS-B040/B010; not silently rewritten by A010」，所以不由这一轮顺手抹平）：
  **条数仍是 1，身份两半都变了**，实测读数
  `recorded=DL-TP-20261019-DIRECTION-R1 / current_authority=DL-TP-20261023-DESKTOP-KB-R1`，
  `AUTHORITY_CHAIN=PASS (classification matches for 146 entries)`。不要把"改 manifest 让 finding 归零"
  当成收尾动作——那要另一条 owner 授权，且必须与 `manifest.yaml` 的其他字段同时读回。
- **新包是 SHA 钉住的**。改它必须走 `docs/history/taskpacks/20261009-adoption/AUTHORITY-PIN-CHANGE.json` 流程：
  追加 revision + 改 `scripts/verify_top_level_authority.py` 的哈希，不要只改文件。
- `guidance-paths-resolve`：`AGENTS.md` / `README.md` / `AUTHORITY.md` / 本文件里出现的每个 `docs/...`
  路径必须是**受跟踪文件**。新文档先 `git add` 再跑闸。交接/审计可以引用死路径（那是记录），指引不可以。
- `entry-not-dated-again`：不许存在 `NEXT-AGENT-PROMPT-<日期>.md`；入口就地改。
- **登记哈希要算 blob，不要算工作树**：本机 `core.autocrlf=true`，同一份 `docs/history/**` 文件
  在提交对象里是 LF、检出后是 CRLF，`sha256sum <文件>` 与 `git cat-file blob HEAD:<路径> | sha256sum`
  必然不同（2026-10-19 实测 `MANIFEST.json` 85,966 B → 87,833 B）。登记件要写清哈希取自提交对象，
  **并写明测于哪个提交**；提交不能含自己的哈希，所以「首次读自」和「重算于」两个读数都要留下。
- **跑测试期间不要在同一工作树上 commit**：本轮 pytest 子集跑到一半时我提交了一个 docs 改动，
  `test_projection_freshness` 立刻 `findings=2 FAIL`；工作树静止后单跑同一条 43.8s PASS，
  `verify_projection_freshness.py` 直跑 `OK findings=0`。中途改树的运行不是判定，别照着它改产品。
- **`git ls-remote --tags` 的字段提取会吃掉 SHA**：`sed 's|.*refs/tags/||'` 连前面的 SHA 一起删，
  比对本地/远端 tag 时会 12/12 全报 MISMATCH。用 `sed 's|\trefs/tags/| |'` 后按 `$2 $1` 输出，
  再 `diff`（本轮这样核过：12 个 tag 名与对象 id 全部一致）。
- **不要在测试文件的注释里写脚本文件名**：`test_gate_reachability` 把"测试模块里出现的脚本名"当作调用点，
  一句注释就能把豁免的手动闸变成"可达"，触发 `no_exemption_has_gone_stale`。用角色称呼。
- **新增/删除 `apps/workbench/` 下文件会让 `verify_inert_contract_survey` 红**（`productFiles` 计数）。
  按该脚本自己的文档：先不带 `--check` 重跑刷新投影，再 `--check`；不要手改 JSON。
- **U09/T16 的在途改动已提交，工作树干净**：`apps/workbench/shell.ts`、`http_service.py`、
  `state_resources.py`、知识候选运行时与 schema/state、测试与构建产物已在 2026-10-19 的
  U09 批次上传（用 `git log` 自读 SHA，不要抄文档），CI 在该 SHA 上全绿。
  **落代码 ≠ 解冻任务**：`currentExecution` 的 34 项仍是 `FROZEN_DEFERRED`；知识候选没有 AAOS
  接收回执，E3/E4 未执行。若工作树再出现未提交改动，仍按保护规则处理。
- 本机沙箱跑不了全量 Python 套件：safe-delete shim 会中途 `SystemExit`，另有 Windows 造不出锁的用例。
  本机聚合闸基线**不是 0**；差别只在 CI 上消除。
- `gh run view <id> --log` 有时返回空；用
  `gh api repos/<owner>/<repo>/actions/jobs/<job_id>/logs --allow-escape-sequences`，
  但日志会被截断，**不要指望它给出失败测试名**——该用本地复现。
- 改工作流先用 `actionlint` 校验；**PyYAML 通过不代表 GitHub 会接受**（重复映射键 PyYAML 静默取最后一个）。

- **桌面端验收宽度是 2048 CSS px，不是 2560**：本机实测 `Screen.Bounds` 2048×1152、`WorkingArea` 2048×1104、`AppliedDPI` 120（2560×1440 面板 125% 缩放）。浏览器拿到的盒子就是 2048 宽，2560 是面板物理宽、用户看不到那个盒子。UI 审计闸门因此扫 `1280,1920,2048`（`audit_workbench_ui.mjs` 的 `HEIGHT` 表配 `2048→1152`），13 个 scope × 3 档 = 39 次量测，本机一趟约 9 秒。高度维度见下面那条（先写错过、后重量过的那一条）。
- **跨轮像素回归没有解释力，除非先冻结 fixture**（本轮实跑证实，不是推定）：23 张 1440 截图与改动前基线比对，品牌块 0 px、导航带每张 48–52 px（其中 4 行 2 px 正是页脚发丝线下移 12 px 的预期变化，其余是导航点同一几何下的亚像素边缘差）、内容带 26 万像素集中在带活数据的屏（`21-records` 一张就 10.6 万，看下去是播种项目名 `Closeout 179…` 与多出一条真实 `RECEIPTED` 作业，版式没动）。两个仪器教训：整页 `getbbox()` 在活数据页上毫无用处（一个十六进制字符就能把框拉到最右），必须按布局带计数；以及**基线没有被覆盖**——按规矩只有 owner 认可实现结果后才能重制。
- **推 `main` 的取消规则是半条，别按半条办事**：`cancel-in-progress` 的条件写作 `github.event_name == 'pull_request'`，所以**正在跑**的 main run 不会被后一次 push 打断（实测 `37bee232` 在跑时推了 `0c0a50c3`，两个各自跑完、各自 11 个真作业 success）；但**还在排队**的那条会——`9a3a3f37` 一个字作业都没跑就被 `2087509d` 顶掉了（`CONC=cancelled jobs=0`）。所以：不必为"怕取消"压批次，但也别以为每个 tip 都会各自出判定——只有队尾那个会。读到 `cancelled` 就当"被取代"，不要当证据。
- **`GET /api/projects/<id>/design-layer` 里没有资产实体**（本轮把链路测试的断言从"子串出现"改成"作为身份字段的值出现"时量出来的）：投影只有 `briefs / directions / chosen_direction / bindings / active_binding / design_systems` 六个键，资产仅通过 `design_layer.briefs[i].reference_asset_ids[j]` 被引用。所以桌面端要显示"这个资产的分析/判定"，要么从简报的引用列表拿 id 再单独读，要么走资产自己的路由——别以为聚合读回里能直接找到资产对象。
- **写进文档的数字现在有闸门了**：`scripts/verify_documented_counts.py` 把契约与提示词里逐条写出的计数对回代码——下面列的是 2026-10-22 那一批的 11 条（条数本身只以它自己输出的 `claims=<n>` 为准，2026-10-23 后端 I 又交进三条设计层分母，同日规划轮 J0 再交两条账本分母（仍冻结 34 与当前派工 16，两条各自播种皆红），闸门自己现数 `claims=20`）：`DESIGN.md` 的"导航 21 项"、CLI 子命令 24、适配器注册表 30、HTTP 路由 66、20 跳验收链、4 跳交付链，剩下五处是同一条账本事实在 `NEXT-AGENT-PROMPT.md`（"34 项父/子任务全部"）、`AUTHORITY.md`、`AGENTS.md`、`docs/current/PRODUCT_DEFINITION.md` 与 20261020 owner 决定件里的逐字复述。测量只读代码、句子只被比对，两边不互相喂数据；任何提取式匹配不到就 `SystemExit`，不会退化成"读到 0 所以没有差异"。它经 `design-lab/tests/test_documented_counts.py` 进 CI（不用改工作流），并且自带播种反证：把 DESIGN.md 那个 21 改成 20，闸门立刻红。今天那两处过期数字（源码注释里的 15、契约里的"11 项 / 587px / ≤720 才溢出"）都是靠人眼撞出来的，这条闸门的作用是让下一处自己红——本句自己就红过两次：一次是 2026-10-21 它写"当前 4 条"并列出 19/16/58 三个对不上代码的数字（闸门看不见，因为那三个数不在它的模板里，是人眼撞出来的）；一次是 2026-10-22 加了两跳之后。**同一批还修了这条闸门自己的一个缺陷**：它在"报告哪句过期"时把模板当正则用，`**{n} 跳验收链**` 以 `**` 开头就是非法模式，于是一次普通的散文过期变成 traceback 而不是 finding；现在先 `re.escape` 再替换占位符，过期必须说得出名字。
- **`generate_current_reports.py --check` 的三种词要分清**：`STALE` 退出 0（绑定输入没动、HEAD 前移了，正常）；`DRIFT` 退出 1（**被绑定的输入本身老化**——跟踪的源码/文档/测试改了都算，必须重生成并重钉）；`PASS` 才是当前字节自洽。本轮 `DRIFT` 出现过两次，两次都是我自己刚提交了绑定输入，不是闸门在找事。

- **溢出闸门的高度维度：这一条我先前写错过，现在的版本是重量过的**。把高度做成可覆盖（`OV_HEIGHT` / `OV_SHORT_HEIGHT`，默认仍是 900/620，CI 不变）之后，在宽度 1440 上按名义高 1100 / 900 / 750 各跑一趟：`navEdge overflow` = **299 / 499 / 649**，`gap` 三趟都是 **12**，而被切的元素在 1100 与 900 是 `nav-group` 分组标签、**到 750 变成 `button` 导航项**。所以列表溢出量**随视口高变化**（`.nav` 的 `clientHeight` 跟着窗口长高）；我上一版写的"clientHeight 由 CSS 定死、几何与高度无关"是错的，错因是把 620 那一趟的 `hiddenPx=779` 当成两趟的共同读数——而当时我只覆盖了名义高度，短档根本没变，两次当然同值。真正与高度无关的只有**发丝线与切割线的间距**（固定 token 边距，620/750/900/1100 四档实测恒为 12）。结论不变但理由换了：CI 不加 1100 档，因为 1100 与 900 切到同一个元素、判同一条不变量，属重复；750 会切到另一个元素，说明现有 900+620 两档也不是摆设。

- **两个闸门里的 "routes" 不是同一个东西，别去"对齐"它们**：`verify_contract_bindings` 报 `routes=64`，数的是 `design-lab/config/contract-bindings.json` 的 route 行（每行带 handler/kind/marker/method/reason/route）；`verify_workbench_route_calls` 报 `routes=64`，数的是 `http_service.ROUTES` 的路由模式。本轮实跑过一条自以为是"对账"的口令：拿 `row['route']` 去比 `pattern`，结果是"60 条声明全部命中服务、同时 58 条服务里 57 条未被声明"——两个结论互不相容，说明字段映射本身就是错的，不是数据有缺口。**这条口令不要再用**；真要查某个路由有没有登记，得先读那个 JSON 自己的 schema 与闸门的读法。
- **本轮在 tip 上重跑过的只读闸门（一次成批，供下一轮对照基线）**：`AUTHORITY_GATES=PASS gates=7`、`VERIFY_CONTRACT_BINDINGS=PASS schemas=32 routes=60 dispatched=60 bound=21 schema_less=39`、`VERIFY_WORKBENCH_ROUTE_CALLS=PASS calls=96 routes=58 matched=47 backend_only=11`、`STRUCTURE_CONTRACTS=PASS tests=31`、`DOCUMENTED_COUNTS=PASS claims=4`、`KNOWLEDGE_LIFECYCLE=PASS findings=0`。

- **2048×1152 这一档已经人工看过，而且我在那里看错过一次**：采集工装补了 `2048:1152` 档（原来会走 `w*0.62` 的兜底，量出一个谁都没有的画幅），重采 23 张后逐张看仪表盘与能力目录。能力目录在宽屏下看着像"表头与单元格逐列错位"（`MIT` 落在 许可 表头左边、`UNRESOLVED` 徽标落在 修订 表头右边）。读构造即被否证：那一屏是**单个 `<table>`**（表头清单是 `apps/workbench/shell.ts` 里的 `TABLE_COLUMNS`，起于 2563 行；每格都是 `el('td', …)`），列宽由整列共享，结构上不可能逐行错位——看到的是目测像素的误差，加上 auto 布局把富余宽度全给最宽列造成的空档。所以 **2048 档没有缺陷**（同档的系统性检查已由 ui_audit 判 13 scope `violations=0`）。教训写下来：宽屏截图里"列不对齐"这种判断，先回去读它是 `table` 还是 `grid`，不要拿肉眼估的 x 坐标下断言。

- **桌面 jury 面板的判定对象有测试了**：面板不自己找版本，它把 `GET /api/projects/<id>/jury` 返回的 `reviewable_versions` 直接灌进版本下拉（`apps/workbench/shell.ts` 的 `juryVerdictForm(projectId, data.reviewable_versions ?? [], reload)`），再对着读回来的 `subject_ref` 提交判定。新增 `test_the_jury_readback_offers_an_imported_asset_version_as_a_verdict_target` 证明：真导入一张图之后，读侧会给出 `version:<该版本>` 且 `artifact_sha256` 等于导入返回的摘要——此前只证明过"拿导入响应里的 version_id 能 POST 判定"，那不等于界面能列出它。

- **无障碍复核（本轮，桌面端）**：能测的都测了——**没有发现可修的缺陷，但补了一条原来没人看的断言**。自动化看不见的部分逐项核过：`outline:none` **0** 处、`:focus-visible` 规则 **10** 条、`prefers-reduced-motion` 在 CSS 与 shell 各有处理（1 / 3 处）、toast 自带 `role="status"`（`apps/workbench/shell.ts:5794`）、状态词按合同在标签自身带 `lang="en"`（7085 行写明为什么不再套一层 `en()`）、表单侧 `<label>` **72** 处对 `aria-label` **44** 处。**新增**：溢出闸门现在逐屏量渲染出的标题序列并断言不得跨级跳（23 条路由读数里 **0** 处跳级；落地路由 `workbench` 的 h1 在 `#route-view` 之外，作为具名例外而不是静默放过），并有一条播种反证证明三条分支都会红——axe 每屏仍拒评 9–71 个节点，标题顺序本来没有任何东西在看。**仍属人工**：真实读屏软件下的措辞与键盘-only 主路径本轮没做，也没假装做过。

- **工具类与组件类的层叠冲突现在有闸门**：`scripts/verify_utility_class_conflicts.py`。来历是同一批里两次静默回归，形状完全一样——把重复内联样式收成 `.spaced-top` / `.grid-stack` 之后，组件类（`.quick-launch{margin-top:0}`、`.row-card{display:flex;gap:12px}`，都定义在工具类之后）按源码顺序开始获胜，元素被挪位；而**四道浏览器闸门全程绿**（它们量溢出/边界/对比度/控件尺寸，不量卡片间距）。正确修法是把意图写成复合选择器（`.row-card.grid-stack{...}`，特异性 0-2-0，与文件顺序无关），不是把工具类挪到文件末尾。闸门读样式表 + `shell.ts` 里字面 `class:` 集合：工具类与同一元素上的组件类共享属性即红，除非有复合规则显式解决；当前 20 个受保护站点干净，测试里删掉那条复合规则必须回红。**给样式做"等价重构"之前先看这条**，也别再把"浏览器闸门绿"当成布局未变的证据。

- **层叠冲突现在有两道闸门，各自都被播种证明会红**：静态的 `scripts/verify_utility_class_conflicts.py` 与浏览器里的 `test_workbench_overflow_gate._assert_utility_geometry`。**两道各有覆盖范围，别拿一道当两道用**：把 `.quick-launch{margin-top:0}` 种回去，静态闸门立刻红（`FAIL shell.ts:877 class="panel quick-launch spaced-top" ...`），而浏览器闸门**没红**——那张卡在测试 fixture 下根本没渲染（`seen: {'spaced-top': 9}`，shell 里有 14 处）；把 `.three-col{margin-top:0}` 种回去，浏览器闸门就红了，报 `.spaced-top expected margin-top:16px but computed 0px alongside .three-col`（在 `1280:dashboard`）。所以：**对这一类 bug，不依赖 fixture 数据的静态闸门才是主承重**，浏览器那道只覆盖渲染出来的站点（每次跑会打 `NOTE ... not rendered under this fixture: [...]` 把盲区说出来，而不是静默通过）。

## 10. 什么算完成

- 改动有**可复核的读数**（命令 + 输出），不是"应该没问题"。
- 闸与测试在**同一份字节**上通过；CI 上按作业读到 success。
- 没建的、没验证的，写在可见文字里（面板、提交信息、验收报告、本文件），不留在暗示里。
- 状态分轴写清：文档 / 规划 / 代码 / 真实运行 / 人工验收 / 外部知识系统接收，各自独立（最后一轴本项目只写候选、只读回执，不据其判定本项目是否闭环）。
- 回退路径写明（按批 revert / 按文件 revert），冻结件与账本历史不被改写。

> 上一轮三次 CI 红，全部是**闸对了、人错了**：债务被结清却说没结、登记行被删但钉子没动、
> 一句注释冒充调用点。下次红的时候，先假设闸是对的。
>
> 2026-10-18 补：**审计也会错，而且错法有规律**——用 grep 计数代替权威文档、用"没人引用"
> 代替"明文冻结"。所以"完成"还要求：**结论的来源写清楚**（命令 / 权威文档哪一节 / 闸的哪一条），
> 让下一轮能复算，而不是只能选择相信。
