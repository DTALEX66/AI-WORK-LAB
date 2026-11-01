# DESIGN-LAB 项目梳理报告

**生成时间：** 2026-09-27（本地，Asia/Shanghai）
**观察 exact SHA：** `634071f3c8ffa87e08fa1386f49c185ff6fa36d8`（`main` = `origin/main`）
**性质：** 只读梳理（read-only survey）。报告本身不改动任何 tracked 文件。
**触发：** 用户要求「整理梳理本项目，确保 HERMES 软件执行的任务都被接收到」。

---

## 0. 结论摘要

1. **HERMES 软件当前未在执行任何本项目任务。** 定时作业 0 个、看板任务 0 个、项目运行记录 0 个（`project-local-runs` 只有 WORK-LAB）。DESIGN-LAB 在 HERMES 的验证事件库里**命中 0 行**——HERMES 从未对 DESIGN-LAB 跑过 test 类验证。
2. **本会话对 HERMES 的任务面可见性完整**：全部 16 个历史 job_id、全部作业产物目录、全部存活进程、全部异步委派状态、全部验证事件的项目分布均可枚举（§2 有据）。
3. **发现 7 项真实问题**（§4），其中 3 项等级为高——共同特征是：**项目的「任务真值」与「投影」系统性落后于实际已交付事实**。
4. 本轮已完成的动作：HERMES 普查、`.project-local` 归属清理（§5）。

---

## 1. 项目真值链（权威顺序，实测）

| 层 | 文件 | 状态 |
|---|---|---|
| 顶层权威 | `AUTHORITY.md` — `DL-AUTHORITY-2026-09-18-R2` | `TOP_LEVEL_CURRENT` |
| 分类仲裁 | `.project/governance/authority-index.json` (`authority-index/v2`) | CURRENT / PROJECTION / HISTORICAL 判定 |
| 执行规则 | `AGENTS.md` | MUST READ FIRST |
| Current 文档 | `docs/current/PRODUCT_DEFINITION.md`、`docs/architecture/{BOUNDARY_CONTRACT,ARCHITECTURE,DIRECTORY-AUTHORITY,LANGUAGE-POLICY}.md` | 6/6 存在 |
| **唯一** current TaskPack | `docs/taskpacks/DESIGN-LAB-FINAL-AUTHORITY-CONVERGENCE-TASKPACK-2026-09-18.md` | 128 行，A–O 共 15 段 |
| **唯一** 任务状态编辑源 | `design-lab/config/task-ledger-r3.json` | `schemaVersion=design-lab/task-ledger/r5-v1`，28 任务 |
| 投影（非权威） | `reports/current/**`（71 文件） | 须经 fresh 校验 |
| 历史 | `docs/history/**`、`docs/handoffs/**` | 永不作顶层权威 |

**治理机读面**：`.project/governance/` 6 文件（active-capability-allowlist / authority-index / data-ownership / gates / path-ref-policy / path-risk）。
**边界政策**：`.project/manifest.yaml`、`.project/paths.json`；运行根 `.project-local/`（`.gitignore:71`），legacy `.hermes`（`.gitignore:25`）。

---

## 2. HERMES 任务面普查（只读；不读凭据与会话正文）

刻意**未读**：`.env`、`auth.json`、`vault/**`、`sessions/**`、`memories/**`、`state.db` 的 messages/prompt 正文。以下全部为路径、行数、表名、job id、时间戳、状态。

### 2.1 调度类（唯一能「自己跑任务」的来源）

| 项 | 实测 | 判读 |
|---|---|---|
| `cron/jobs.json` | `{"jobs": [], "updated_at": "2026-09-19T00:04:07+08:00"}` | **无作业定义** |
| `cron/ticker_heartbeat` / `ticker_last_success` | mtime `2026-09-27 23:07` | **调度器活着，但无作业可跑** |
| `cron/executions.db` | 902 行，**16 个 distinct job_id**，24 个 (job_id,source,status) 组 | 窗口 `2026-07-26 → 2026-08-11`，**已停 7 周** |
| `cron/output/` | 3 目录；仅 `4cb922c18e8b/2026-07-30_08-16-27.md`（164,056 B）；`a2f71a322f56/`、`b1cdf7fdf800/` 空 | 历史产物 |

