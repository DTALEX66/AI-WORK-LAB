# 文档与任务总索引（DOCUMENT CENSUS）

> Record资料统一入口：`docs/history/owner-inputs/INDEX.md`（完整登记、别名、包内成员、内容去重、历史摘要）。
> 本次来源覆盖与原字节验证见`docs/history/owner-inputs/RECORD-ARCHIVE-VALIDATION.json`；旧数量仍只是原盘点快照。

> **2026-10-19 权威收敛（增量说明，不改下方旧盘点数字）**：其他任务冻结，唯一CURRENT为
> `taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md`；
> 路线图`docs/current/authority-convergence-20261019/ROADMAP.md`，报告`docs/current/authority-convergence-20261019/AUTHORITY-CONVERGENCE-20261019.md`。
> 该收敛下的首个真实最小闭环`WORK-LAB-MINIMAL-LOOP-001`已交付（2026-10-19）：实现卡
> `docs/current/authority-convergence-20261019/implementation/WORK-LAB-MINIMAL-LOOP-001-ACP-HERMES-RESUME.md`，
> 方案记录`docs/current/authority-convergence-20261019/solutions/SOLUTION-001-ACP-HERMES-RESUME.md`；
> 产品修复一处`services/execution-federation/hermes_adapter.py`，未提交、未跑exact-SHA CI、未提交AAOS候选。
> UI包与`docs/history/archive/ui-priority-20261009/`交接均为SUPERSEDED_20261019/FROZEN，仅作历史证据（2026-10-19 整体归档）；手机端不做。
> 以下2026-10-09/10-18各行是当时快照，保留供追溯；现行任务以OPEN与两个治理索引为准。
> 2026-10-09范围切换（历史快照）：唯一CURRENT为`taskpacks/history/pre-convergence-20261019/WORK-LAB-UI-PRIORITY-TASKPACK-20261009.md`，完整交接在`docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip`（成员 NEXT-AGENT-PROMPT）。
> **2026-10-18 本轮交接（历史快照）**：`docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip`（成员 HANDOFF-20261018-SESSION）（`main` = `fae41c4d`）。
> 旧文档数量/状态/建议只描述此前盘点，现行任务以OPEN为准；UI已冻结、手机端不做。
> 旧任务归档与逐条继承：`taskpacks/history/UI-PRIORITY-CUTOVER-20261009/FROZEN-MANIFEST.json`、`docs/history/archive/ui-priority-20261009/LEGACY-TASK-DISPOSITION.json`。


> 本文件解决一件事：**任何会话都不该再问"任务在哪、文档在哪"**。它不新增权威，只把已有权威的位置、
> 状态与守卫一次说清；权威顺序仍以 `WORK-LAB-AUTHORITY.md` 与
> `.project/governance/project-authority-index.json` 为准。
> 生成：2026-10-08。所有数字都注明测量命令与口径；未测的写"未测"。

## 1. 新任务该落在哪（有文字依据，不是我总结的）

| 问题 | 依据（原文位置） |
| --- | --- |
| 新任务卡放哪 | `taskpacks/current/README.md`：任务权威模型是 `CURRENT TaskPack -> OPEN Register + currentTaskCards`； subordinate 卡片是"本目录内的规划记录，不是第二个 CURRENT taskpack"，其机器权威在 `.project/governance/taskpack-authority-index.json` 的 `currentTaskCards[]` |
| 唯一开放任务账本 | `README.md:16`：`taskpacks/current/OPEN-TASK-REGISTER.md`（唯一在册开放任务账本，不建第二个） |
| 归档怎么做 | `docs/current/workflow-assistance/workflow/active-authority-index.md:69-70`：新增权威文件必须登记到索引；归档操作＝移入 `taskpacks/history/` 或 `docs/history/`（保留 Git 历史），**不删除** |
| 移动会被谁拦 | `scripts/ci/verify_authority_index_paths.py` 默认扫 `docs/current/` 下全部受跟踪 md ∪ `EXTRA_SURFACES`（register + 两份设计合同面，实测 42 面）；7 个严格面（`NAVIGATION_SURFACES` ∪ `EXTRA_SURFACES`）refs=0 即 FAIL，每个面另有 refs 下限防扫描面自己缩水报绿；解析只对着 `git ls-files` |

## 2. 文档面全景（实测）

总体：`git ls-files` = **2,172** 个受跟踪文件，其中 `*.md` = **1,046**（`git ls-files -- '*.md' \| wc -l`）。

| 位置 | 数量 | 最后提交 | 角色 | 规范性 |
| --- | --- | --- | --- | --- |
| `WORK-LAB-AUTHORITY.md` | 1 | 2026-10-07 | 最高人类权威 | 是 |
| `AGENTS.md` | 1 | 2026-10-08 | 执行规则 | 是 |
| `.project/governance/` | 54 | 2026-10-08 | 机器权威（含 `.project/governance/generated/CURRENT_STATE.md`） | 是 |
| `taskpacks/current/` | 4（2026-10-19 归档后；原记 26） | 2026-10-19 | 活账本 + 当前 taskpack | 是 |
| `docs/current/` | 40 md（2026-10-19 归档后；2026-10-10 记 43） | 2026-10-19 | 当前工作文档 | 是（受引用门禁） |
| `docs/decisions/` | 20（2026-10-24 复点：新增 OpenViking 标准/手册；原记 18） | 2026-10-07 | ADR、`docs/decisions/global-execution-standard.md`、`docs/decisions/instruction-precedence.md` | 是 |
| `docs/future/` | 3 | 2026-10-08 | 蓝图与覆盖投影（含生成物） | 计划 |
| `taskpacks/history/` | 104（146 → 第一批汇总删 38 → 第二批删 4） | 2026-10-19 | 冻结历史 + §12/§13 汇总归档 | **非规范** |
| `docs/history/` | 169 md（2026-10-24 复点：新增 AgentRules 交接 2 md；2026-10-19 归档 180 → 汇总删除 14 后） | 2026-10-19 | 冻结历史 + `docs/history/archive/` + `docs/history/archive/recovered-originals/` | **非规范** |
| `reports/` | 527 | 2026-10-06 | 审计证据（`reports/audit-archive/` 479、`reports/audit-evidence/` 34） | 证据 |
| `knowledge-staging/` | 224 | **2026-09-23** | 边界标记为 `HISTORY_ONLY_CONVERGE`，非活动模块 | 冻结候选 |
| `90-archive/` | 1 | **2026-09-24** | 只剩边界标记文件；内容 2026-09-23 已并入 `docs/history/` | 冻结候选 |
| 仓库根 `*.md` | **5**（2026-10-19 归档后；2026-10-10 记 11） | 2026-10-19 | 权威 2 + 现行约定 3；不在权威链里的历史记录 = **0**（见 §4） | 权威/约定 |

## 3. "自称是任务清单"的东西有 9 份，只有一份是账本（2026-10-10 复点；标题原记 10，下表逐名点数实为 9）

实测口径：`grep -cE '^\| [A-Za-z0-9._-]+ \| P[0-9]' taskpacks/current/OPEN-TASK-REGISTER.md` = **163 行**
带优先级的在册任务行（另一口径按"表头行"数到 183，差异来自无优先级单元格与续行；两个数都写出来，
避免下次又为"到底多少条"吵架）。

| 声称者 | 处置 |
| --- | --- |
| `taskpacks/current/OPEN-TASK-REGISTER.md` | **唯一账本** |
| `WORK-LAB-AUTHORITY.md` §14（18 条"当前未决"） | 权威摘要，条目须与账本一致；不一致时以账本行 + 机器合同为准 |
| `docs/future/WORK-LAB-BLUEPRINT-COVERAGE.md` | **生成物，禁手改**；实测 22 个 U 行里 **19 行读 `UNVERIFIED`** 而账本读 `IMPLEMENTED@…`/`CLOSED_LOCAL` → 词汇过期不是新事实，由 `scripts/ci/verify_blueprint_coverage.py --write` 重生成 |
| `README.md`、`taskpacks/current/README.md`、`docs/decisions/PROJECT_POSITIONING.md`、`docs/audits/BLUEPRINT_SYNC_AUDIT_2026-10-06.md`、`taskpacks/current/WORK-LAB-UNIFIED-…-20260918.md` | 描述/投影，不得当账本读 |
| `taskpacks/history/OPEN-TASK-REGISTER-20260917.md` | 冻结孪生，非规范 |

