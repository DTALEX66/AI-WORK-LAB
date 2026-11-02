# AIWORKLAB / AI-WORK-LAB — 当前状态（唯一顶层入口）

**WORK-LAB + DESIGN-LAB 已合并为 AIWORKLAB / AI-WORK-LAB。旧名称只用于历史追溯与迁移兼容，
不再是两个并行维护的产品，也不再各自持有生产权威。**

本文件是薄入口：只给结论、关键未完成项与可到达的链接。数字一律指向下方"唯一维护位置"里的
登记表，不在这里复制维护；本文件的每个数字都由 `scripts/check_project_current.py` 与寄存器
现值比对，对不上即为红。

- 最近核验：2026-11-01（本地，不联网）
- 依托提交：`cc4155f`（分支 `integration/local-fusion-20261029`；本行写的是全量收据所测的那棵树，本文件这次修订在它之后的提交里）
- 远程：`DTALEX66/AI-WORK-LAB`，分支 `integration/local-fusion-20261029` 已推至 `a490f7c`
- 入口三件套：本文件 + `README.md` + `AGENTS.md`（同在本仓根目录，读序见 `AGENTS.md` §1）

<!-- entry-figures:start -->
acceptance_blocked_by_boundary = 2
acceptance_confirmed = 41
acceptance_deferred_p3 = 3
acceptance_partial = 2
archive_excluded_raster_media = 344
archive_import_verified = 1131
archive_in_repo_bytes = 217126876
archive_in_repo_objects = 694
archive_manifest_rows = 7210
archive_objects = 1212
archive_recorded_not_copied = 93
archive_registered_not_migrated = 80
archive_source_hints = 1212
archive_unclassified_residue = 1
archived_excluded_cache_and_build = 515
archived_linked_in_archive = 11
archived_linked_in_repo = 1108
archived_objects_copied = 5270
archived_objects_duplicated = 306
authority_index_entries = 23
blocker_items = 7
byte_copy_rows = 1234
capability_families = 30
capability_implemented_verified = 18
capability_partial = 12
crlf_tracked_files = 116
distinct_paths_design = 4055
distinct_paths_union = 6774
distinct_paths_work = 2734
lf_tracked_files = 702
route_endpoints = 164
source_rows_design = 4476
source_rows_total = 7210
source_rows_work = 2734
spdx_claimed_files = 223
spdx_malformed_lines = 0
suite_test_files = 34
suite_test_nodes = 497
task_acceptance_clauses = 48
unsettled_files = 237
<!-- entry-figures:end -->

上面这段不是手抄的：它由 `.venv/Scripts/python.exe -B -X utf8 scripts/check_project_current.py --write-block`
从寄存器现算并写回（派生值没变时报 `UNCHANGED` 且零字节写入），`--check` 逐条比对；
对不上就是红，不做"大致没错"。

## 一、现在成立什么

- 单一融合后端：统一信封、统一存储、只读验收门；两套旧生产权威已不是并行入口。
- 历史资产去向已逐条登记：来源仓逐仓去重的不同路径数、跨仓并集、总行数与本项目按字节持有的行数，
  一律取下方现算数字里的 `distinct_paths_work`、`distinct_paths_design`、`distinct_paths_union`、
  `source_rows_total`、`byte_copy_rows`，处置枚举与实际行值的差集为 0。
- 置顶区已立：根级 `AUTHORITY-INDEX.md` 收 `23` 条 2026-10 当时两仓各自的"任务·规划·权威索引"，
  原件逐字节复制进 `docs/authority-202610/`；每条记来源仓、原路径、版本或日期、SHA-256、字节、
  现在的定性与替代关系。检查器会**重算每个原件的摘要**并与表里记的比对，摘要一旧就红。
