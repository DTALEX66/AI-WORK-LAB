# HERMES 更新与修复归档（2026-09-17）

**性质**：维护记录与交付归档，**不是**新的任务权威。`currentTaskpack`（`WORK-LAB-WLR-FINAL-TASKPACK-2026-08-25` R1）在其 2026-09-24 到期前**仍然权威**；本文件是覆盖层/交接视图。
**写入者**：DSH / DeepSeek（外部写入者身份维护 Hermes）。**目标软件**：Hermes Agent。
**结论**：Hermes 已更新至 `v0.21.3 (2026.9.14)`，覆盖层全面落位并验证，**可完整使用**。

---

## 1. 最终状态（可核对的值，不是叙述）

| 项 | 值 |
|---|---|
| 引擎版本 | `Hermes Agent v0.21.3 (2026.9.14)` |
| 安装 HEAD | `98f758ae7e8db83c2bb9214c3b35adf41df15f03`（升级前 `53c57871`） |
| 配置版本 | 两个 profile 均 `v45`（升级前 `v44`） |
| CLI | `doctor` exit 0：`✓ Version files consistent (0.21.3)`、`✓ Config version up to date (v45)`、`✓ No deprecated config keys`、`✓ state.db exists (1943 sessions)`、`✓ Lock file OK` |
| 桌面入口 | 从桌面快捷方式**真实启动成功**：5 进程、主窗口标题 `Hermes`、`responding=True`；关闭后进程归零 |
| 受管资产 | **21 / 21 CONVERGED**（守卫计划 exit 0） |
| curator 漂移 | **0**（`curator_foldback --check`） |
| hooks | `doctor` → **All shell hooks look healthy**（原 1 issue） |
| 受管字段 | `display.language = "zh"`、`display.busy_input_mode = "queue"` —— 未被升级改动 |
| 用户模型路由 | `default` = `agnes-3.0-flash` / `agnes-3-0-flash`；`deepseek-review` = `deepseek-v4-flash` / `deepseek`；两者 `fallback_providers = []` |
| 仓库 | 分支 `r4-recovery-exec`，本地 == 远端，工作树 `clean` |
| 门禁 | **38 / 38 PASS，0 FAIL，0 TIMEOUT**（逐门禁单独调用） |

`doctor` 余下 2 项与本次无关且不阻塞使用：`state.db` 体积告警（`sessions.auto_prune` 早已为 `true`，可选动作是离线跑 `hermes sessions optimize-storage`）、以及提示可补**可选** API key。Discord/Telegram/Slack 的凭据缺失属"配置了平台但未给凭据"的**可选**项，不在 issue 列表内。

---

## 2. 版本升级（v0.21.2 → v0.21.3）

**决策依据**：既有 `KEEP` 裁决写死的重估条件第 1 条（出现 ≥ `v2026.9.12` 的稳定 tag）已满足 —— 远端出现 **`v2026.9.14` = `Hermes Agent v0.21.3`**（自 v0.21.2 起 1,036 提交 / 2,642 文件 / 338 PR），其中**长驻进程重复 `state.db` 写者句柄泄漏修复**正命中本机主风险（3.8 GB state.db、2 个 profile）。

**执行**：`hermes update --yes --backup` → `hermes config migrate`（v44→v45）→ 重跑 `hermes update`（补齐第二 profile 配置迁移并清除 pending-restart 记录）。

| 关键读数 | 值 |
|---|---|
| 完整升级前备份 | `backups\pre-update-2026-09-17-195657.zip`，1,784,290,101 B / 155.3 s，**3,125 条目**；**已核实含 `state.db`**（未压缩 4,084,162,560 B）、`config.yaml`（含 2 个 .bak）、`.env`、`auth.json`、2,000 项 skills（108 MB）。恢复：`hermes import <zip>` |
| 代码回滚引用 | `refs/hermes-update-backups/orphan-main-20260917-115944-53c57871d67e` → 升级前 HEAD；**30 天后过期**（产品行为） |
| 历史分叉 | 本地浅克隆与 origin/main 无共同祖先，产品 reset 到远端并留上述备份 ref |
| 升级对覆盖层的影响 | **21 项摘要 changed = 0**；`config.yaml` 摘要升级前后**不变**（迁移前）；受管字段与用户路由**零漂移** |