## 4. 仓库根目录是真正的踩坑点（2026-10-19 已清零）

**2026-10-19 结果（用户指示：旧资料全部归档、不得再被索引）**：根上六份历史记录
（`ASSET_REPLACEMENT_MANIFEST.md`、`HANDOFF-UI-L10B.md`、`UI_DECISIONS.md`、`UI_IMPLEMENTATION_REPORT.md`、
`UI_REFERENCE_MANIFEST.md`、`VISUAL_QA_REPORT.md`）连同 `design.qa.yaml` 已 `git mv` 到
`docs/history/archive/root-ui-records-20261019/`，逐件 `from`/`to`/`sha256`/`bytes` 登记在
`docs/history/archive/MOVED-PATHS-20261019.json`；根目录现只剩 **5** 份受跟踪 Markdown（权威 2 + 现行约定 3）。
两个以大写文件名为载荷的测试夹具已改指根级 `NOTICE.md`（`docs/` 是非 diffable root），
`taskpacks/current/error-ledger.json` 的 8 处旧路径引用（门实测）保留为证据并在移动清单中**具名豁免**。
“先改引用、再移动、同一提交内完成”在本次一次完成：54 项归档移动 + 活跃索引改指；
`scripts/ci/verify_stale_surface_paths.py` 读取移动清单，防止旧路径再次出现在活跃面上。

**以下是 2026-10-10 的原始测量，保留供追溯（当时六份都在根目录，现均已在 archive）**：

根上有 **8 个不在权威链里的 md（105.9 KB，2026-10-10 复测；原记 10 个约 127 KB）**，其中两份**看起来像活任务**：

- `HANDOFF-UI-L10B.md`（12,588 B）开头即 `⛔ CLOSED — DO NOT RE-EXECUTE`，但放在根目录，新会话按文件名读就会误接；
- `UI_IMPLEMENTATION_REPORT.md`（54,649 B，2026-10-08）与 `reports/UI-CHECK-OBSERVER-20261006.md` 角色重复。

**处置（本索引提出；移动部分 2026-10-19 已执行）**：`git mv` 进 `docs/history/archive/` 是规范动作，但这些路径被
`README.md`、账本行与 `docs/current/workflow-assistance/workflow/active-authority-index.md` 引用，移动会同时打红引用门禁。因此要求：**先改引用、
再移动、同一提交内完成**，并让 `scripts/ci/verify_authority_index_paths.py` 当场复验。逐个移动的清单见 §7。

**2026-10-10 执行结果（WUI-17：当时判定移动被证伪，改为就地标注＋机器守护——该结论已被 2026-10-19 用户指示取代）**：先量消费者，再决定动不动，当时的结论是
**这六份历史记录当时不能移**（不是因为不能归档，而是因为夹具与账本尚未改写）。逐名引用实测（口径：`grep -rl -F "UI_IMPLEMENTATION_REPORT.md"`，
即 2026-10-10 的根文件名；扩展名 md/json/py/csv，全仓排除 `.project-local/`，含其自身 = **21** 个文件点名；其中
`taskpacks/history/UI-PRIORITY-CUTOVER-20261009/original-tree/**` 3 份、`docs/audits/` 3 份、`tests/` 2 份、
`taskpacks/current/error-ledger.json` 1 份、`HANDOFF-UI-L10B.md` 1 份），关键约束是：
它被两份测试当作**伪证夹具**使用
（`tests/workflow-assistance/test_path_text_is_one_predicate.py`、
`tests/workflow-assistance/test_control_service.py`——该夹具的作用是让"折叠大小写后仍在根内"这类断言
必须真红），以及**活账本**`taskpacks/current/error-ledger.json:5574`
在某条记录的 `fix` 文字里逐字引用了它；`taskpacks/history/UI-PRIORITY-CUTOVER-20261009/original-tree/**`
在 `.gitattributes` 里标了 `-text -diff`，即刻意保留原字节的冻结树。当时的做法是**就地标注**：
根目录每份 Markdown 的处置登记在 `.project/governance/root-document-dispositions.json`（2026-10-10 为 11 份：
`authority=2`、`convention-current=3`、`historical-non-normative=6`——本文上面的"8 份不在权威链里"用的是
"除 AGENTS/README/WORK-LAB-AUTHORITY 之外"的口径，两套分类各自成立，故都保留原措辞），六份历史记录在 H1
下方插入一段可见的 `NON-NORMATIVE-HISTORICAL` 声明（含现行任务包逐字路径），正文其余字节未动；必门
`scripts/ci/verify_root_document_dispositions.py`＋`tests/workflow-assistance/test_root_document_dispositions.py`
（14 例）钉住四件事：新出现在根上的 md 若没人分类即红、权威集合是从机器权威里**解析**出来的而不是抄进清册的
（把 AGENTS.md 降级会红）、声明里指向的任务包必须等于 `.project/governance/project-authority-index.json`
的 `currentTaskpack`（旧指针会红）、以及去掉声明块之后的字节必须逐字节等于提交版本（**改写历史正文会红**）。
该门在真文件上做过两次伪证（删掉一段声明→`UNLABELLED_HISTORICAL`；在正文追加一行→`BODY_REWRITTEN`），
两次都红并逐字节还原（13,210 B / 10,255 B），脚本 `.project-local/runs/falsify_root_dispositions.py`。

## 5. 活文档里仍在引用已退役根（实测 `git grep -c -F`，限 `docs/current` + `taskpacks/current`）

以下都是**已退役根的名字，不是可跟随的路径**，故不加反引号：10-workflow **7**（全仓活 md 口径 17/10 文件）、
00-governance 9、contracts/ 21、scripts/workflow 7、apps/observer/web 8（`git ls-files -- apps/observer/web` = **0**，
即引用一个仓库里已不存在的根）、50-taskpacks 5、30-observer 4、80-evidence 3、docs/handoffs 2、docs/audit/ 1。

这些是**引用腐坏**而不是任务缺失；`scripts/ci/verify_authority_index_paths.py` 只覆盖 `docs/current` 与账本，
`reports/`、`knowledge-staging/`、根目录不在其扫描面内——这是"找不到文档"的第二个来源。

## 6. 从 `D:/All projects/Record` 收回来了什么（2026-10-08）

库总量实测 **15,301,597,876 B / 168 项**，其中 **98.31% 是另一个项目的构建包**。WORK-LAB 相关约 44 MB，
其中 11 文件 / 6.5 MB 与仓库字节相同 → **真正在 Git 根外的唯一副本是 9 个文档（456,606 B）+ 一个
37,048,117 B 的 UI 资料包**。

- 入库位置：`docs/history/archive/recovered-originals/RECORD-20261008/`（提交 `3862499b`）。
- 通道：`scripts/maintenance/recover_shared_root_original.py`，逐件产出 sha256、`flow=ALLOW`、
  `untouched=True`，证据 JSON 在 `.project-local/runs/qoder-20261008-d/recovery/`。
- 提交前 `scripts/audit/tracked_secret_shape_scan.py`：6 处命中，**新目录 0 命中**（6 处是此前已裁定的
  占位符与测试植入假值）。
- **故意不导入**：`WORK-LAB_MASTER_ATLAS_2026-09-29.zip`（`.project-local` 下已存两份，其压缩包内 repo 快照的 111 个
  文件今天全部能解析到受跟踪路径 → 零独有代码）；4 个 taskpack ZIP（成员与受跟踪文件哈希相同）；
  142 MB 三项目共享材料（不是 WORK-LAB 可单独发布的）。
- 待裁定：共享材料是否由本项目代表三项目发布；`C:\Users\ALEX` 出现在 atlas 的 4 个文件里（与 ERR-177
  同类，已在册）。

## 7. 让"下次还找不到"不再发生的四条硬要求

