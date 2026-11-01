# AUTHORITY-INDEX — 2026-10 任务 / 规划 / 权威索引（历史权威快照）

## 这份清单是什么，不是什么

WORK-LAB 与 DESIGN-LAB 合并成 AI-WORK-LAB 之前，两个来源仓各自维护着一套"任务、规划、权威索
引"。owner 2026-11-01 的要求是把这些东西里 **2026 年 10 月当时现行的那一份**挑出来、置顶到融合
仓顶层，让新打开仓库的人一眼看见"10 月当时现行的任务/规划/权威索引在哪、是什么、还管不管用"，
不用再去散落的归档目录里猜。

下表点名的原件逐字节放在 `docs/authority-202610/`。它们的定性口径是：

- **这些是 2026-10 当时两个来源项目各自的现行权威**，各自只在**自己那个来源仓**里成立；
  其中若干份文件自称为"CURRENT""TOP_LEVEL_CURRENT""唯一 integrated TaskPack""唯一活账本"，
  那是**当时那个仓**的自我描述，不是对本仓的声明。
- **融合后它们作为历史权威快照保留**。本仓的"现在成立什么、还差什么、下一步"只由
  `PROJECT_CURRENT.md` 回答；`AGENTS.md` §0 已明确警告来源仓 `agents.md` 里的派工与冻结口径
  不在本仓生效。
- 因此本表**不构成状态来源，也不构成开工依据**。旧独立项目里的限制（任务冻结范围、
  Human Gate 清单、能力枚举、派工编号）与融合后的新要求**不得并列生效**；要用它们，先回
  `PROJECT_CURRENT.md` 与 `INTEGRATION_POLICY.md` 确认该约束是否已被取代。
- 来源仓 `D:\All projects\WORK-LAB`、`D:\All projects\DESIGN-LAB` 全程只读；本目录里的字节是
  从来源仓原样复制（`read_bytes`/`write_bytes`，无行尾转换）。**SHA-256 与字节是对复制后的
  目标文件现算的**，不是从来源仓任何登记表搬来的。逐条实测与对账脚本见
  `.project-local/edits-20261101/authority202610_pin_and_hash.py`（生成
  `authority202610-manifest.json`）。
- "版本或日期"一列一律取**文件自身正文里的 ID / 修订号 / 日期节**，不取文件系统时间。23 行全部
  有正文日期可依；只有一处正文与文件系统时间打架——`design--NEXT-AGENT-PROMPT.md`
  （正文 `updatedAt` 10-28，落地时间 10-29），按正文记并把矛盾写在同一行。

主题、原件数量：**23 条置顶文件**（DESIGN-LAB 12 条 + WORK-LAB 11 条），字节合计
**2,116,859 B**。候选扫描量与收敛过程见文末"筛选口径"。

## 置顶清单

