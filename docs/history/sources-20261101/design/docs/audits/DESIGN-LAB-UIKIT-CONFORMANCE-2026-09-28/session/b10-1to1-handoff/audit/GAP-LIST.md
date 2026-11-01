# B10 1:1 结构缺口清单（运行时推导）

生成方式：真实 Chromium（chromium-1228）同源对照 B10 参考页与 workbench dev server 的
**实际渲染 DOM**，逐视图比对 class 集合与计数。证据：`evidence/dom-diff.json`。

- 参考：`.project-local/b10-1to1-handoff/ui-suite-extract/B10/index.html`（sha256 `BCECFFE9…E2C2E51B`）
- 样式：同目录 `extracted-style.css`（sha256 `D7354185…8316FD4D`）
- 工具：`audit/extract-b10-structure.ps1`（静态）、`audit/compare-dom.mjs`（运行时）
- 基线 SHA：`e273436aa547720e682c3ad6ae3814f7002b4279`

## 0. 两个前置事实（已核实）

1. B10 `index.html` 的内联 `<style>` 与 `extracted-style.css` **逐行相同**（520/520 行，0 差异）
   → `extracted-style.css` 是权威样式。
2. `apps/workbench/style.css` 已包含 B10 全部 79 个 CSS 类（`.app` … `.warn` 全部为 YES）
   → **CSS 层已完整，缺口 100% 在 DOM 结构层。**

## 1. 根因（运行时复现）

在 `#/dashboard` 实拍 Chromium 截图（`evidence/cur-workbench-dashboard.png`）显示：
**路由视图只渲染出侧栏 + 一片空黑区**，topbar 与视图内容完全不可见。

静态根因（与截图一致）：

| # | 缺陷 | 证据 |
|---|---|---|
| R1 | `header.topbar#b10-topbar` 被 append 到 `body`，不是 `.app` 网格第二列 → 被 `.b10-app-grid.routed ~ header{display:none}` 隐藏 | style.css:236，shell.ts:933 |
| R2 | 视图宿主 `.route-panel`（`z-index:20`）被 `.b10-app-grid.routed`（`position:fixed;z-index:65`+不透明背景）完全覆盖 | style.css:222-229、255-262 |
| R3 | 从未生成 B10 的 `main.main` 与 `section.content#content`，视图无处安放 | dom-diff：所有视图 `wb view host: div.route-view` |
| R4 | 根节点用自造类 `.b10-app-grid`（B10 无此规则，B10 用 `.app`） | style.css:222；B10 CSS:26 |
| R5 | 浮层全用自造 `dl-*` 类，B10 的 `.overlay/.modal/.drawer/.palette/.toast/.item` 从未生成 | shell.ts:821-870 |
| R6 | dev 模式无 token 时 `show()` 直接短路为"请先连接"，四个视图不渲染任何 B10 结构（与 shell.ts:22 声明的 "browsable without a service token" 意图矛盾） | shell.ts:660-668 |

## 2. 缺口类清单（跨 6 视图并集，33 个）

`actions app body comment content drawer editProject input item kpi kpi-grid list list-item
main modal muted overlay page-actions page-head palette primary-btn progress scan-line spark
split table table-wrap three-col toast trend two-col up warn`

按归属分组：

| 组 | B10 类 | 现状 | 修复点 |
|---|---|---|---|
| **A 外壳** | `app` `main` `content` | 用 `.b10-app-grid`，无 `main.main`/`section.content` | shell.ts `mountB10Sidebar` |
| **B 浮层** | `overlay` `modal` `body` `actions` `drawer` `palette` `item` `toast` | 全部 `dl-modal*`/`dl-drawer`/`dl-palette*`/`dl-toast` | shell.ts `mountB10Overlays` |
| **C 视图体** | `page-head` `page-actions` `kpi-grid` `kpi` `list` `list-item` `tag` `three-col` `two-col` `toolbar` `table` `table-wrap` `split` `comment` `progress` `spark` `scan-line` `trend` `up` `warn` `muted` `input` `primary-btn` `editProject` | 渲染器已写 B10 类，但 dev 无 token 时不执行（R6） | shell.ts `show()` 短路 |

## 3. workbench 独有的非 B10 类（漂移，30 个）

`app-nav app-nav-brand app-nav-item app-nav-meta b10-app-grid dl-drawer dl-modal
dl-modal-actions dl-modal-body dl-modal-overlay dl-palette dl-palette-item dl-toast error
eyebrow items preflight-input preflight-result project-picker project-select resource-table
route-panel route-view route-view-body secondary state-machine state-machine-step view-hint
view-loading view-unopened`

其中 `.b10-app-grid`、`.dl-*` 属 **R4/R5 自造类，须替换为 B10 类**；
`app-nav*`、`route-panel/view*`、`resource-table` 等属 workbench 自身产品类，
只在与 B10 同名位置冲突时让位，不整体删除。