**未启动 gateway**：产品首轮曾报 `gateway auto-restart failed / Update incomplete`，但 `gateway status` 明确 `not running`，停机原因是用户 2026-09-15 刻意的状态纠正 → 属陈旧记录假警报；重跑 update 后产品自身报 `✓ Pending fleet restart completed.`，**未启动任何服务**。

**一处产品侧缺口（登记）**：完整备份**不含 `SOUL.md`**（3,125 条目中搜索为 0）。该受管资产只能由仓库源 + 同步器重建。

**一处上游默认变化（登记）**：配置迁移启用了 **Connections toolset**（Gmail / Linear / Notion / 本地 MCP）。属"官方基线优先"范围；可用 `hermes tools` 关闭。

---

## 3. 本轮修复的实质缺陷

| # | 缺陷 | 根因 | 修法 | 验证 |
|---|---|---|---|---|
| 1 | 分类器"结构化成功压过终端错误"：`exit 0` + 输出 `Billing or credits exhausted.` + `structured{completed,success:true}` + `acceptance_passed=True` → **SUCCESS**，且终端标记不出现在 `evidence` | 终端模式只在**版本门控的文本路径**里检查；structured 声称成功时**根本不读文本** | 签署结构化成功**之前**检查字面终端模式（运行时字面串，不需版本门控）；**只撤销不该给的成功，绝不制造成功** | 两个终端用例 → `FAILURE`；正常路径不变（clean+success+acceptance → `SUCCESS`，无 acceptance → `UNKNOWN`）；额度套件 12 项 + 既有分类器 23 项 OK |
| 2 | 偶发测试让 `governance` 门禁**假红** | 测试等 `calls >= 2`（入口自增），而 `_revision` 在 `publish_observed()` 内部赋值 → 主线程可能在 worker 未完成时断言 | 改为等待**真正被断言的条件** | 修前独立 5 次错 1 次 → 修后 **30 次全过**；整文件 25 项 OK |
| 3 | 29 个 tracked 文件违反 `.gitattributes` 的 `eol=lf`，且**每次重生成即复发** | `scripts/ci/generate_current_state.py` 用 `Path.write_text()` **未传 `newline="\n"`** → Windows 文本模式写出 CRLF | 规范化 29 个文件 + 该脚本 3 处写出均加 `newline="\n"` | 重生成后 CRLF=0；`CURRENT_STATE_FRESHNESS_PASS`；**692 个受策略约束文件扫描违规 = 0** |
| 4 | 受管终端守卫的 hook 批准失效（`hooks doctor` 1 issue） | 脚本在批准后被修改 1 行（`.hermes/task-runtime` → `.project-local/runs`） | 复核（sha256 `c928a695…` 与 09-15 全文审查所记**一致**）后**刷新**批准（非 revoke）；先备份 allowlist | `hooks doctor` → **All shell hooks look healthy**；`hooks test` 仍返回真实 wire-shape 拦截 |

**刻意不做**：`.py` 文件的 CRLF 未动 —— `text=auto` 下这是本仓库**正常结出**（382 个 tracked `.py` 中 325 个为 CRLF）；把它当缺陷即"见到字符串就判不合格"的同类错误。

---

## 4. curator 冲突：已定策略并自动化

**问题**：Hermes 原生 curator 会自行改写技能，且写入 `HERMES_HOME/skills/**` —— 正是 WORK-LAB 声明为"受管单元、整体替换语义"的目录。两个写入者共用一个目录：守卫正确地拒绝发布会污染的内容，于是部署通道被卡住；而 curator 仍在写 → **会复发**（已在 `python-testing` 上发生过一次）。

**用户裁决**：**一律折回**（选项 C）。

**落地**：
- **策略记录**在 `config/config-ownership.json` 的 `hermes.managed_asset_units.native_curator_output.scope`（标准指定的字段所有权权威，**不是** `AGENTS.md` —— 后者被本会话加载，按项目隔离规则不得由本会话编辑）。
- **自动化**：`integrations/executors/hermes/curator_foldback.py`。安全形状为**只允许"加"**：文件新增 / 追加行 / 仅行尾差异 → 自动折回（按 `.gitattributes` 归一 LF）；**文件被删 / 行被删 / 行被改 → `NEEDS_REVIEW`，绝不自动应用**。一处改写会阻止整个目标。`--check` 默认只读；`--apply` 折回仓库（**从不删除仓库文件**）；`--publish` 登记已复核摘要并驱动官方同步器。每次产出可复核 diff。
- **测试**：`tests/workflow-assistance/test_curator_foldback.py` 17 项 OK（含"折回永不删除仓库文件"这条保证）。
- **端到端**（合成 HERMES_HOME，不动真实环境）：基线 0 漂移 → 合成新增判 `FOLDABLE/EXTENDED` 且 diff 落盘 → 删掉仓库一行判 `NEEDS_REVIEW/TRIMMED`。真实环境 `--check` → **0 漂移**。

