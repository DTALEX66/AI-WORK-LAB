# 云端三项目审计（2026-10-11）— WORK-LAB 条目逐条判定

来源：`WL-REC-0104`，入站文件 `D:/All projects/Record/AAOS-WORK-DESIGN-cloud-audit-20261011.zip`，
8,038,362 B，SHA-256 `b8bd438e74b91cb0193ffda03c13c1191a4dd54bb1614a92ada012519a1fda72`，包内 163 个文件成员。
原件按只读入站根规则未改动、未写回；仓内归档在
`docs/history/owner-inputs/record-20261011/originals/AAOS-WORK-DESIGN-cloud-audit-20261011.zip`（字节一致，
`docs/history/owner-inputs/record-20261011/SOURCE-INTEGRITY.json` 逐成员记 name/bytes/crc32/sha256），WORK-LAB 相关可读成员 51 个解到
`docs/history/owner-inputs/record-20261011/cloud-audit-readable/`。登记核对：`scripts/maintenance/owner_material_catalog.py verify` = PASS（104 材料 / 2382 成员 / 0 errors），
`find <sha>` 命中本条。**包内脚本与提示词没有执行权**：本文件只做判定，未运行其探针，未采信其对其它项目的结论。

## 版本映射（报告「版本与证据口径」原文口径，本仓复核）

| 审计所称 | SHA | 与本线的关系（实测） |
|---|---|---|
| WORK `main` | `cd4daa83e107afab8438c0e85f63a10e75314d5a` | 仍是 `origin/main`，本线领先 470+ |
| UI 分支 `ui-commercial-polish-20261007`（"WORK UI71"） | `71b1ae86bc2f9b1a756d5367bb149a7263604c9f` | **是本线 HEAD 的祖先**（`git merge-base --is-ancestor` 为真） |
| 当前登记开发线（"WORK50"） | `50dab56058765f1b61f11e45e1ca0cb2111b4a8f` | 本线历史中的一个提交 |

这一行是本文件最重要的事实：审计把 W01/W02 标为「UI71 分支」问题并声明"未直接外推 50"，但 71b1ae8 就在这条
开发线的历史里，其代码仍在当前工作树中。因此 W01/W02 不能按"别的分支"结案；只有当现行代码给出**不同结果**
时，才能判"已消失"。

## CI 读回对照（审计只是读回，未触发）

审计记录：UI71 run37567373288 failure；50dab run38125141168/38125138425 gate failure（workflow structural
contracts），同批 wlr060 run38125141147/38125138416 success。本仓 2026-10-11 自行读回：`work-lab-gate` 在
`33051db7`（run 38130943781）与 `63d9a58c`（run 38131270591）均为 failure，唯一失败成员
`test_entry_baseline_projection.py (rc=1)` → `LookupError: unknown encoding: mbcs`，即 W03。
`wlr-060-production-gates` 在两个 SHA 均 success。**同一 SHA 两条流水线结论不同**，所以引用 CI 必须点名作业。

## 计数核对：封面说 25 项，正文只有 21 项——差额是四条 WORK 条目

`docs/history/owner-inputs/record-20261011/cloud-audit-readable/00-START-HERE.txt` 写"实测报告列25项问题"，而 `docs/history/owner-inputs/record-20261011/cloud-audit-readable/findings.json` 与 `docs/history/owner-inputs/record-20261011/cloud-audit-readable/REPORT.txt` 的问题清单只有
A01–A04（4）+ W01–W04（4）+ D01–D13（13）= **21**。剩下的 4 项是 WORK 的，写在补测附录
`docs/history/owner-inputs/record-20261011/cloud-audit-readable/LINUX-REPORT.txt`「WORK50新增确认问题」一节里，编号 `WL-L01…WL-L04`，**未进 findings.json、
未进 REPORT.txt 的编号清单**。本文件把它们从附录提出来逐条对现行码位复核，四条全部成立：

