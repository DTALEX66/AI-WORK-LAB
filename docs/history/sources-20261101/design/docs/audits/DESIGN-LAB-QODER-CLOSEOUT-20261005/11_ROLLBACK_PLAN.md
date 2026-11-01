# 11 — 回滚计划（按可独立回滚单元）

本轮**没有** force-push、没有 reset --hard、没有改写已发布历史、没有删除证据或历史任务包。
所有改动都是追加式 commit，因此回滚 = 反向提交或放弃分支。

## 单元 1 — UI 分支（`feat/ui-commercial-workbench-20260930`，远端已前进到 `84ffc19`）

远端历史：`0fbb674` → `8036439` → `ab193e6` → `13fa81e` → `fbe94ac` → `893a3ec`
→ `694ad2d` → `84ffc19`。

| 想退什么 | 做法 | 影响 |
|---|---|---|
| 截图证据 + 文档对齐（`893a3ec`/`694ad2d`/`84ffc19`） | `git revert -m 1` 逐个反做（无合并 commit，直接 `git revert <sha>`） | 只回退 docs/ 与 sidecar；代码不动 |
| 截图采集器（`ab193e6`/`13fa81e`/`fbe94ac`） | `git revert` 对应 sha | 只回退 `scripts/` + `design-lab/tests/e2e/` |
| KPI 修复（`8036439`） | `git revert 8036439` | 会重新引入「服务版本 KPI 显示 0.1」的真实缺陷，**不建议** |
| 整条 PR | 关闭 PR #213 不合并 | `main` 不受影响（未 merge） |

注意：`build/main.js` 是提交产物（Build Output Truth），任何 revert 必须把
`apps/workbench/build/main.js` 与 `shell.ts` 一起回退，否则
`git diff --exit-code -- apps/workbench/build` 门会红。revert 后重跑
`corepack pnpm --filter @design-lab/workbench build` 即可自洽。

## 单元 2 — closeout 分支（`qoder/designlab-m1-closeout-20261005`，本地未 push）

| commit | 内容 | 回滚 |
|---|---|---|
| `c3e43ea` | Plan→RIR 接缝 + 测试 | `git revert c3e43ea`（纯新增文件，无下游依赖） |
| `95b446d` | 账本合同修复 + 投影重生成 + CI drift 门 | `git revert 95b446d` 会把投影退回 `4c9f1849/2026-09-28` 的**过期**状态并让 `--check` 重新崩溃；若只想撤 CI 步骤，单独 revert 该 hunk |
| 审计文档 | `docs/audits/DESIGN-LAB-QODER-CLOSEOUT-20261005/` | 直接删该目录的 commit 即可，不影响任何门 |
| worktree | `.project-local/wt/c1` | `git worktree remove .project-local/wt/c1`（运行根内，非产品资产） |

## 单元 3 — 数据与外部性

- 未写用户项目数据：截图采集用 `tempfile` 临时项目根 + `PROJECT_LOCAL_ROOT` 覆盖，
  跑完即删；宿主软件未启动，无文档被创建或修改。
- 未访问 E 盘；未改 git config；未装第三方包（Playwright/Chromium 用本机既有安装）。
- 远端唯一动作：两次 `git push origin feat/ui-commercial-workbench-20260930`
  （fast-forward，无 force）。

## 验证回滚是否干净

```
corepack pnpm --filter @design-lab/workbench typecheck
corepack pnpm --filter @design-lab/workbench build
node apps/workbench/tests/unit.mjs && node apps/workbench/tests/appshell.mjs
git diff --exit-code -- apps/workbench/build
.venv/Scripts/python.exe design-lab/scripts/verify_design_lab.py
.venv/Scripts/python.exe scripts/generate_current_reports.py --check
.venv/Scripts/python.exe design-lab/scripts/verify_asset_governance.py
.venv/Scripts/python.exe design-lab/scripts/verify_license_coverage.py
```