## 4. 共享类计数差异（视图内容缺失的直接后果）

| 视图 | 差异 |
|---|---|
| dashboard | `panel: 10→9`、`tag: 10→2`、`ghost-btn: 4→2`、`ok: 4→1`、`info: 4→1`、`active: 1→2` |
| brand | `panel: 7→9`、`tag: 6→2`、`ghost-btn: 3→2` |
| preflight | `panel: 6→9`、`tag: 6→2` |
| settings | `panel: 4→9`、`tag: 15→2` |
| projects | `panel: 2→9`、`tag: 10→2`、`ghost-btn: 8→2` |
| collab | `panel: 3→9`、`tag: 9→2` |

workbench 侧 `panel: 9` 恒为 legacy `#workspace` 的隐藏面板，说明**路由视图本身几乎没渲染**。

## 5. 验收口径

1. `dom-diff` union gap = 0（或仅剩有据可依的豁免项）
2. Chromium 实拍 workbench `#/dashboard` 与 B10 `#dashboard` 视觉一致
3. `typecheck` + `build` + `tests/unit.mjs` + `tests/appshell.mjs` 全绿
4. dev server 实读 `/workbench/style.css` 确认 B10 块在位

---

# 修复结果（本轮）

## 改动文件（4 个）

`apps/workbench/shell.ts`、`apps/workbench/style.css`、`apps/workbench/index.html`、
`apps/workbench/build/main.js`（重新构建，CI 双门禁要求）

## 根因修复

| 编号 | 修复 |
|---|---|
| R1 | 删除 body 级 `header.topbar`，改为 `.app > main.main > header.topbar`，不再被 `~` 兄弟规则隐藏 |
| R2 | 删除 `position:fixed;z-index:65` 的 `.b10-app-grid` 覆盖层；视图宿主即 B10 `section.content` |
| R3 | 新增 `main.main` + `section.content#content`，`#route-view` 移入 `.content`（B10 的 26/28/30 内边距生效） |
| R4 | 根节点改用 B10 `.app`（280px + 1fr 网格），自造类 `.b10-app-grid` 归零 |
| R5 | 浮层改为 B10 `.overlay#modal > .modal > h3 + .body + .actions`、`.drawer#drawer`、`.palette#palette > .item`、`.toast#toast`；`dl-*` 归零 |
| R6 | 新增 `apiOrEmpty()` dev/offline 读回缝：无 token 时以**诚实空载荷**渲染，并显示可见的「本地浏览模式」提示（不伪造数字） |
| R7 | `kpiCard` 形参声明 `(label, value)` 与全部 13 处调用点 `(value, label)` 相反 → 大号蓝字显示的是**标签**而非数值。已按调用约定修正形参 |
| R8 | 删除死 CSS：`.resource-table`（4 条）、`.route-panel`、`.b10-app-grid*`；`header/main/footer` 页面级规则加 `body >` 作用域，不再把 192px gutter 泄漏给 B10 `.topbar`/`.main` |

## 运行时验收（真实 Chromium chromium-1228，同一浏览器同源对照）

### union gap：33 → 5，四个受验视图全部 0

| 视图 | 修复前 gap | 修复后 gap |
|---|---|---|
| **dashboard** | 26 | **0** |
| **brand-systems** | 19 | **0** |
| **preflight** | 23 | **0** |
| **settings** | 19 | **0** |
| projects | 22 | 1 |
| collaboration | 21 | 4 |

所有视图的 `wb view host` 由 `div.route-view` 变为 **`section.content`** — 视图已真正落在 B10 内容槽内。

### 剩余 5 项（有据可依的豁免）

| 类 | 归属 | 豁免理由 |
|---|---|---|
| `editProject` | projects | B10 的 JS 钩子类，**B10 CSS 79 类中不含它**，无任何样式规则 → 非视觉类 |
| `comment` `split` `page-head` `page-actions` | collaboration | 该项目已明确 `VIEW_NOT_OPEN`：本机单用户服务**没有协作路由**。B10 的评论流/审批双栏是 localStorage 演示态；照搬即等于伪造协作能力，违反铁律「不伪造」 |

其余 27 个 `extra`（`app-nav*`、`route-view`、`dl-shell`、`eyebrow`、`items`、`badge`…）
是 workbench 自身的产品类或 legacy 视图类，B10 无对应物，不构成缺口。

### 三件齐证据

1. **B10 class 存在于 CSS**：dev server 实读 `http://127.0.0.1:5173/workbench/style.css` → HTTP 200 / 34383 B；
   `.app{` `.ambient` `.grid-bg` `.sidebar{` `.brand-mark` `.nav button.active::before` `.main{` `.topbar{`
   `.search{` `.content{` `.page-head{` `.kpi-grid` `.panel{` `.list-item{` `.tag.ok` `.overlay{` `.modal{`
   `.drawer{` `.palette{` `.toast{` `.spark{` `.two-col` `.three-col` `.split` `.comment{` `.scan-line`
   + 4 个 keyframes（floatGlow/dashMove/pulse/scanSweep）**全部 PRESENT，0 MISSING**
