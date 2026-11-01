# WORK-LAB · Hermes 执行面审计（2026-09-27）

**性质**：审计记录（非权威、非执行授权）。`currentTaskpack`
（`WORK-LAB-UNIFIED-PRODUCT-CONVERGENCE-TASKPACK-20260918`）与 `WORK-LAB-AUTHORITY.md`
仍然权威；本文件是证据分层回读结果。
**范围**：受管客户端 **Hermes Agent** 在本项目内执行过的全部任务面 + 其当前 live 事实。
**方法**：先按 `WORK-LAB-AUTHORITY.md` §1 引导顺序解析当前权威，再逐份回读 Hermes 任务记录，
最后**独立重跑**记录所声称的验证命令（不采信记录自述）。

---

## 0. 审计基线（可复核的值）

| 项 | 值 |
|---|---|
| `origin/main` commit | `9ffb0c5fbdebfae0e7565a5b0d22528258c3e638` |
| `origin/main` tree | `63501c9e624bc04240e810c72c9a9ade3f2d3108` |
| 本地 HEAD | `9ffb0c5…`（== origin/main；工作树干净，仅未跟踪 `docs/future/`） |
| 权威 ID | `WORK-LAB-AUTHORITY-20260918-V2` |
| CURRENT taskpack | `WORK-LAB-UNIFIED-PRODUCT-CONVERGENCE-TASKPACK-20260918` |
| 开放任务登记 | `taskpacks/current/OPEN-TASK-REGISTER.md`（HU-01 为本轮 Hermes 行） |
| 证据边界 | 全部读取均在 `D:\All projects\WORK-LAB` 与 `%LOCALAPPDATA%\hermes` 内；**未触碰 `E:\`/`F:\`**，**未读取任何凭据/token/.env 值** |

证据等级（`WORK-LAB-AUTHORITY.md` §10）：本报告使用的等级为
`REAL`（可复核句柄 + 当轮读回）> `INTEGRATED`（真实组件 + 本地端到端）>
`SYNTHETIC`（合成夹具）。**本地结构 PASS ≠ exact-SHA CI PASS**，凡未取 GitHub Actions
精确 SHA 运行的结论一律标 `EXACT_SHA_CI_UNVERIFIED`。

---

## 1. Hermes 执行面任务清单（5 轮 + 1 工具面）

| # | 轮次 | 记录（仓库内） | 执行者 | 交付落地 |
|---|---|---|---|---|
| 1 | **WL-BASELINE-HERMES**（2026-09-14 起） | `.project-local/artifacts/task-artifacts/WL-BASELINE-HERMES/`（61 个证据文件 + `H1..H5` 分册 + `LIMITATIONS.md` + `HANDOFF.md` + 2 轮 LEDGER） | DSH / DeepSeek | **本地证据**；内容经 `6bd0bd5` cutover 进入 `main` |
| 2 | **Hermes v0.21.2 → v0.21.3 更新 + 4 项缺陷修复**（2026-09-17） | `taskpacks/current/HERMES-UPDATE-AND-FIXES-20260917.md` + `WL-BASELINE-HERMES/HERMES-UPDATE-20260917-LEDGER.md`、`ROUND-FULL-AUTH-20260917-LEDGER.md` | DSH / DeepSeek | 内容在 `main`（经 cutover）；**原提交被压缩，独立 SHA 已不在 `main` 祖先链** |
| 3 | **Hermes 任务包对账**（2026-08） | `taskpacks/current/WORK-LAB-HERMES-TASKPACK-RECONCILIATION.json` | Hermes 附件任务包 | **陈旧单据**（见 F-02） |
| 4 | **Hermes v0.21.3 → v0.21.5+3115 更新 + 5 项覆盖层漂移修复**（2026-09-27） | `taskpacks/current/HERMES-UPDATE-AND-MAINTENANCE-20260927.md`、`HERMES-UPDATE-HANDOFF-20260927.md`；证据 `.project-local/runs/hermes-update-20260927/`（25 文件）、`.project-local/artifacts/curator-foldback/`、`.project-local/artifacts/task-artifacts/hermes-sync-plan-20260927.json` | DSH / DeepSeek | **PR #140 squash 合并 → `main` = `8f334f7`** |
| 5 | **Hermes 工具面（持续）** | `integrations/executors/hermes/`（同步器 / curator 折回 / 任务结果分类器）、`config/skill-provenance.yaml`、`config/config-ownership.json`、`bin/*` 6 个启动器、13 个受管技能 | WORK-LAB 自持 | 全部在 `main` |

> 轮次 1–2 与轮次 4 是**两条独立工作线**（厂商更新 ↔ 覆盖层发布），互不证明 ——
> 这一纪律本身在记录中被明确写出，本审计维持该口径。

---

## 2. 逐轮回读（声明 vs 事实）

### 2.1 轮次 4（2026-09-27，最近一轮，`REAL`）

**本审计独立重跑**（非采信记录）：

| 声明 | 本审计事实 | 判定 |
|---|---|---|
| `hermes --version` = `v0.21.5+3115.g10938a7` | 读回 **`Hermes Agent v0.21.5+3115.g10938a7 (2026.9.24) · upstream 10938a7c`** | ✅ |
| 安装方式 git | `Install method: git`，`Install directory ...\hermes-agent` | ✅ |
| 更新 receipt `outcome=success` / `18m36s` | `logs/update_receipts/latest.json`：`outcome=success`、`finished_at 2026-09-27T02:01:38.900321+00:00`、`argv=[hermes update --yes --backup]`、`pre 98f758ae → post 10938a7c`、`gateway_restart.incomplete=false`、`pm_venv_rebuild.ok=true` | ✅ |
| config **v46** | `doctor` 读回 `Config version up to date (v46)`、`No deprecated config keys or env vars` | ✅ |
| 覆盖层 **21/21 CONVERGED** | 重跑 `sync_hermes_workflow_assets.py`（只读判定）：21 行全部 `CONVERGED`，`baseline == live == candidate`，`guard: will write 0 target(s); skip 21 converged` | ✅ |
| curator **0 漂移** | 重跑 `curator_foldback.py --check` → **`drifted managed targets: 0`** | ✅ |
| hooks healthy | 重跑 `hermes hooks doctor` → `allowlisted (approved 2026-09-17T12:18:25.985000Z)`、`script unchanged since approval`、`produced valid JSON on synthetic payload (exit=0)`、`All shell hooks look healthy`；exit 0 | ✅ |
| `SOUL.md` 被拒绝 live 旧版、发布仓库版 | live = `9da0bd4884af9fdb` = 仓库 `config/SOUL.md` | ✅ |
| `project-data-boundary` 拒绝删掉 `F:\` 保护的 live 旧版 | live = `3508aafe7a9d9343` = 仓库包内版本 | ✅ |
| `codex` 从仓库重建（`82aaece3`） | live = `82aaece396b2403f` = 仓库 | ✅ |
| 桌面入口真实启动读回 6 进程 / 标题 `Hermes` / responding | `.project-local/runs/hermes-update-20260927/desktop-launch-readback.json`：`process_count=6`、`main_window_title="Hermes"`、`responding=true`、6 个 pid；`win-unpacked\Hermes.exe` mtime **2026-09-27 09:58:35** 与记录一致 | ✅（文件为 UTF-16LE，见 F-06） |
| skill-provenance PASS | 重跑 `run_quality_gate.py skill-provenance` → `SKILL_PROVENANCE_PASS skills=13`、`QUALITY_GATE_PASS`、exit 0 | ✅ |
| `skill_lifecycle.py status` PASS | 重跑 exit 0（该命令无 stdout 输出，属其正常形状） | ✅（弱证据：exit code only） |
| 回滚备份含 `SOUL.md`（3492 条目） | `backups\pre-update-2026-09-27-094303.zip` **1,923,061,795 B** —— 与记录字节数逐字节一致；zip 内部清单未在本审计重新解包（避免读取 `.env`/`auth.json`） | ✅（清单为记录所载，未重复解包） |
| doctor 余 2 项非阻塞 | 重跑 `doctor`：`Found 2 issue(s)` = `state.db is large (4.2 GB)` + `Run 'hermes setup' to configure missing API keys` —— 与记录同类同数量（体积由 4.1 → 4.2 GB，正常增长） | ✅ |

**新增观测（记录未写、本审计发现）**：

- `hermes --version` 现报 **`Update available: 4 commits behind — run 'hermes update'`**
  —— 09-27 之后上游又前进 4 个提交。属正常漂移，不构成缺陷，但**下次维护入口的有效前提已变化**。
- `doctor` 本轮多出一行 `state.db write-health probe skipped: store is held by a live writer and larger than 1 GB`
  —— 因为 **Hermes 桌面当前正在运行**（记录 §7 已预告"本轮之后 Hermes 桌面正在运行"）。
  ⇒ 任何**停机维护**（含 `sessions optimize-storage`）必须**先关闭桌面**，否则写健康探针不可用。

### 2.2 轮次 2（2026-09-17，`REAL`（本地）/ 祖先链已压缩）

| 声明 | 本审计事实 | 判定 |
|---|---|---|
| 4 项缺陷修复（分类器终端证据优先 / 偶发测试去竞态 / 生成器 LF 根因 / hooks 批准刷新） | 内容**均在 `main`**：`integrations/executors/hermes/hermes_task_result.py:49` 含 `billing_or_credits_exhausted` 终端模式；`scripts/ci/generate_current_state.py` LF 修复经 `6bd0bd5` 落地；`tests/workflow-assistance/test_hermes_task_result.py` + `test_hermes_quota_no_paid_fallback.py` 存在 | ✅ 内容 |
| 记录 §7 列出的提交 `62d5f50 / 3d8b22a / e4e57cc / 1b8bc3d`（分支 `r4-recovery-exec`） | 4 个对象**存在且提交信息逐字匹配**（`git cat-file -t` = commit，日期 2026-09-17），但 **`--is-ancestor HEAD` 全部为 false，且无任何本地/远端分支包含它们** ⇒ 分支退役后成为**不可达对象** | ⚠️ 见 F-01 |
| `test_curator_foldback` 17 项 OK | 本审计用 Hermes venv python 重跑 → **`Ran 17 tests ... OK`** | ✅ |
| 门禁 38/38 PASS | 未重跑（其对应树为已退役分支；当前树门禁为 CI 的 42 门计划） | ⏸️ 未复现，标注为历史读数 |
| 备份 `pre-update-2026-09-17-195657.zip`（1,784,290,101 B）可用 | **该文件已不存在**（`keep_policy=2`，被 09-27 的两份新备份轮换掉） | ❌ 见 F-03 |
| `refs/hermes-update-backups/orphan-main-20260917-…` 30 天后过期 | 记录自述"30 天后过期"，未在本审计验证（属产品行为） | ⏸️ |

### 2.3 轮次 1（WL-BASELINE-HERMES，`REAL`（本地））

- `LIMITATIONS.md` 的 9 条常驻限制中，**L-5（hooks 批准失效）、L-7（分类器证据层级）、
  L-8（EOL 29 文件违规）已在轮次 2 关闭**，且本审计在轮次 4 现场确认：
  hooks `script unchanged since approval` = L-5 关闭成立；`hermes_task_result.py` 终端模式 = L-7 关闭成立；
  当前受管技能目录三方比较无 CRLF 类异常 = L-8 不复现。
- **仍生效的常驻限制**：L-1（无会话级取消）、L-2（计费/额度 UNKNOWN）、
  L-3（Hermes 侧 exact-SHA CI 未验证）、L-4（本项目不使用 `hermes plan` 入口）、
  L-6（curator × 受管目录结构性冲突，策略=折回、删改类仍需人工）、
  L-9（第二 profile `deepseek-review` 独立，覆盖层不外推）。
- **L-4 现场核验**：`D:\All projects\WORK-LAB\.hermes\plans` **不存在**，
  `.hermes/` 下仅 `task-artifacts/`、`task-runtime/`、`tmp/`，且 **`.hermes/` 无任何被 Git 跟踪的文件**
  ⇒ 该项目边界治理决定被遵守。

### 2.4 轮次 3（任务包对账，**陈旧**）

- 记录内 `authority.archive = .hermes/desktop-attachments/WORK-LAB-HERMES-TASKPACK-v1.0.0.zip`
  → **文件不存在**；`current_tree.head = f89b2ac…`（非当前主干）；
  `workflow_comparison` 引用的 `10-workflow/workflow-assistance`、`50-taskpacks/` 等
  路径在当前树**已不存在**（目录收敛已删除）。
- 落地状态 `READY_FOR_USER_APPROVAL` 已无对象；其 6 条 `approval_boundaries` 中
  `hermes_live_apply_readback` 已由轮次 2/4 推进（受管覆盖层已发布并读回），
  其余（minigame / root license / second reference client）仍为用户决定项。
  ⇒ 见 F-02：该单据应标注为 `SUPERSEDED/HISTORICAL`。

---

## 3. 覆盖层受管资产：21/21 逐项 sha256（本审计现场读回）

`baseline == live == candidate`，全部 `CONVERGED`（截取前 16 位）：

| # | 目标 | sha256 |
|---|---|---|
| 1 | `.env.template` | `5c9de7599c0e5edb` |
| 2 | `SOUL.md` | `9da0bd4884af9fdb` |
| 3 | `bin/codex` | `096799d1904eb260` |
| 4 | `bin/codex.cmd` | `02a8ce078564626c` |
| 5 | `bin/hermes-npx` | `7bd8160da1e9eb09` |
| 6 | `bin/hermes-npx.cmd` | `d89f1ce4e01ce6fd` |
| 7 | `bin/hermes-project-data.py` | `99adf7d6509d5262` |
| 8 | `bin/hermes-project-terminal-guard.py` | `c928a6953151f1a7` |
| 9 | `skills/autonomous-ai-agents/codex` | `82aaece396b2403f` |
| 10 | `skills/github/github-auth` | `980b996df033d7a6` |
| 11 | `skills/github/github-code-review` | `32a80044e4aaf227` |
| 12 | `skills/github/github-issues` | `37333c1c7f7b697d` |
| 13 | `skills/github/github-pr-workflow` | `37e57297ec4febe2` |
| 14 | `skills/github/github-repo-management` | `c45ce9457ffd228e` |
| 15 | `skills/model-switch` | `7a75077e3ac76c3d` |
| 16 | `skills/software-development/agent-workflow-fortress` | `f56043a8b4337ee3` |
| 17 | `skills/software-development/project-data-boundary` | `3508aafe7a9d9343` |
| 18 | `skills/software-development/python-testing` | `278c6fbd1cf31869` |
| 19 | `skills/software-development/requesting-code-review` | `abf9ca1b3549dc41` |
| 20 | `skills/software-development/sleep-mode` | `337aab54b396fd13` |
| 21 | `skills/software-development/windows-development-environment` | `00bdce3de21e6c80` |

- 仓库侧清单与声明一致：`packages/client-neutral-core/skills` 下 **13 个 `SKILL.md`**、
  `packages/client-neutral-core/bin` 下 **恰好 6 个启动器**。
- `config.yaml` 为**混合所有权**，同步器输出 `skip_mixed_ownership` —— **永不被整体提升**
  （受管字段仅 `display.language` / `display.busy_input_mode` / `sessions.auto_prune` /
  `memory.*` / `platform_toolsets.cli` / `mcp_servers.context7` / `hooks.pre_tool_call[terminal]`）。
- live 侧技能总数 **1259**、bin 总数 **19** ⇒ 受管 21 项只是**声明子集**，
  其余为 Hermes 自带/原生 curator 产出，**不受 WORK-LAB 管理**（禁止外推）。

---

## 4. 五维基线核对（AGENTS.md 强制项）

| 维度 | 事实 | 判定 |
|---|---|---|
| 1 唯一入口 | 官方桌面 `…\win-unpacked\Hermes.exe` + `hermes` CLI（`venv\Scripts\hermes.exe`，**不在 PATH**）；未发现第二启动器/第二运行时 | ✅ |
| 2 桌面入口 | 桌面 `.lnk` 与开始菜单 `.lnk` 均指向同一 `win-unpacked\Hermes.exe`，`TargetPath` 存在（`Test-Path=True`）；开始菜单图标指向 `apps\desktop\assets\icon.ico`、桌面图标指向 `win-unpacked\resources\icon.ico`（**两处 icon 路径不同**，见 F-05） | ✅（附观察） |
| 3 官方基线 + 用户配置 | config v46 由官方更新器迁移；受管字段与用户 provider/model/auth 零改写（receipt `gateway_restart.restarted_services=[]`、`failed_units=[]`）；`model.*`/`credentials`/`auth.json` 在 `preserved` 清单 | ✅ |
| 4 无阻塞开销 | hooks 1 个、`doctor` 无阻塞项；覆盖层未新增全局规则；`.hermes/task-runtime` 仅 0.8 MB | ✅ |
| 5 任务级模型策略 | 未触碰模型路由；无新增全局成本/速率上限；计费仍为 `UNKNOWN`（L-2 生效，禁止成本声明） | ✅ |

---

## 5. Hermes 自有执行/调度面（本审计新读）

| 面 | 事实 | 含义 |
|---|---|---|
| `state.db` | **4,509,577,216 B（≈4.2 GB）**；`sessions 2007`、`messages 293,527`、`async_delegations 23`、`session_model_usage 1720`、`system_prompts 241`、`gateway_heartbeats 27` | 会话历史库；体积为**已登记的 `O1` 可选项**（`OPEN-TASK-REGISTER` 标 DEFERRED） |
| `kanban.db` | **tasks 0 / task_runs 0 / task_events 0** | 本项目任务**不经 Hermes Kanban**；任务真值在 `taskpacks/` + `.project-local/runs/`（治理最小化） |
| `projects.db` | 9 个已注册项目（含 `work-lab`）、`project_folders 9` | 仅项目注册表；无调度语义 |
| `cron/jobs.json` | **`"jobs": []`**（`updated_at 2026-09-19`） | **当前无任何定时任务** |
| `cron/executions.db` | 902 行；`completed 854 / failed 46 / unknown 2`；**最后一次 `started_at 2026-08-11T20:58:05+08:00`** | 历史定时执行已停止；两个大 job（562 / 202 次）为 8 月历史 |
| `verification_evidence.db` | `verification_events 128`、`verification_state 198`，**最后事件 `2026-08-26`** | 该库已停用，当前验证走 CI + `.project-local` 证据 |
| `spawn-ledger.json` | 2 条 | 历史 spawn 记录 |
| `processes.json` | 0 条 | 无受管长期子进程登记 |

> 结论：Hermes 在本项目**当前没有自动化调度面在跑**；所有任务都是**显式会话驱动 +
> 仓库内记录 + 短分支 PR**。这与 `WORK-LAB-AUTHORITY.md` §5「治理最小化」一致。

---

## 6. 发现（按严重度）

### F-01（中）轮次 2 的提交证据与当前 `main` 祖先链脱钩
- 事实：`HERMES-UPDATE-AND-FIXES-20260917.md` §7 的 4 个提交可解析（信息逐字匹配），
  但 `--is-ancestor main` 全为 false、无分支包含；内容经 `6bd0bd5 [Cutover]` 压缩进入 `main`。
- 影响：按 `WORK-LAB-AUTHORITY.md` §11，**不可再用这些 SHA 断言交付**；记录本身仍是一条
  **已落地**的修复台账。
- 建议：在该记录 §7 增加一句 `PROVENANCE: commits were squashed into main by 6bd0bd5 (r4 cutover);
  SHAs are evidence-only and not in main's ancestry`。**不改历史。**

### F-02（中）`WORK-LAB-HERMES-TASKPACK-RECONCILIATION.json` 是对不上盘的单据
- 事实：其 `authority.archive` zip **不存在**；`current_tree.head f89b2ac` 非当前主干；
  引用路径 `10-workflow/`、`50-taskpacks/` 已随目录收敛删除；`stop_state READY_FOR_USER_APPROVAL` 已无对象。
- 影响：它仍被 `OPEN-TASK-REGISTER` P2-05 列为"有意保留（machine authority + live consumer）"，
  但已**不能被读作现状**。
- 建议：保持文件（有 `migration-status.json` + `tests/ci/test_runner_paths` 消费者），在文件头加
  `SUPERSEDED/HISTORICAL — 2026-08 snapshot; paths and head are pre-convergence`。

### F-03（中）轮次 2 的产品回滚垫片已被保留策略轮换掉
- 事实：`HERMES-UPDATE-AND-FIXES-20260917.md` §6 把 `pre-update-2026-09-17-195657.zip`
  写成可用恢复材料；`backups/` 现仅存 **2 份 09-27 备份**（`keep_policy=2`），该 zip 已不在。
- 可用性：`state-snapshots/20260917-115657-pre-update` **仍在**（部分恢复面）；
  代码回滚 ref 依记录为"30 天后过期"。
- 建议：把该行改为 `EXPIRED_BY_RETENTION_POLICY`，并在新记录中把"备份仅保留 2 份"写成
  **已知恢复窗口约束**（现在起算：最近两份 09-27 备份）。

### F-04（低-中）仓库内瞬态运行面 2.96 GB，其中 2.45 GB 为一次性隔离区
- 事实：`.project-local` = **2,963.4 MB**，构成：
  `quarantine/dsh-011-removed-20260824` **2,449.9 MB**（DSH 移除隔离区，2026-08-24 生成、至今未清）、
  `runs/dsh-reconfig-20260904` 134.5 MB、`runs/tmp` 85.2 MB、`runs/ui-suite` 68.6 MB（含 3 个已完成的 B10 参考包）、
  `runs/pycache` 33.4 MB、`quarantine/*-bin` 各 ~6 MB、`runs/legacy-task-runtime` 27.7 MB。
- 影响：全部在 Git 根内（**边界合规**，无外溢），但属可回收的**已生成工作副产物**；
  `quarantine` 是 DSH 011 移除动作的**归档对象**，删除前需明确"是否仍需保留证据"。
- 建议：作为一次**单独授权**的清理任务（`cleanup` 类别）处理；本审计**未删除任何文件**。

### F-05（低）桌面入口两个 `.lnk` 的图标路径不一致
- 事实：桌面 `.lnk` icon = `win-unpacked\resources\icon.ico`；开始菜单 `.lnk` icon =
  `apps\desktop\assets\icon.ico`。二者均存在，App 目标一致。
- 影响：属外观一致性，不影响启动；与 `ERR-087`（DSH/NSIS 重置 `.lnk` 目标）不同类
  （Hermes 为 Electron 打包，未被 NSIS 触碰）。
- 建议：可选统一为同一图标源；不属缺陷。

### F-06（低）最新一轮的部分证据文件为 UTF-16LE
- 事实：`.project-local/runs/hermes-update-20260927/desktop-launch-readback.json` 与
  `pre-state-20260927.json` 带 `FF FE` BOM（PowerShell `Out-File` 默认编码）。
- 影响：人/工具直读会判"二进制"；JSON 语义本身正确（已用显式解码复核）。
- 建议：后续证据脚本统一 `-Encoding utf8`（或交给 `hermes-project-data.py` 的 UTF-8 约定）。

### F-07（低，观察）上一轮记录的两处信息已过期
- `hermes --version`：`Update available: 4 commits behind`（上游继续前进）。
- `doctor`：新增 `state.db write-health probe skipped … held by a live writer`
  （因桌面正在运行）；`state.db` 由 4.1 → **4.2 GB**。
- 建议：写入 `HERMES-UPDATE-HANDOFF-20260927.md` §6 的"维护前必读"，并保持
  `O1`（optimize-storage）为**需停机窗口 + 用户授权**的可选项。

### F-08（低，记录完整性）`h5-deploy-verification.json` 是历史快照
- 事实：其 `expected` 含 `windows-development-environment = 5132fc01855817c3`（轮次 4 前的旧摘要），
  与当前 `00bdce3de21e6c80` 不同；该文件为 H5 轮次现场记录，**不是当前断言**。
- 建议：无需改（历史快照），仅在引用时标注轮次。

---

## 7. 当前未闭环 / 待办（继承 + 新增）

| # | 事项 | 状态 | 归属 |
|---|---|---|---|
| O1 | `hermes sessions optimize-storage`（state.db 4.2 GB） | **DEFERRED**（`OPEN-TASK-REGISTER` 明确；需停机窗口 + 用户授权；桌面须先关闭） | 用户授权 + 维护轮 |
| — | Hermes 4 commits behind（`hermes update`） | 可选 | 下次维护轮 |
| — | `hermes setup` 补齐可选 API key | 可选（不阻塞） | 用户 |
| L-1 | 无会话级取消 | 能力限制（禁止假设可取消） | 继承常驻 |
| L-2 | 计费/额度 UNKNOWN | 未知（禁止成本声明） | 继承常驻 |
| L-3 | Hermes 侧无 exact-SHA CI | 未验证（不得写 CI green） | 继承常驻 |
| L-6 | curator × 受管目录冲突 | 未解决（策略=折回；删改仍需人工） | 继承常驻 |
| L-9 | 第二 profile `deepseek-review` 独立 | 范围约束（禁止外推） | 继承常驻 |
| F-01..F-04 | 见 §6 | 记录修正 / 单独授权清理 | 本审计建议 |
| U18 | Universal Workflow 真实外部切片（需 Hermes+Codex 第二真实执行者） | `externalProjectWrite: NOT_AUTHORIZED_BY_TASKPACK` | 逐项授权 |
| U19 | 真实桌面 WebView2 E2E | `SKIPPED_HEADLESS`（已知外部） | 需 MSVC 桌面 runner |

---

## 8. 本审计未做（边界）

- 未解包任何备份 zip 的内容（只按记录与文件大小核对；**未读取 `.env` / `auth.json` 值**）。
- 未读取 Hermes `state.db` 的 messages / prompts / responses 正文（只读表结构与计数）。
- 未重跑轮次 2 的"38/38 门禁"（其树为已退役分支，当前树门禁由 CI 的 42 门计划覆盖）。
- 未修改任何 Hermes 配置、未发布覆盖层、未删除任何文件、未改写任何历史记录。
- 未把本地结构 PASS 提升为 CI 结论（`EXACT_SHA_CI_UNVERIFIED` 在本地一律为真）。

## 9. 证据位置

| 材料 | 路径 |
|---|---|
| 本审计现场读回 | `.project-local/runs/hermes-audit-20260927/`（`doctor.log`、`hooks-doctor.log`、`probe_stores.py`、`probe_tasks.py`） |
| 覆盖层只读判定 | 重跑输出（21 × `CONVERGED`）+ `HERMES_HOME/.workflow-assistance-baseline.json` |
| curator 漂移报告 | `.project-local/artifacts/curator-foldback/curator-foldback-report.json`（本轮 `--check` 覆盖写为 0 漂移） |
| 轮次 4 记录与证据 | `taskpacks/current/HERMES-UPDATE-AND-MAINTENANCE-20260927.md`、`HERMES-UPDATE-HANDOFF-20260927.md`、`.project-local/runs/hermes-update-20260927/` |
| 轮次 1–2 记录与证据 | `taskpacks/current/HERMES-UPDATE-AND-FIXES-20260917.md`、`.project-local/artifacts/task-artifacts/WL-BASELINE-HERMES/`（61 文件） |
| 对账单据（陈旧） | `taskpacks/current/WORK-LAB-HERMES-TASKPACK-RECONCILIATION.json` |
| 开放任务行 | `taskpacks/current/OPEN-TASK-REGISTER.md`（HU-01 / O1 / U18 / U19） |