- 历史区已迁入：按 owner 规则（缓存与构建不要、其他按历史/文档归档进本仓）把来源内容复制进
  `docs/history/sources-20261101/`，逐条去向在 `MANIFEST.csv`（行数 = `archive_manifest_rows`，全覆盖）：
  逐字节复制 = `archived_objects_copied` 行、同字节去重指回已复制件 = `archived_objects_duplicated` 行、
  本仓已按字节持有 = `archived_linked_in_repo` 行；
  `123` 张截图与照片（64,092,364 字节）按 owner 2026-11-01「截图照片去掉」移出 Git，先搬进本机隔离区；
  owner 2026-11-02 又裁定「历史记录归档 文档形式归档就行 去掉其他格式的」，于是**这类二进制连隔离区也不再留存**——
  本仓保留的是摘要与逐条登记（`linked_location` 已清空并在 reason 里写明原因），删除时点这些原件的其余副本
  只在来源仓自己的对象库与工作树里，来源仓一旦删除即无第三份。`38` 个 SVG 是图形不是照片，仍按文档留仓。

  `EXCLUDED_BY_OWNER_RULE` 的 `515` 行由三部分构成：`390` 行缓存/构建、`123` 行截图与照片
  （64,092,364 字节）、`2` 个字体二进制（17,313,940 字节，曾进隔离区，现随"去掉其他格式"一并移除），
  移动前后各现算一次摘要。另有 `archived_linked_in_archive` 行原来只记成"与统一归档逐摘要相同、
  不搬第二份"——本轮（2026-11-02）现算过：文档格式的那些行已把同一字节补采进历史区，或改记成指向仓内原件的
  别名；剩下的 `archived_linked_in_archive` 全是容器包、Word 文档与一张位图，按「去掉其他格式的」继续只留摘要、
  字节与位置。第二遍自己抓出的三处错法（扩展名白名单漏了 SVG 与无扩展名 JSON、同摘要别名仍记成外部链接、
  `LINKED_ARCHIVE` 的登记摘要属于归档根对象而不是来源仓同名文件）逐件记在 docs/CODEX-AUDIT-ENTRY.md §15.25。
  三处缺陷都是复验时抓到并修好的：`37` 行原判"本仓已持有"只凭台账 `sha256_source`，而改后文件让
  本仓实际持有的是修复版本、原始字节无处可寻（已补采并逐行复验摘要）；`1` 个 260 字符以上的
  长路径文件首轮静默丢失（已用 `\\?\` 前缀重写，并按行复验，不再用集合式抽查）。
  第三处是本轮按 blob 逐分支头核对抓出的：来源仓一条特性分支上有、`main` 上没有的一份
  reduced-motion 契约测试，导入按工作树走时它不在磁盘上，所以既没进本仓也没进登记——
  台账 `2639` 对登记表 `2638` 那一行差就是它（DESIGN-LAB 的 7 个分支头 `0` 缺口）。
  已从来源对象库按 blob 补采进仓并登记摘要，它在融合仓的位置是
  `docs/history/sources-20261101/work-branch-feat-ledger-truth-20261027/apps/observer/frontend/src/reducedMotion.contract.test.ts`
  （来源侧路径与 ref 记在同一行的台账与登记里，不在这里当本仓路径引用），
  登记生成器的人群口径同时改成"工作树 ∪ 台账"，并把这条不变式的反例改为读现值而不是记死数字。
  同一次核对里"950 / 151 个摘要对不上"不是缺口而是版本差：那是被后续版本覆盖的中间态，只存在于镜射里，
  路径集合比对之后确定的未吸收代码就是这个文件。
  第四处不是复制缺陷而是**人群口径的盲区**：覆盖登记枚举的是来源仓的工作树（跟踪 + 未跟踪但未被忽略）
  与归档台账，而来源仓自己 `git-ignore` 掉的路径两边都不在——所以 `--plan` 报 `unmanaged 0` 时，
  `.ui-reference`、`.hermes`、`.workbuddy` 这些目录里的内容其实从未被任何登记表称过。本轮按"除 `.git`
  之外的每个文件"重扫两仓，先按扩展名与路径规则分桶（构建与缓存、位图、其他格式、文档），只给文档桶算摘要，
  再和登记表现值做联合判定：**登记行都没有的 101 个**、以及**台账只链到统一归档根的文档件**，一起补采进
  `docs/history/sources-20261101/`，写后逐个现算摘要复验，台账改记 `COPIED`；已按具名规则处置的行
  （构建/仓库元数据、或本仓持现行版的版本差）不动，因为摘要不同 ≠ 内容缺失。落盘前对补采字节做过凭证形态扫描，
  命中 0 处。分桶读数与逐件清单一律取 `docs/history/sources-20261101/MANIFEST.json` 的
  `source_ignored_sweep_20261102` 块，不在这里抄第二份。
- 统一归档的正文对象也已进仓，防的就是"任务漂移"：`1212` 个唯一对象现在**每一个都有具名去处**，
  不再有 `ARCHIVE_ONLY` 这种"没决定"状态——`694` 个（`217,126,876` 字节）逐字节进
  `docs/history/archive-objects-20261101/`、按摘要命名、写后现算复验（失败 0）；`93` 个容器包
  （513 MB，其中最大一个 **135,878,909 字节已越过 GitHub 单文件 100MB 硬限**，push 必被拒）
  不入 Git 但逐个记摘要+字节+成员数+位置；`344` 个位图媒体按「截图照片去掉」排除。
  这条不变式由检查器守：出现未知处置、`ARCHIVE_ONLY`、或"标了进仓却不在盘上/摘要不符"，直接红。
- 顶层每个目录都必须在入口三件套里被说明（`ROOT_DIR_UNDOCUMENTED`），未说明即红——
  一个没人解释的目录就是下一个 Agent 靠猜的地方。
- 统一归档（`D:\All projects\Project Archiving`，只读）与本仓已逐摘要对账：`1212` 个唯一对象中
  `1131` 个**只在归档里有一份副本**（约 `1.06 GB`），`80` 个已登记但未迁入，`1` 个停在未归类；
  本仓 `migration/copies.json` 的 `962` 个来源摘要与归档对象摘要**交集为 0**——两边的字节不是同一批。
  逐条见 `migration/archive-object-reconciliation-20261101.csv`。
- 机器可核证的验收与追溯：`migration/task-acceptance.csv`（48 条验收子句）、
  `migration/capability-family-register.csv`（30 个能力族）、
  `migration/audit-item-closure.csv`（A/F 审计项闭环）、
  `docs/CODEX-AUDIT-ENTRY.md`（含逐轮实测与收回记录）、`docs/AUDIT-STATE.json`。

## 二、尚未成立（不要当成已完成）

| 类别 | 现状 | 权威位置 |
|---|---|---|
| 能力验证状态 | `IMPLEMENTED_VERIFIED` 与 `PARTIAL` 并存，PARTIAL 每条都写明缺什么 | `migration/capability-family-register.csv` |
| 验收子句 | `CONFIRMED / PARTIAL / BLOCKED_BY_BOUNDARY / DEFERRED_P3` 分列，不合并计成"通过" | `migration/task-acceptance.csv` |
| 待裁决来源 | `237` 个文件停在 `REGISTERED_GAP` / `OWNER_DECISION_PENDING` | `migration/source-unsettled-groups-20261101.md` |
| 阻断项 | 验收门 `REFUSED`，blocking `L10#0`（owner 决定队列） | `config/blocker-register.json`、`docs/AUDIT-STATE.json` |
| 界面（STITCH 前端） | 未做：本批只做本地后端 | `migration/ui-entry-disposition.csv` |
| 真实宿主写入 / 模型推理 / 真实私有数据迁移 / 真人专业验收 | `NOT_RUN`，按边界如实记录 | `docs/CODEX-AUDIT-ENTRY.md` §5、`migration/deferral-register.json` |
| 系统级出站隔离 | 未证明（无防火墙/沙箱配置；云端会话模型上下文可离开本机这一限制仍成立） | `INTEGRATION_POLICY.md` §2 |
| workbench bundle | 无法重建（缺 `picomatch`，需网络安装，未授权），两个读 bundle 的 JS 闸门仍校验旧字节 | `docs/CODEX-AUDIT-ENTRY.md` §15.22 |
| 顶层入口自身 | 本文件与 `README.md`、`AGENTS.md` 是本轮新建；`HEAD 2312963` 那 `2 failed` 已全部定位并各自修好（`test_v16…does_not_relamp_them`：寄存器里一个行号指针随 `migrate_sources.py` 漂移，重发布；`test_v23…machine_independent_part`：台账查键只按本机绝对根剥前缀，克隆里剥不出来，改为按路径结尾取且要求唯一）。收据已在这两个修复之后重取：现记 `499 passed / 0 failed / 0 errors`，绑在 `94dd47c`（摘要 `1467eeaea846ac08…`），改绑之后只有 `docs/` 与 `migration/` 的字节的动过 | `.project-local/audit/20261031-fullclosure/CLOSURE-STATE.json`、`docs/CODEX-AUDIT-ENTRY.md` §15.23 |
| 归档原件的唯一副本 | `1131` 个对象（约 `1.06 GB`）目前只在统一归档里有；归档自己的 `完整性校验报告.json` 仍写 `source_file_set_unchanged: true`，而它点名的 `2031` 条来源路径现在**一个都不存在**（`D:\All projects\Record` 已消失，`xiangmuguidang` 是空目录）——那句话对今天的磁盘已不成立，归档不可再被当作可清理的副本 | `migration/archive-object-reconciliation-20261101.csv`、`_归档管理\完整性校验报告.json` |
| 删掉两个来源仓之后本仓还能不能独立跑 | **已实测，且本轮重测过**（受控对照，head `86a0642`）：control 65、treatment 67，delta 恰 **2** 个节点、无反向变绿（上一轮同一方法是 **15**）。差额 13 个的来源：12 个是共享 fixture `work_project` 指向宿主机 WORK-LAB，改指仓内 `tests/fixtures/live-work-root/`；1 个是来源根缺失时 `build_audit_state` 崩溃而不是给具名结论。剩下这 2 个——`test_backend_boots_twice_and_recovers_the_orphan`（真实进程重启）与 `test_design_task_definition_pointers_match_their_bytes`（断言对象就是来源仓那批字节）——按其语义本就是本机前提，所在文件自身写着来源路径，`test_v23` 把它们归入 machine-bound 并**点名**，而不是删断言换绿。另一件与本轮无关但必须知道：**全新克隆跑不了全量套件**（control 那 65 个就是它），由 `未在本机测量` 的点名机制承担 | `.project-local/runs/independence-20261102.json`（上一份 `independence-20261101.json`，head `2477d7b`，delta 15） |