1. **本索引必须被引用**：`README.md` 与 `docs/current/workflow-assistance/workflow/active-authority-index.md` 各加一行指向本文件；
   本文件位于 `docs/current/`，因此受 `scripts/ci/verify_authority_index_paths.py` 约束——写错路径会直接红。
2. **根目录清零**：**已完成 2026-10-19**。§4 的六份历史记录与 `design.qa.yaml` 按"改引用 → 移动 → 同提交复验"移入 `docs/history/archive/root-ui-records-20261019/`；根目录现只剩 5 份受跟踪 Markdown（权威 2 + 现行约定 3），旧路径由 `scripts/ci/verify_stale_surface_paths.py` 拦住。
3. **冻结面要被标记**：`knowledge-staging/`（224 文件，2026-09-23）与 `90-archive/` 需一份
   `FROZEN` 声明（现只有 `BOUNDARY.md`）；`taskpacks/history/` 无 README，`docs/history/archive/` 6 个子树
   只有 3 个有——统一补，并采用 `reports/audit-archive/20260930/ARCHIVE-INDEX.json` 那种**逐文件
   path+bytes+sha256** 清单（三套归档约定里只有它做到字节可核对）。
   **已做（2026-10-08，第 3 项的清单部分）**：`knowledge-staging/`、`docs/history/archive/`、
   `reports/audit-archive/` 各得一份 `FROZEN.md` 声明 + `FROZEN-MANIFEST.json` 逐文件清单
   （225 / 137 / 480 条，字段沿用 `ARCHIVE-INDEX.json` 的 `path`/`bytes`/`sha256`，不另立新约定），
   由 `scripts/audit/generate_frozen_surface_manifest.py` 生成、
   `tests/ci/test_frozen_surfaces_are_intact.py` 每次复验并点名增删改；清单不能自摘要所以按名字排除自己，
   该排除也被断言。已在真实文件上注入一次字节改动验证门禁会红（`CHANGED knowledge-staging/BOUNDARY.md
   manifest=0c84bdef6151 now=ce0703307370`），随后按字节还原。
   **`90-archive/` 不配清单**：它只剩 1 个边界标记文件（本文件第 34 行早就这么写），对单文件做逐文件
   哈希清单是仪式而非控制，`BOUNDARY.md` 本身就是冻结声明——我一度以为本文件写错了，核对后是本判断错，
   在此收回。
   **实测更正一处**：`docs/history/archive/` 6 个子树里有 README 的是 **2 个**（`session-history`、
   `superseded-current`），不是 3 个；缺的是 `recovered-originals`、`reports-history`、`scripts-history`、
   `workflow-assistance`。另外该面字节数 38.5 MB（96% 是 2026-10-08 导入的一个 UI 资料原件包），
   我用不带 `-z` 的 `git ls-files` 量到过 1.09 MB——git 会引号化非 ASCII 路径，那些"文件"根本不存在，
   于是被静默跳过；清单类统计一律 `-z` 分割。
4. **活引用要收敛**：§5 的退役根引用逐条改指现路径；把 `reports/`、根目录、`knowledge-staging/` 纳入
   引用门禁扫描面，否则"文档存在但没人能找到"仍会发生。
   **已做（2026-10-08，第 4 项的设计合同部分）**：`apps/observer/frontend/DESIGN.md` 与
   `apps/observer/frontend/SCREEN_SPEC.md` 进 `EXTRA_SURFACES`（受严格面规则），每个面配实测下限（`apps/observer/frontend/DESIGN.md` 25 / 34、
   `apps/observer/frontend/SCREEN_SPEC.md` 8 / 10、register 300 / 393、`docs/current/` 300 / 396），下限的作用是**缩水必须被
   决定一次**，不是装饰。同一轮把提取器补上样式与组件后缀（css/scss/sass/less/vue/svelte）：此前
   `apps/observer/frontend/DESIGN.md` 引用最密的那一列它一条都读不到。实测两个口径都写清楚——原始匹配 837→854，去掉示意名后
   真正被判定的引用 817→833；新增判定里 6 条落在外树或路由上，5 条需要各自的就地声明
   （`apps/observer/frontend/DESIGN.md` 3、`apps/observer/frontend/SCREEN_SPEC.md` 1、register 1），第 6 条被同面已有的目录级声明顺带覆盖。都按所在句
   声明，不改成仓库级静音。引用解析加了"先根、后同目录"两级候选：设计文档里的 `src/…` 写法指的是自己
   旁边的文件（示意名按本仓约定带省略号，才不会被当成一次死链断言——我第一版把示例直接写成反引号路径，
   引用门禁当场把这一句判红，这是它在正常工作）；顺序就是安全性——根形式永远先试，
   原本能在根上解析的名字断了仍报 broken。新增 8 条断言（`tests/ci/test_authority_index_paths_resolve.py`
   由 28 例到 36 例全绿），5 个关键特性各做一次"把实现拿掉必须变红"的反证。反证脚本的第一版是**假通过**：
   加载器名写错，五条全部在到达断言之前就报错，而判据只看"有失败或错误"，于是统一打印 CAUGHT。
   认出它的特征是五条形状完全一致（`errors=1 failures=0`，真实断言失败应是 `failures=1 errors=0`）；
   修正判据为"必须是 failures 且 errors=0"并重跑，才是真的 5/5。
   **未做（第 4 项剩余部分，含明确理由）**：`reports/`、`knowledge-staging/`、根目录**没有**并入扫描面。
   开闸前先量代价（2026-10-09 复量，口径：这三面全部受跟踪 md，用同一条规则逐面 `check()`）——
   397 个有引用的面、4,153 条引用里 **3,262 条断链**。naive 并入就是把这些一次倒进队列，那是负担不是控制。
   按文档来源拆开看才有办法：
   外购技能副本（`knowledge-staging/asset-provenance/` 下的，与任何名为 SKILL.md 或路径含 /skills/ 段的文件）559 面 /
   3,327 引用 / **2,871** 断——这些句子讲的是它们自己上游仓库，本来就不是本仓的导航面；
   本仓日期化归档（`reports/audit-archive/`，非技能副本）70 面 / 329 引用 / **243** 断——改了会让带日期的
   记录说假话，与第 3 项冻结清单冲突；
   当下仍在写的（根目录 9 面与归档外的 reports）33 面 / 497 引用 / **148** 断——只有这一档是真正的活引用腐坏。
   所以并入不是一份 3,262 行的基线，而是三种策略各一条：副本子树按**面**声明为"非本仓导航面"（并让测试盯住该
   声明仍然成立），日期归档用**棘轮**（条数不得增长、基线里每条今天仍须断，修好一条就同提交重发基线），
   当下在写的 148 条**逐条清**。追正一句：本轮早先我写过 naive 代价是 **3,492**，那是更宽口径下的旧数，
   以本次复量的 3,262（口径如上）为准。登记为账本行 `REFS-RATCHET-HISTORY-SURFACES-20261009`，不是静默丢弃。

## 8. 未测 / 不确定（不假装）

- `.project-local/` 内未被跟踪的 md 数量：**已测 2026-10-18**——1,269 个 md / 16,329,118 B；该根在 `.gitignore:42` 整体忽略，`git status` 对其中 md 的未跟踪计数为 0（设计如此）。
- `apps/observer/docs/` 的 md 字节数：未测。
- 账本行数 163 与 183 的差集逐条归因：**已完成 2026-10-18**，见 §10。

## 9. 2026-10-10 复测更正（WUI-17：默认加载链的引用可追溯性）

- **本文件自身四组数字已过期，现按逐名点数复值**：`docs/current/*.md` = **43**（原写 38）；仓库根受跟踪 md =
  **11**，其中不在权威链里的 = **8**（11 − AGENTS/README/WORK-LAB-AUTHORITY 三份，原写 10），合计 **105.9 KB**
  （原写约 127 KB）；§3 标题的"自称任务清单"逐名点数为 **9** 份（原写 10，差异就在被合并进同一表格单元格的 5 项
  只计了一次标题行）；§7.3 之后三处冻结面已共用同一 `FROZEN.md` + `FROZEN-MANIFEST.json` 约定，
  所以"三套归档约定"今天是**一套约定、三处实例**——本文其余段落保留当时的措辞，因为那是那天的事实。
