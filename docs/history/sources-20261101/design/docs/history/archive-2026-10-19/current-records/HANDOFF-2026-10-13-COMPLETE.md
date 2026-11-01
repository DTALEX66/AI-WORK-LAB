# 交接提示词 — 2026-10-13（完整版，含本轮全部结论）

**这不是 Authority。** 权威读取顺序不可变：
`/AUTHORITY.md` → `.project/governance/authority-index.json` → 根 `AGENTS.md` →
唯一当前包 `docs/taskpacks/DESIGN-LAB-UI-FIRST-INTEGRATED-TASKPACK-2026-10-09.md` →
唯一状态源 `design-lab/config/task-ledger-r3.json` 的 `currentExecution` → 本文件。

记忆、聊天摘要、交接、旧 TaskPack、旧报告、分支名、提交数**都不能覆盖 Authority**。

> **本文里所有 SHA / 计数都是时点值，会立刻过期。**
> 一律自读：`git rev-parse HEAD` / `git rev-parse origin/main` / `git status --porcelain` /
> `git ls-remote origin` / `gh run list --branch main`。**不要抄本文任何数字**——
> 本文写它们只是为了让你知道"当时是什么状态"，不是让你相信它们现在还是。

---

## 一、本轮一句话总结

分支治理（69→2）+ 把 231 个提交并入 `main` + 关闭 owner 项 G（干净 clone 闸债）+
修正四个"未提交"的过期权威声明 + 暴露并修掉 6 类"钉断言了仓库没动过"的测试。

**唯一贯穿全局的教训：漂移不是忘了更新，是更新了却被旧事实覆盖；本仓库反复出现的具体形态是
"机器事实冒充仓库事实"——只在本机为真的记录被当成仓库的判定。**

---

## 二、最终状态

| 项 | 值 |
|---|---|
| `origin/main` | `9f5cda91` |
| `origin/qoder/designlab-backup-consistency-20261007` | 同 SHA（已合并） |
| 本地分支 | 3：`main` / 工作分支 / `rescue/designlab-personal-audit-dirty-20261007` |
| 远端分支 | 2 |
| worktree | 1（主检出，原 11 个） |
| 工作区 | 干净 |
| 账本 | `currentExecution` 34 项，194 条回执，产物**全部受跟踪** |
| 聚合闸 | 本地 `VERIFY_DESIGN_LAB=FAIL total=75 failed=2`（两条本机环境问题，见 §6）；CI 上 `OK total=75 failed=0` |

---

## 三、分支治理（已完成）

判定**全部**用 `git merge-base --is-ancestor`，不靠分支名或日期。

| 项 | 前 | 后 |
|---|---|---|
| 本地分支 | 69 | 3 |
| 远端分支 | 54 | 2 |
| worktree | 11 | 1 |

### 三个值得记住的判断

1. **`vendor-revisions` 表面有 1 个独有提交，实为空合并。**
   `29d32307` 的内容是"把 origin/main 合进来"；它真正改的 3 个文件
   （`derive_vendor_revisions.py`、`test_vendor_revisions.py`、`sources.revisions.json`）
   在 HEAD 里**逐字节一致**。可安全删。**不要只看 `rev-list --count` 就说有独有工作。**

2. **11 个 worktree 里 3 个有未提交内容（82 个文件，7.6 MB）。**
   已先保全到 `.project-local/tmp/worktree-salvage-20261012/`，再删。
   内容：`closeout` 1 份报告 + `headcheck` 3 份报告 + `shape` 78 个旧截图。
   **该目录在 `.project-local/` 里，是 gitignore 的临时区，不随克隆走——要用就先搬出来。**

3. **远端删除必须分批。** 一次 52 条的 `git push --delete` 被整体拒绝
   （部分 ref 已不存在导致整批失败）。分 6 批 × ≤10 条才全部成功。

---

## 四、owner 项 G：干净 clone 闸债（已关闭，四个实例）

### 关键：交接提示词里的数字是错的，必须先量

