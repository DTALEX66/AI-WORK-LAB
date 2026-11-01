# T1 账本逐任务复核 · 第五项：DL-R5-005

- 观测 SHA：`2796965c4ae69ced985f3894bbaed77c61626894`（本次读回的 `refs/remotes/origin/main`）
- 复核日期：2026-10-07
- 账本：`design-lab/config/task-ledger-r3.json`（**只读**，本次未改任何状态字段）
- 范围：只复核 DL-R5-005 一个任务
- 顶层权威：`/AUTHORITY.md`（DL-AUTHORITY-2026-09-18-R2）→ `.project/governance/authority-index.json` → `AGENTS.md` → 本账本

## 一、任务实况（从账本直接读回）

| 字段 | 值 |
|---|---|
| title | 资产原子版本与完整交付清单 |
| priority / depends_on | P0 / `DL-R5-002`、`DL-R5-004`（两项均已复核） |
| required_axes | implementation / unit / **host_live** |
| 四轴 | 全 `PARTIAL`；implementation 与 unit 共用一条 `r5-005-static-unit-20260928`；host_live、delivery 证据数组**为空** |

acceptance：A1 同名三版本可回退；A2 任一副文件失败无假成功；A3 重开与打包读回可核对；A4 不得遗失链接素材。

**结论：A1 不成立、A2 成立（本记录初稿误判为部分成立，更正见 §A2）、A3 部分成立（被引用的核对工具问错了对象）、A4 未证明。四条轴一律不抬。**
本记录的主要产出是 §四：**两份在仓报表把"存在但不可达"的模块记成了 R5-005 的能力来源**。

## 二、清单字段逐项（这是任务名里"完整交付清单"那一半）

清单结构只有一个：`runtime/bundle_store.py:101` 构造
`{'schemaVersion','primary','files','metadata'}`，且 `verify_bundle` 在 `:64-65` 硬断言键集恰好是这四个。
`metadata` 由调用方给出，唯一真实生产者是 `native_bundles.py:61-69`。

| 要求字段 | 实况 | 依据 |
|---|---|---|
| 原生工程 | **有** | `native_bundles.py:51-53` role `primary` |
| 预览 | **有** | `:53` role `preview`（png/svg） |
| 链接素材 | **半个** | `:54-60` 只取 `request['inputs']`（任务自报的输入），且 `link_relocation='NOT_VERIFIED'`（`:63`）；**PSD/AI 内部的链接不枚举** |
| 字体信息 | **声明值，非观测值** | `requested_fonts` 来自任务意图（`:13-26`、`:64`），并自标 `font_observation='NOT_COLLECTED'`、`font_rights='NOT_REVIEWED'`（`:65-66`） |
| Brief | **无** | 在 `native_bundles.py`/`native_delivery.py`/`native_assets.py`/`runtime/asset_store.py` 中 `brief` 零命中 |
| rights | **一个字符串，不是一条记录** | `rights='NOT_REVIEWED'`（`:63`），没有 rights 登记处查询 |
| 节点模型 | **无** | 发布路径无 `node_model`/`nodeModel` |
| seed | **无** | 发布路径无 `seed` |
| hash | **有** | 成员级 `sha256`（`bundle_store.py:99`）、`job_sha256`/`bridge_sha256`（`native_bundles.py:62,66-67`） |
| Jury 引用 | **无** | `bundle_store.py:4` 只有一句否认："No rights/Jury approval is inferred" |

即 10 项里约 5 项为实，4 项完全不存在，1 项是占位字面量。**任务名里的"完整交付清单"目前不成立**，
而且这一点在 `docs/handoffs/R5-ATOMIC-BUNDLE-2026-09-09.md:3-4` 已被作者自己声明为
"Not R5-005 acceptance"、`:32-36` 逐条列出 Brief/字体/rights/模型/seed/Jury 尚未接入 —— 本记录与它一致。

## 三、逐条 acceptance

### A1「同名三版本可回退」— 不成立（保住了三个版本，但没有任何东西回退）