- **默认加载链的引用已机械化正规化**：`scripts/audit/normalise_doc_citations.py` 把权威引导链 8 份文档中的
  201 条反引号路径引用里的 **56 条**改写为仓库根相对真路径（裸文件名与相对前端的 `src/...` 形状），
  对 14 个"类指/非本仓"引用（`SKILL.md`、`FROZEN.md`、`BOUNDARY.md`、`config.yaml`＝Hermes Home live、
  `tauri.conf.json` 两应用各一份、包内 `design_tokens.json`/`ui_read_model.ts` 等）改为**带理由的显式声明**，
  并要求每条声明仍被实际使用（不再需要的声明会让复验变红，避免许可腐化）。历史副本
  （`taskpacks/history/`、`docs/history/`、`reports/audit-archive/`）不参与"按文件名猜路径"，
  因此 `project-authority-index.json` 这类同名不会再被指向 2026-10-09 冻结树。
- **必门**：`tests/workflow-assistance/test_default_load_doc_citations_resolve.py`（5 例）钉住范围文件在盘、
  引用零不可解析、扫描数 ≥150（防止正则失明）、许可全部仍在用，并用合成断言证明解析器确实会判
  "不存在的路径"为不可解析、会把相对简写改回真路径、且不会把简写建议成历史冻结副本。
- **仍属未做**（保持原样，不假装完成）：上列"未做"三条今天仍未做；`reports/`、`knowledge-staging/`、根目录
  也还没并入引用扫描面（§5 第 4 项）。WUI-17 本轮只处理"仍影响默认加载"的消费者。
- **同日稍后更正上一条**：上一条写"正是这 8 份文档"是**错的**——`auditBootstrap` 第 6 步就是活账本
  `taskpacks/current/OPEN-TASK-REGISTER.md`，而它不在作用面里；把它加进去（8→9 份）之后当场量出
  **374 条引用、80 处从根目录打不开的简写形状、9 条完全解析不了**（7 个裸证据回执名 + 2 条"引用它就是为了说它错"的路径）。
  同轮还修了作用面本身的口径缺陷：`working_tree()` 原先按手写的 `SOURCE_DIRS` 十一根目录走盘，量得 2,474 个路径，
  里面**没有**受跟踪且被 WUI-16 引用的 `projections/agents/generate.py`，于是一条诚实引用被判为不可解析；
  改为 `git ls-files` ∪ 全仓走盘（排除 `.project-local`，运行时副本不得决定一个裸名的含义），量得 **2,700**。
  走盘一放宽又立刻出现**相反**缺陷：`.ui-reference/WORK-LAB/**` 里另有一套与本仓同名的前端文件（对应本仓
  `apps/observer/frontend/src/types.ts` 与 `apps/observer/frontend/src/lib/navigation.ts`），
  两条正确引用改判"歧义"——处理方式是把冻结树与外购参考副本从**裸名索引**里排除（`NOT_INDEXED_PREFIXES`），
  显式路径照旧可引。两条被判错的错误路径改由 `QUOTED_AS_ABSENT`（按整条引用而非文件名匹配、逐条带理由、
  **必须仍在被使用否则复验变红**）豁免；七个裸回执名改为逐字运行时路径（7 处替换、写后按字节复核）。
  最终态：`DOC_CITATIONS CHECKED docs=9 citations=365 rewritten=0 blocked=0 generic_allowed=14 absent_quoted=2 stale_allowances=0`，
  门增至 **8 例**（新增：账本必须在作用面内、受跟踪文件与目录无关地可见、外购副本不作裸名含义），
  且三条都用**改工具本体**的方式伪证过（去掉参考副本排除→该例红 failures=1；把走盘限制到单个根→红 failures=2；
  两次工具均按字节还原、还原后 8/8 绿，`.project-local/runs/falsify_citation_cases.py`）。教训登记 ERR-242。
- **根目录处置已成机器合同**（§4 末）：2026-10-10 的清册实测为 11 份 =
  `authority=2 / convention-current=3 / historical-non-normative=6`，门输出
  `ROOT_DISPOSITIONS_PASS root_md=11 authority=2 convention=3 historical=6`，必门
  `tests/workflow-assistance/test_root_document_dispositions.py` **14 例全绿**
  （含 6 条合成伪证 + 2 条真文件伪证：删声明→`UNLABELLED_HISTORICAL`、追加正文→`BODY_REWRITTEN`，
  均逐字节还原 13,210 B / 10,255 B）。六份历史文件各 +481 B，正文与提交字节逐字节相同由门复核。
  **2026-10-19 更新**：六份已移入 `docs/history/archive/root-ui-records-20261019/`，清册收敛为 5 份
  （`authority=2 / convention-current=3 / historical-non-normative=0`），见 §11。
- **同日第三轮：两表引用形状与"改完又被整表覆掉"的收据问题**。绑定矩阵与验收清单自身的必门
  `tests/workflow-assistance/test_ui_v2_csv_citations_resolve.py` 本轮两次判红，量出的形状是：233 条引用里
  **58 条只有 basename**、**6 条写了不存在的目录**、**1 条指从未存在的文件**；而指针内容检查"打不开就跳过"，
  于是 144 条带行号引用只有 **106** 条被真正读过（普查地板 `POINTER_FLOOR=140` 因此判红——地板不是被下调的，
  是被路径修复满足的）。修法是**改数据不是改门**：`.project-local/runs/wui-20261010/expand_shorthand_citations.py`
  的替换表取自门自己的扫描（所以正文里类指的文件名不会被机械改写），裸名必须在树中**唯一**才落笔，
  写错目录的六条还要求**候选文件里确实命中被引代码**才采用；B34 的死人路径改为具名 `ABSENT:` 并指向
  `apps/observer/frontend/src/lib/ruleProjectionTruth.ts:34`。路径一通即暴露 **8 条行号漂移**（±1～4 行），
  由 `.project-local/runs/wui-20261010/repoint_convicted_pointers.py` 只搬"门点名"的指针、只落在 30 行内唯一命中处，写后用门的谓词复跑：
  `BEFORE checked= 144 problems= 8` → `AFTER checked= 144 problems= 0`；最终 `resolves=223 / runtime=10 /
  declared_absent=1 / 未解析 0`。
- **两条早先修复在出厂字节里找不到**（WUI-23 段登记的 `CITATION_NORMALISE APPLIED rewritten=58` 与上一段登记的
  7 条指针改正，重读文件时都回到了修前状态）：链式脚本里**最后一个写者**拿的是自己早先载入的整表副本，
  而每个写者都只在"自己写完"后复读过。此后规则写进 ERR-248：一批写入链的末尾必须重读出厂文件、复跑判决，
  并把读回的 SHA 写进登记（矩阵 `13ece1b83c2c24be` → `17a89217d7ad509b` → **`4c39aff8677b48c3`**，
  清单 **`6c93e1bb4a51ec30`**）。同轮我自己的第二缺陷：把含逗号的句子原文替换进**未加引号**的 CSV 字段，
  B34 由 14 列变 15 列，而 `csv.DictReader` 把多余字段挂在 `None` 键下、门只断言表头与行数因而**看不见**；
  门已加**逐行字段数**断言并伪证（对照 exit 0 → 种入多一列 exit 1 且命名 `('B34', 15)` → 按字节还原 exit 0）。
- **文档引用面随之调整**（同一类问题的另一面）：账本新段要原样写出六条坏路径才能记录"这里曾经写错"，
  而 `scripts/audit/normalise_doc_citations.py` 的 basename 兜底会把它们"改好"——那等于把判决从文档里抹掉。故六条按**整条
  引用**加入 `QUOTED_AS_ABSENT`（理由逐条写明是 ERR-247 更正记录），类指的 `package.json` 加入
  `GENERIC_CITATIONS`；新增必门例 `test_a_quoted_wrong_path_is_only_safe_because_of_its_allowance`
  证明这些豁免是**承重**的（撤掉一条，工具立刻报 `rewritten=1` 即会把更正记录改写）。最终态
  `DOC_CITATIONS CHECKED docs=9 citations=436 rewritten=0 blocked=0 generic_allowed=16 absent_quoted=8 stale_allowances=0`，
  该门 8→**9 例**、两表门 **7 例**全绿。教训登记 ERR-247（假出处与失明普查）、ERR-248（写入秩序与表形状）。