| 主题 | 置顶文件（仓内路径） | 来源仓 / 原路径 | 版本或日期 | SHA-256 | 字节 | 现在的定性 | 替代关系 / 适用范围 |
|---|---|---|---|---|---|---|---|
| 顶层权威（人读） | `docs/authority-202610/design--AUTHORITY.md` | DESIGN-LAB / `AUTHORITY.md` | `DL-AUTHORITY-2026-09-18-R2`；末条修订 `AUTOMATION-20261028-R1`（2026-10-28） | `2bec69fcc77939d82476ab12d5316c439469c4e7c53ceef0270fcd8ffa139fce` | 34,942 | 来源仓当时顶层权威（自标 `TOP_LEVEL_CURRENT`）；本仓仅历史快照 | 稳定 ID 不变、按日期段追加。10-28 条优先于 10-23／10-20／10-19／10-09 的**冲突**条款，其余条款当时继续有效 |
| 顶层机器权威索引 | `docs/authority-202610/design--authority-index.json` | DESIGN-LAB / `.project/governance/authority-index.json` | `design-lab/authority-index/v2`；含 `automationAdoption`（2026-10-28） | `7ffe85d1f4043c10940f889a84c9cebc30b36597b044da7f0cc95bc2a5c5051b` | 13,201 | 同上（机器面） | 与上一行同批修订；`desktopKbAdoption.stillFrozen` 里的 `EXTERNAL_SOFTWARE_AUTOMATION` 一项已被 10-28 条取代 |
| 项目级执行规则 | `docs/authority-202610/design--AGENTS.md` | DESIGN-LAB / `AGENTS.md` | 正文最新日期节 2026-10-28 | `0302156c0f03e6075d9e58e62c20361b87f44ed603569ae92fca5726fd1a8e42` | 22,147 | 来源仓当时的根执行规则 | 其中的派工清单、冻结面、Human Gate 只对来源仓成立，**不延伸到本仓**（本仓 `AGENTS.md` §0） |
| 派工入口（integrated TaskPack） | `docs/authority-202610/design--DESIGN-LAB-DESKTOP-KB-INTEGRATED-TASKPACK-2026-10-23.md` | DESIGN-LAB / `docs/taskpacks/DESIGN-LAB-DESKTOP-KB-INTEGRATED-TASKPACK-2026-10-23.md` | `DL-TP-20261023-DESKTOP-KB-R1` | `ed7d4dbd8bb38dd543318dca20701da0c64e7f5743356b217de478f65f80be5c` | 15,653 | 来源仓当时唯一派工入口 | 取代 `DL-TP-20261019-DIRECTION-R1`（降为 SUPERSEDED／LINEAGE，原字节未动）。10-28 owner 决定**没有**换派工入口，只把外部软件自动化移出冻结清单 |
| owner 决定沿革（最新一条逐字转录） | `docs/authority-202610/design--OWNER-DECISION-2026-10-28.md` | DESIGN-LAB / `docs/taskpacks/20261028-automation/OWNER-DECISION-2026-10-28.md` | `DL-OWNER-DECISION-20261028-AUTOMATION-R1`，状态 `ADOPTED` | `43f58a5c056b84bb6d1470bdbe62326a7e63b37254842c8554a840f87335e892` | 7,831 | 来源仓当时最新一条决定 | 只取代 10-23 的冲突条款。10-19／10-20／10-23 三份决定原件**未置顶**（属沿革件，非索引/派工面），仍在来源仓 `docs/taskpacks/` 各自目录 |
| 任务定义原件（账本按 sha256 钉住） | `docs/authority-202610/design--TASK-DEFINITIONS.json` | DESIGN-LAB / `docs/history/taskpacks/20261023-adoption/TASK-DEFINITIONS.json` | `version: "1"`；采纳 2026-10-23；台账 `currentExecution.source.sha256` 与本文件实测摘要**逐字符一致** | `e54f55f3246263926f45eef70bfbc0d6839301b680235c4e37cab8e0e70176ed` | 89,864 | 来源仓当时冻结定义原件 | 取代 `20261009-adoption/` 同名件（文件内 `carried_from` 点名）。定义逐字节冻结，状态只写在台账，不写在这里 |
| 可变任务台账（状态真值） | `docs/authority-202610/design--task-ledger-r3.json` | DESIGN-LAB / `design-lab/config/task-ledger-r3.json` | `design-lab/task-ledger/r5-v1`；信封 `updated_at` 2026-10-24T00:57:00Z；`currentExecution.evidence` 最新戳 2026-10-28 | `abcba5144ebe49fe27686a760cd3c75668a55d7b820d69b568095e9fd5370a7f` | 890,853 | 来源仓当时的可变状态源 | `currentExecution.tasks` 实测 50 项 = 34 项 `FROZEN_DEFERRED` + 16 项 `DL-KB-*`，两个数字不可互换；`tasks/evidence` 为冻结 R5 证据区 |
| 任务文档定态登记 | `docs/authority-202610/design--task-document-states.json` | DESIGN-LAB / `design-lab/config/task-document-states.json` | `design-lab/task-document-states/v1`；正文最新日期 2026-10-28 | `753cbe75585a34a8b59f4d5b38491d50596424ddeaf0b1a675b277f68cb9f704` | 25,045 | 来源仓当时定态登记 | 约定"恰好一个 `DISPATCH_ENTRY`"指向上面的 taskpack，由 `verify_task_document_states.py` 现数，不靠人肉维护 |
| 路线图（规划面） | `docs/authority-202610/design--ROADMAP.md` | DESIGN-LAB / `docs/current/ROADMAP.md` | 版本 `1.3`，状态 `ACTIVE`，U 段落 2026-10-23 | `fb8f5c4e81ca41689ef8be078faccaa4881a98e2fad41ae4ad89c3109b6cff90` | 12,257 | 来源仓当时规划面 | 自述"是派工项的阅读面，不是第二套账本"，真值仍指台账。文内多处数字明写"本轮没有重测" |
| 产品定义（规划面） | `docs/authority-202610/design--PRODUCT_DEFINITION.md` | DESIGN-LAB / `docs/current/PRODUCT_DEFINITION.md` | 正文最新日期 2026-10-28 | `2e25d22c331c497e257807b11908c87faedd6b69bda0a16a787cc863192a4a96` | 16,427 | 来源仓当时定义面 | 10-28 决定的 `impact` 点名同步本文件，故随权威列入；定位与范围裁定仍以权威与 taskpack 为准 |
| 续接入口（下一会话提示词） | `docs/authority-202610/design--NEXT-AGENT-PROMPT.md` | DESIGN-LAB / `docs/current/NEXT-AGENT-PROMPT.md` | 正文 `updatedAt` 2026-10-28（文件落地时间 2026-10-29，两处不一致，**未核实孰是孰非**） | `2aca3c5da7d0be1ccfc461cf14430410d8b4f96d43f0e56e20d23deec0f293ea` | 247,725 | 来源仓当时续接件 | 该文件自己声明"就地更新，不是独立 Authority"；历史条目在来源仓 `docs/history/next-agent-prompts/` |
| 资料归档索引 | `docs/authority-202610/design--RECORD-ARCHIVE-INDEX.md` | DESIGN-LAB / `docs/RECORD-ARCHIVE-INDEX.md` | 正文最新日期节 2026-10-28 | `d53fed8d9f2f27a658f104579d106388f885a4e9bcf6d187d6f446fe108b521c` | 84,012 | 来源仓当时资料入口 | 自述"非 Authority、非第二任务状态账本"。**已知内部矛盾未修改**：开头一句仍写"当前派工仍为 20261009 桌面 UI 优先统一包"，与其 10-23／10-28 日期节冲突 |
| 顶层权威（人读） | `docs/authority-202610/work--WORK-LAB-AUTHORITY.md` | WORK-LAB / `WORK-LAB-AUTHORITY.md` | `WORK-LAB-AUTHORITY-20261019-CONVERGENCE` | `c159ca8828f9cceb48b24f3f16efd9deea74ccec0fe1d9ebf2b846fcd4a03c88` | 11,301 | 来源仓当时顶层权威（`TOP / NORMATIVE`） | 10-19 收敛后未再出新的 Authority ID。§1 规定八步审计读序与优先级：最新明确用户决定 > 本文件 > 机器索引 > CURRENT／OPEN > AGENTS > 代码/CI/读回 > 冻结历史 |
| 顶层机器权威索引 | `docs/authority-202610/work--project-authority-index.json` | WORK-LAB / `.project/governance/project-authority-index.json` | `work-lab/project-authority-index/v1`；`convergenceBaseline.date` 2026-10-19 | `25845d5f23f05c4d60651a6b749711c094298d8b1e56209ac9e6d459d859b3bb` | 5,387 | 来源仓当时机器权威 | 字段直接点名 `currentTaskpack` 与 `currentOpenTaskRegister`，即下面两行 |
| 作用域任务权威索引 | `docs/authority-202610/work--taskpack-authority-index.json` | WORK-LAB / `.project/governance/taskpack-authority-index.json` | `workflow/taskpack-authority-index/v1`；`generatedAt` 2026-10-19 | `69b8f3bda081ad5b51c33276dd464aee0e03227607572d7a63f9b00fc56b3d5a` | 18,556 | 来源仓当时任务包索引 | `supersedes` = `WORK-LAB-UI-PRIORITY-TASKPACK-20261009`；有效期自述"只被更新的已注册 CURRENT 取代"，10 月内没有再注册新的 CURRENT |
| 项目级执行规则 | `docs/authority-202610/work--AGENTS.md` | WORK-LAB / `AGENTS.md` | 正文引用最新为 2026-10-24（含 `OPENVIKING_..._20261024`） | `68496fbf1d75ff972a757ca58ee47cd853ae060bf4d05726bd289e27c7af276c` | 13,567 | 来源仓当时的根执行规则 | 同目录 `AGENTS.md.bak-20261024` 是它的前身，**未置顶**。手机端在来源仓是"不做"，本仓不继承该口径 |
| CURRENT 任务包（派工入口） | `docs/authority-202610/work--WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md` | WORK-LAB / `taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md` | 自标 `Status: CURRENT / MINIMAL_LOOP_DELIVERED`（2026-10-19） | `5a6311e44a595b48c6778811b8835e5a0a9da216b30d1929bc76b01500a3f28a` | 46,698 | 来源仓当时唯一派工入口 | 取代 20261009 UI 优先包（`SUPERSEDED_20261019`）。除该收敛任务外其他任务当时一律冻结、不派工 |
| 派工入口说明 | `docs/authority-202610/work--taskpacks-current-README.md` | WORK-LAB / `taskpacks/current/README.md` | 2026-10-19 | `aa30c1ae38237f48ad89807d6403f104ca090c1cd0c509c5da94f7e04bb834f9` | 1,250 | 来源仓当时指向件 | 一句话点出唯一 CURRENT、唯一活账本、收敛报告位置；并声明"冻结不等于关闭""`error-ledger.json` 未清零" |
| 活任务账本（状态真值） | `docs/authority-202610/work--OPEN-TASK-REGISTER.md` | WORK-LAB / `taskpacks/current/OPEN-TASK-REGISTER.md` | 正文最新状态戳 2026-10-29（`WUI-03 PARTIAL_20261029`） | `13a0db533678f59cca7476ffdf702d11c26890e0d8a5cd5c3ec347e6bb90feee` | 447,288 | 来源仓当时的活账本 | 自述"不建第二份任务真相；派生 JSON/CSV 不是第二运行账本"。同目录 `error-ledger.json`（1.16 MB）是运行错误证据，属运行产物，**未置顶** |
| 路线图（规划面） | `docs/authority-202610/work--ROADMAP.md` | WORK-LAB / `docs/current/authority-convergence-20261019/ROADMAP.md` | 2026-10-19 建立；含 2026-10-23 Task Grant（登记号 `WL-REC-0107`），逐行标注复测日期 | `9b220a0e9821c446e148ea289627b816649e1b5c9db9786b62e4eca5d7c8a21b` | 17,333 | 来源仓当时规划面 | 自述"不是第二 Authority，也不是第二任务账本"；CURRENT／NEXT／FROZEN／DEFERRED／RETIRED 的解冻门槛写在自己正文里 |
| 文档与任务总索引 | `docs/authority-202610/work--DOCUMENT-CENSUS.md` | WORK-LAB / `docs/current/DOCUMENT-CENSUS.md` | 2026-10-19 增量说明；正文引用最新 2026-10-24 | `f9dd5e7b41d3bde57fefa132673f8a4896ccf99ee8142811c8156e5dd24e5552` | 58,927 | 来源仓当时的文档／任务总索引 | 明写"以下 2026-10-09／10-18 各行是当时快照"。数字不维护，现行任务以活账本与两个治理索引为准 |
| 作用域权威导航索引 | `docs/authority-202610/work--active-authority-index.md` | WORK-LAB / `docs/current/workflow-assistance/workflow/active-authority-index.md` | 2026-10-19 第四次修正；正文引用最新 2026-10-24 | `3936387874c8563129bce57d3bf3f5a4fca82257f360add3e0f44232f005efaa` | 10,268 | 来源仓当时模块级导航件 | 自己标 `NON-AUTHORITY VIEW`：与 `WORK-LAB-AUTHORITY.md`、`project-authority-index.json` 冲突时以上述两份为准 |
| 资料归档索引 | `docs/authority-202610/work--owner-inputs-INDEX.md` | WORK-LAB / `docs/history/owner-inputs/INDEX.md` | 正文最新日期 2026-10-24 | `029bda95993e25a9aa249f76da46afc0d1db593b3bf6da87e2880422877500c8` | 26,327 | 来源仓当时的资料定位入口 | 与 DESIGN 的 `RECORD-ARCHIVE-INDEX.md` 同主题、两仓各一份，分别只管自己仓的素材。自述"历史资料只作来源，不激活旧任务、AGENTS 或 Authority" |

