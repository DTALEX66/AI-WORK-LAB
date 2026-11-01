# DESIGN-LAB UI 商业级 Workbench — FINAL_IA（最终信息架构）
任务包：DESIGN-LAB_UI_FRONTEND_TASKPACK_20260930 · 分支 feat/ui-commercial-workbench-20260930

## 全局导航（.app-nav，E2E 冻结 12 项，本分支未增减）

| # | hash | view | 标签 | 本轮变化 |
|---|---|---|---|---|
| 0 | （空） | workbench | 工作台 | 保留 legacy 单页（旧入口，E2E 依赖） |
| 1 | #/dashboard | dashboard | 仪表盘 | **升级**：活跃生产 + 最近交付 + Host/Capability + Quick Launch + blueprint 能力卡 |
| 2 | #/projects | projects | 项目 | 保留（列表 + 进入详情） |
| 3 | #/research | research | 研究洞察 | **诚实化**：未开放文案 + 能力卡（PLANNED，接入点 GET /api/research/…） |
| 4 | #/brand-systems | brand-systems | 品牌系统 | 保留（/design-systems 真实读回） |
| 5 | #/domains | design-domains | 设计领域 | **诚实化**：未开放文案 + 能力卡（PLANNED，Domain Pack 接入点） |
| 6 | #/tools | creative-tools | 创作工具 | **升级**：+ Host/Capability 状态卡（宿主 UNKNOWN + 共享输入 + MCP BLOCKED 卡） |
| 7 | #/preflight | preflight-qa | 预检 / QA | 保留（/task-preflight 读回，任务 ID 输入） |
| 8 | #/deliverables | deliverables | 交付中心 | **升级**：真实 /bundles 读回面板 + 交付包数 KPI |
| 9 | #/evidence | evidence | 证据系统 | **升级**：证据绑定链面板（项目→brief→方向→交付包） |
| 10 | #/collaboration | collaboration | 团队协作 | **诚实化**：feature-gated 未开放文案 + 能力卡（PLANNED，单用户模型） |
| 11 | #/settings | settings | 系统设置 | 保留（/environment 读回） |

参数化路由 `#/projects/:id`（project-detail）**不进 nav**（E2E itemCount===12
约束 + B10 sidebar 11 项 1:1），仅从项目列表行导航进入。

## 项目详情页固定创作流（新增 .stage-nav + .project-detail-layout）

```
横向阶段导航（.stage-nav，10 节点，可横滚）：
  Brief → References → Research* → Directions → Design System
  → Production → Versions → Review / Preflight → Handoff* → Evidence
  （* = PLANNED，标注 + tooltip，不造假）

主区（.project-detail-main，纵向面板堆叠，既有面板保留原 id）：
  任务台账（#pd-tasks-panel） + 设计层契约
  最近交付（#pd-deliveries）
  简报编辑器（#pd-brief-editor，真实写入 + 读回）
  方向面板（#pd-direction-panel）
  设计系统面板（#pd-design-system-panel，Token 写 API 缺口诚实标注）
  参考素材（#pd-reference-panel，按需预览 + 批量导入 + 取消）

右侧（.inspector，sticky 280px，可折叠）：
  方向版本环（.version-ring，data-driven）
  活动绑定摘要
  设计系统登记
```

阶段节点点击 → scrollIntoView 到对应 panel；Review/Preflight 节点 → 跳
#/preflight 路由；PLANNED 节点（Research/Handoff）→ 无目标，仅 tooltip。

## 路由 → 数据源映射（全部为既有 API，无新增）

| 视图 | 读回端点 |
|---|---|
| dashboard | /health /projects /design-systems /environment /projects/:id/tasks /projects/:id/bundles |
| creative-tools | /projects/:id/tasks /environment + 能力卡（静态登记） |
| deliverables | /projects/:id/tasks /projects/:id/bundles |
| evidence | /projects/:id/design-layer /projects/:id/bundles |
| project-detail | 同上（tasks / design-layer / design-systems / bundles） |
| brand-systems / settings / preflight-qa | 既有（本轮未动） |

## 组件策略（裁决记录）
- 既有 B10 class 体系保留：.panel / .list / .tag / .kpi-grid / .two-col /
  .three-col / .table-wrap / .progress / .status-stack / .actions。
- 新增 class（仅追加，不动既有规则）：.stage-nav* / .project-detail-* /
  .inspector* / .version-ring* / .capability-card / .quick-launch。
- UI08/UI09 Web Components：**不采用**（与 D004 classic-script + CSP + vm 单测
  三条硬合同冲突）；UI02/11/14 轻量项按需内联（CSS 进度条既有、SVG 版本环新增、
  glyph 用既有文本标签）。
