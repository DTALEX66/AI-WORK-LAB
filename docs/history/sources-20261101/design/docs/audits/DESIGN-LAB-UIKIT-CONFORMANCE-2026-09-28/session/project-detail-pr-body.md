## 背景

W01 把 **B07 `routes.json`** 与实现逐条比对：B07 声明 **12 条路由**，实现只有 **11 条**——缺的是 **route #3 `/projects/:id`（project-detail）**，也正是 W03「项目中心」的入口。

## ⚠️ 为什么它**不能**加进 `ROUTE_VIEWS`

两条独立核实的硬约束禁止加第 13 项：

| 约束 | 证据 |
|---|---|
| `.app-nav-item` 必须恰为 **12** | `design-lab/tests/e2e/browser_design_layer_e2e.mjs:385` — `if (layout.itemCount !== 12 ...) throw` |
| B10 侧栏必须保持 **11** 项 | B10 无详情页；dom-diff 比对 `.nav button` 数量 |

所以参数化路由**独立解析**（`projectDetailId` / `projectDetailHash` + `AppView = RouteView | 'project-detail'`），**只能从项目行导航进入**——详情页本来就该这样。

## 做了什么

- `renderProjectDetail(id, target)`：B10 类体系（page-head + kpi-grid + two-col panel），真实读回 `/api/projects`、`/projects/<id>/tasks`、`/projects/<id>/design-layer`，走既有 `apiOrEmpty` 缝 → dev/离线态渲染**诚实空载荷**而非 401
- 项目表新增第 4 列，每行一个 `ghost-btn` **打开**（对齐 B10 的逐行动作按钮）
- `sync()` 在详情页保持 **项目** 导航高亮（详情页自己没有导航按钮）

## 真实 Chromium 验证（生产 CSP + 已提交 build/main.js）

| 路由 | `.app-nav-item` | B10 `.nav button` | page-head | KPI/panel | CSP 违规 |
|---|---|---|---|---|---|
| `#/projects` | 12 ✅ | 11 ✅ | h2=项目 | 3/4 | 0 |
| `#/projects/proj-abc123` | 12 ✅ | 11 ✅ | **h2=proj-abc123** | **4/6** | 0 |
| `#/projects/a%2Fb` | 12 ✅ | 11 ✅ | **h2=a/b**（编码往返） | 4/6 | 0 |
| `#/dashboard`（回归） | 12 ✅ | 11 ✅ | h2=仪表盘 | 4/9 | 0 |

**9/9 检查 PASS**，含：两条导航不变量在**每条路由**上都成立、详情页高亮 项目、编码 id 正确往返、四条路由 **0 CSP 违规**、dashboard 无回归。

## 本地门禁

`tsc --noEmit` / `vite build` / `tests/unit.mjs` / `tests/appshell.mjs` 全绿。
`build/main.js` 已重建（86.51 → 90.85 kB）并提交，满足 workbench-gate no-drift 与 generated-artifact clean-tree 两道门禁。

## 边界

只读页面：**不**提交、**不**运行、**不**取消、**不**导出，页脚 view-hint 明说由工作台执行。变量未应用（X 系列裁决仍待 owner）。