| 条目 | 审计断言 | 现行码位复核（本仓实测） | 判定 |
|---|---|---|---|
| WL-L01 / P1 | 项目 Git 错归属：B 没有自己的 git 时显示 A 的 SHA/branch | `packages/client-neutral-core/scripts/snapshot_api.py` 的 `_project_projection` 里 `effective_git = (git_map or {}).get(project_id) or git_state`；`services/orchestration/composition_root.py` 又传 `git_state=git_states.get("work-lab") or next(iter(git_states.values()), None)`。两处 `or` 串起来就是"没有自己的 git 就顶上前一个仓库的" | OPEN，未修 |
| WL-L02 / P2 | 项目 CI 归属丢失 → 投影里 `ci=[]` | `services/orchestration/composition_root.py` 的 `_ci_rows` 输出键只有 runId/workflow/headSha/status/conclusion/sourceRef，**没有 projectId**；`snapshot_api.py` 却按 `r.get("projectId") == project_id` 筛选。空列表不是"没有 CI"，是筛选条件永不成立 | OPEN，未修 |
| WL-L03 / P2 | 部分估计被提升为精确 | `snapshot_api.py` 的 `_rollup_usage`：任一样本 `costQuality == "EXACT"` 即把整项目记为 EXACT（`elif ESTIMATED and != EXACT` 只做降级不做保留），而全局 `_token_summary` 在同一数据上给 ESTIMATED。两处精度规则不同源 | OPEN，未修 |
| WL-L04 / P2 | 存储失败仍称"已自动保存" | `apps/observer/frontend/src/views/WorkflowEditorView.tsx`：`localStorage.setItem(...)` 的异常被 `catch { /* quota — non-fatal */ }` 吞掉，而页头无条件渲染 `已自动保存`（tooltip `本地编辑已自动持久化`）。宣称与写入结果无因果关系 | OPEN，未修 |

这四条比 W01/W02 更要紧：它们落在**当前登记开发线**（审计标 WORK50），且都是本仓自己的读模型；
其中 WL-L01 是 P1，WL-L02 与 WL-L04 是"沉默空值/无据宣称"，正对本仓的真值纪律三条（未知不补 0、
absent ≠ 空列表 ≠ 实测为 0、一条事实一个名字）。处置去向：WL-L01/L02/L03 属 WUI-15 与 WUI-04 的读模型
接缝，WL-L04 属 WUI-11/WUI-12 的状态真值；本批只判定与登记，未改产品代码。

## 逐条判定

### W04（P2 / S：受控生成物过期）— 已修，并已把"看不见"本身修掉

审计实测 `tools[15].citedBy shipped=4 fresh=5`。根因与修复见 ERR-153/ERR-222 一族的既有登记：清单从 git
索引发现工具，新增/改动引用面后必须重读；本批在 `16461093` 重读并在 `5712fc91` 修了随之而来的引用面变化。
更重要的是这条门**此前在本地与 CI 都跑不到**：`root-governance-suite` 未接入（AG-06t 已接线）。现在的读回：
`tests/ci/test_shipped_projections_are_current.py` 11 passed（同一提交内重生成并比对，不是事后补测）。

### W03（P2 / S：Linux 上门禁无法运行）— 已修，结论待 runner 在同一 SHA 给出

根因不是"解析器在 Linux 坏了"，而是**门禁自己无法在 runner 上跑**：`mbcs` 不是编码名而是 Windows 对系统
ANSI 代码页的称呼，CPython 只在 Windows 注册它。仪器四处 `decode("mbcs")`、fixture 两处 `encode("mbcs")`——
两处拼写同一个决定，于是在写它的那台机器上永远一致。修复（ERR-267）：`ansi_codec()` 单点决定（Windows=`mbcs`，
其它主机=声明的 `cp1252`），解析结果携带 `ansiCodec`，非 Windows 侧另带 `ansiCodecBasis`
（`assumed cp1252: this host has no system ANSI codepage…`），fixture 改为向被测模块询问编码。守护 4 例，
其中 `test_the_fallback_branch_is_exercisable_on_every_host` 通过换掉模块的 `os` 绑定在 Windows 上跑通 Linux 分支，
使这次修复可以在推送之前被检验，而不是从 CI 日志里反推形状。负控制 4 处植入逐一定罪对应一例，文件全部按 sha256
还原一致（`.project-local/runs/record-20261011/falsify_ansi_codec_fix.py`）。本地 29 passed / 1 skipped。
**判定停在 FIXED_LOCALLY_PENDING_RUNNER**：Linux 结论只能由 runner 在同一 SHA 给，这条本身就是 W03 的教训。

### W01（P1 / C+真实断网：断流后页头仍称 LIVE/FRESH）— 未修，且现有守护的群体定义看不到它

