# DESIGN-LAB UI 商业级 Workbench — MERGE_READY_HANDOFF
任务包：DESIGN-LAB_UI_FRONTEND_TASKPACK_20260930 · 分支 feat/ui-commercial-workbench-20260930

## 交接状态
- 基线：main @ `1acbfa15a8c036907aadbdc6938b8706c91b5d3e`（LIVE 读回，open PR=0）
- 改动文件：`apps/workbench/shell.ts` / `apps/workbench/style.css` /
  `apps/workbench/tests/appshell.mjs` / `apps/workbench/build/main.js`（重建）/
  `docs/UI-CONVERGENCE-20260930/`（6 份报告 + ASSET_MANIFEST.json）
- 未 tag、未 release、未动 main 保护（任务包 + 用户范围裁决）。

## 本地已验证
- tsc strict PASS；vite build PASS（4 modules，157.75 kB / 157747 B）
- unit.mjs / appshell.mjs PASS；test_service_http + test_design_layer_http 47 tests PASS
- verify_design_lab.py（V3 verifier 全链）/ verify_top_level_authority.py /
  verify_project_drift.py / verify_path_refs.py / verify_identity_gate.py /
  verify_workbench_packaging.py 全 PASS；`git diff --exit-code -- apps/workbench/build` CLEAN
- 视口截图：40 张真实渲染（5 视口 × 8 页面），零 pageerror / console error
- 全量 unittest discover（1762 tests）：本地后台执行 + CI 复核

## Evidence Truth Repair（2026-10-05）
- 缺陷：commit `0fbb674` 新增的 `SCREENSHOTS.md` 声称「12 张截图已生成 / 真实渲染 /
  hash 已记录」，但 `docs/UI-CONVERGENCE-20260930/screenshot/` 不存在，表格数值全是
  占位符，且所写路由 `#home` / `#/project/:id` / `#/host-tools` 与代码真实路由
  （`#/dashboard` / `#/projects/:id` / `#/tools`）不一致；同目录 `VISUAL_QA.md`、
  `COMPLETION_REPORT.md` 却写 DEFERRED。属**假完成**，不是笔误。
- 处置（方案 A：真做，而不是降级文案）：新增
  `scripts/capture_workbench_screenshots.py` +
  `design-lab/tests/e2e/capture_workbench_screenshots.mjs`，真实起服务 + 真实
  Chromium + UI 内写入数据，产出 40 张 PNG 与逐张 SHA-256 清单；
  `SCREENSHOTS.md` 按实测重写，`VISUAL_QA.md` / `COMPLETION_REPORT.md` /
  `ASSET_MANIFEST.json` 状态与之对齐（统一 IMPLEMENTED / 未完成项显式 DEFERRED）。
- 截图过程暴露的真实缺陷已修：KPI count-up 以 `parseFloat` 解析
  `0.1.0-alpha.0` → 服务版本卡显示 `0.1`（假值）。修复 commit `8036439`。
- 仍未做（不假称）：宿主 E3、人工视觉验收 E4、tag/release E5。

## 合并前 CI 门（已在 `84ffc19` 实测，不再是预期）
1. `workbench-gate`（pnpm frozen install → tsc → vite build → unit smoke →
   packaging verifier → No-drift `git diff --exit-code build/`）= **SUCCESS**。
   本分支提交的重建 bundle 与 CI 重建逐字节一致。
2. `workbench-browser-e2e`（no-skip，exact-SHA controlled-runtime）= **SUCCESS**；
   冻结断言 `.app-nav-item===12` 与 `#design-*` 选择器未触碰。本机另以
   `E2E_REQUIRED=1` 跑过一遍：`ran=2 skipped=0 failed=0`、`consoleErrors=0`。
3. `Python gate`（unittest 全量 + V3 verifiers）= **SUCCESS**。
   注：`694ad2d` 上曾红过一次，根因是截图 sidecar 缺 `sourceId` 例外记录，
   未过 `verify_asset_governance`；`84ffc19` 修复后转绿。
4. `DeepSeek authority gate chain` = **SUCCESS**（本分支未改 ledger 与链产物，
   故无投影漂移）。
5. `License & secret hygiene` / `Generated-artifact clean-tree` /
   `MiniGame node` / `Top-level Authority` / `Open Design host adapter` = **SUCCESS**。

## 合并后（owner 门，不在本 PR 内）
- E3/E4 宿主实操验收（owner gate）
- tag / release（用户明确不操作自动化任务，本分支不 tag）
- ~~Playwright 截图 4 分辨率补拍~~ → 已于 2026-10-05 真实完成（见上 Evidence Truth Repair）

## 当前合并判定（2026-10-06 更新，LIVE 读回）
- PR #213 状态：`OPEN` / **`DRAFT`** / `MERGEABLE` / `mergeStateStatus=CLEAN`。
- 远端 head 已推进：`0fbb674` → … → `84ffc1954b71c34ab638d85ea0cbc41e5abe33a3`
  （已 push；`fbe94ac` 是截图证据基线，`84ffc19` 修的是 sidecar 权利记录格式）。
- CI 对 **exact SHA `84ffc19`** 判读：`Canonical Verify` 全部 job **SUCCESS**
  （18 pass / 2 skipped，skip 的是仅 main 推送才跑的 artifact proof）。
  对照证据：`694ad2d` 曾 **failure**（`Python gate`，根因 = 截图 sidecar 未过
  `verify_asset_governance`），由 `84ffc19` 修复后转绿。
- 判定：`UI_MERGE_READY` 成立（本地门全绿 + Evidence Truth 已修 + 文档内部一致 +
  无第二 ledger + 无 Authority drift + **CI exact-SHA 已绿**）。
- 仍停在 `READY_FOR_OWNER_MERGE`：un-draft、merge、branch 删除需 owner 授权。
- **合并顺序提醒**：账本合同修复与投影重生成在另一条分支
  `qoder/designlab-m1-closeout-20261005`（PR #214）上；`main` 目前的账本仍是
  违反自身 R5 合同的状态。两条都进 `main` 之后，#214 里那条 PASS evidence 因
  `apps/workbench/shell.ts` / `build/main.js` 字节变化会自然衰减为
  `SOURCE_CHANGED_OR_MISSING`，需在新 SHA 上重跑一次 61 用例再补记录
  （这是投影器设计的证据衰减，不是回归）。

## 回滚
- 单 PR squash 回滚：revert 该 merge commit；build/main.js 随 shell.ts/style.css
  一起回退，byte-determinism 门自洽。