- `WORK-LAB_UI开发资料总包_按批次.zip` 内 12 个内层 ZIP 的逐成员清单：**已展开 2026-10-18**，见 §10。

## 10. 2026-10-18 三面复量与三策略执行（WUI-17 收尾）

- **三面复量（与活门同一条规则）**：直接 import `scripts/ci/verify_authority_index_paths.py` 的 `check()`，不另写解析器；扫描 `reports/`、`knowledge-staging/`、仓库根全部受跟踪 md，得 **662 面 / 4,168 条引用 / 3,257 断**（2026-10-09 记的 397/4,153/3,262 是当时口径与树，今天不沿用）。按来源拆：外购技能副本 **559 / 3,327 / 2,871**；日期化归档 **70 / 329 / 243**；其余（原称"当下仍在写"）**33 / 512 / 143**。回执 `.project-local/artifacts/wui-20261009/refs-census-20261018.json`。
- **"当下仍在写"这一档按证据重分类，不再当作活引用去改**：143 条逐面归因 = 五份根级 `historical-non-normative` 记录 93 条（`docs/history/archive/root-ui-records-20261019/ASSET_REPLACEMENT_MANIFEST.md` 8、`docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip`（成员 HANDOFF-UI-L10B） 3、`docs/history/archive/root-ui-records-20261019/UI_DECISIONS.md` 2、`docs/history/archive/root-ui-records-20261019/UI_IMPLEMENTATION_REPORT.md` 53、`docs/history/archive/root-ui-records-20261019/UI_REFERENCE_MANIFEST.md` 27）+ `AGENTS.md` 6 条（那 6 条正是"仓库根没有 `skills/`、`bin/` 目录"这句话本身[no-tree-claim DELETED ref=skills/][no-tree-claim DELETED ref=bin/]）+ 日期化报告 44 条。六份根级历史文件的正文被 `scripts/ci/verify_root_document_dispositions.py` 按字节冻结，日期化报告改写即让记录说假话；因此这一档与日期归档同用棘轮。"逐条清"在这里的正确落地是**逐条归因并锁死**，不是改历史。
- **三策略已机器化**：`.project/governance/refs-surface-policies.json`（面级声明 + 386 行基线）与 `scripts/ci/verify_refs_surface_policies.py`。门同时拒绝"新增断链"与"基线里已修好的条目未重发基线"，外购副本声明设 500 面下限防失效。现态 `REFS_SURFACE_POLICIES_PASS surfaces=662 refs=4168 external_surfaces=559 ratchet_surfaces=103 ratchet_baseline=386 new=0 fixed=0`；必门 `tests/workflow-assistance/test_refs_surface_policies.py` **8 例全绿**，含两条真文件伪证（删一条基线→`NEW_BROKEN` 点名该行；加一条假基线→`FIXED_BUT_BASELINE_STALE` 点名该行）。
- **账本行数 163 与 183 的差集已逐条归因**：在 `taskpacks/current/OPEN-TASK-REGISTER.md` 修订 `9488cf9707`（2026-10-08）上复量，163 = 匹配 `^\| <id> \| P<digit>` 的任务行；183 = 196 个表格行 − 7 条分隔行 − 6 条表头行。20 条差额逐类为：**8** 条没有优先级列（SKILLS-…、GATE-RECHECK-…、TOOLCHAIN-PROBE-…、U19-MSVC-…、U19-P0C-…、UI-CHECK-…、SPILL-…、HANDOFF-…）、**4** 条来自另一张"层/处置"表、**6** 条优先级单元格不是 `P<digit>`（D1 ENV、D2 USER AUTH、C2/C3/O1/O2 OPTIONAL）、**2** 条首列含空格（`AG-01..04 gate`、`AG-05..07 gate`）。现行账本（HEAD `0369d349`）为 **25 条任务行 / 27 条表格行 / 1 条分隔行**，旧口径两数都不再适用。
- **`.project-local/` 未跟踪 md 已测**：**1,269 个 md / 16,329,118 B**；该根在 `.gitignore:42` 整体忽略，`git status` 对其中 md 的未跟踪计数为 0。
- **UI 资料总包内层 ZIP 已展开**：外层 `WORK-LAB_UI开发资料总包_按批次.zip` 37,048,117 B、sha256 `c94ff634dad3fa47cd843493c5f3b59c946fd987295085b8c821febba13eef48`，含 **12 个内层 ZIP / 197 个非目录成员**（逐 ZIP 成员数 12/25/12/39/11/19/14/21/23/15/3/3），逐成员 name+size+CRC32 回执 `.project-local/artifacts/wui-20261009/ui-batch-zip-census.json`（25,930 B）。
- **owner 已决定并执行（2026-10-19）**：六份历史文件已 `git mv` 进 `docs/history/archive/root-ui-records-20261019/`；
  同一指示还归档了 UI 优先目录、23 份非当前 taskpack 等共 54 项，见 §11。消费清单与字节保留证明见
  `docs/history/archive/MOVED-PATHS-20261019.json`。

## 11. 2026-10-19 归档规范化（用户指示：旧资料不在明面上，且不得再被索引）

**指示原文**：“任何旧的过时的冗余的陈旧的，不要再明面上，全部归档到该去汇总的地方，包括仓库目录文件夹整体搬走，
要么压缩归档到历史里。我描述不准确，按照规范化处理，防止再次索引路径到旧资料上”。

**规范化目标（沿用既有约定，不新造第二套）**：文档历史统一锚点 `docs/history/archive/`；taskpack 历史统一锚点
`taskpacks/history/`；证据留在 `reports/` 与 `docs/audits/`；外购/参考副本留在 `knowledge-staging/`；
`90-archive/` 仍只有 `BOUNDARY.md`。移动一律 `git mv`，不删除、不改写正文。

**本次移动（54 项，全部为 `git mv`；逐件 `from`/`to`/`sha256`/`bytes`/`lastCommit` 见
`docs/history/archive/MOVED-PATHS-20261019.json`）**：

| 组 | 数量 | 目标 |
| --- | --- | --- |
| 根级六份 UI 历史记录 + `design.qa.yaml` | 7 | `docs/history/archive/root-ui-records-20261019/` |
| 已冻结的 UI 轮次目录（原在 `docs/current/` 下，名 ui-priority-20261009，反引号在本仓意为“可解析路径”，故只写名） | 20 | `docs/history/archive/ui-priority-20261009/**` |
| `taskpacks/current/**` 中除活账本、README、账本 JSON、唯一 CURRENT 外的 23 份 | 23 | `taskpacks/history/pre-convergence-20261019/**` |
| 模块指令文件（原在 `docs/current/` 根，名 workflow-assistance-AGENTS.md） | 1 | `docs/history/archive/workflow-assistance/module-instructions-20261019.md` |
| 两份 workflow 历史记录 | 2 | `docs/history/archive/workflow-assistance/handoffs/` 与 `docs/history/archive/workflow-assistance/audit/`（带日期文件名） |

**保留在明面上的当前位置**：`taskpacks/current/` 只剩 4 份（`OPEN-TASK-REGISTER.md`、`README.md`、
`taskpacks/current/error-ledger.json`、`taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md`）；`docs/current/` 剩 40 份
（以 OPEN、两个治理索引与收敛报告/路线图为核心）。

**防再次索引（机器控制）**：

- `docs/history/archive/MOVED-PATHS-20261019.json` 登记每条旧路径、新路径与内容哈希；它是唯一移动真相。
- `scripts/ci/verify_stale_surface_paths.py` 扫描受跟踪的**活跃面**，出现任一旧路径即 `STALE_SURFACE_PATHS_FAIL`；
  冻结历史（`docs/history/`、`taskpacks/history/`）、证据（`reports/`、`docs/audits/`）、`knowledge-staging/`、
  `.workbuddy/` 不参与扫描；受保护文件 `taskpacks/current/error-ledger.json` 与 `AGENTS.md` 以**具名豁免**登记，
  且豁免必须仍被使用（旧路径消失即报 `ALLOWANCE_UNMET`），不允许静默放行。
