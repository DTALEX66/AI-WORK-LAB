# WORK-LAB Observer 前端重设计方案（UI 冻结解除）

> 2026-08-16 · 状态：DESIGN_PROPOSAL · 归属：apps/observer
> 依据：任务包 UI 冻结已解除；历史审计 observer-truth-audit-20260814；同类项目调研（Langfuse/Grafana/agent observability）

## 1. 现状问题（审计 + 用户反馈）

| 问题 | 表现 | 根因 |
|---|---|---|
| 布局与文档不符 | README 描述 Four views（hero+4 metrics），实际 v3 渲染器不同 | 双渲染器（render.js 老 / render-v3.js 新），schema 驱动切换，README 未更新 |
| 界面显得空 | 数据驱动省略：无真实数据时面板消失 | 生产策略：无 canonical 样本不渲染 KPI/任务/用量（正确但观感空） |
| 缺少现代仪表盘模式 | 无侧栏/无图表/无状态趋势 | 历史审计刻意删除（避免假数据），但未补真实可视化 |

## 2. 同类项目调研（2026）

| 项目 | 借鉴点 |
|---|---|
| Langfuse | 可定制 home dashboard；trace/session 视图；成本/用量聚合卡 |
| Grafana | 面板行布局（rows）；状态/告警色阶；动态仪表盘 |
| OpenTelemetry/Jaeger | trace 可视化（时间线）；span 层级 |
| 现代 SaaS 监控 | 暗色优先设计系统；状态徽章；指标卡 + 趋势迷你图 |
| agent observability 平台 | 会话时间线、工具调用追踪、成本归因 |

## 3. 重规划：信息架构（对齐数据真实性）

### 3.1 布局结构（Full 视图）

```
┌──────────────────────────────────────────────────────────┐
│ Topbar: 品牌 · 只读徽章 · 连接状态 · 项目数 · 主题切换   │
├──────────────────────────────────────────────────────────┤
│ ① 数据链条（truth strip）：Sidecar / SSE / 采集时间     │
│ ② 全局指标卡（真实数据驱动，无数据不渲染）：             │
│    · 项目数 · 任务数 · Token 用量 · 数据质量             │
│ ③ 项目矩阵（table/cards）：登记状态 · Git · 分支 · SHA  │
│ ④ 任务面板（有 canonical 样本才渲染）：状态分布 · 列表   │
│ ⑤ 用量/成本（有样本才渲染）：趋势迷你图 · 合计           │
│ ⑥ 治理健康（可选）：规则/技能/适配器版本                 │
└──────────────────────────────────────────────────────────┘
```

### 3.2 视图矩阵（保留 Four views 概念，升级渲染）

| 视图 | 内容 | 用途 |
|---|---|---|
| Full Dark/Light | ①-⑥ 全部 | 日常观测 |
| Compact Dark/Light | ①③（项目矩阵）+ 状态摘要 | 常驻小窗 |

### 3.3 数据驱动原则（保留审计决策）

- 无 canonical 样本 → 面板隐藏（不渲染 UNKNOWN/0/假数据）；
- 只有真实采集 → 渲染（sourceWatermark/revision 可见）；
- 连接状态始终显示（Sidecar 离线/在线）；
- 不渲染：collector_health 0/0、fixture、executions、治理漂移（无生产数据）。

## 4. 视觉设计（保留现有 token，增强）

### 4.1 保留（已批准的 token）
- 暗色优先：#08090a canvas + indigo accent #5e6ad2；
- Apple 玻璃质感（blur 34px）+ Linear 精确 + Vercel 阴影边界；
- 技术 mono 标签（ui-monospace）。

### 4.2 增强
- 指标卡加趋势迷你图（canvas，无数据隐藏）；
- 项目矩阵支持排序（按状态/最近活动）；
- 状态徽章统一色阶（ok=green/warn=amber/bad=red/unknown=gray）；
- 增加空态设计（无数据时友好提示，非空白）。

## 5. 架构建议

| 层 | 建议 |
|---|---|
| 渲染 | 合并 render.js + render-v3.js 为单一渲染器（消除双渲染切换）；或明确 v3 为唯一 |
| 数据 | 保持 GET /api/v1/snapshot v3 + SSE（不新增 API） |
| 组件 | 保持原生 JS（无框架依赖，静态可托管） |
| 状态 | 保留 state.js（view/theme/mode） |
| 图表 | 用现有 charts.js（canvas，无外部库） |

## 6. 落地步骤（待批准）

| 步骤 | 内容 | 类型 |
|---|---|---|
| 1 | 合并渲染器为单一 v3 渲染（删 render.js 老路径或标记废弃） | 重构 |
| 2 | 新增全局指标卡区（项目/任务/用量/质量，真实数据驱动） | 新增 |
| 3 | 项目矩阵增强（排序/状态徽章/空态） | 修改 |
| 4 | 趋势迷你图（charts.js canvas，无数据隐藏） | 新增 |
| 5 | 更新 README 布局描述（消除文档偏差） | 文档 |
| 6 | 测试（渲染契约/数据驱动/无假数据）+ 质量门禁 | 测试 |

## 7. 边界与不做什么

- 不新增后端 API（复用 v3 snapshot + SSE）；
- 不引入前端框架（保持零依赖静态）；
- 不渲染假数据/UNKNOWN/0（审计铁律）；
- 不读凭据/正文（Observer 只读边界不变）。