`asset_store._record_version`（`:113-146`）只递增 `version_no`；原生发布路径里
**没有任何代码把旧 ACTIVE 置 `SUPERSEDED` 或重新指向历史版本**（只有 `UPDATE asset_publication`，
`:371`、`:412`）。读取侧一律是 `MAX(version_no) ... state='ACTIVE'`
（`native_assets.py:29`、`:93-94`；`asset_store.py:155-158`），即"永远拿最新"。
除了用裸 `version_id` 直接下载（`native_delivery.py:36-43`），没有"选择某个历史版本"的 API。

`creative/version_guard.py` / `creative/asset_versions.py` 确有分支与标签，但
**`native_bundles` / `bundle_store` / `asset_store` / `native_delivery` 都不 import 它们**
（本次 grep：只有 `creative/asset_versions.py:55`、`lineage_view.py:133` 两个不可达的引用点）。

最接近的测试 `test_runtime_asset_safety.py:94-105` 证明的是"发布三个版本后重开，三份字节互不相同"——
这是**保全**，不是**回退**；没有任何测试在 ≥3 个同名版本之间做选择。

### A2「任一副文件失败无假成功」— 部分成立，且缺的正是它字面要求的那种测试

真实发布序列（`asset_store.py:306-372`）：journal 写 `PREPARED`（`:337-339`）→ 拷进
`staging/<pid>/` + fsync + hash（`:343-348`）→ **`_after_stage(pid)`**（`:349`）→
开 `BEGIN IMMEDIATE`（`:350`）→ 重新 fence（`:351`）→ 再校验暂存 hash（`:356`）→
`os.replace(stage, final)`（`:363`）→ **`_after_rename(pid)`**（`:364`）→ 校验最终 hash（`:365`）→
写 `asset_version` 行（`:367`）→ `state='COMMITTED'`（`:371`）。
任一门上失败**不回滚，走隔离**：`recover_publications` 把残留 `os.replace` 进 `quarantine/`
（`:404-412`）并标 `QUARANTINED`/`MISSING`。

多文件一致性是靠**把副文件折叠成一个 ZIP 再发布**取得的
（`bundle_store.py:106-120` 打包，`:121-123` 发布 `delivery.zip`），副文件在打包前逐个校验
（`:97-98`、`:118-119`）。所以现有的是**单文件原子性**（`os.replace` 对 `delivery.zip` 原子），
不是"多个磁盘文件一起成立或一起不成立"。

测试侧：`test_bundle_store.py:92-99` 在 `_after_stage` 注入失败并断言 `COUNT(asset_version)=0`；
`test_bundle_store.py:80-90` 是发布后篡改成员的回读；`test_native_tasks.py:514-523` 让预览内容变化而失败。

> **2026-10-07 本条初稿结论错误，已更正。** 初稿写"没有任何一个测试让某一个副文件失败、
> 其余副文件有效并断言不记录成功"，而 `test_bundle_store.py:67-71`
> （`test_wrong_hash_or_escaping_name_never_publishes`）**恰好就是这个形态**：
> 把**副**文件 `preview.png` 的声明 sha256 改成 `'0'*64`、主文件 `native.ai` 保持有效，
> 断言 `ValueError` 且 `COUNT(*) FROM asset_version` 为 0。
>
> 失误机制可复现，值得单独记：**我用"存在性检索"去支撑一个"不存在性断言"**。
> 依据的检索报告按函数名/调用点枚举，未逐个读 6 个测试的断言体；我复验了它**给出的**行号是否属实
> （属实），却没有复验它**未列出**的测试里断言了什么。行号正确 ≠ 结论完备。
> 否定式结论必须由覆盖式检查支撑（读遍该文件全部测试体，或对断言行做全量枚举），
> 这也正是本记录 §四 要反过来防的那类推断。

**更正后 A2 判为成立**（机制：全部副文件在任何落盘动作之前逐个校验，
`bundle_store.py:95-98`，任一不符即 raise，故不可能记录成功；且已有对应测试）。

**A2 仍然存在的真实缺口**（形态很具体，不是笼统"缺测试"）：
1. **校验通过之后、拷贝期间**副文件被改：`bundle_store.py:114-119` 的两个分支
   （`bundle source grew while copying` / `bundle source changed while copying`）**无测试触发**。
   这是唯一能绕过"先校验后打包"的时间窗，也是"无假成功"最该被证伪的地方。
2. 校验阶段失败时**不留 journal 孤儿**：`:65-70` 与 `:92-99` 都只断言 `asset_version` 计数为 0，
   没有断言 `asset_publication` 中不存在 `PREPARED` 行。