历史作业 id：`a44c41749168`(519+41+1) · `4cb922c18e8b`(154+46+1+1) · `001f5f9c87bc`(69+15) · `927e5ad6c004`(40+2) · `j1..j10` 与 `j-65773`/`j-65773b`（2026-07-29 一次自测，5 个 failed）。

### 2.2 看板 / 队列 / 中继

| 项 | 实测 |
|---|---|
| `kanban.db` | 8 张表（tasks/task_links/task_comments/task_events/task_runs/task_attachments/kanban_notify_subs/sqlite_sequence）**全部 0 行**；mtime `2026-09-17 20:43`（10 天未动） |
| `pending/` | 仅 `memory/`；`pending_messages/` 空 |
| `bot_relay/` | `claimed/` `outbox/` `replies/` 全 0；`roster.json` = `{"agents": [], ...}` |
| `hooks/` `desktop/` `desktop-plugins/` | 全空（无挂载任务） |
| `delivery_obligations` / `gateway_hygiene_state` | 0 行 |

### 2.3 项目级运行与异步委派

| 项 | 实测 |
|---|---|
| `project-local-runs/` | **只有 `WORK-LAB/`**（2 个 `gateplan-check-*.txt`）；**无 DESIGN-LAB** |
| `state.db::async_delegations` | 23 行：`completed` 10（2026-09-20 → 09-21）、**`error` 13**（最近 **2026-09-27 15:05**，即本会话之前） |
| `spawn-ledger.json` | 2 个存活进程：`hermes serve`（pid 23548, port 54593）、`mcp-helper`（pid 19600） |

### 2.4 验证事件库（HERMES 对哪些项目跑过验证）

`verification_evidence.db`：128 条 `kind=test`（passed 79 / failed 49），窗口 `2026-07-27 → 2026-08-26`。
按 `root` 分布：Cognitive-Loop-OS 84 + 31 + 6 + 2 + 2 + 1、**MINIGAME 1**、**ArcheAxis 1**。
**`DESIGN-LAB` 命中 0 行。**

### 2.5 HERMES 项目登记

`projects.db` 共 9 个项目。DESIGN-LAB = `p_517e2512`，`slug=design-lab`，`primary_path=D:\All projects\DESIGN-LAB`，`archived=0`。
**但 `project_meta.active_id = p_8b0eb5be` = `ArcheAxis-Knowledge-OS`** —— active 不是 DESIGN-LAB。

### 2.6 普查判读

> HERMES 侧的「任务」= ①cron 定时作业 ②kanban 任务 ③project-local-runs ④async_delegations ⑤hooks/plugins 挂载。
> **①=0、②=0、③=0（无 DESIGN-LAB）、④最近一条 error（本会话之前）、⑤=0。**
> 因此：**没有任何 HERMES 后台任务在为 DESIGN-LAB 执行工作**；本项目的全部进展由会话内驱动 + GitHub CI 门禁保证。

---

## 3. 已交付事实 vs 项目记录（本轮 live 读回）

| 事实 | live 读回值 | 项目文档里的旧值 |
|---|---|---|
| `origin/main` | `634071f3…`（PR #173 已合） | PROJECT_STATUS 观察 `6ba2578a…` |
| 远端分支数 | **1**（仅 `main`） | AUTHORITY.md §13/§15：28 |
| open PR | **0** | — |
| main required checks | **9** | AUTHORITY.md §15：7 |
| `apps/workbench` 文件数 | **10** | TaskPack D 段：3 |
| 最近合并 PR | #173 (14:40:41Z) / #172 / #171 / #170 / #169 | — |

9 项 required checks（`gh api /repos/DTALEX66/DESIGN-LAB/branches/main/protection` 实读）：
Python gate · MiniGame node gate · Generated-artifact clean-tree gate · License & secret hygiene gate · Open Design host adapter gate · Top-level Authority consistency gate · Workbench strict-TS product gate · Workbench browser E2E · DeepSeek authority gate chain。