- `tests/ci/test_stale_surface_paths_are_gone.py`（**14 例**）钉住：活树判绿、人口不小于地板（1,287 面 / 2,599 受跟踪文件实测）、
  每条移动的目标文件按 sha256+bytes 复核、47 条旧路径与旧目录在磁盘上确实不存在、7 个裸名不得重现在仓库根、
  种入旧路径必判 `STALE`、`original-tree/**` 冻结写法**不得**被判旧、历史/证据面不扫、豁免不再被使用即红、
  移动清单自身不被扫、不可解码字节不冒充判决。`tests/ci/` 由 `scripts/ci/run_root_governance_suite.py` 按 glob 发现，
  新门落地即被 CI 度量，不依赖手工登记。
- 门的第一个缺陷是**测试自己找到的**：`(?<!x)a|b|c` 解析成 `((?<!x)a)|b|c`，一条 lookbehind 只保护 48 个分支中的第一个，
  于是索引里 5 条 `archivePath` 冻结写法全部被误判为旧路径；改为 `(?<!x)(?:a|b|c)` 后清零，并留下
  `test_a_frozen_original_tree_spelling_is_not_convicted` 作为回归例。另两条真实残留也是门先于文档发现的：
  `docs/current/` 下的 ui-priority-20261009 目录与 `taskpacks/current/` 下的 WORK-LAB-UNIVERSAL-WORKFLOW-TASKPACK-20260916
  目录在 `git mv` 之后留下**空目录**（反引号在本仓意为“可解析路径”，故此处只写名），即“旧目录还在明面上”，
  已 `rmdir` 清除并由 `test_no_enforced_old_path_still_exists_on_disk` 钉住。

**已改指的活跃消费者（要点）**：两个治理索引、`WORK-LAB-AUTHORITY.md`、CURRENT taskpack、活账本、
`docs/current/workflow-assistance*`、`docs/decisions/`、`docs/future/`、Observer 设计合同与测试夹具、
`packages/client-neutral-core/scripts/` 中的路径常量、`scripts/ci|audit|maintenance` 的锚点与默认目标。
**故意不改**：`taskpacks/history/UI-PRIORITY-CUTOVER-20261009/original-tree/**`（`-text -diff` 冻结原字节）、
历史记录正文中的旧路径（它们是被引用的历史对象）、`taskpacks/current/error-ledger.json` 的既有记录。

## 12. 2026-10-19 汇总后删除（用户指示：旧交接与提示词资料归档后删除）

**指示原文**：“旧交接和一些提示词的资料 汇总到一起归档后 就删除了吧”。这条指示取代
`docs/current/workflow-assistance/workflow/active-authority-index.md` 第 4 节“归档操作＝移入历史，
**不删除**”的默认约定：删除只适用于**先汇总、后验证**的一类文件，且只由 owner 本次指示授权。

**范围按名字与位置判定，不靠记忆**：`git ls-files` 中文件名含 HANDOFF / NEXT-AGENT-PROMPT /
PROMPT-PACK / CLOSEOUT / START-ANY-AGENT / AGENT-PROMPT，且位于 `docs/history/` 或
`taskpacks/history/`。命中 91 份，其中：

| 处置 | 数量 | 依据 |
| --- | --- | --- |
| 汇总后删除（第一批） | **52** | 内容 484,845 B → 单一归档 `docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip` 263,031 B，sha256 `3bd841513b4623781068…` |
| 具名保留（机器指针在读，故第一批未删） | **4** | `staticHandoffViews[].entry_record`、`frozenTaskCards[].path`、审计脚本与其测试的夹具名、`scripts/ci/generate_current_state.py` 的来源清单各点名一份；第二批（§13）按 owner 授权连指针一起改 |
| 规则性排除 | **35** | `taskpacks/history/UI-PRIORITY-CUTOVER-20261009/original-tree/**`（`-text -diff` 原字节冻结树）、`docs/history/owner-inputs/**` 与 `docs/history/archive/recovered-originals/**`（owner 入库原件，部分是仅存副本）、`docs/history/archive/session-history/**`（导入的多项目材料）、`reports/**` 与 `knowledge-staging/**`（证据面与外购副本） |

**逐件证明在先，删除在后**：清单 `docs/history/archive/HANDOFFS-AND-PROMPTS-20261019-MANIFEST.json` 对每个成员记 `path`/`bytes`/`sha256`/`crc32`；构建脚本把 ZIP
重新打开、逐成员读回并与记录哈希、尺寸、CRC32 三方比对，52/52 全对才执行 `git rm`。恢复路径两条：
在项目根解压该 ZIP，或从 Git 历史取回（这些文件在删除前已提交）。

**删除后不留在明面上的东西（第一批）**：52 条旧路径在受跟踪树中全部消失（必门逐条断言
`path not in git ls-files` 且文件不存在）；`docs/history/archive/FROZEN-MANIFEST.json` 重生成
（158 条，含 ZIP 与清单本体；条目字节求和会随每次重发变化，故只记条数，求和值以清单自身为准），所以这两个新产物从今天起也是字节冻结的。

**受影响的活引用**：25 处改指到 `docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip` 并就地写出
成员名；`docs/history/owner-inputs/INDEX.md` 由生成器重生成，其“UI 历史交接”行改指汇总清单。
默认加载链引用门随后判红一次：我在括号里把成员名连着扩展名一起写了出来，被引用扫描当成一条从根打不开的裸名引用，
去掉扩展名后归零——记录这一点是因为**它是我自己造出来的缺陷，由门先看见**，不是工具误报。

**删除后的面计数（`git ls-files -z` 实测）**：受跟踪文件 **2,550**（删除前 2,602）；
`docs/history/` md **167**；`taskpacks/history/` **108**；`docs/current/` md **40**；
`taskpacks/current/` **4**；仓库根 md **5**。§2 表已按这组数字更新。
**一处保留的红（具名，不静默）**：`tests/workflow-assistance/test_project_local_citation_audit.py`
的 `test_regenerating_the_record_is_idempotent_apart_from_the_timestamp` 判 `unadjudicated != 0`。
归因实测：受跟踪记录 `docs/audits/PROJECT_LOCAL_CITATION_AUDIT_2026-10-07.json` 的 `generatedAt` 为
2026-10-10T14:38:39Z（counts.unadjudicated=0, reviewQueue=8, presentOnThisMachine=309）（`counts.unadjudicated=0`、`reviewQueue=8`、`presentOnThisMachine=309`），最后一次提交是
5f14677d；该测试扫的语料是整棵 `.project-local/`（9 天里多轮会话的运行残留，含本轮
`.project-local/runs/archive-normalization-20261019/` 的脚本与回执），**不来自本轮的受跟踪改动**。
该测试也未登记进 CI：`.github/workflows/` 与 `services/orchestration/run_quality_gate.py` 的 stage 表里
都没有它的名字（本轮实测两处 grep 皆空），所以它是本地未登记门——CI 的判决不含它。
另记一条危险：`scripts/audit/project_local_citation_audit.py` 不只读，它会 DISPOSE `.project-local` 运行目录
并重写上面那份受跟踪记录；本轮运行过一次，把记录改坏后按字节 `git checkout --` 还原（还原后该测试回到 1 红而不是 2 红）。
**因此本轮不再重跑它**，把它作为 owner 决定项登记：要么按既定顺序重发派生审计（先 `scripts/audit/ledger_regression_command_targets.py --apply`
再 `scripts/audit/triage_unbound_ledger_records.py`，并连带清理运行残留），要么把它登记进 CI 或明确降级为本地观察。
**exact-SHA CI 的第一次判决与修法（2026-10-19）**：推送 `249e5fea` 后 `work-lab-gate` run 39226565397 判
`aggregate=failure`，唯一红模块是 `workflow-assistance` 的 `test_the_shipped_inventory_describes_the_tree`
（gate-plan / supply-chain-security / integration / observer / token-monitor 皆 success）。
原因不在本轮改动本身，而在派生清单落后：`docs/audits/TOOL_INVENTORY_2026-10-07.json` 存的是每件工具的
git-index blob sha256，本轮改过 9 份 `scripts/audit|maintenance` 工具后清单仍是旧哈希。
修法按该工具自己的顺序纪律（ERR-151：先 `git add`、后重测清单、再提交）：暂存后重跑
`scripts/audit/tool_inventory_readback.py`，得 `trackedTools=77 withLedgerPromise=19 referencedSomewhere=77 unclaimed=0`，
`tests/workflow-assistance/test_tool_inventory_coverage.py` 复跑 `Ran 12 tests / OK`。
新门 `scripts/ci/verify_stale_surface_paths.py` 不在该清单口径内（清单只覆盖 `scripts/audit` 与
`scripts/maintenance`），它的 CI 覆盖来自 `tests/ci/test_stale_surface_paths_are_gone.py` 被
`scripts/ci/run_root_governance_suite.py` 按 glob 发现。
**空签出复现抓出本门自己的两个缺陷（已修，登记在此）**：为了不在只信本地绿的前提下宣布完成，本轮用
`git worktree add --detach .project-local/worktrees/ci-repro HEAD` 造了一份**没有 `.project-local/` 的干净签出**
复跑 6 个定向模块。它立刻抓出 1 红：`docs/history/archive/MOVED-PATHS-20261019.json` 里的 sha256 是**工作树字节**的哈希，
而 `.gitattributes text=auto` 在 Windows 签出 CRLF、在库里存 LF，于是两份本轮被编辑过的 CSV 在干净签出里
必然与记录不符（同一文件两处哈希相差仅换行符）。修法是把计量基准改成 git blob——
`scripts/ci/verify_stale_surface_paths.py` 新增 `tracked_blob(root, rel)`（`git show HEAD:<path>`），
清单与测试都按 blob 比，并额外断言"工作树文本 == blob 文本（忽略换行符）"，这样跨主机成立的只有"字没变"这一件事。
第二个缺陷同批暴露：重新生成清单会把具名豁免的 `minOccurrences` 退回脚本里手写的旧数（19 与 12），
而实测是 8 与 6，门因此自判 `ALLOWANCE_UNMET`。修法是让生成器写完清单后立刻调用门自己的
`--write-allowances` 以实测覆盖，豁免下限从此是**测量**而不是常量。两处修好后干净签出 16 例复跑 `OK`。