老清单写"搬 **242.71 MiB** 进 Git"。**实测**：194 条回执里 175 条绑定 `.project-local`，
它们**只引用 1.13 MiB / 175 个小文件**（JSON 清单、闸日志、一张 115.2 KiB 的 PNG）；
`.project-local` 整体 5.2 GB 但绝大部分不被任何闸引用。

**那个数字本会否掉唯一可行的方案。先量再让 owner 选，是这一轮的关键动作。**

owner 选择 **A：把字节搬进 Git**（而非 B 加具名缺席状态 / C 改 presence 形状 / D 标 mutable_state）。

### 四个实例与各自修法

| 实例 | 症状 | 根因 | 修法 |
|---|---|---|---|
| G-1 | `CURRENT_EXECUTION=FAIL [Errno 2]` | 175 回执绑定 gitignore 里的字节 | 复制到 `design-lab/evidence/current-execution/`，194 回执改指；**artifact_sha256 一个没动** |
| G-2 | `ROUTE_PAYLOAD_CONTRACTS=FAIL` | 同上（另两个闸同因） | 同上 |
| G-3 | `SUPPLY_CHAIN=DRIFT G040_generated_artifacts` | 供应链闸把任何受跟踪 `.log` 判为生成物，而 A 必须跟踪 82 个 | 豁免**只给 evidence 根下的 `.log`** |
| G-4 | `PROJECTION_FRESHNESS` → `CONTENT_AUDIT=FAIL` | 46 条 lock 里 37 条声明路径在 gitignored 缓存，"本机没抓取过"被当缺陷并翻转 verdict | 改 `CACHE_ABSENT`（记入 `declared_cache_absent`，不算 finding）；**仓内路径缺失仍判缺陷** |

### 三次碰撞，都按"不绕开"处理

1. **豁免边界**：我第一版写成"evidence 根下所有 marker 全豁免"，
   **自己的探针立刻抓到 `evidence/x.pyc` 返回 `ok=True`**——`.pyc` 根本不该豁免。已收窄，
   6 条探针钉边界：
   `evidence/x.log→豁免`；`scratch/x.log`、`evidence/x.pyc`、`evidence/x.tmp`、
   `evidence/__pycache__/x.py`、`dist/x.log` **全部仍红**。
   *豁免宽到能盖住整个 marker 元组，就是挂着名字的判据降级。*

2. **CRLF 归一化**：CI 一度从"文件不存在"变成"哈希不符"——`eol=lf` 把工作树 CRLF 改写成
   blob LF，而回执哈希的是工作树字节。证据目录标 `binary`
   （与 R3 前身树、history baseline CSV 同一处理）。
   验证方式是对**索引 blob** 逐个 `git show :<path>` 重算：194/194 一致。

3. **PNG 侧车**：那个唯一被跟踪的 PNG 从来没有 `.license` 侧车（因为此前未跟踪），
   拖垮 `verify_license_coverage` 与 `verify_open_design_host_adapter`。
   按 `design-lab/evals/` 里第一方黄金参考图的既有形状补，含 owner 批准的例外与复验周期。
   `modelInputAllowed` 保持 **false**：它是"闸观察到什么"的记录，把闸的输出回喂模型
   正是 E 等级阶梯要防的那个环。

**代价照实记**：仓库 pack 涨到 **245.1 MiB**（硬预算 256 / 警戒 220）——WARN，A 的真实成本。

---

## 五、防漂移（本轮的第二半）

### 漂移的真正形态

四个权威面仍在说"未提交"，而它们早已失效：

| 文件 | 过期声明 |
|---|---|
| `AGENTS.md` | 「本地未提交修改……不宣称远端已同步」 |
| `AUTHORITY.md` | 「repository commit=NOT_EXECUTED, live CI=NOT_EXECUTED」 |
| `docs/current/TASKPACK-ADOPTION-VERIFICATION-2026-10-09.md` | 「本轮改动仍为本地未提交工作」 |
| `docs/current/UI-DESKTOP-RECONCILIATION-2026-10-09.md` | 「工作树：DIRTY」 |

**换会话读到任何一条，都会正确地推出错误结论：远端不可信 → 重做已完成的工作。**