2. **dev server 实读 + 结构对齐**：`evidence/dom-diff.json`（union gap 5，四视图 0）
3. **Chromium 实拍**：`evidence/final-dashboard.png`、`final-brand-systems.png`、
   `final-preflight.png`、`final-settings.png`；对照基线 `evidence/ref-b10.png`

### 本地门禁

| 门 | 命令 | 结果 |
|---|---|---|
| typecheck | `tsc --noEmit` | exit 0 |
| build | `vite build` | exit 0（main.js 86.50 kB） |
| unit | `node tests/unit.mjs` | WORKBENCH SMOKE: all checks passed |
| appshell | `node tests/appshell.mjs` | APPSHELL REGRESSION: all checks passed |

**环境说明（诚实标注）**：本机 `pnpm` 自身安装损坏
（`D:\All projects\DSH\pnpm-store\v11\links\@\pnpm\11.22.0\...` 缺失，属 DSH 运行时问题，
不在本项目范围且不得外溢修改）。因此上述门禁用**同一底层工具直接调用**
（`node node_modules/typescript/bin/tsc`、`node node_modules/vite/bin/vite.js`、`node tests/*.mjs`），
等价于 `pnpm --filter @design-lab/workbench typecheck|build|test:unit`。
CI 用可用的 pnpm 跑权威命令，作为最终门禁证据。

---

# 追加：CI `workbench-browser-e2e` 失败的真实根因（R9）

## 现象

首次 push 后 CI：**9 个门禁全绿，唯 `workbench-browser-e2e` 失败**。
日志显示**全部 E2E 步骤都通过**（含 `E2E ok: mobile appshell layout`），
失败只来自 console-error 断言：

```
E2E_BROWSER_ERRORS: console: Applying inline style violates the following
Content Security Policy directive 'style-src 'self'' ...
```

## 根因

服务端对 `/workbench*` 全部响应下发
`CSP = "default-src 'none'; script-src 'self'; style-src 'self'; ..."`
（`src/design_lab/workbench.py:14`，经 `src/design_lab/http_service.py:144` 发出）。
`style-src 'self'` **没有 `'unsafe-inline'`**，因此 **`style` 属性被阻断并产生 console error**。

B10 源 HTML 大量使用 `style="..."` 内联属性（drawer 的 4 处、progress 宽度等）——
它在静态页里没有 CSP 所以合法，照搬到本项目即违规。R5 的 drawer 复刻正因此引入 4 条内联样式，
成为压垮 E2E 的直接原因。

## 定位手段：对精确 CSP 做浏览器实测

`audit/csp-style-probe.mjs` —— 用服务端**逐字相同**的 CSP 响应头，在真实 Chromium 中比较各写法：

| 写法 | 结果 |
|---|---|
| `setAttribute('style', …)` | **BLOCKED**（computed color 未变，报 CSP console error） |
| `style.cssText = …` | **生效** |
| `style.setProperty(…)` | **生效** |
| `style.color = …` | **生效** |
| 注入 `<style>` 元素 | **BLOCKED** |

→ 结论：**CSSOM 写入豁免于 CSP，`style` 属性不豁免。**

## 修复（R9）

1. **`el()` 根因修复**：`style` 选项改走 `node.style.cssText`，不再 `setAttribute`。
   一处修复覆盖全应用。这也顺带修掉**两个此前潜伏、E2E 覆盖不到的内联样式违规**——
   它们在 dashboard 路由上，生产 CSP 下会静默丢弃 `.progress` 条宽度与 two-col/three-col 顶部间距，
   即恰好是本轮要复刻的 B10 视觉。
   vm DOM mock 没有 `CSSStyleDeclaration`（且 vm 环境无 CSP），故保留 `setAttribute` 回退。
2. **`sparkSvg()`**：`innerHTML` 里的 `style="filter:drop-shadow(…)"` 同样按 HTML 解析 →
   同属内联样式违规。移除该属性，辉光改由 `style.css` 的 `.spark polyline` 承担；
   描边改用 primary→secondary 渐变，与 B10 的 `url(#spark-grad)` 对齐。

## 复核（`audit/verify-csp-workbench.mjs`）

用服务端**精确 CSP 响应头** + 真实 `index.html` + 已提交 `build/main.js` + `style.css` 在 Chromium 中加载：

| 目标 | CSP 违规 | console error |
|---|---|---|
| `/workbench`（生产路径，无 hash） | **0** | **0** |
| `/workbench?dev=1#/dashboard` | **0** | **0** |
| `/workbench?dev=1#/settings` | **0** | **0** |

且 `progressWidth=266.9px` —— CSSOM 写入的进度条宽度确实生效（非被静默丢弃）。

修复后本地四门禁仍全绿；dom-diff 四视图 gap 仍为 0。