## 13. 2026-10-19 第二批：owner 授权后改指针并删净，AGENTS.md 同批改对

**owner 决定（本轮问答逐字）**：问“AGENTS.md 第 12/16 行仍把已归档的 UI 任务包写成唯一 CURRENT，
是否授权修改这一受保护并行写者文件？”→ **“授权改这两行”**；
问“另外 4 份旧交接因机器指针/代码按路径读取而未删，是否连指针一起改并把它们也汇总删除？”→
**“删文件并同步改指针”**。因此 `docs/current/workflow-assistance/workflow/active-authority-index.md` 第 4 节“归档不删除”的默认约定，
在这两类对象上由 owner 明确覆盖；覆盖是逐次授权，不是新常设规则。

**AGENTS.md**：第 5 节抬头改为“当前任务范围更新（用户2026-10-19明确决定，取代2026-10-09的UI优先范围）”，
唯一 CURRENT 指向 `taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md`，
UI 轮次交接改指 `docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip`（成员名写在括号里、不带扩展名）。仍生效的旧规则（默认主线、手机端不做、
HUD 为桌面浮窗、单写者与隐私规则保持）逐条保留原文，没有借这次改指削弱它们。

**四份指针与两处代码**：删除 `.project/governance/taskpack-authority-index.json` 里
`staticHandoffViews` 的 HERMES-UPDATE-HANDOFF-20260927 视图项与 `frozenTaskCards` 的
WORK-LAB-UI-PROMPT-PACK-EXECUTION-TASKCARD-20261007 卡项；从 `scripts/ci/generate_current_state.py`
的来源清单里去掉那条早就指向 `taskpacks/current/` 的死路径（该项过去靠 `is_file()` 静默跳过，
即“证据源少一份而无人报警”）；`scripts/audit/project_local_citation_audit.py` 里剩下的只是
按名字引用它自己读过的记录，属句子的宾语而非路径，未动。

**归档器必须是累加的（本轮第二次自我缺陷，已修）**：第一批的构建器是“按当前命中重写 ZIP”。
第二批运行时 52 份已不受跟踪，于是它把出厂归档重写成了 6 个成员——**如果当天就提交，52 份的字节
留存承诺会静默失效**。修法：构建器先读出厂 ZIP 与清单，逐成员复核 sha256/尺寸后原字节搬入新归档，
再追加本批命中，并断言成员集合只增不减（缩小即 `ARCHIVE_SHRINK` 中止）；同时把归档自身与它的清单
按名字排除在候选之外（否则 `HANDOFFS-AND-PROMPTS…` 会被自己的命名规则吞进去）。
出厂状态实测：成员 **56**（52 carriedForward + 4 addedNow），内容 **492,296 B**，归档 **268,142 B**，
sha256 `1b1effdf7f80128b4007181dbc7fdb1af01d0776db9ce5f26eb8199d93503347`。
破坏那次重写靠 `git checkout --` 按字节还原后重做。

**豁免随之作废（不是放宽，是收口）**：`AGENTS.md` 的两条具名豁免、
`.project/governance/live-doc-path-exceptions.json` 的两条例外、
`scripts/audit/normalise_doc_citations.py` 的两条 QUOTED_AS_ABSENT、
棘轮基线里 AGENTS.md 的两行——四处都随旧指向消失而失效，按“许可不再被使用即红”的规则删除；
防再索引门的豁免从 8 条收敛到 **4 条**，实测
`STALE_SURFACE_PATHS_PASS scanned=1289 enforced=104 allowances=4 taskpacks/current/error-ledger.json=8 tests/ci/test_project_authority_reference.py=2 tests/ci/test_stale_surface_paths_are_gone.py=10 tests/workflow-assistance/test_project_local_citation_audit.py=1`，棘轮基线 295 → **293 行**。
`docs/history/archive/MOVED-PATHS-20261019.json` 的 consolidation 段同步记下 `keptInPlace={}` 与 12 条 `removedInto`，
必门新增一例：断言这四份既在归档成员里、又不在树上，且机器索引里再也找不到它们的路径。

**§13 之后的面计数（`git ls-files -z` 实测）**：受跟踪 **2,548**；`docs/history/` md **167**（第二批 4 份全在 `taskpacks/history/`，故此项不变）；`taskpacks/history/` **104**；`docs/current/` md **40**；`taskpacks/current/` **4**；仓库根 md **5**。防再索引门 `STALE_SURFACE_PATHS_PASS scanned=1289 enforced=104 allowances=4 taskpacks/current/error-ledger.json=8 tests/ci/test_project_authority_reference.py=2 tests/ci/test_stale_surface_paths_are_gone.py=10 tests/workflow-assistance/test_project_local_citation_audit.py=1`。
**门的一次实质加强（同轮）**：`old_patterns()` 原先只吃移动记录里的 `from`，也就是只盯"移动前的旧路径"。
现在把 `consolidation.deletedPaths`（56 条被汇总删除后的目的地）一并纳入判定，因此"指向一份只剩归档成员的文件"
与"指向移动前的旧位置"同罪——这正是"防止再次索引路径到旧资料上"的下半句。判定分支 48 → **104 条**，
必门 16 → **18 例**：新增一条"种入已删成员路径必须判红"，一条"活树全量不得点名任何已删成员"；
population 断言改成按记录本身重算期望值，不再写死数字，免得清单扩充时门自己先失真。
**同轮另外两处由门先看见的缺陷（已修）**：

- `tests/ci/test_source_pointers_are_current.py` 的 `MATRIX` 常量仍写 `docs/current/` 下那份 CSV。
  该测试断言"漂移探测工具的默认目标必须存在"，所以这不是文字错：默认目标失效 = 这个探测器从此没人会跑，
  行号漂移就会像 ERR-247 那样以"读报错→猜行号→再差一行"的形式回来。改指 `docs/history/archive/` 后 3 例复绿。
  **它是我"手挑模块复跑"的漏洞**：我先前复跑了八个模块就宣称复现完成，而 CI 注册的门是
  `scripts/ci/run_root_governance_suite.py`——它对 `tests/ci/` 做 glob。跑一遍那个发现式作业才把第九个红挖出来。
  结论：复现要跑"覆盖本次改动的那个注册作业"，不要跑"我记忆里的受影响清单"。
