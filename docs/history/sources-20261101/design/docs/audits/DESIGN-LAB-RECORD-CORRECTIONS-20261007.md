# 记录更正 · 2026-10-07

**观测 exact SHA**：`main` = `48d214e2cbb2095cd25ff0779e29853620fced1b`（`gh api commits/main` 实读）
**观察窗口**：`2026-10-06T16:07Z`–`17:21Z`
**性质**：本文件只更正已被写进仓内文档与投影的错误陈述，不改账本、不改冻结原件、不抬升任何轴。

---

## 一、撤回「账本 253 个工件路径中 216 个缺失」

该数出现在 `docs/handoffs/DESIGN-LAB-SESSION-HANDOFF-2026-10-06B.md` §3.6 与 §未完成清单，
并被我在 `docs/audits/DESIGN-LAB-T1-LEDGER-REVIEW-DL-R5-001-20261007.md`（PR #226，已合入 main）
里当既有事实引用过。**它是错的，且指错了账本。**

本次独立复算（解析器输出，非手抄）：

| 账本 | evidence 条目 | 路径引用 | 唯一路径 | tracked 存在 | tracked 缺失 | `.project-local` |
|---|---|---|---|---|---|---|
| **活动** `design-lab/config/task-ledger-r3.json` | 39 | 73 | **37** | 34 | **0** | 3 |
| **冻结前继** `docs/history/taskpacks/r3-ledger-pre-r5-20260909.json` | 32 | **254** | **215** | 0 | 0 | **215** |

三点结论：

1. **活动账本没有 216 个缺失工件**。它引用的 37 个唯一路径里，tracked 的 34 个全部存在，
   缺失 **0**；只有 3 个绑在 gitignored 的 `.project-local/` 下。
2. **254 / 215 这组数属于冻结的 R3 前继账本**，不属于当前派工入口。把前继账本的债算到活动账本上，
   会让人去"修"一个不存在的问题。
3. 原口径 **216 > 215 本身自相矛盾**（缺失数不可能大于唯一路径数），这在当时就该被当作
   该数不可信的信号。

**真实存在的债仍然成立**，只是形状不同：**把证据绑到 gitignored 的每机运行根**这一做法，
在活动账本里已有 3 例、在冻结前继里 215 例全中。这是设计决定（哪些工件必须入仓、或改用
tracked 绑定），不是可以靠重跑消除的漂移。`verify_evidence_artifact_presence.py` 的口径
（`runtime_present=33 runtime_missing=1`）是 **ref 级**且只读活动账本，与上面的"路径级"统计
不是同一分母，两者结论一致。

## 二、§九「两条合成项目会出现在仪表盘」已过期

`docs/audits/DESIGN-LAB-WORKBENCH-VISUAL-AUDIT-20261006.md` §九 记录了两条
`Closeout …` 合成项目落在 `.project-local/task-runtime/service/state.db`，并说明"没有代为删除"。

实测现状：`.project-local/task-runtime/service/` 下**已无活动 `state.db`**，只有一个退役文件
`state.db.retired-20261006-capture-scratch`（356352 字节，mtime `2026-10-06T13:50:02Z` = 本地 21:50）。
所以那两条记录**不在仪表盘上**。§九 该段作为时间点记录保留，但不得再被当作当前状态。

附带核实：抓图入口 `scripts/capture_workbench_screenshots.py` 确实把 `PROJECT_LOCAL_ROOT`
指向 `tempfile.TemporaryDirectory()`，运行期在 `screenshot-capture/` 下自建独立库并在退出时自净；
真实 `service/` 未再长出活动库。**该入口是隔离的**，§九 的那条自我更正依然成立。

## 三、DL-GOV-130 对否定句无感知（记录，不修门）

`design-lab/scripts/verify_project_drift.py` 的 `FORBIDDEN_DEFAULT_HOST` 是对
`默认宿主` 等五条短语的**裸子串匹配**，不含否定判断。因此 README 里
"Open Design … **也不是**默认宿主" 这句**正确的**中立声明被门禁判红
（`FAIL default-host language: README.md`，PR #227 首跑）。

处理方式：**改措辞，不改门**。`不享有预设入口的地位` 表达同一主张且不含任一被禁短语；
收窄正则会让真正该拦的肯定句漏过去。`AGENTS.md` 含同样措辞但不在 `ACTIVE_DOCS` 清单内，
所以从未触发——这是该门的覆盖边界，不是它的漏洞。

留给后续决定：是否给 `verify_project_drift.py` 增加否定上下文识别。这属于门禁语义变更，
需要单独一个带证伪用例的 PR（注入"Open Design 是默认宿主"必须变红、保留否定句必须变绿），
不在本次范围内。

## 四、两处执行侧方法缺陷（写下来防止重犯）

1. **`git diff --name-only` 被 `run()` 只取 stdout 末行截断**，导致我一度把"分支改了 10 个文件"
   读成 1 个。已用直接命令纠正。任何"取末行"的探针都不能用于多行输出。
2. **`grep -c` 无匹配返回 exit 1**，打断了我一条 `&&` 链，使一次 CI 读数缺失。
   本会话已两次踩到管道/链式退出码问题（另一次：`gh pr merge` 的失败被 `| tail` 吞成 exit 0）。
   规则不变：`set -o pipefail`，逐条命令单独取退出码，读回执不读包装状态。

## 五、根目录唯一游离项

`services/` = 4 个空目录（`delivery` / `jobs` / `quality` / `review`）、0 个文件、未被 git 跟踪。
是 tracked 树之外唯一的游离结构。删除属破坏性动作，需先建保留点再执行，本文件只登记。
