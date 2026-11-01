## 问题

`apps/workbench` 的前端在路由态（`#/dashboard` 等）**只渲染出侧栏 + 一片空黑区**，与 UI 套件 B10 的 1:1 复刻目标不符。

真实 Chromium 实拍基线（修复前）：只看到 280px 侧栏，topbar 与全部视图内容不可见。

## 根因（静态分析 + 运行时双向确认）

| # | 缺陷 |
|---|---|
| R1 | `header.topbar` 被 append 到 `body`，不是 `.app` 网格第二列 → 被 `.b10-app-grid.routed ~ header{display:none}` 隐藏 |
| R2 | 视图宿主 `.route-panel`（`z-index:20`）被 `.b10-app-grid.routed`（`position:fixed;z-index:65` + 不透明背景）完全覆盖 |
| R3 | 从未生成 B10 的 `main.main` 与 `section.content#content`，视图无处安放 |
| R4 | 根节点用自造类 `.b10-app-grid`（B10 用 `.app`） |
| R5 | 浮层全用自造 `dl-*` 类，而这些类**在 CSS 里根本没有规则** |
| R6 | dev 模式无 token 时 `show()` 直接短路，四个视图不渲染任何 B10 结构 |
| R7 | `kpiCard` 形参声明 `(label, value)` 与全部 13 处调用点 `(value, label)` 相反 → B10 的 35px 主色大数字显示的是**标签**而非数值（且 count-up 失效） |
| R8 | legacy `header/main/footer` 全局元素规则把 1240px `main` 上限与 192px gutter 泄漏进 `.main`/`.topbar` |

## 修复

- **shell**：按 B10 权威标签树构建
  `.app > .ambient + .grid-bg + aside.sidebar + main.main > header.topbar + section.content#content`，
  `#route-view` 即 `.content` 内的视图槽。删除 `.b10-app-grid` 与 `.route-panel`；
  改由 `show()` 单一 `sync()` 决定 chrome 可见性，取消第二个竞争的 hashchange 监听。
- **浮层**：改用 B10 类（`.overlay#modal > .modal > h3 + .body + .actions`、`.drawer#drawer`、
  `.palette#palette > .item`、`.toast#toast`）。
- **视图**：新增 dev/offline 读回缝 `apiOrEmpty()`——无 token 时以**诚实空载荷**渲染真实结构，
  并显示可见的「本地浏览模式」提示；持有 token 仍走真实 API，真实失败仍抛出，不掩盖错误。
- **kpiCard**：按调用约定修正形参顺序。
- **CSS**：legacy 页面级规则加 `body >` 作用域；删除死规则 `.resource-table`/`.route-panel`/`.b10-app-grid*`。

## 验证证据

**真实 Chromium（chromium-1228）同源对照 B10 参考页，逐视图 class 集合 diff：**

| 视图 | 修复前 gap | 修复后 gap |
|---|---|---|
| dashboard | 26 | **0** |
| brand-systems | 19 | **0** |
| preflight | 23 | **0** |
| settings | 19 | **0** |
| projects | 22 | 1 |
| collaboration | 21 | 4 |

- union gap **33 → 5**；所有视图的 `wb view host` 由 `div.route-view` 变为 **`section.content`**。
- 剩余 5 项为**有据可依的豁免**：`editProject` 是 B10 的 JS 钩子类，**不含于 B10 的 79 个 CSS 类**，无任何样式规则；
  `comment/split/page-head/page-actions` 属 collaboration 槽，本项目已明确 `VIEW_NOT_OPEN`（本机单用户服务没有协作路由），
  照搬 B10 的 localStorage 演示评论流等于伪造协作能力，违反「不伪造」铁律。
- dev server 实读 `/workbench/style.css` → HTTP 200 / 34383 B；B10 全部结构类 + 4 个 keyframes
  （floatGlow/dashMove/pulse/scanSweep）**PRESENT，0 MISSING**。
- 实拍对照：`ref-b10.png` vs `final-dashboard.png` / `final-brand-systems.png` / `final-preflight.png` / `final-settings.png`。

**本地门禁全绿：**

| 门 | 结果 |
|---|---|
| `tsc --noEmit` | exit 0 |
| `vite build` | exit 0（main.js 86.50 kB） |
| `node tests/unit.mjs` | WORKBENCH SMOKE: all checks passed |
| `node tests/appshell.mjs` | APPSHELL REGRESSION: all checks passed |

**`build/main.js` 已重新构建并提交**（满足 `workbench-gate` no-drift 与 `generated-artifact-gate` 全树干净）。
另已实测：从 LF 规范化源码重建产物与所提交产物**逐字节相同**（`git diff --exit-code -- apps/workbench/build` = 0），
确保 CI 在 Linux 检出的行尾下重建不会产生漂移。

## 环境诚实标注

本机 `pnpm` 自身安装损坏（`D:\All projects\DSH\pnpm-store\v11\links\@\pnpm\11.22.0\...` 缺失，属 DSH 运行时问题，
不在本项目范围、也不得外溢修改）。因此上述本地门禁以**同一底层工具直接调用**
（`node node_modules/typescript/bin/tsc`、`node node_modules/vite/bin/vite.js`、`node tests/*.mjs`），
与 `pnpm --filter @design-lab/workbench typecheck|build|test:unit` 等价。CI 以可用的 pnpm 跑权威命令作为最终门禁。

## 兼容性

- `.app-nav` / `.app-nav-item` 保留，且 `.app-nav` 仍是 `document.body` 首个子节点 → `appshell.mjs:117-120`
  的位置断言与 browser E2E 的移动端导航几何断言均不受影响。
- `#route-view` id 保留（`appshell.mjs:133/140/146`）。
- `#login` gate 仅新增 B10 `input` / `primary-btn` 类，`#connect-form button`、`#token` 选择器不变。
- 未连接且非 dev 模式时，仍显示「请先连接本机设计服务」（不伪造数据）。