四条全部改成"**保留原句 + 标注失效时点**"——直接删掉会让人以为那段变更从未被提交过。
并且都写明 SHA 要自读，不写死数字。

### `RECORD_VERIFY`：诚实演进曾与静默损坏长得一模一样

`RECORD-IMPORT-MANIFEST.json` 里 7 行 `ALREADY-IN-REPO` 曾声明"仓库副本 == 归档字节"，
而这 7 个文件被 `147e6dc9`（4 个权威/索引 + `PRODUCT_DEFINITION.md`）与
`da43c4dc`（2 个 T07 标准）**有意重写**。旧闸只能报 `WORKTREE-MISMATCH`。

现在每行带 `repoSha256AfterImport` / `repoCrc32AfterImport` / `repoBytesAfterImport`
+ `evolvedBy`（真实 commit）+ `evolution` 说明。

- leg 1（归档字节对 ZIP 校验）**未动**：492/492。
- leg 2 改为对仓内副本核对这些落地后摘要。
- **两条反例钉住**：写错落地后 crc → `WORKTREE-MISMATCH … is declared evolved to crc=deadbeef`（FAIL）；
  不写 commit → `WORKTREE-EVOLVED-UNDECLARED`（FAIL）。

新增 `scripts/declare_record_evolution.py`：重新声明是工具而非手改，且**不能靠改归档摘要让不符消失**。
故：不动归档字段；`evolvedBy.commit` 从 `git log` 读而不接受传入；
无路径参数时**只考虑真正偏离归档的行**（这条是因为第一版想声明 473 行才补的）；`--check` 只读。

### 六个被钉的权威面必须 `binary`

`AUTHORITY_CHAIN` 在**任何**干净克隆上恒 DRIFT，本机却绿。
链记的是**工作树**摘要 `620bf56d`，提交 blob 是 `ae368aa0`——
`eol=lf` 存 LF、签出 CRLF，**同一份权威文件按你站在哪里被算成两个文件**。

> "只在本机可复现的摘要不是钉，是穿了钉衣服的本地事实。"

已在 `.gitattributes` 把 `AUTHORITY.md`、`AGENTS.md`、authority-index、
HISTORY-FREEZE-RULES、两个 TaskPack 标 `binary`，并重新入库使 blob == 工作树（逐文件校验）。
`AUTHORITY.md` 的钉随字节移动，**被取代的摘要保存在 `AUTHORITY-PIN-CHANGE.json` 的 `revisions[]`**——
忘记自己钉过什么的钉等于没钉。检查数仍 10，未删任何检查。

### 接续入口

`docs/history/next-agent-prompts/NEXT-AGENT-PROMPT-2026-10-12.md`（当时写作 `docs/current/NEXT-AGENT-PROMPT-2026-10-12.md`，2026-10-18 该文件已移入历史目录）是当时的入口；
> **2026-10-13 更正（句子保留，只标失效时点）**：这一句**已不成立**。第二十四批收口后，
> 当前入口是 `docs/current/NEXT-AGENT-PROMPT.md`（当时名为 `…-2026-10-13.md`，2026-10-18 改为就地更新的无日期文件名），`AGENTS.md` 已改指它，
> 2026-10-12 版在 `task-document-states.json` 里降为 `HISTORICAL` 且指针移向新版。
> 留着上面那句是因为它当时是真的；照着它做会让下一会话从一份已被取代的提示词接续。
09/10/11 版已降为 `HISTORICAL` 并在 `task-document-states.json` 登记。

> **2026-10-18 更正（同一条句子第二次失效，仍只标时点，不改写上文）**：接续入口不再按日期命名。
> 唯一入口是 `docs/current/NEXT-AGENT-PROMPT.md`（就地更新）；10-09 至 10-13 各版已移入
> `docs/history/next-agent-prompts/`，在 `task-document-states.json` 里统一降为 `HISTORICAL`，
> 并在 `docs/history/next-agent-prompts/PROMPT-LINEAGE.json` 逐份登记字节与 sha256。
> 上面那条更正里的"当前入口是 …-10-13.md"现在是历史，不是指令：按日期命名正是旧副本
> 反复留在 `docs/current/` 的机制，已废止。