---

## 4. 发现的问题（分级）

### ［高］P-1 任务账本与已交付事实脱节

`design-lab/config/task-ledger-r3.json`（28 任务）：

| 指标 | 实测 |
|---|---|
| `implementation` / `unit` / `host_live` / `delivery` 状态 | **全部 `PARTIAL`**（112 个轴） |
| `reassessment` | **全部 `PENDING_EVIDENCE_REVIEW`** |
| `definition.execution_state` | **全部 `PLANNED_DELTA`** |
| 有证据绑定的轴 | **3 / 112**（`DL-R5-008` unit + host_live、`DL-R5-012` implementation） |
| `ledger.evidence` receipts | **3** |
| 优先级 | P0 14 / P1 14 |
| 依赖图 | 无悬空 `depends_on`（OK） |

而 `AUTHORITY.md` §15 已把多个 P0 标为 `CLOSED_WITH_REGRESSION_GUARD`，且 #165–#173 均已合并。
→ 账本**缺少「已完成」语义**，且系统性**低报**已交付事实。这不是本轮引入的。

**契约硬约束**（`src/design_lab/governance/r5_contract.py`）：
- `definition` / `title` / `depends_on` / `predecessor_task_ids` / `required_axes` **逐字节冻结**，不可改（:88-92）。
- `reassessment != 'REVIEWED'` 时，轴状态**不得**为 `PASS`/`IMPLEMENTED_LOCAL`（:100-101）。
- 每个 `axis.evidence` 引用的 id 必须存在于 `ledger.evidence`（:98-99），且 id 唯一（:79-81）。
- evidence 记录必填 11 字段，`artifacts` **至少 1 项**。
→ 因此合法回填 = **加 evidence receipts + 从轴引用，状态保持 `PARTIAL`**。

### ［高］P-2 生成投影已漂移

`reports/current/PROJECT_STATUS.md`：观察 SHA `6ba2578a…`（live `634071f`），生成 `2026-09-27T05:34:05+00:00`，且写的是任务包 `DL-TP-20260908-R5`，而 authority-index 指定的 current integrated 是 `DL-TP-20260918-FINAL-AUTHORITY-CONVERGENCE-R2`。
按 `authority-index.projectionRule`，`reports/current/**` 属 `PROJECTION`，**必须经 fresh 校验才可用** → 当前状态不可用。
`TASK_PROGRESS.json` 亦为同一批次（71 个投影文件同源）。

### ［高］P-3 顶层 Authority 的动态事实已成陈旧快照

`AUTHORITY.md` §13/§15 记录：required checks = 7、branches = 28、`main@0e9f687`、Workbench 仅 3 文件。
live 实测：checks = **9**、branches = **1**、main = **634071f**、Workbench = **10 文件**。
文内 §13 自称「以后必须重新实时读取这些动态事实」，§16 亦要求 never memory-only — 但读者若只看文件会得到错误结论。

**改动约束**：`scripts/verify_top_level_authority.py:69-74` 对 `AUTHORITY.md` 与 `.project/governance/authority-index.json` 做 **byte-pin**（`f7c1e6ad…` / `38c01eb0…`），且该 verifier 是 9 项 required checks 之一。
文件内已有**再钉先例**（:56-68，2026-09-20，按 §17 记 owner intent / reason / superseded / impact）。
→ 改 AUTHORITY 必须**同步再钉**，否则 `r2-release-integrity` FAIL。

### ［中］P-4 `.project-local` 顶层混入 agent 会话暂存 —— 本轮已修

详见 §5。

### ［低］P-5 嵌套残留目录 —— 本轮已修

`.project-local/.project-local/task-runtime`（空）。同类于 skill 文档记录的 `C:\d\...` / `D:\c\Users\admin` 路径拼接残留。已删（删前确认 0 文件）。

### ［低］P-6 HERMES 侧膨胀

