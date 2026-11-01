# W03 记录 —— 项目中心：B07 `/projects/:id` 路由落地

**状态：** W03 **首片已交付并合并**（W03 整体仍 `PARTIAL`——真实 Project/Brief 的
create/open/edit/save/version 全流程未做完）
**PR：** #177 → merged `main` = `4c9f18493e909283a5448763f704b3f838531d0a`
**观察 SHA（改动前）：** `cac30c7aa83e701d9ad851fa6669231bea4b7199`

---

## 1. 闭合的差异

W01 差异清单 **G-9：`project-detail` 路由缺失** → ✅ **已修**。

| | 改动前 | 改动后（merged main 实测） |
|---|---|---|
| B07 `routes.json` 声明 | 12 | 12 |
| 实现覆盖 | **11**（缺 `/projects/:id`） | **12 / 12** ✅ |

B07 的 12 条：`/`、`/projects`、**`/projects/:id`**、`/research`、`/brand-systems`、
`/domains`、`/tools`、`/preflight`、`/deliverables`、`/evidence`、`/collaboration`、`/settings`。

---

## 2. 关键设计约束（**不能**加进 ROUTE_VIEWS）

两条独立核实的硬约束禁止把 `project-detail` 作为第 13 个 `ROUTE_VIEWS` 项：

| 约束 | 证据 |
|---|---|
| `.app-nav-item` 必须恰为 **12** | `design-lab/tests/e2e/browser_design_layer_e2e.mjs:385`：`if (layout.itemCount !== 12 …) throw` |
| B10 侧栏必须保持 **11** 项 | B10 无详情页；dom-diff 比对 `.nav button` 数量 |

→ 参数化路由**独立解析**：

```ts
export type AppView = RouteView | 'project-detail';
export function projectDetailId(hash: string): string | null;   // #/projects/<id>
export function projectDetailHash(id: string): string;          // 编码往返
```

**只能从项目行导航进入**——详情页本来就该如此。

---

## 3. 真实 Chromium 验证（生产 CSP + 已提交 build）

| 路由 | `.app-nav-item` | B10 `.nav button` | page-head | KPI/panel | CSP |
|---|---|---|---|---|---|
| `#/projects` | 12 ✅ | 11 ✅ | h2=项目 | 3/4 | 0 |
| `#/projects/proj-abc123` | 12 ✅ | 11 ✅ | **h2=proj-abc123** | **4/6** | 0 |
| `#/projects/a%2Fb` | 12 ✅ | 11 ✅ | **h2=a/b**（编码往返） | 4/6 | 0 |
| `#/dashboard`（回归） | 12 ✅ | 11 ✅ | h2=仪表盘 | 4/9 | 0 |

**9/9 检查 PASS**：`nav12_everywhere` · `b10nav11_everywhere` · `detail_renders_pagehead` ·
`detail_renders_kpis` · `detail_renders_panels` · `detail_highlights_projects_nav` ·
`list_has_open_buttons` · `no_csp_violations` · `dashboard_still_ok`

机读证据：`.project-local/.../W03-ROUTE-VERIFY.json`；脚本 `w03-verify-route.mjs`（可重跑）。

---

## 4. 实现范围与边界

- `renderProjectDetail(id, target)`：B10 类体系（`.page-head` + `.kpi-grid` + `.two-col` + `.panel`/`.list`/`.list-item`/`.tag`），
  真实读回 `/api/projects`、`/projects/<id>/tasks`、`/projects/<id>/design-layer`
- 走既有 `apiOrEmpty` 缝 → dev/离线态渲染**诚实空载荷**，不 401、不伪造
- 项目表新增第 4 列，每行 `ghost-btn` **打开**（对齐 B10 的逐行动作按钮）
- `sync()` 在详情页保持 **项目** 导航高亮
- **只读**：不提交 / 不运行 / 不取消 / 不导出；页脚 `view-hint` 明说由工作台执行

---

## 5. W03 剩余（未完成）

| 项 | 状态 |
|---|---|
| B07 `/projects/:id` 路由 | ✅ **已完成** |
| 真实 Brief 的 create / open / edit / save / version 全流程 | ⏳ 未做 |
| 刷新保留项目上下文 | ⏳ 未做（当前详情页刷新可保持 hash，但未做「最近项目」持久化） |
| 失败不弹「保存成功」 | ⏳ 需真实写路径才有意义 |
| 旧单页工作入口在迁移完成前可用 | ✅ 现状即如此，未破坏 |
| 无假 KPI | ✅ 空载荷 + 可见离线提示 |

---

**END — W03 首片记录。**