## 三、证据分级（不拼接旧成绩）

| 级别 | 本次状态 |
|---|---|
| 文档 / 登记 | 已核：登记互相勾稽，7 台生成器 `--check` 全 rc=0 |
| 代码 | 已核：静态与反例断言在套件内 |
| 构建 | 部分：Python 侧可导入安装（离线隔离安装 PASS，见 `config/isolated-install-verdict.json`）；`apps/workbench` bundle 不可重建 |
| 运行 | 已核：164 端点逐路由实测（`migration/route-surface.csv`），loopback HTTP |
| 外部 Agent / 宿主真实往返 | 未做：`NOT_RUN`，不拿合成回执冒充 |
| 迁移恢复 | 已核（合成夹具与副本）：崩溃注入下旧字节不被半写；真实私有数据迁移仍 `NOT_RUN` |
| 安装态 | 已核：wheel 安装后读回通过，含随包发布的领域包校验器可载入 |
| 用户验收 | 未做：真人专业签字是 Human Gate，不由 Agent 代签 |

## 四、唯一维护位置（防止出现第二套当前权威）

| 内容 | 唯一位置 | 其他文件只做 |
|---|---|---|
| 项目身份与当前结论 | 本文件 | 引用，不改写口径 |
| 能力族与验证状态 | `migration/capability-family-register.csv` | 链接 |
| 验收子句逐条状态 | `migration/task-acceptance.csv` | 链接 |
| 来源文件去向（含未迁原因） | `migration/source-coverage-work.csv`、`migration/source-coverage-design.csv`、`migration/copies.json`、`migration/archive-object-reconciliation-20261101.csv` | 链接 |
| 阻断与延期 | `config/blocker-register.json`、`migration/deferral-register.json` | 链接 |
| 端点面实测 | `migration/route-surface.csv` | 链接 |
| 审计项闭环与逐轮实测 | `docs/CODEX-AUDIT-ENTRY.md` | 追加小节，不改写历史 |
| 执行边界与授权沿革 | `INTEGRATION_POLICY.md` | 定点放行，不整份重写 |
| 统一归档原件 | `D:\All projects\Project Archiving`（**只读**） | 只引摘要，不整包复制、不反向清理 |