`state.db` **4.51 GB**；`verification_evidence.db` 1.70 MB（mtime 2026-09-04）；`kanban.db` 10 天未动。非本项目范围，仅记录。

### ［低但会误导审计］P-7 本机控制台编码

PowerShell 5.1 默认按 GBK 读文件 → UTF-8 中文文件（账本/文档）乱码，`ConvertFrom-Json` **直接解析失败**。本轮实测复现一次（账本读取报 `ArgumentException`）。
→ 任何脚本化审计必须显式 `-Encoding UTF8`，或改用 `.venv\Scripts\python.exe`（Python 3.13.14）。

---

## 5. 本轮已执行的清理（归属优先，非「位置好看」）

规则：「位置合规 ≠ 归属正确」——先判数据所有权，再选目录。

### 移入 `task-artifacts/external-recovery-2026-09-27/`（agent 会话暂存 = 工作流基础设施）

| 文件 | sha256（移后回读，前=后） |
|---|---|
| `check170-h001.py` | `8852787f1d067d2f…` |
| `diagnose-170.py` | `eed4890abc215237…` |
| `merge-170.py` | `6ebdc6a3a73b4099…` |
| `topics-payload.json` | `f844bc96f0b4c873…` |

### 保留在 `.project-local` 根（位置由契约/引用决定）

| 文件 | 保留依据 |
|---|---|
| `context-capsule.json` | `design-lab/scripts/context_capsule.py:42` 的 `CAPSULE_REL` 契约输出路径；移走即破坏工具契约 |
| `prune-manifest-2026-09-26.json` / `-09-27.json` | 被 tracked 文档与 AGENTS.md 引用的审计证据 |
| `stash-backup-2026-09-26.json` | 被 `reports/history` closeout ledger 引用的证据 |

### 删除

`.project-local/.project-local/`（嵌套、0 文件，删前已核）。

### 回读

`MANIFEST.json` 已追加 `followups[0]`（action=`root-residue-ownership-cleanup`，含 moved/kept/removed 与 rationale）。
清理后 `.project-local` 根：12 目录 + 4 个有据保留文件。

---

## 6. 本会话对「HERMES 执行的任务」的接收确认

| 问题 | 回答 |
|---|---|
| HERMES 有没有在跑本项目任务？ | **没有**。cron 作业 0、kanban 0、project-local-runs 无 DESIGN-LAB、hooks/plugins 0 |
| 有没有跑过？ | 有历史痕迹：cron 902 次执行（`2026-07-26→08-11`，16 个 job_id）；`async_delegations` 23 条（10 completed，13 error） |
| HERMES 对本项目跑过验证吗？ | **没有**。`verification_events` 中 DESIGN-LAB 命中 **0 行** |
| 本会话能看到全部任务内容吗？ | 能。§2 的枚举覆盖 HERMES 全部任务来源；凭据与会话正文**刻意未读**，那属私有数据、不属任务内容 |
| DESIGN-LAB 在 HERMES 里的状态 | 已登记 `p_517e2512`（archived=0），但**非 active**（active = ArcheAxis `p_8b0eb5be`）；按用户指示**不做任何 HERMES 侧改动** |

---

## 7. 建议的后续（需 owner 决定，本报告不改仓）

| 优先级 | 事项 | 性质 |
|---|---|---|
| 高 | 回填账本证据绑定（§4 P-1），或明确「R5 账本已降级为血统记录、当前真值改由 TaskPack/CI 表达」 | 改 tracked，走 PR |
| 高 | 重生成 `reports/current/**` 修正投影漂移（§4 P-2） | 改 tracked，走 PR |
| 高 | 更新 `AUTHORITY.md` §13/§15 动态事实并**同步再钉** verifier hash（§4 P-3） | 改 tracked，走 PR；需 §17 记录 |
| 中 | 决定 `stash-backup`/`prune-manifest` 等历史证据的最终处置 | owner |
| 低 | HERMES `state.db` 4.5 GB 瘦身 | HERMES 全局，高风险 |

---

**END — 只读梳理报告，exact SHA `634071f3c8ffa87e08fa1386f49c185ff6fa36d8`**