现行码位复核（静态面）：`apps/observer/frontend/src/components/layout/TopStatusBar.tsx` 第 64 行
`const stateText = live ? 'LIVE' : (ts || 'UNKNOWN')` —— 本地的 `live` 为真时**覆盖**后端 `transportState`；
`apps/observer/frontend/src/lib/api.ts` 的 `reportReadFailure` 只在读取抛错时把 `live` 置假并把 source 记为
`stale`。审计的复现是真离线 6.5 秒后页头仍绿，页内 last-good 显示 STALE、compact 显示 OFFLINE——三面不一致。

本仓已有的传输真值守护为什么没抓到：`apps/observer/frontend/src/laneTransportTruth.sweep.test.tsx` 扫的是
`transportState ∈ {LIVE, …}` 并断言"快照不是 LIVE 时不得有药丸写 LIVE"。它的群体就是被审计的那个字段，所以
"快照自身仍写着 LIVE 但采样时间已过"这一状态**在该控制里根本无法构造**。这是"门的群体不得由它审计的性质定义"
的一条新实例（与 ERR-142 同族）。判定 OPEN；修复面 = 把传输健康与 `sourceWatermark` 采样时刻统一派生到每个
状态徽标（页头/页内/compact 同源），并把扫参群体改成"新鲜度×传输态"二维。归属：WUI-11（状态矩阵）与
WUI-18（真实采集与恢复）的交集，不在本批范围内动手。

### W02（P2 / R：画布连线、平移、适应画布）— 未修，且该组件在本线零测试消费者

`apps/observer/frontend/src/components/graph/workflow-canvas.tsx` 在当前工作树中存在，唯一引用者是
`apps/observer/frontend/src/views/WorkflowEditorView.tsx`；`git grep` 在 `apps/observer/frontend/src` 下**没有任何
测试文件引用它**。因此审计的三条实测（拖端点连线边数不变、点击抛 `No active pointer`、背景 overlay 令默认平移失效、
适应只重置 zoom 不重置 pan）没有本地门可以反驳，也没有门会因它回归而变红。判定 OPEN，且登记一条真实缺口：
WUI-11/WUI-14 的几何断言从未覆盖这条泳道——按既有铁律，画布类交互必须断言指针生命周期与视口几何
（pointerdown/move/up 一致、命中背景、fit 同时计算 zoom 与 pan），不能只断言组件在场。

## 其它与本项目相关、但不是"缺陷判定"的内容

- 报告 §复现运行说明第 214 行独立记下了本仓侧车的一个真实启动条件：`PYTHONPATH` 必须含
  `packages/client-neutral-core/scripts`，否则 `ModuleNotFoundError: canonical_store`。本会话在同一天以另一种方式
  撞上同一件事，现已写进本文件的来源说明之外——建议把它并入 `apps/observer` 的启动文档，而不是每人踩一次。
- 报告称 WORK50 前端 57 文件 / 672 例通过（与本仓 2026-10-10 实测一致）；本批 WUI-08 之后为 59 文件 / 683 例，
  数字变化来自新增两份测试，不是同一群体的重测。引用时必须点名是哪一条线（50dab560 还是现行 HEAD）。
- 报告 §定位与视觉 第 201 行：`最新50分支的观察/配置/治理定位比71控制台UI更接近最新边界`。这与本仓 2026-10-09
  的用户决定同向（UI 优先但Observer 是只读投影），因此 71 的控制台式表意**不**作为现行设计目标；
  但如上表所述，71 的代码在本线历史里，不能靠措辞把 W01/W02 归给"旧 UI"。
- 报告 §交给本地Windows Codex的必要补测：Windows 安装/卸载/升级与用户备份恢复、真实 LFS 归档哈希、
  外部执行端授权后的真实运行——这些属 OWNER 级前置（需要单独 Task Grant 与真实机器读回），
  与本仓 WUI-19 的「桌面安装」层缺口是同一件事，记为未执行而非通过。
- 审计明确「没有修改、提交或发布产品代码」，且 `冻结ZIP仅见5个LFS pointer，未读取真实载荷`——
  因此其对归档内容完整性的结论是 `NOT_VERIFIABLE`，本仓不得反过来把它读成"归档完好"。

## 本轮实际改动（与本判定相关的最小集）

W03 修复：`scripts/audit/entry_baseline_readback.py`（`ansi_codec()` + 结果携带编码与依据）、
`tests/ci/test_entry_baseline_projection.py`（`AnsiCodecPortabilityTests` 4 例）、`taskpacks/current/error-ledger.json`
（ERR-267，265 行，`verify_error_ledger.py` = PASS）。W01/W02 本轮**未**改动代码，只给出可检验的判定与归属。