> **2026-10-07 缺口 1 与 2 已由 #247 补齐**（纯测试 PR，未改生产文件）：拷贝期两种改动（变大 / 等长换内容）各有独立用例，校验阶段失败另断言 `asset_publication` 无残留且纠正后可重试。两条守卫分别删除后都被检出，并暴露出第三层防线：任一带内守卫被删时 `verify_bundle` 仍会以成员 hash 不符拒绝。缺口 3（候选档案泄漏）保持未动、也未写断言，因为它按 owner 口径才定得了性质。

3. 候选档案泄漏：`bundle_store.py:106` 每次尝试写一个 `runtime/bundle-candidates/<uuid>.zip`，
   失败后不清理。`:105` 注释把它声明为 "project-owned recovery evidence"，
   所以**这是设计意图还是遗漏属 owner 口径**，不由实现侧静默改；
   需要断言的是"泄漏的候选不会被误认成已交付版本"。

### A3「重开与打包读回可核对」— 一半成立，且引用的核对工具问错了对象

"重开读回"有真实证据：`test_image_import_recovery.py:22-53` 证明 rename 之后崩溃会落到
`OUTCOME_UNKNOWN` 而不是成功；`test_bundle_store.py` 有确定性与成员 hash 回读；
`test_service_http.py:114-166` 比对下载字节 hash、篡改返回 409、跨项目隔离。

但被账本当作"打包"一侧的 `design-lab/scripts/verify_workbench_packaging.py` **与 A3 无关**：
它 grep 的是 `workbench.py` 的路由、`build/main.js` 体积、`.gitignore` 与 pyproject 的 wheel/sdist 映射
（`:47-99`）——它核对的是"Python 包能不能装"，不是"交付清单能不能核对"。
把这两件事混为一谈会让 A3 看起来比实际强。

### A4「不得遗失链接素材」— 未证明

枚举点：`native_bundles.py:54-60`（即 `request['inputs']`），再 hash 点：`native_tasks.py:143-144`。
**全仓没有任何完整性断言**（没有计数比较、没有 hash 清单比对、没有 manifest diff）。
若某素材没出现在 `request['inputs']` 里，它不是"被检测到丢失"，而是**根本不在清单里**；
只有当下游恰好按 key 取它时才会以 `KeyError → BUNDLE_EXPORT_UNVERIFIED`
（`native_bundles.py:68-69`、`:94-95`）炸出来 —— 那是偶然暴露，不是核对。
`test_native_tasks.py:468` 断言的是**单输入** fixture 的恰好 4 个成员名。
另有一处硬上限值得记：`bundle_store.py:22-24` 的 `_names` 对**超过 512 个成员直接拒绝**
（同时强制 casefold 去重），所以大清单不是被静默截断，而是在入口被拒 —— 这两种失败模式的处置方式完全不同，
不要按"截断"去设计修复。

## 四、主要发现：两份在仓报表把"不可达模块"记成 R5-005 的能力来源

`reports/current/DEEPSEEK-WORKTREE-DIFF-SUMMARY.md:110`：

> `src/design_lab/creative/version_guard.py` | DL-R5-005, … | rejected-version guard
> supports R5-005's 'no false success' and rollback acceptance.

`:111` 同样把 `interop/delivery_receipt.py` 记为 "the manifest half of R5-005's delivery list"。

两条都经不起可达性检查：

- `version_guard` 没有被原生发布路径 import（§A1 已列 grep 结果）；
- `delivery_receipt` 的全部引用者是 `interop/__init__.py`、
  `test_creative_ledgers.py`、`test_interop_provenance.py`，**发布/打包路径一个都没有**。

也就是说：一份当前报表用任务 ID 作为"归属标签"，把两个各自有测试、但**从未接入 R5-005 数据通路**的模块，
写成了该任务两项 acceptance 的支撑。这类标签式归属的危险在于它可以被后人读成取证 ——
而同一份文件 `:93` 其实自己承认 R5-005 "needs the manifest half before … can claim anything"，
两句相距 17 行，互相拆台。

