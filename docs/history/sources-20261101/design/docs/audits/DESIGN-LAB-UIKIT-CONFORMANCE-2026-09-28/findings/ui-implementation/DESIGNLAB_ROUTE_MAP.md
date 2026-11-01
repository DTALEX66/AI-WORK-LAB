# DESIGN-LAB 路由地图（DESIGNLAB_ROUTE_MAP）

权威来源：B07 `routes/routes.json`（12 路由）+ `routes.ts`

## 主路由（11 条 primaryNav，排除 `:id` 参数路由）

| # | 路径 | ID | 标签 | shell.ts 渲染器 | 数据源 | 状态 |
|---|---|---|---|---|---|---|
| 1 | `/` | `dashboard` | 仪表盘 | `renderDashboard` | `/api/health` + `/api/projects` + `/api/design-systems` | ✅ 已实现 |
| 2 | `/projects` | `projects` | 项目 | `renderProjects` | `/api/projects` | ✅ 已实现 |
| 3 | `/projects/:id` | `project-detail` | 项目详情 | （工作台内联） | 真实 API | ✅ 默认视图 |
| 4 | `/research` | `research` | 研究洞察 | `renderRoute` default | 无后端 | ⚠️ 诚实未开放 |
| 5 | `/brand-systems` | `brand-systems` | 品牌系统 | `renderBrandSystems` | `/api/design-systems` | ✅ 已实现 |
| 6 | `/domains` | `design-domains` | 设计领域 | `renderRoute` default | 无后端 | ⚠️ 诚实未开放 |
| 7 | `/tools` | `creative-tools` | 创作工具 | `renderCreativeTools` | `/api/projects/{id}/tasks` | ✅ 已实现 |
| 8 | `/preflight` | `preflight-qa` | 预检 / QA | `renderPreflight` | `/api/task-preflight` | ✅ 已实现 |
| 9 | `/deliverables` | `deliverables` | 交付中心 | `renderDeliverables` | `/api/projects/{id}/tasks` | ✅ 已实现 |
| 10 | `/evidence` | `evidence` | 证据系统 | `renderEvidence` | `/api/projects/{id}/design-layer` | ✅ 已实现 |
| 11 | `/collaboration` | `collaboration` | 团队协作 | `renderRoute` default | 无后端 | ⚠️ 诚实未开放 |
| 12 | `/settings` | `settings` | 系统设置 | `renderSettings` | `/api/environment` | ✅ 已实现 |

## 默认视图（空 hash）

`window.location.hash === ''` → 工作台单页布局（`#workspace`），保留全部现有表单/按钮/状态。

## hash 路由映射

```
''          → workbench（默认）
'#/dashboard'      → dashboard
'#/projects'       → projects
'#/research'       → research
'#/brand-systems'  → brand-systems
'#/domains'        → design-domains
'#/tools'          → creative-tools
'#/preflight'      → preflight-qa
'#/deliverables'   → deliverables
'#/evidence'       → evidence
'#/collaboration'  → collaboration
'#/settings'       → settings
```

## Command Palette 可导航项

11 条（排除默认 workbench），全部可搜索 + 跳转。

## 页面契约（B07 `pages/page-map.json`）

每页 states：`loading` / `empty` / `error` / `permission-denied` / `ready`
shell：`AppShell`
layout：`PageHeader + ResponsiveGrid`

## 权限模型（B07 `permissions/permissions.json`）

| 角色 | 权限 |
|---|---|
| Owner | 全 9 域 × 6 动作（read/create/update/delete/approve/export） |
| DesignLead | 9 域 × 5 动作（无 delete） |
| Designer | 9 域 × 4 动作（read/create/update/comment） |
| Reviewer | 9 域 × 3 动作（read/approve/comment） |
| Producer | 9 域 × 3 动作（read/update/comment） |
| Viewer | 9 域 × 1 动作（read） |

注：当前本地单用户服务无角色切换 UI，权限模型作为契约保留，
后续多用户/协作路由开放时启用。

## 设计域状态机（B07 `state/domain-state-machine.json`）

```
brief → research → designing → review → qa → approved → delivered → archived
       ←BACK    ←BACK       ←BACK     ←BACK  ←BACK
```

每态 NEXT/BACK 双向，`approved`/`delivered` 在 UI 中呼吸动画标记。
