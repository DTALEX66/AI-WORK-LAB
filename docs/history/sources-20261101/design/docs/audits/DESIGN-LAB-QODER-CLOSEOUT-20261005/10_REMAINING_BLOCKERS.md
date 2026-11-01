# 10 — 剩余阻塞与遗留项（精确到可执行）

## A. 人工 / 权限门（Agent 不能自解）

| # | 项 | 状态 | 下一动作 |
|---|---|---|---|
| A1 | Photoshop / Illustrator 真宿主 E3 | `BLOCKED_PERMISSION`（本轮 owner 选择「只做只读探测」） | 授权后执行 `design-lab/tests/host_fixtures/prepare_illustrator_lowered.py --execute-com` 与 `prepare_photoshop_native.py --execute-com` |
| A2 | Human Jury（REJECT→修正→RE-SUBMIT→PASS） | `BLOCKED_HUMAN` | 见 `08_JURY_RIGHTS_PREFLIGHT.md` 的 5 个问题，需 A1 产物 |
| A3 | PR #213 un-draft / merge / 分支删除 / tag / release | `BLOCKED_PERMISSION`（owner 门） | 已 push 到 `84ffc19`，保持 DRAFT；等 owner 决定 |
| A4 | 截图内系统字体的再分发权利确认 | `UNKNOWN RIGHTS` | 法务/许可确认前，不得据此做 `PRODUCTION_CERTIFIED` |
| A5 | Ruff 是否真正 enforce（Authority §8 遗留决策） | `OPEN` | 单独决策，不重开全语言迁移 |

## B. 账本 / 投影遗留（Agent 可执行，本轮未做）

| # | 项 | 现状 | 建议动作 |
|---|---|---|---|
| B1 | ~~`DL-R5-010` implementation/unit 投影为 `UNVERIFIED`~~ → **已闭合**：补 `outcome=PASS` evidence（61 tests OK / skipped=0，绑定 `5fb8878d`）后投影为 `IMPLEMENTED_LOCAL` / `PASS`；`host_live` / `delivery` 仍 `PARTIAL` | 后续每有产品代码提交，该证据会自然衰减为 `UNVERIFIED`，需按同法重观测（这是设计，不是缺陷） |
| B2 | `design-lab/config/capability-evidence-current.json` 的 `generatedAt=2026-09-04` / `task=DL-TP-R2-014` 是生成器里的**常量**：本轮实跑 `generate_capability_evidence_index.py` 内容幂等（50 capabilities、`current_E3=0`、`supported_current` 全 false），但日期永远不变 | 投影无法自证新鲜度，属生成器设计缺陷；修它要先定「时间戳如何处理才不破坏 drift 门」，本轮不擅自改，只记录 |
| B3 | 28 项 R5 任务 `reassessment` 仅 010 变 `REVIEWED`，其余 27 项仍 `PENDING_EVIDENCE_REVIEW` | 未复核 | 逐条按当前 Authority 产品轴复核；无证据不得抬升 |
| B4 | 11 项产品轴（CONTRACT/BACKEND/FRONTEND/…）在 ledger 里仍是 4 轴词表 | 词表与 Authority §2 不一致 | 属 Authority 级映射决策，需 owner 定口径后再改，不自作主张 |
| B5 | `reports/current/DEEPSEEK-AUTHORITY-CHAIN.json` 生成于 2026-09-29 | 可能已漂移 | 用 `scripts/deepseek_authority_chain.py` 重生成并核对 |

## A.5 数据完整性事件（本轮唯一由 Agent 造成的损失，详见 `13`）

误删 `task-runtime/service/state.db` → 346 个 / 357,703,756 bytes 原生产物失去索引；
0 个有 git 副本；卷影副本不可达；**索引不可重建**。文件本体已固化为归档
`.project-local/backups/orphaned-project-state-20261006.zip`
（sha256 `4fed9987c1348f3c7b9516872d0c39b3620db4764a38be707477b30e072bdef3`），
**但该归档仍在 gitignored 运行根内，需 owner 立即移出**。

## B.1 本清单写下后已在同日（2026-10-06）闭合的项

- **C7.1 一条命令启动**：`python -m design_lab --project <dir> workbench` 已实现，
  README 增「启动 Workbench（一条命令）」；`design-lab/tests/test_workbench_launch.py`
  读回 LISTENING/CSP/bundle 逐字节/health/401 与服务重启后项目仍在（E2）。
