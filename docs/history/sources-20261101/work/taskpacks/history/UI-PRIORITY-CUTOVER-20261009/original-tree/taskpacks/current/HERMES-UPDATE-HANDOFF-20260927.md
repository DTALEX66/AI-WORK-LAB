# HERMES 维护交接摘要（2026-09-27）

**性质**：交接摘要（handoff summary），面向**后续任何 AGENT / 模型 / 会话**在 WORK-LAB 中继续维护 Hermes 时使用。**不是**新的任务权威、**不是**执行授权。权威顺序仍为 `WORK-LAB-AUTHORITY.md` → `.project/governance/project-authority-index.json` → 当前 taskpack / `taskpacks/current/OPEN-TASK-REGISTER.md`。
**详细记录**（四层证据分层、11 项验收门、逐项限制）：`taskpacks/current/HERMES-UPDATE-AND-MAINTENANCE-20260927.md`
**上游交付**：PR [#140](https://github.com/DTALEX66/WORK-LAB/pull/140)（squash 合并，`main` = `8f334f7`）

---

## 1. 一句话现状（2026-09-27 读回）

Hermes Agent 已更新到 **`v0.21.5+3115.g10938a7 (2026.9.24)`**（`hermes-agent` 检出 `origin/main @ 10938a7c`，install method = **git**），config **v46**，受管覆盖层 **21/21 CONVERGED**、curator **0 漂移**、hooks healthy、桌面入口可用。**可正常使用**；余下 2 项 doctor 提示为**非阻塞既有项**（见 §6）。

## 2. 关键身份与路径（照此核对，不要凭记忆）

| 项 | 值 |
|---|---|
| HERMES_HOME | `C:\Users\ALEX\AppData\Local\hermes`（本机唯一 Hermes Home） |
| 检出 | `%LOCALAPPDATA%\hermes\hermes-agent`（Git 安装；`origin` = `git@github.com:NousResearch/hermes-agent.git`） |
| CLI | `%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\hermes.exe`（**不在 PATH**，需全路径调用） |
| Python（跑仓库脚本用） | `%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe`（3.11.15）；`python`/`py`/`uv` **不在 PATH** |
| 桌面入口 | `%LOCALAPPDATA%\hermes\hermes-agent\apps\desktop\release\win-unpacked\Hermes.exe`（桌面 + 开始菜单 `.lnk` 指向它） |
| 更新 receipt | `%LOCALAPPDATA%\hermes\logs\update_receipts\latest.json` |
| 更新日志 | `%LOCALAPPDATA%\hermes\logs\update.log` |
| 覆盖层基线（live 侧） | `%LOCALAPPDATA%\hermes\.workflow-assistance-baseline.json` |
| 22 项受管目标 | 21 项由 guard 守护；`config.yaml` 为混合所有权，**同步器永不整体提升** |

## 3. 本轮做了什么（两条独立工作线，禁止互相证明）

**① 厂商更新（只走官方更新器）**
`hermes update --yes --backup`：`v0.21.3 (2026.9.14)` → `v0.21.5+3115.g10938a7`；fetch 8183 提交；config v45→v46；`outcome=success`、exit 0。
Git 检出安装**没有"下载预编译桌面包"路径**——桌面 Electron 产物由**同一检出构建**，官方更新器自动执行打包（本轮 `win-unpacked\Hermes.exe` 重建于 2026-09-27 09:58:35）。不要为此另建安装流程。
未触碰用户 provider/model/auth；受管字段 `display.language=zh`、`display.busy_input_mode=queue` 零改写。

**② 覆盖层漂移修复（策略：仓库是唯一权威，curator 输出一律折回）**

| 目标 | 处置 |
|---|---|
| `skills/software-development/python-testing` | live 纯新增 → 自动折回仓库 |
| `skills/software-development/windows-development-environment` | live 纯新增（+201/+1 新参考文件）→ 操作者逐行复核后折回 |
| `skills/autonomous-ai-agents/codex` | live 树被删空 → 从仓库重建受管单元 |
| `SOUL.md` | **拒绝 live 旧版**（缺 E/F 边界、最小权限、模型中立等 11 条）→ 发布更强的仓库版 |
| `skills/software-development/project-data-boundary` | **拒绝 live 旧版**（删掉了 `F:\` 保护，违反 `project-data-boundary.json` 的 `forbiddenExternalRoots`）→ 发布仓库版 |

发布读回：`ACTION_PLAN_READBACK_PASS`、`guard: will write 0 target(s); skip 21 converged`、curator `drifted managed targets: 0`。

## 4. 下次维护照抄这 5 条命令

```powershell
$H  = "$env:LOCALAPPDATA\hermes"
$R  = "D:\All projects\WORK-LAB"
$PY = "$H\hermes-agent\venv\Scripts\python.exe"
$HM = "$H\hermes-agent\venv\Scripts\hermes.exe"

# 1) 覆盖层只读判定（21 目标三方比较；有漂移会 exit 1 并 refuse，这是设计行为）
& $PY "$R\integrations\executors\hermes\sync_hermes_workflow_assets.py" --repo $R --home $H

# 2) curator 漂移检查（0 才是干净）
& $PY "$R\integrations\executors\hermes\curator_foldback.py" --repo $R --home $H --check

# 3) 健康与 hook（hook 若因脚本重发布失效，会在此报出）
& $HM doctor
& $HM hooks doctor

# 4) 有漂移时：先把 live 新增折回仓库（只允许"加"），删改类必须人工复核
& $PY "$R\integrations\executors\hermes\curator_foldback.py" --repo $R --home $H --apply
#    然后：--adopt-baseline --adopt-target <target>@<已复核sha256> --adopt-operator "<who>"
#    再：--apply --approved   （读回必须是 ACTION_PLAN_READBACK_PASS）

# 5) 升级（务必带 --backup；会写 HERMES_HOME，需要更宽文件权限）
& $HM update --yes --backup     # 随后确认 receipt outcome=success 与配置版本
```

## 5. 恢复材料（本轮实测可用）

| 层面 | 材料 |
|---|---|
| 全量数据/配置 | `hermes import "C:\Users\ALEX\AppData\Local\hermes\backups\pre-update-2026-09-27-094303.zip"` —— 1.8 GB / **3492 条目**，已核实含 `state.db`、`config.yaml`、`SOUL.md`、`auth.json`、`.env`（两 profile） |
| state.db 快照 | `%LOCALAPPDATA%\hermes\state-snapshots\20260927-014302-pre-update`（4.1 GB 超 1 GB 上限，快照按策略跳过该文件、保留更旧快照） |
| 代码回滚 | 检出 reflog：`10938a7cf9 main@{2026-09-27 09:48:29} merge origin/main: Fast-forward` 的上一行即旧 `98f758ae`（对象仍在库） |
| 覆盖层 | `HERMES_HOME\.workflow-assistance-baseline.json` + `HERMES_HOME\backups\workflow-assistance-sync-*` |
| hook 批准 | `HERMES_HOME\shell-hooks-allowlist.json`（当前 `approved 2026-09-17`，脚本重发布后仍有效） |

## 6. 限制与陷阱（接手前必读）

| # | 限制 | 影响 |
|---|---|---|
| L-1 | Hermes **无会话级取消**（`hermes pause --help` 仍写 "In-flight work is never killed"） | 禁止假设可取消；用"单次请求预算 + 不启动长任务"规避 |
| L-2 | 计费/额度 `UNKNOWN`（目录价 ≠ 账单） | 禁止成本声明 |
| L-3 | Hermes 侧无 exact-SHA CI 覆盖 | 不得写 "CI green" |
| L-10 | 安装落点跟随 `origin/main`（`v0.21.5+3115`），**领先发布 tag `v2026.9.24` 3115 个提交** | 运行的是未发布主线代码；要 tag 基线需官方支持 `origin/<tag>` |
| L-9 | 第二 profile `deepseek-review` 有独立 skills/SOUL | 受管覆盖层**只作用根 profile**，禁止外推 |
| — | `doctor` 余 2 项非阻塞：`state.db` 4.1 GB（`sessions.auto_prune` 已 `true`，可选离线 `hermes sessions optimize-storage`）、可选 API key 提示 | 不阻塞使用 |
| — | 沙箱陷阱：`hermes update` 会写 `HERMES_HOME`（工作区外）。DSH 的 workspace-write 会以 `Permission denied` 拒绝（`.backup.lock`、`.git/FETCH_HEAD`）；需在更宽文件权限下运行 | 见本轮实测 |
| — | `config/skill-provenance.yaml` 属于 `generate_current_state.py` 的 `CANONICAL_FILES`：**改它必须同步重算投影**，否则 CI 报 `CURRENT_STATE_FRESHNESS_FAIL source-digest-mismatch` | 提交前先跑 §4 之外的一条：`& $PY "$R\scripts\ci\generate_current_state.py" --check-current` |

## 7. 未做（明确边界）

- 未执行 `hermes sessions optimize-storage`；未 `--suspend` 或删除任何受管/用户内容。
- 未改动 Hermes provider/model/auth/桌面 state；未新建第二运行时或替代启动器。
- 本轮之后 Hermes 桌面**正在运行**（Electron 进程组，主窗口 `Hermes`）；如需停机维护请先关闭它。

## 8. 证据位置（gitignored，不入源码管理）

`.project-local/runs/hermes-update-20260927/`（更新日志、doctor/hooks 读回、guard verify 前后、curator 检查前后、发布日志、桌面启动读回、pre-state JSON）
`.project-local/artifacts/curator-foldback/`（curator 漂移报告 + 各目标 diff）
`.project-local/artifacts/task-artifacts/hermes-sync-plan-20260927.json`（结构化发布计划）