## 筛选口径（怎么从 7108 行收敛到 23 条）

1. 先用 `migration/source-coverage-work.csv` + `source-coverage-design.csv` 逐行读（共 7,108 行），
   排除缓存／构建／锁文件／位图／压缩包／`.project-local`／运行库，再用"权威·任务·规划·索引"
   词族筛出 **719 个候选**（DESIGN 443 + WORK 276，含 DESIGN `docs/history/**` 224 条、
   WORK `taskpacks/history/**` 104 条归档件）。扫描器与逐行清单见
   `.project-local/edits-20261101/authority202610_scan_candidates.py` → `authority202610_candidates.txt`。
2. 按主题收敛：同一主题的多个日期/版本只留 10 月当时现行那一份；被现行权威**引用的**具体任务卡
   原文（`docs/taskpacks/2026*/TASK-CARDS.md`、`source/` 投递成员、`docs/history/**` 归档原件）
   归 owner 说的"其他内容"，本轮不收。

## 明确没有收的东西，以及原因

| 项 | 为什么没收 |
|---|---|
| DESIGN `docs/INDEX.md`（仓库目录分类与归档索引，2026-10-19） | 自称数字来自 `scripts/classify_repo.py` 派生的 `reports/current/REPO-CLASSIFICATION.json`，属生成物族，只留了分类规则说明 |
| DESIGN `design-lab/config/CAPABILITY_INDEX.md`（2026-09-04）与 `capability-index.json`（2026-09-04） | 日期在 9 月且自述"Generated from `product-manifest.json`"；10 月那份能力索引**不存在**，其 10 月源是 `design-lab/config/product-manifest.json`（正文观察 2026-10-19），属能力清单而非任务/权威索引，未收 |
| WORK `config/capability-matrix.json` | 自标 `generated_at` 2026-08-15，文件系统时间却是 10-25，无法判定 10 月是否重新核准过；生成物 + 日期不可靠 |
| WORK `.project/governance/config-authority-index.json` | `generated_at` 2026-08-13，早于 10-19 收敛链，非"10 月最新" |
| DESIGN `design-lab/config/current-report-index.json`、`design-lab/config/record-archive-crosswave.json`、`reports/current/*.json`（含 `CAPABILITY_INDEX.json`、`DEEPSEEK-AUTHORITY-CHAIN.json`）、WORK `.project/governance/generated/CURRENT_STATE.{json,md}` | 全部由 `generate_current_reports.py` 一类脚本现算，属生成物，owner 明确"缓存和构建不要" |
| DESIGN `design-lab/config/task-ledger.yaml`（2026-09-18） | 9 月的旧信封 stub，早于 10 月 |
| `design-lab/schemas/task-ledger-r3.schema.json` / `task-ledger-r5-v1.schema.json` / `capability-index.schema.json`、WORK `packages/contracts/schemas/workflow/task-ledger.schema.json` | 是合同 schema，不是索引也不是派工面 |
| DESIGN `docs/taskpacks/DESIGN-LAB-DIRECTION-ALIGNMENT-2026-10-19.md`、`DESIGN-LAB-UI-FIRST-INTEGRATED-TASKPACK-2026-10-09.md`、`docs/taskpacks/{20261019-direction,20261020-unfreeze,20261023-ui-kb}/**` | 前两者是已被取代的派工入口（10-19／10-09），不列成现行；`2026*` 三个目录里除 OWNER-DECISION 外是投递包、`SOURCE-MANIFEST.json` 与 `source/` 原件。**owner 决定只置顶最新一条（10-28）**，10-19／10-20／10-23 三份逐字转录按"其他内容归历史归档"处理，路径已写在上面 owner 那一行 |
| WORK `docs/current/authority-convergence-20261019/AUTHORITY-CONVERGENCE-20261019.md`（176 KB） | 是收敛**报告**，不是索引也不是派工入口；它的权威链已被上面四行覆盖。**这条是猜的**：文件里没有任何字段说自己是报告还是权威面，"报告/索引"的分界是我按正文体裁定的，缺的是一条明文的可收/不可收规则——要收就多一行，不影响其余 22 条 |
| `SOURCE-MANIFEST.json` / `ARCHIVE-MANIFEST.json` / `AUTHORITY-PIN-CHANGE.json` / `PROMPT-LINEAGE.json` / `OLD-TASK-CROSSWALK.json` | 来源与摘要登记、取代关系登记，属沿革件；本表已在"替代关系"列直接给结论 |

