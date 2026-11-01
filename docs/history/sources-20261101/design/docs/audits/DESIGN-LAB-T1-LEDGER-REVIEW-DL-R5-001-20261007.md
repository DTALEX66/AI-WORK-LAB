# T1 账本逐任务复核 · 第一项：DL-R5-001

**复核对象**：`design-lab/config/task-ledger-r3.json`（唯一任务状态编辑源）中的 `DL-R5-001`
**观测 exact SHA**：`main` = `origin/main` = `3f2842c513a58b41e790de45dfb2c052a85473d5`
**观察窗口**：2026-10-06T16:07:14Z – 16:19:00Z（`date -u` 首末各读一次；本地 2026-10-07 00:07–00:19）
**结论**：四条 acceptance 中 3 条满足、1 条按其原意满足但不可机检；**四轴一律不抬升**。

> 本文件不修改账本、不修改冻结原件、不填写任何人工门字段。
> 它是"逐任务复核"的第一条记录，用途是把"为什么不翻牌"写成可复查的证据，而不是口头理由。

---

## 一、任务实况（从账本直接读回，不是摘要）

| 字段 | 值 |
|---|---|
| `definition.priority` | `P0` |
| `definition.execution_state` | `PLANNED_DELTA` |
| `depends_on` | `[]` —— 28 任务中**唯一**无依赖根节点 |
| 被直接依赖 | `DL-R5-002/003/004/006/009/023/028`（7 项） |
| `required_axes` | `["implementation", "unit"]` |
| `axes.implementation` | `PARTIAL`，证据 `r5-branch-convergence-live-20260927` |
| `axes.unit` | `PARTIAL`，证据 `r5-001-static-unit-20260928` |
| `axes.host_live` | `PARTIAL`，**证据为空**（且不在 required_axes 内） |
| `axes.delivery` | `PARTIAL`，**证据为空**（同上） |
| `reassessment` | `PENDING_EVIDENCE_REVIEW` |
| `predecessor_task_ids` | `["R3-01", "R3-03"]`（R3 命名空间，与 crosswalk 的 R4 命名空间是两套并行血统） |

账本整体分布（同一次解析读回）：28 任务 = 14 P0 / 14 P1；`reassessment` 为
27 `PENDING_EVIDENCE_REVIEW` + 1 `REVIEWED`（`DL-R5-010`）；
`implementation` 27 PARTIAL + 1 IMPLEMENTED_LOCAL；`unit` 27 PARTIAL + 1 PASS；
`host_live` 与 `delivery` 各 28 全 PARTIAL。

账本元数据：`taskpack=DL-TP-20260908-R5`、`baseline_sha=ed8d45ab2857b312f6056c43f7bb5e19dd9b65eb`、
`updated_at=2026-10-06T03:12:05Z`、`source.sha256=31dde89eb4ede81fe88c0a5c5144adfb86af8db4c4d8c263bde2199180369b69`。

---

## 二、逐条 acceptance 核验

### A1「每个旧 R4 ID 可追踪」— 满足，但**不满足朴素全文检索**

`docs/history/taskpacks/r5-20260908/old-new-crosswalk.csv` 实测：28 行数据（表头外）。

- `DL-R4-*` 行 **27**，`previous_id` 唯一且从 `DL-R4-001` 连续到 `DL-R4-027`；
- 27 行的 `new_id` 全部存在于当前账本（缺失 **0**）；
- 反向也成立：28 个账本任务**全部**有 crosswalk 行（孤儿 **0**）；
- `disposition` 分布：`incremental-reuse-not-reset` ×27、`explicit-workstream` ×1
  （`language-governance → DL-R5-028`，唯一一个不是 R4 ID 的前驱标记）。

**这里有一次我自己的误判，必须留在记录里。** 我最初用
`git grep -l "DL-R4-025"` 全仓检索，只命中该 CSV，于是判断 025/026/027 三行"无来源"。
**该结论是错的**：`docs/taskpacks/R4.1-R3-INCREMENTAL-ALIGNMENT-2026-09-07.md`
用**缩写形式**引用了它们——