- 本文件此前两次把冻结清单的**条目字节求和**写进正文（2,305,855 与 2,304,018），同一会话内就过期两次——
  因为清单每吸收一次上游记录变化就要重发。这类可再生产物的易变数字不该进散文，改为只写条数（158 条），
  求和值以清单自身为准且由 `tests/ci/test_frozen_surfaces_are_intact.py` 校验。

**一条环境红，判明不改**：`tests/ci/test_sidecar_documented_launch.py` 在本机报
`PermissionError [WinError 32] %TEMP%\...\canonical.sqlite`（teardown 删目录时被自己拉起的子进程占着句柄），
同一模块在 CI 的 `integration` 作业为 success。与归档规范化无关，未改产品也未放宽测试。
**账本派生投影确实过期，但我先记错了它的阻塞理由（2026-10-19 按代码实测改正并重发）**：
`tests/ci/test_shipped_projections_are_current.py` 实测 `docs/audits/LEDGER_REGRESSION_COMMAND_TARGETS_2026-10-07.json`
与当前树不一致：`records SHIPPED=274 FRESH=276`、`counts.PATH_GONE SHIPPED=36 FRESH=38`、
`stateDigest 4fc45f59… → 4dc25201…`、"238 PASS 记录"→"240"。差异里属于本轮迁档影响的是 PATH_GONE +2，
属于既有 owner 项的是 ERR-276/277 未随投影发布。
本段原文写的是"唯一重发通道会**同时改写受保护账本**，因此本轮不执行；也不做只改投影不改账本的半套"——
读 `scripts/audit/ledger_regression_command_targets.py` 的写出路径后**这条前提是假的**：投影在 `main()` 里
无条件按 `--audit-out`（默认就是出厂文件）写出，只有账本才需要 `--apply`。于是本轮按"先只读预览、再落地"
重发：预览差异 `changed_existing=0`（没有任何既有记录的断言被改写）、新增行只有 ERR-276 与 ERR-277 两条、
`repointMap` 与 `handAdjudicated` 逐键未变；再由 `scripts/audit/triage_unbound_ledger_records.py` 把
`docs/audits/LEDGER_UNBOUND_TRIAGE_2026-10-07.json` 的 `unboundPass 94→96` 同步追正。受保护账本字节未动
（`git status` 只出现这两份审计）。效果：本轮之前 8 项 CI 红中的 4 项成因消除（标签齐全、两次测量同 digest、
计数分布、未绑定计数），gone-guard 命名项转绿；仍属 owner 的只剩 ERR-276/277 的 `fixedCommit` 绑定
（那是一条"修复在哪个提交"的断言，必须有真实提交才可写）、executor registry pin、DSH 日期合同与派生审计幂等。

## 14. 2026-10-19 晚：界面补齐与两份独立复核（设计对齐 / 重构评审）

**缺口是量出来的**：`apps/observer/frontend/src/contractConformance.ts` 钉住 22 个 v3 快照键，界面源码只消费 20 个——
`artifactHandles` 与 `artifactHandlesSummary` 零消费者，而快照实测已下发 200 行把手（枚举 5024、省略 4824、
敏感名拒 231、剪枝 114、有摘要 40 / 无摘要 160）。补齐后新增门 `scripts/ci/verify_snapshot_keys_rendered.py`
（键清单从契约读，注释与类型声明不算消费）与 `tests/ci/test_snapshot_keys_are_rendered.py`（6 例含 4 例植入反例）。

**两份复核查出、随打磨提交处理的问题**：① 界面文案声称"该生产者不发 surfaceRoot"，与实测相反
（`.project-local/artifacts/standalone-run-20261019/05-artifact-handles-shape.json` 里 surfaceRoot 200/200）；
② `refused` 存在但缺键时打印"核对时丢弃 0"，把"没有这个键"说成"值为 0"，与同文件自述矛盾且无测试；
③ 同物两名（shelf 写"绝对句柄"、新区块写"把手"）与"投影"三义（窗口行数 / 快照下发 / `data-origin=PROJECTED`）；
④ 拒绝卡用整页级状态壳，而拒绝在本仓是长期常态，构成告警疲劳——语义按词表保留，只降呈现强度；
⑤ `apps/observer/frontend/src/views/EvidenceView.tsx` 中 48% 是把手专用代码，拆出
`apps/observer/frontend/src/views/EvidenceHandles.tsx`，并同步
`apps/observer/frontend/src/views/evidenceHandles.contract.test.tsx` 里那条
`readFileSync` 禁写检查（不同步就会静默失效变假绿）；⑥ `apps/observer/frontend/src/lib/evidenceRange.ts`
的链接构造保留清单缺 `handlesSurface`/`handlesDigest`/`palette`，点一下来源就丢过滤。

**我先前的一处臆断被复核纠正**：我看图时说那张卡是"红色故障卡"，取样核实它并非红色（ink 白标题 + primary 蓝图标），
真正的问题是呈现重量而不是配色——结论以取样为准，不以我的目测为准。

**契约不符不止一处（本轮只修了暴露出来的那条）**：`droppedOnVerification` 前端声明 number、生产者发 dict（已改）；
同类还有 `digest`/`digestSource`、`generatedAt`、`orderingRule`、`cost`、`contentIncluded`、`enumerationScope`、
`digestIndex` 的多个子键未进合同，`order` 与 `orderingKey` 两份顺序声明无人核对。门之所以没抓到：
`apps/observer/frontend/src/contractConformance.ts` 把 `artifactHandlesSummary.refused` 列在豁免里，
生成的 schema 对该字段只写 `{"type":"object"}`，而 `Refines` 只检查"手写 → 生成"单向。下一轮把这些字段进 schema，
让豁免行能撤掉。

**两条操作性事实**：`docs/audits/TOOL_INVENTORY_2026-10-07.json` 会引用自己登记的条目，因此新增工具后需
**两次**重测才收敛（本轮 trackedTools 77→78，第一次 `citedByRecords=1`、第二次=2）；
`apps/observer/frontend/src/lib/legacyRoutes.ts` 头注释长期写"23 条"而实测 26 条，已把计数从散文里去掉，
只让表格自身承载数量。

**900 地板 AA 扫描：第一次的绿不算数，补了滚动扫掠才算覆盖到表体**。`scripts/audit/text_legibility_via_cdp.py
--live-backend --all-views --sizes 900` 首跑（无滚动）在两个主题下都是 `LEGIBILITY_GATE_PASS`
（31 泳道、1273 节点、belowFloor=0、aaFailures=0），但逐泳道拆开看，证据泳道只采到 42 个节点、与把手块
相关的只有标题一格——因为采样器按"已画在视口内"过滤，200 行把手表体在 900×600 折叠以下根本没进样本。
所以那次绿只能证明标题与泳道表面合规。给仪器补上**逐屏滚动扫掠**（每个可滚动区域按视口 0.8 高度分步、
每泳道 16 次采样预算、合并去重）并新增两条检查：`no_horizontal_overflow_at_this_width` 与
`scrollable_lanes_gained_nodes_after_scrolling`。重跑后：全局节点 1273→**2676**（light 2678），
证据泳道 42→**120**，其中 32 格是行内单元格、20 格是路径串，全部实测 **12px**，
`aa_failures=0 belowFloor=0`，900px 下 `scrollWidth=900=innerWidth` 且 `offenders=[]`（无横向溢出）。
仍要如实说明：扫描期间静态服务器的 stderr 打出一条连接被重置的 traceback（Chrome 关连接），
不影响判定，但它是日志里出现过的真实内容，不假装没有。**未做**：把手区块的 AA 对比与 900×600 溢出需 CDP 仪器补测后方可作为测量证据引用；
`.github/workflows/work-lab-gate.yml` 注释里的"44 modules"与实测 56 不符——那是 CI 配置，属共享管道，改动等 owner 点头。