## 判定"10 月最新"用的依据（逐类）

| 主题 | 依据强度 | 实际用的证据 |
|---|---|---|
| 顶层权威（两仓） | 强 | 文件内 Authority ID + 追加日期段的最后一条；DESIGN 的 ID 是 9-18 但正文有 10-28 修订，故取"同一文件的最新修订"而不是文件日期 |
| 派工入口（两仓） | 强 | DESIGN：`task-ledger-r3.json` 的 `currentExecution.taskpack` 与 `plan_path` 逐字指向 10-23 包，`taskpack-authority` 索引同向。WORK：`project-authority-index.json` 的 `currentTaskpack` 字段 + `taskpacks/current/README.md` + `AGENTS.md` + `DOCUMENT-CENSUS.md` 四处独立点名同一份 |
| 任务定义原件 | 最强（可伪证） | 台账 `currentExecution.source.sha256` = `e54f55f3…0176ed`，与本目录复制件实测摘要逐字符相同；旧的 `20261009-adoption` 同名件由新件里的 `carried_from` 点名取代 |
| 活账本／定态登记 | 强 | 两仓权威正文各自点名唯一可变状态文件路径（DESIGN `task-ledger-r3.json`；WORK `OPEN-TASK-REGISTER.md`），不靠 mtime |
| 路线图／定义面／资料索引 | 中 | 文件内版本或日期节（DESIGN ROADMAP `1.3`／U 段 10-23；WORK ROADMAP 收敛日期 + 10-23 Task Grant） |
| 续接入口 | 中，且**有矛盾** | DESIGN 正文 `updatedAt` 2026-10-28，文件系统时间是 10-29；WORK 侧**没有**对应的现行文件——10-19 已把 52 份 HANDOFF／NEXT-AGENT-PROMPT 类文件汇总成 `docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip` 并 `git rm`，WORK 的续接面就是它的活账本本身。这一条是"WORK 无此主题"，不是"WORK 有一份我没挑出来" |
| 能力索引 | **未能判定** | 见上一节：DESIGN 只有 9-04 生成物，WORK 自称 8-15 生成但 10-25 落盘。缺的是"最后一次再生的时间戳"这一自证，两仓文件里都没有；不拿 mtime 冒充权威日期 |