| 行 | 原文 |
|---|---|
| 26 | `\| R3-16 ComfyUI \| DL-R4-008、025、026 \| … \|` |
| 30 | `\| R3-20 视频 / Premiere \| DL-R4-019、025 \| … \|` |
| 33 | `\| R3-23 跨媒体 \| DL-R4-022、027 \| … \|` |

同一文档第 5 行给出 R4.1 包本体：`DESIGN-LAB-EXECUTION-TASKPACK-2026-09-07-R4.1.zip`，
SHA256 `7baf542aee76db184641d41a6ddcb09c1d5e93e999c033836da6b90c3ee81169`，
"原包 11 个文件、27 个任务，依赖图无循环、无缺失 ID"；第 44 行重申"27 项范围保留"。
`git ls-files | grep '\.zip$'` 只命中另一个无关包（UIKIT 会话目录里的
`DESIGN-LAB-FINAL-TASK-PACKAGE-2026-09-04.zip`），**R4.1 ZIP 未入仓**。

pickaxe 复核（`git log --all -S`，逐 ID）：`DL-R4-025/026/027` 全仓历史上**只由一个提交引入**
—— `d48458647e746dfa69eb2f5bf955ee0ef5aac603`（2026-09-09，
"docs: preserve verified R5 taskpack source for incremental adoption"），
且该提交树上含此串的只有 `old-new-crosswalk.csv` 一个文件。

**因此 A1 的准确表述是**：血统可追到仓内真值（缩写引用 + ZIP 哈希声明），
27/27 双向覆盖无孤儿；但它**不能按完整 ID 检索**——全形 `DL-R4-025` 在仓内仅存在于 CSV，
其定义方（ZIP）不在仓内。若将来要把"可追踪"做成机检门，这是一个必须知道的形式缺口。

**不建议由 agent 自行修复**：`old-new-crosswalk.csv` 被 `SHA256SUMS.txt` 钉住
（`cab2dcecb4972ae4ee7d50158e1cb2d2e08389756a5b1eb222de64c75384c499`），
且同目录 `.gitattributes` 显式声明 `old-new-crosswalk.csv -text` 以保留原始字节。
本次实测该目录 11 个文件**逐个哈希全部 MATCH**（含 `tasks.json` = `31dde89e…`，
与账本 `source.sha256` 逐字节一致，证明账本冻结源未被改动）。
任何修正只能是**追加式勘误**，不能是编辑原件——这需要 owner 裁决。

### A2「所有任务具有验收/回退/证据字段」— 满足（全 28 任务，非仅 001）

逐字段扫描 28 个任务，缺失计数：

| 字段 | 缺失任务数 |
|---|---|
| `acceptance` | 0 |
| `rollback` | 0 |
| `evidence_required` | 0 |
| `required_axes` | 0 |
| `axes` | 0 |
| `definition.title` | 0 |

`evidence_required` 在全仓 28 任务上只有 **1 种**取值，即统一的 6 字段：
`source_sha, environment_versions, commands_and_exit_codes, artifact_hashes, limitations, rollback_record`。
`acceptance` 条目数分布：2 条 ×3 个任务、3 条 ×14、4 条 ×9、5 条 ×2（合计 28）。

DL-R5-001 的四条 acceptance 原文即本文 §二 的 A1–A4，可逐条复查，不是占位文本。

### A3「报告 check 在锁定环境通过」— 部分满足；**"通过"不得当作产品 PASS**

本机锁定环境（解释器 `3.13.14`，`D:\All projects\DESIGN-LAB\.venv\Scripts\python.exe`）实测：

| 命令 | 退出码 | 读回 |
|---|---|---|
| `scripts/generate_current_reports.py --check` | 0 | `CURRENT_REPORTS=STALE … scope=bound-input-and-output-integrity; not current Git or cloud freshness` |
| `design-lab/scripts/verify_task_ledger_contract.py` | 0 | `TASK_LEDGER_CONTRACT=OK` |
| `design-lab/scripts/verify_evidence_artifact_presence.py` | 0 | `EVIDENCE_ARTIFACTS=WARN tracked_broken=0 tracked_drifted=1 runtime_present=33 runtime_missing=1` |