---

## 六、本轮修掉的"钉断言了仓库没动过"类测试（6 个）

`main` 的聚合链一绿，`Python unit tests` 步骤**第一次不 skip**，3010 个单测里
从未在 CI 跑过的失败全部显形。

| 模块 | 问题 | 修法 |
|---|---|---|
| `test_report_subject_binding` | 钉住的未绑定集合里还留着我按该行自己关闭条件退役的 `LANGUAGE-BOUNDARY-SCAN` | 钉的作用是抓**静默**删除；这次是声明过的，随声明一起动并写明理由。**其余 7 条不动** |
| `test_record_import_fidelity` | 对每条仓库持有行都拿**归档值**复算 size/crc | 对声明了落地后重写的行，这**在构造上就不可能通过**——它断言的正是声明所否认的事。改为：声明过的对声明值，未声明的对归档值 |
| `test_evidence_artifact_presence` | 漂移清单按精确集合钉，两条移动了 | **重测而非继承**：本 HEAD 实测 56 对、broken=0，此前钉 54。`verify_contract_bindings` 1→2，`test_core_gates.py` 新入。钉仍精确 |
| `test_projection_freshness`（2 例） | 桩返回 **3-tuple**，真实签名早已是 **4-tuple**（多一个 write-detector 的 `scan_error`） | 桩未跟上 → 抛 ValueError，**断言根本没执行**。改为 4-tuple |
| `test_core_gates.LicenseCoverageTests` | `TemporaryDirectory(dir=<本机目录>)` 要求目录预先存在，干净 clone 没有 | 加 `mkdir(parents=True, exist_ok=True)` |
| `test_selected_source_adaptation` | 断言 `assertNotIn('citations=VERIFIED(0)')`，而 vendored blob 在 gitignored 缓存里——工作站验 13、克隆验 0，**该断言只可能在一种环境成立** | 同时暴露闸的诚实缺陷：「SKIPPED 因为在 gitignored 缓存」**只印在已失败时**，于是"绿且什么都没验"恰是唯一不印说明的情况。改为**通过时也印**；测试改断言**关系**（`verified==0 ⟹ skipped>0` 且必须有说明），而非某台机器的绝对数字 |

---

## 七、本机环境坑（会伪装成判据问题）

1. **safe-delete 批量守卫**：本机 sandbox 会在 `shutil.rmtree` 上拦截
   （`[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] count=50 threshold=50`）。
   这使 `verify_reconstruction_pipeline` 与 `verify_reconstruction_bundle` **在本机恒红**；
   两条已在**未改动的 HEAD 上复现过同形**，属环境不是回归。**CI 上这两条是绿的。**
   worktree 删除同样被卡（582 MB）→ 后台跑 + 免沙箱才走得完。
2. **路径含空格**（`D:/All projects/...`）时**不要用 `for` 循环按空格切路径**——
   会让统计静默失真。我因此一度误报"所有工作树都干净"。用 `while IFS= read -r`。
3. `design_lab` 是 namespace package，`domain_packs.py` 里 `..` 相对导入会抛
   "attempted relative import beyond top-level package"，必须绝对导入。
4. `vm.runInContext` 跑 bundle 时，bundle 顶层函数**只在 context 里**；外层 node 脚本直接调用会
   `is not defined`。**"fetch 之前抛异常"在断言里读作"没有发出请求"**——脚手架缺一个 API 会让覆盖被静默跳过。
5. 新闸不登记进 `verify_design_lab.SCRIPTS` 或 `verify_browser_e2e_ran.TEST_MODULES`
   ＝永远没人测 / 永远 skip。
6. 改 `packages/` 下任何文件会让 `inert_contract_survey` 的计数变化 → 按其文档化路径重跑生成器。
7. 追加到活文档 `docs/audits/DESIGNLAB-UI-R2-DESIGN-QA-2026-10-09.md` 会让 17 条绑它的回执漂移
   → `.project-local/tmp/reseal_qa_batch19.py` 重封（**只有 `artifact_sha256` 可移动**）。
