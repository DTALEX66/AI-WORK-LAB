# Batch F-2b 规格：Workbench 的 revision 前端流程

## 背景（事实）
- F-2a（PR #129）已落地设计层 revision 语义，路由：
  - `POST /api/design-briefs/{brief_id}/revisions`、`POST /api/design-directions/{direction_id}/revisions`
  - `GET /api/design-briefs/{brief_id}/lineage`、`GET /api/design-directions/{direction_id}/lineage`
  - project-scoped 别名：`/api/projects/{pid}/briefs|directions/{id}/revisions|lineage`
- 语义：修订 = 新行 `version+1` + 父行 `superseded_by` 指针 + 一条 `*-revised` 事件；修订**已 superseded** 版本 → `409 STALE_REVISION`；修订**已 chosen** 的方向 → 人类选择随新版本带走（payload `chosen_moved`），而 append-only 的 `design_system_binding` 仍留在旧绑定版本 → **`active_binding` 在重新绑定前为 null**。
- 前端现状：`apps/workbench/{index.html,style.css,main.ts}`（strict TS + Vite），`apps/workbench/build/main.js` 已提交，CI 有 no-drift 门禁（`git diff --exit-code -- apps/workbench/build`）；浏览器 E2E 驱动 `design-lab/tests/e2e/browser_design_layer_e2e.mjs`，壳测试 `design-lab/tests/test_workbench_design_layer_e2e.py`（本地无 Chromium 时诚实 SKIP、CI 必跑）。

## 交付物
1. `apps/workbench/{main.ts,index.html,style.css}`
   - 每个 brief / direction 行提供「新版本」入口（表单预填当前版本内容）→ 提交到 revisions 路由 → 成功后刷新并把高亮/焦点落在新版本
   - 呈现**版本链**（lineage）：版本号、当前 vs 已取代、`superseded_by` 指向；用纯用户语言，**不暴露** command/package/artifact 等内部概念
   - 修订已 chosen 方向后必须**如实呈现**「绑定需重新建立」（`active_binding` 为 null 可见，**不得**把旧绑定显示为当前）
   - `409 STALE_REVISION` / 404 / 401 走既有错误呈现路径，fail-closed 不静默
   - 视觉沿用既有 Workbench 语言（克制精密；**禁**紫色渐变），不新造第二套样式体系
2. 重建并提交 `apps/workbench/build/main.js`（Vite），保持 `git diff --exit-code -- apps/workbench/build` 为零
3. 扩展 `design-lab/tests/e2e/browser_design_layer_e2e.mjs`：覆盖「改版 brief → 改版已 chosen 方向 → 断言版本链与『绑定需重建』的持久化 DOM 读回」
4. 测试：`-m unittest discover -s design-lab/tests -t design-lab/tests -p "test_workbench*.py"` 全绿；E2E 壳测试保持本地诚实 SKIP 的结构

## 禁区
不碰 `src/design_lab/**`（后端由 F-2a 冻结）、`reports/`、`AUTHORITY.md`、`.project/`、`docs/`、`AGENTS.md`、`design-lab/scripts/**`。

## 验证（贴原始输出）
- 先读 `apps/workbench/package.json` 确认构建命令；构建后 `git diff --exit-code -- apps/workbench/build`（应无 diff）
- `-m unittest discover … -p "test_workbench*.py"` 全绿（含 native UI 测试）
- `design-lab/scripts/verify_design_lab.py` → `VERIFY_DESIGN_LAB=OK total=49 failed=0`
- `scripts/verify_authority_gates.py --zero-spill` → 预期 PASS；若出现 contract-graph 等其他漂移，**原样上报主线**，不要手改快照
- `git status --short`
- 若 `pnpm` / `node_modules` 不可用 → 如实报告为**阻塞项**，**不得伪造**构建产物

## 命令纪律
- wrapper 单命令：`python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- <单命令>`，workdir=`D:/All projects/DESIGN-LAB`；禁 shell 串联。
- 不 commit / stash / push / 建分支；不联网；不安装依赖（用仓库已有的 node_modules/pnpm）。