三点必须分开看：

1. **STALE 是设计语义，不是失败**。`checkScope` 自己写明"不是当前 Git 或云端新鲜度"。
   投影把 `generatedAt` 与 git 观测包进了被绑定内容，所以任何后续提交都会让它 STALE；
   把 STALE 读成 PASS 正是 `DL-UCR-012 / FA-03` 禁止的洗白。
2. **A3 里"锁定环境"最硬的那一份证据在 CI，不在本机**：required context
   `Clean wheel install + Workbench launch gate` 与 `Python gate` 均在 exact SHA 上跑；
   `main@3f2842c5` 的 push 跑 `37492389709` 实测 **completed / success**，9 项 required 全绿。
   本机 exit 0 只覆盖"仓库内 check 分支不崩"。
3. `tracked_drifted=1` 是一条真实衰减：证据
   `r5-workbench-strict-ts-build-truth-20260927` 绑的是 `apps/workbench/build/main.js`
   ——一个可变 tracked 源文件，自 09-27 观察后哈希已前移（`HASH_MOVED_SINCE_OBSERVATION`）。
   这与 `docs/handoffs/DESIGN-LAB-SESSION-HANDOFF-2026-10-06B.md` §3.6 记录的
   216/253 缺失条目是同一类债的**另一个方向**：绑可变 tracked 源文件会衰减，
   绑 gitignored 运行根产物会消失。

### A4「明确合并状态」— 满足（本次读回）

| 项 | 读回 |
|---|---|
| 本地 `main` = `origin/main` | `3f2842c513a58b41e790de45dfb2c052a85473d5` |
| main required contexts | **9 项**，逐项读回 `gh api branches/main/protection` |
| main 上 exact-SHA 跑 | run `37492389709`（push）= completed/success |
| 远端分支 | `main`、`qoder/designlab-handoff-selfreference-note-20261007`、`qoder/designlab-projection-rebind-20261007` |
| open PR | #224（head `d77f4933`，20 pass / 2 skipping）、#225（head `15cf727e`，9 required pass，`Python gate` pending） |
| 工作树 | `git diff --name-only origin/main...HEAD` = 该分支 10 个生成文件；无其它改动 |

---

## 三、为什么不抬升任何轴（这是本记录的主要用途）

1. **历史证据不自动提升当前 SHA**（AUTHORITY §6）。001 的两条证据分别绑
   `634071f3`（2026-09-27）与 `4c9f1849`（2026-09-28）；当前 main 是 `3f2842c5`。
2. **新证据必须齐 6 个 `evidence_required` 字段并绑 exact SHA**，而本会话**没有在当前 SHA 重跑套件**。
   当前 SHA 的套件观测仍未取得；仓内最近的记录是 `Ran 1807 tests — OK (skipped=39)` @ `28667300`
   （由 `dc00d2b0` 落仓）。**那是前一会话的观测，本文件不把它冒充本会话实测**。
3. **把新证据绑到 `.project-local/**` 会立刻变成 `ARTIFACT_CHANGED_OR_MISSING`**——现有 216/253
   缺失条目正是这么坏的。复制这个做法不是补证据，是加债。
4. `host_live` / `delivery` **不在 001 的 `required_axes` 内**，所以"证据为空 + PARTIAL"当前是自洽的；
   但也因此**绝不能**被读成"已验证"。契约还禁止非 implementation 轴写 `IMPLEMENTED_LOCAL`。

**抬升 001 所需的最小充分动作**（按优先级，且第 1 步需要 owner）：

1. owner 授权合入 #225（投影重绑），使 `reports/current/**` 在 main 上通过 freshness 校验；
2. 在合并后的 exact main SHA 上重跑套件，取 `commands_and_exit_codes` + `environment_versions`；
3. 新证据的 `artifact_hashes` **只绑 tracked 路径**（例如本报告自身、账本、crosswalk CSV），
   不绑运行根产物；
4. 逐条对着 A1–A4 写 `limitations`，再决定是否 `implementation: PARTIAL → PASS`。

在 1–3 完成前，任何翻牌都是无证据抬升。