## 五、下一步

1. ~~定位并修掉 `2312963` 上那 `2` 个失败~~ 已修；~~重取全量收据并改绑登记表~~ 已做并于本轮重取：
   收据 `1467eeaea846ac08…`（`499 passed / 0 failed / 0 errors`，绑 `94dd47c`，跟踪树开始时干净且
   全程 `tracked_bytes_moved_during_run` 为空），`migration/audit-item-closure.csv` 的四个收据列
   与 `docs/AUDIT-STATE.json` 一起改绑，七台生成器 `--check` 全 rc=0。判据口径也在本轮改掉：
   原先要求收据点名 HEAD 本身，而改绑与渲染小节必然产生其后的提交，于是它永远停在 `PENDING`；
   现在是"收据的提交是 HEAD 的祖先，且其间每个动过的跟踪文件都是文档或生成登记表，逐个点名"，
   代码或测试出现在那个区间就是 `FAIL`——这条收紧本身有一段死代码，被新加的 6 个反例节点抓出来。
2. owner 对 `237` 条待裁决来源做批量判定（含 32 条阻断 `L10#0` 的）。
3. ~~统一归档 `1212` 个对象与融合仓的逐摘要对账~~ 已建成 `1212` 行逐条登记；
   ~~那 `1131` 个只在归档里的对象要不要按摘要迁入本仓~~ owner 已定（「确保内容全部归档到仓库」）：
   `694` 个正文对象（`217,126,876` 字节）已逐字节进仓并复验摘要，`344` 个位图按「截图照片去掉」排除，
   `93` 个容器包只登记摘要与成员数（最大一个 135.9 MB 超 GitHub 单文件硬限，进仓即无法推送）。
   ~~那 93 个包的长期去处待定~~ owner 2026-11-02 的「文档形式归档就行 去掉其他格式的」已经把这条裁掉：
   容器包属"其他格式"，不再考虑进仓，原件继续留在只读的统一归档里，本仓只保留摘要、字节数与成员数登记。