---

## 5. 仍存在的限制（继承，逐条注明影响）

| # | 限制 | 影响 |
|---|---|---|
| L-1 | **原生取消能力受限**：v0.21.3 的 `hermes pause --help` 仍写 "In-flight work is never killed"，无会话级取消；树里的 `cancelAndWait` 属 SSH bootstrap 协调且在旁支 worktree，非任务取消 | **是**：禁止假设"可取消"。WORK-LAB 侧以"单次请求预算 + 不启动长任务"规避 |
| L-2 | 计费/额度 `UNKNOWN`（目录价不等于账单）；历史一次 402 的准确表述为"请求被拒绝，未观察到成功生成" | **是**：禁止成本声明 |
| L-3 | `EXACT_SHA_CI_UNVERIFIED`：无 exact-SHA CI 覆盖 | **是**：不得写 CI green |
| L-6 | curator ↔ 受管目录的**结构性冲突**：策略已定（折回），但**删除/改写类仍需人工** | **否**（新增类已自动收敛） |
| L-7 | ~~分类器证据层级残余风险~~ | **已关闭**（见 §3 第 1 项） |
| L-8 | ~~29 文件 `eol=lf` 违规~~ | **已关闭**（见 §3 第 3 项，含根因） |
| L-5 | ~~hooks 批准失效~~ | **已关闭**（见 §3 第 4 项） |
| L-9 | 第二 profile 独立性：其有独立 105 个技能、独立 `SOUL.md`/`.env`；受管覆盖层**仅作用于根 profile** | **是**：禁止把根 profile 结论外推 |
| — | 产品完整备份**不含 `SOUL.md`** | **否**：可由仓库源 + 同步器重建 |

---

## 6. 恢复方式

| 层面 | 材料 |
|---|---|
| Hermes 数据/配置 | `hermes import "%LOCALAPPDATA%\hermes\backups\pre-update-2026-09-17-195657.zip"`（已核实含 state.db）；另有 `hermes checkpoints` |
| Hermes 代码 | `refs/hermes-update-backups/orphan-main-20260917-115944-53c57871d67e`（**30 天后过期**）；过期后按官方 installer/`hermes update` 重取 |
| 受管覆盖层 | 守卫三方基线（`HERMES_HOME/.workflow-assistance-baseline.json`）+ `HERMES_HOME/backups/workflow-assistance-sync-*`；重发布：`python integrations/executors/hermes/sync_hermes_workflow_assets.py --repo <repo> --home <HERMES_HOME> --apply --approved` |
| hook 批准 | `%LOCALAPPDATA%\hermes\shell-hooks-allowlist.json` 备份于本包 `09-evidence/`（见归档 ZIP 内清单） |
| 仓库 | `git revert <sha>` 或 `git checkout <sha> -- <path>`；本记录对应提交链见 §7 |

---

## 7. 对应提交（分支 `r4-recovery-exec`）

| 提交 | 内容 |
|---|---|
| `62d5f50` | curator 折回策略 + 自动化工具（选项 C） |
| `3d8b22a` | 生成器 LF 根因修复（`eol=lf` 不复发的关键） |
| `e4e57cc` | 分类器漏洞关闭 + 偶发测试去竞态 |
| `1b8bc3d` | `python-testing` curator 折回并收敛 live 单元 |
| `725210d`/`8fecd02`/`401d88c`/`763da68` | `WL-BASELINE-HERMES` 第 1 包交付与上传记录 |

---

## 8. 归档内容（静态交接视图）

本记录的**静态 ZIP 归档**（含逐项证据与 `SHA256SUMS.txt` 内部清单）位于证据边界内：
`.project-local/artifacts/task-artifacts/HERMES-UPDATE-20260917/`
其 `zip_sha256` 与内部清单登记在 `.project/governance/taskpack-authority-index.json` 的 `staticHandoffViews`。

**证据边界说明**：运行证据按项目标准留在 `.project-local/artifacts/`（被 gitignore），**不入源码管理**；本文件是可复核的入口记录。