## 怀疑但没动的东西（只登记，不改字节）

1. `design--RECORD-ARCHIVE-INDEX.md` 第 3 行仍写"当前派工仍为 20261009 桌面 UI 优先统一包"，与同
   文件的 10-23／10-28 日期节直接冲突。它自己又声明"非 Authority"。按冻结原件处理，未改。
2. `design--task-ledger-r3.json` 的信封 `updated_at` 停在 2026-10-24T00:57:00Z，但
   `currentExecution.evidence` 里有 4 条 `-20261028` 戳（含 automation 相关）。字段没跟着写更新，
   所以"台账最后更新于哪天"这个问题不能用 `updated_at` 回答。
3. `design--NEXT-AGENT-PROMPT.md`（247 KB）正文自称"唯一入口"，来源仓 `AGENTS.md` 也说"接续入口只
   有一个"。置顶后它容易被误读成"本仓的第二个状态入口"。本表已限定：它只是来源仓当时的续接件。
4. `AUTHORITY.md` 与 `design--AGENTS.md` 都是"同一文件里堆多层互相取代的日期条款"的形态
   （10-09／10-19／10-20／10-23／10-28 五层）。这种结构在来源仓靠"后条优先于前条冲突部分"维持，
   一旦被当成整份现行读进融合仓就会串味——这正是本表"定性"列存在的原因。
5. WORK 根目录有 `AGENTS.md.bak-20261024`（13,082 B）与被替换的 `AGENTS.md`（13,567 B）并存；两份
   都在覆盖表里以不同路径登记过，我按"正文引用最新日期"挑了 10-24 那份，`.bak` 未收。
6. `.project/governance/config-authority-index.json` 自称"every config/governance rule 的 single
   normative source"，日期 2026-08-13；`project-authority-index.json` 自称顶层机器权威，日期
   2026-10-19。两份都带"authority index"字样但层级关系没有明文裁决过。我按日期与权威链挑了后者，
   前者未收。**这条是猜的**：缺一份明文说明 `config-authority-index.json` 是否已被 10-19 收敛链
   取代（它管的是 config/governance 规则面，与 10-19 收敛的任务面本来可能不冲突、只是没登记关系）；
   我没有解决这个冲突，只是没让它进置顶清单。