4. 界面与外部宿主往返仍需新的明确授权；在那之前保持 `NOT_RUN`。
5. **删除两个来源仓之前必须先回答的三件事**（本仓不替 owner 决定，也不会在未授权时动手）：
   - ~~来源仓 `.git` 历史与 LFS 载荷的镜射要指定长期去处~~ 已按 owner 2026-11-02
     「历史记录归档 文档形式归档就行 去掉其他格式的」裁定并执行：本机 `.project-local` 下的
     非文档格式镜射全部移除（`2` 个 tar 共 5.07 GB、`2` 个全 refs bundle 0.50 GB、来源仓 `.git`
     pack 副本 0.74 GB、LFS 载荷与运行库 0.32 GB、位图与字体隔离区 81,406,304 字节），
     清单在 `.project-local/runs/format-cleanup-20261102.json`。**删除时点的存活副本**是两仓各自的
     `.git`（各 3 个 pack、`96`/`23` 个 ref、LFS 对象库都在）与各自的 GitHub 远端；因此
     "删掉来源仓之后还能不能找回 git 历史"的答案现在是**不能**——历史以本仓的文档形式归档与逐条
     摘要为准，这正是该裁定选择的取舍，不是疏漏。
   - `237` 条待裁决来源与 `1131` 个归档唯一副本，删了就没有第二次机会；先判定再删。
   - **与两个原仓的切割已完成并被静态证明**：运行面与测试面（`backend/`、`domains/`、`packages/`、
     `apps/`、`tests/`）里**没有任何一处再写出那两个仓的绝对路径**；上一轮留下的最后两个真实依赖
     （`test_v22` 用来源仓字节做主体、`test_v17` 把项目注册到宿主 WORK-LAB）已分别改绑到仓内原件与
     仓内 fixture 根。仍写出这些路径的只剩 `scripts/` 里的 5 台迁移生成器——它们的职责就是读来源，
     来源不在时必须给**具名结论**而不是崩溃或假绿（覆盖登记给 `SOURCE_REPO_ABSENT` / rc=3）。
     删除来源仓后还有一件事必须做：覆盖登记里那 `archived_linked_in_archive` 行现在记的是「统一归档根下
     的原件本轮复验一致」，那个根一旦被删，这些行的证据必须由重发布改成「本机不存在、未复验」——
     `build_source_coverage --check` 会在重发布之前拒绝，这条线是被守卫的，不是靠记得去做。
   - 本仓的独立性以 §二 最后一行的实测结论为准；凡是依赖来源仓的测试都会显式点名前置，
     不会静默跳过或报错伪装成通过。