**处置**：本记录只登记，不直接改那份报表 —— 它是别的工作流生成的 diff 摘要，
删句等于改动别人的取证。正确做法是在 §五 的最小动作里把可达性做成**可机检的断言**：
凡以 `DL-R5-00x` 为归属标签出现在报表里的模块，必须能被该任务的发布路径 import 到，否则不列。
在 (a) 落地前，任何"R5-005 已具备回退能力"的说法都应视为未取证。

（顺带纠正我自己收到的一条二手结论：有份分析称 `test_native_tasks.py:284/:299/:310/:322/:84`
是"只断言函数存在、没有验收价值"的空测试。我逐条读了函数体：那些 `hasattr` 是**实质测试内部的冗余前置守卫**，
同一个测试里真的在断言 `result['asset']==replay['asset']`、状态 `RECEIPTED`、
`asset_version` 计数恰为 1、guard 计数恰为 0。套件不是空的。**不要把这条当缺陷去"修"。**）

## 五、抬升结论与最小动作

**四条轴全部维持 `PARTIAL`。** `host_live` 需要真实 Illustrator/Photoshop 宿主 E3 读回，本次未触碰宿主；
`delivery` 无已交付包验收；`implementation`/`unit` 受 §二（清单缺 4 项）与 §三（A1 无实现、
A4 未证明、A2 仅剩拷贝期窗口与 journal 残留两个具体缺口）约束。

按性价比排序的最小动作（前三项都不需要宿主）：

1. **A2 的两个具体缺口**（更正后范围收窄，见 §A2 缺口 1/2）：
   (a) 副文件在**校验通过之后、拷贝期间**被改 → 断言 `ValueError`、`asset_version` 计数 0、
   且 `asset_publication` 无 `COMMITTED`；
   (b) 校验阶段失败的调用 → 补断言 `asset_publication` 计数为 0（现在只断言了 `asset_version`）。
2. **A4 完整性断言**：给定一个链接素材在 `inputs` 中缺失的场景，断言系统**报告缺失**而不是静默少一项；
   实现上需要一个"声明的链接集 vs 清单成员集"的差集检查（现无）。
3. **A1 回退语义**：要么实现"选择历史版本并置 ACTIVE/旧版本 `SUPERSEDED`"（含同名多版本测试），
   要么把 acceptance 文案改成它实际做到的"三版本保全 + 按 version_id 取回"，
   并由 owner 裁决取哪一种 —— 这属于承诺变更，不该由实现侧静默改口径。
4. **§四 的可达性闸门**：报表生成处对 `DL-R5-00x` 归属标签做 import 可达性校验。
5. 清单补齐（Brief / rights 记录 / 节点模型 / seed / Jury 引用）是**实现工作量**，
   其中 rights 与 Jury 属人工门，不能自动填 —— 与 001/003 记录同一口径。

## 六、诚实边界

- 本次只读：未改账本、未改报表、未运行宿主、未写 `.project-local` 之外的路径。
- §二/§三/§四 的行号在 `2796965c` 上逐条 grep 复验（清单键集 `bundle_store.py:64-65`、
  报表两句 `DEEPSEEK-WORKTREE-DIFF-SUMMARY.md:110-111`、
  `delivery_receipt` 的引用者集合、`test_native_tasks.py:280-292` 的函数体）。
  行号是点状时间戳，改动相关文件后即失效，引用前先复验。
- **本记录自己就犯过一次该防的错**：§A2 初稿把 A2 判成"部分成立、缺关键测试形态"，
  实为已覆盖，已在本条所在文件里更正并保留原文可追溯。教训写成规则：
  **检索报告给的行号属实，不等于它未列出的内容不存在**；要断言"没有 X"，
  必须读完该模块全部测试体（或对断言做全量枚举），不能靠"按名字找调用点"。
- 未改账本、未改他方生成的报表、未运行宿主。§四 的发现只登记不代改，理由已写在该节。
- 既有证据记录 `r5-005-static-unit-20260928` 的 `outcome` 本就是 `PARTIAL`，
  note 自称"非完成声明"；`reports/current/TASK_PROGRESS.json:468-472` 还额外把它标为
  `OUTCOME_NOT_PASS`、`STALE_SUBJECT_SHA`、`SOURCE_CHANGED_OR_MISSING:src/design_lab/native_assets.py`。
  本记录不推翻它，只是把**为什么**逐条落到行号上。