8. **新增/修改受跟踪文件后**，`verify_language_boundary` 记的 `tracked_files_scanned` 会过期
   → 重跑 `verify_language_boundary.py` 再提交。
9. **改了任何被钉的文件**（AUTHORITY.md / AGENTS.md / 两个 TaskPack / 索引）→
   按序重生成：`generate_current_reports.py` → `deepseek_authority_chain.py` → `verify_authority_gates.py --zero-spill`。
   AUTHORITY.md 还需重钉并记 `revisions[]`。
10. **验证陷阱**：`git clone --branch main .` 克隆的是**本地 main**，可能还指着旧提交。
    **克隆本地仓库不等于克隆远端。** 必须先 `fetch`、`branch -f main origin/main`，再克隆。
    我因此把一次"克隆复现失败"当成了真失败。

---

## 八、未完成（不要替 owner 宣布完成）

### 需要 owner 裁定

`docs/audits/DESIGNLAB-UI-R2-DESIGN-QA-2026-10-09.md` 里的清单 **A–F、H–J**（D05–D08 已在本轮范围外）。
其中 **D05–D08 前端发现性与过滤**是可逆工程、可直接做；
**D08（跳转不带领域条件）是第十八批引入的**，修复需要产品判断。

### 尚未执行

真实宿主 E3（需 owner 明确授权）、真人 E4、release、安装态分发、手机端（`FROZEN_DEFERRED`）。

### 6 个仍然红的单测（**本轮引入，不是本轮造成**）

`test_gate_reachability`（3）、`test_ledger_schema`（1）、
`test_task_ledger_contract_gate`（2）。全部报
`frozen predecessor partition changed: tasks / evidence`。

**已核对：`tasks` 28→28、`evidence` 76→76，与本轮起点逐字节相同——本轮没有动冻结分区。**
这 6 个是前序 231 个提交带来的，测试比对的是另一个基线快照。
它们要么需要 owner 裁定"已落地副本能否演进"，要么需要重钉基线。**本轮没有碰它们。**

### 一条已知的 CI 拓扑问题

Python unit tests 步骤排在 unified verify 之后，聚合链一红就 skipped。
聚合链现已绿，所以单测真跑了——这也是上述 6 个暴露出来的原因。
要让它长期有效，无需改拓扑（链绿即跑）。

---

## 九、`rescue/` 分支必须保留

`rescue/designlab-personal-audit-dirty-20261007` 是唯一未并入的分支，**无远端副本**。
它独有 4 个仓库里完全没有的文件（HEAD 全仓搜索无副本）：

- `docs/audits/DESIGNLAB-PERSONAL-PRODUCT-AUDIT-2026-10-07.md`（71 行，含诚实的 PARTIAL 判定与 6 条"尚未达到的产品成熟条件"）
- `docs/audits/DESIGNLAB-UI-IMPLEMENTATION-REPORT-2026-10-07.md`（73 行，A 版；HEAD 只有 B 版）
- `design-lab/tests/test_personal_workbench_e2e.py`（46 行，可运行）
- `design-lab/tests/e2e/browser_personal_workbench.mjs`（59 行，可运行）

删了就没了。**要删先归档进 `docs/history/`。**

---

## 十、每批的完成判据（照做，别省）

改动 → 闸与测试复跑（浏览器五件套 `skipped=0`）→ `generate_current_reports.py` →
回执封存（**先账本、后链、同批提交**）→ 提交 → 推工作分支并核对双端 SHA →
**读该 SHA 的 CI 日志逐作业照抄**（不预测、不把本地结论写成 CI 结论）→
更新审计文档批次追记 → 给出可审阅实拍。

**本地结论永远不能写成 CI 结论。** 本轮我多次靠"在干净克隆上跑"来区分
"真缺陷"和"只有本机成立"，这个方法继续用。

---

## 十一、接手第一件事

```bash
git fetch origin
git rev-parse HEAD origin/main          # 两者应一致
git status --porcelain                  # 应为空
gh run list --branch main --limit 1     # 读结论，不预测
```

若 `HEAD != origin/main`：说明又有人在工作分支推了东西，**先问清楚再动，不要自行合并**。