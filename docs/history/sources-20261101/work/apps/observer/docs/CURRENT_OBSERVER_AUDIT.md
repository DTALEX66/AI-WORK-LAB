# CURRENT_OBSERVER_AUDIT — WL-OBS-UI-DSH-20260816

> 生成：2026-08-16 · baseline SHA `bc5c17b482`（main，33 未提交改动均来自本会话 Observer 工作）

## 1. 当前组件结构

| 文件 | 职责 | 行数/KB |
|---|---|---|
| `web/scripts/fusion-v3.js` | Command Center 渲染（当前：sidebar/signalStrip/projectOverview/runtimeMatrix/tokenDash/projectHealth/governance） | 9.3KB |
| `web/scripts/render-v3.js` | v3 渲染器（truth-aware primitives：connectionStrip/metricCards/platformStatusMatrix/tokenDashboard/governanceAndGaps/historySection/sourceEvidence） | 24.7KB |
| `web/scripts/render.js` | legacy/v2 兼容渲染（KPI/项目表/阻塞/用量/治理/健康 6 面板） | 25.3KB |
| `web/scripts/app.js` | 入口：bootstrap/state/render 选择/theme/SSE/refresh（full 视图走 fusion 单壳） | 12.5KB |
| `web/scripts/api.js` | 数据层：SNAPSHOT/FIXTURE/LIVE 区分，GET-only loopback v3 | 20.9KB |
| `web/scripts/state.js` | last-good/stale/offline/revision 拒绝 | 4.4KB |
| `web/scripts/charts.js` | 原生 SVG lineChart（零依赖） | 5.5KB |
| `web/scripts/formatters.js` | escapeHtml/tokens/cost/duration/relativeTime/coverage/shortSha | 4.3KB |
| `web/scripts/accessibility.js` | live region/aria/keyboard/focus | 2.0KB |
| `web/styles/tokens.css` | 设计 token（canvas/blue/green/amber/red/purple/cyan/glass） | 6.4KB |
| `web/styles/command-center.css` | Command Center 紧凑样式（本次会话新增） | 7.1KB |
| `web/styles/components.css` | 组件样式 | 30.4KB |
| `web/styles/layout.css` / `base.css` / `themes.css` | 布局/基础/主题 | 11.9KB |

## 2. 当前数据流

```
sidecar GET /api/v1/snapshot (v3)
  → api.js normalize → state.js lastGood
  → app.js isV3Surface → WlFusionV3.render(d)（full）| WlRenderV3.compact(d)（compact）
```

## 3. 当前 UI 问题（TaskPack 判定）

- **projectOverview / runtimeMatrix / projectHealth 三函数大面积重复**（同一项目数据渲染 3 次）；
- 多个 Dashboard 设计语言拼接（Homepage 卡 + OneUptime 表 + Grafana 条），非统一 Command Center；
- sidebar 用字符图标（◈▦☰），未复用 SVG icon sprite；
- 视觉层级弱（无 Typography scale、状态色散落）；
- token 无样本时整块消失，缺设计空状态；
- compact 是 full 缩水版，非独立小窗设计。

## 4. 即将修改文件（Primary Rewrite Zone）

| 文件 | 动作 |
|---|---|
| `fusion-v3.js` | **主重构**：Command Center Composer（renderShell/renderSidebar/renderTopbar/renderGlobalCommand/renderProjectGrid/renderActivity/renderTelemetry/renderTokenTrend/renderDelivery/renderGovernance/renderDataTrust） |
| `command-center.css` | 重写：统一 token 引用 + Typography scale + 收敛卡片 |
| `tokens.css` | 加 status token（--status-success/running/warning/critical/muted/unknown） |
| `app.js` | 只保留 bootstrap/render 选择（fusion 单壳不变） |
| `tests/test_render_v3.js` | 加 Truth/Renderer/Accessibility 测试 |
| `docs/` | 新建 `COMMAND_CENTER_2_DESIGN.md` + `COMMAND_CENTER_2_VALIDATION.md` |

## 5. 明确冻结文件（Frozen Zone）

| 文件 | 冻结原因 |
|---|---|
| `api.js` | LIVE/OFFLINE/last-good/loopback/GET-only 语义不可改 |
| `state.js` | revision 拒绝/lastGood/stale 语义不可改 |
| `render.js` | legacy 兼容，最小改动 |
| `formatters.js` | 尽量冻结，pure function |
| 数据层协议/snapshot schema/sidecar writer | 不在本任务范围 |

## 6. 可能风险

- fusion 重构可能破坏现有 18 测试 → 需同步更新；
- 视觉改动大，需保持 truth-first（不伪造 KPI）；
- compact 重定义需保持小窗可用性；
- 无截图基础设施 → 视觉验证记 PENDING。