- **C7.5 备份/恢复契约**：`project_backup.py` + CLI `backup`/`restore` + 版本兼容拒绝恢复，9 项测试；已在真实孤儿数据上完成备份→恢复→逐哈希回读验证。
- **C7.2 clean install**：本机离线不可建 wheel（venv 无 hatchling、`uv` 不在 PATH），
  改由 CI job `wheel-install-gate` 承担；首版 1 秒变绿被判定为疑似空转并加反空转断言，
  硬化版在 `725c5b12` **真判读通过**（16s，`Ran 3 tests` + `OK` + packaged 测试未 skip）。
- **C6 的 raster materialization 前置**：`materialize_raster_regions` 已补，
  照片区域可 lower 成合法 Illustrator raster 层（见 `04`）。

## C. 本轮发现的环境/工程性事实（值得记录，避免重复踩）

| # | 事实 | 影响 |
|---|---|---|
| C1 | `node`/`pnpm` 不在 Git Bash PATH；本机 Node 在 scoop 工具链根 `10-toolchains/scoop/apps/nodejs-lts/24.18.0`，pnpm 经 `corepack pnpm` 可用 | 不探测就误判「未安装」；门需在正确 PATH 下跑 |
| C2 | 深路径 git worktree（`.project-local/task-worktrees/closeout-20261005`）会让 `verify_asset_governance.py` 因 Windows MAX_PATH 报 `cannot stat tracked file` | worktree 放在 `.project-local/wt/c1` 后全绿；Windows 上 worktree 根要短 |
| C3 | Playwright 全量 Chromium（`chromium-1228/chrome-win64/chrome.exe`）与 headless-shell 并存；既有浏览器 E2E 的探针**优先 headless-shell**，其 E2 记录里的 browser 字段是路径字符串而非版本号 | 截图证据与 E2 记录的“浏览器”口径不同，报告中已分别写明 |
| C4 | KPI count-up 是 JS 动画，Playwright `animations:'disabled'` 无效 | 任何“数值证据”截图都必须等数值收敛 |
| C5 | 仓库体积预算 `pack_mib=216.0 / hard_budget_mib=256` | 再向 docs 提交二进制证据前需先定 artifact 策略 |
| C6 | **git worktree 不得放在本仓目录树内**：closeout worktree 建在 `.project-local/wt/c1`（后试 `.wt/c1`）时，`test_reconstruction_evidence` 从「主工作树 1762 tests 无错」变成卡死/超时——它会向上扫到宿主仓库的 `.project-local` 运行时根（含归档与其他 worktree），扫描量爆炸；改在主工作树切分支跑即恢复 | 后续任何 Agent 建 worktree 必须放在仓库外部；本轮已按此纠正执行 |
| C7 | `design-lab/tests/test_reconstruction_evidence.py:657` 把真实用户目录字面量 `C:\Users\ALEX\private.json` 写进隐私负例（另一例 `/home/alex/private.json`），把本机用户名固化进测试 | 可移植性/隐私卫生问题，宜改合成路径；本轮只记录不擅改（该测试的边界用例需一并核对） |
| C8 | `generate_current_reports.py --check` **结构上不可能**在「携带刚生成好的报告的 commit」上通过：它比较 `stored_subject` 与 `current_head`，任何提交都会让 HEAD 前进，于是永远返回 `STALE ... rebind required`。本轮实测两次：生成→提交→`--check` 即 STALE（差一步自引用） | 这就是 CI 从未接这个 check 的真实原因，也说明「把 --check 直接接进 CI」是错的（我试过，红了，且红得有理）。CI 侧改用不依赖 git 快照的 `verify_task_ledger_contract.py`；将来若要接投影 drift 门，必须先在生成器里实现「允许报告自身 commit 的一步自引用」判定 |

## D. 明确冻结的外围扩张（未做，符合任务书 §9/§10）

`H3 / 全面 ComfyUI / TTS / Music / Premiere / Blender / Game asset / Collaboration /
Penpot collaboration / OpenPencil 深度集成 / 第二画布 / 第二 runtime / 第二前端`
全部维持 `DEFERRED_AFTER_M1`；`DL-R5-008/016/017/018/019/020/021/022/024/025/026/027/028`
状态未改，未删除。

## E. 历史恢复

`HISTORY_RECOVERY_PARTIAL` 维持不变：未宣称历史 100% 恢复；
本轮未触碰 `DESIGN-LAB完整项目对话与时间线汇报.md` 及其 manifest。
历史恢复与产品 M1 分离，不阻塞主链。
