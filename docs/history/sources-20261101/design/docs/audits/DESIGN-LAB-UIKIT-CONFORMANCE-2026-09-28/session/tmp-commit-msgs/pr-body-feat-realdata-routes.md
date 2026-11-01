## 范围

前端轻量界面批次（用户全量指令：**前端优先，后端延后/并行，实操自动化不执行，保留任务文档**）。

把 AppShell 中 **4 个"有真实后端路由、但前端只有占位"的 IA 路由** 升级成**只读真数据页**，共享一个项目选择器：

| 路由 | 真实后端 | 本页行为 |
|---|---|---|
| 项目 | `GET /api/projects` | 读回项目台账。新建/选择在工作台执行，**不修改** |
| 创作工具 | `GET /api/projects/{id}/tasks` | 读回宿主任务台账（Illustrator/Photoshop）。**不触发实操** |
| 交付中心 | `GET /api/projects/{id}/tasks` | 读回交付候选任务。**不下载不打包** |
| 证据系统 | `GET /api/projects/{id}/design-layer` | 读回 briefs/directions/选定方向/活动绑定/设计系统登记。**只读** |

## 铁律遵守

- **架构边界保留诚实占位**（不凭空造 KPI）：研究 / 设计域 / 协作 三条仍标"未开放 + 原因"——本地单用户无协作模型、无持久化研究模型，是**架构边界事实**，不是数据缺失。
- **实操自动化不触发**：`POST /native-plans`、`/tasks/{job}/run`、`/patch`、`/bundle`、`/choose`、`/bind` 一律不在前端触发；页面只读回状态并**明确标注"由宿主/工作台执行"**。

## 实现

- `main.ts`：`projectPickerPanel`(共享只读选择器) + `renderProjects/renderCreativeTools/renderDeliverables/renderEvidence` + 4 个 case 接入 `renderRoute`；`VIEW_NOT_OPEN` 移除已升级 4 条、保留 3 条边界。
- `style.css`：`.project-picker/.project-select/.route-view-body/.items/.error`（dl-shell 作用域，Electric Blue 主色不变，紫色仍只进创意内容）。
- `build/main.js`：重建（53.87kB → 60.72kB，**no-drift 基线更新**）。

## 验证（真实执行，非声明）

- `tsc --noEmit` → **0 错误**
- `vite build` → 成功，产物 **60.72 kB**
- `tests/unit.mjs` → **4/4 PASS**（bundle present / no top-level import / vm-executes / labels+handlers+route-prefix）
- `tests/appshell.mjs` → **PASS**（AppShell 12 路由 + 导航 + 移动端回归）

## Evidence

E1（静态合同）+ E2（真实读回 fixture，bundle 可 vm 执行）。**未触及 E3/E4/E5**。
