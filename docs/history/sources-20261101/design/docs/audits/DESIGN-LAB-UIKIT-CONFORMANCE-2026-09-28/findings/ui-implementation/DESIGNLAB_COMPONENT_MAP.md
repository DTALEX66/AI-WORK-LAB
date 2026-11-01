# DESIGN-LAB 组件地图（DESIGNLAB_COMPONENT_MAP）

权威来源：B07 `shared-ui-core/component-registry.json`（30+ 组件契约）
实现落点：`apps/workbench/style.css` + `shell.ts`

## 组件族（B07 分类）

### navigation
| 组件 | 状态 | 实现位置 |
|---|---|---|
| AppShell | ✅ 已实现 | `shell.ts` `mountAppShell` |
| Sidebar | ✅ 已实现 | `style.css` `.app-nav`（B10 玻璃 + 发光） |
| Topbar | ✅ 已实现 | `index.html` `<header>`（B10 玻璃 + 光晕） |
| Breadcrumb | ❌ 未实现（B07 有契约，B10 无视觉） | — |
| Tabs | ❌ 未实现 | — |
| CommandPalette | ✅ 已实现 | `shell.ts` `mountB10Overlays` + `style.css` `.dl-palette` |

### inputs
| 组件 | 状态 | 实现位置 |
|---|---|---|
| Button | ✅ | `style.css` `button`（B10 渐变 + 发光） |
| IconButton | ❌ | — |
| Input | ✅ | `style.css` `input` |
| SearchInput | ✅ | `.dl-palette-input` |
| Select | ✅ | `style.css` `select` |
| MultiSelect | ❌ | — |
| TagInput | ❌ | — |
| DateRange | ❌ | — |

### display / data
| 组件 | 状态 | 实现位置 |
|---|---|---|
| Card | ✅ | `style.css` `.panel`（B10 hover 发光） |
| ProjectCard | ✅ | `.brand-module`（品牌模块卡） |
| ImageCard | ❌ | — |
| AssetCard | ✅ | `.tool-card`（工具/交付格式卡） |
| EvidenceCard | ✅ | `.resource-table` + KPI |
| ToolAdapterCard | ✅ | `.tool-card` + pill |
| QualityCard | ✅ | `.kpi-card`（B10 发光 + count-up） |
| Table | ✅ | `.resource-table`（hover + 发光边框） |
| Tree | ❌ | — |
| Timeline | ✅ | `.state-machine`（B10 呼吸动画） |
| Gallery | ❌ | — |
| Graph | ✅ | `.spark`（SVG 折线 + 渐变发光） |
| Version | ✅ | 设计层版本链（`design.ts`） |
| Review | ❌ | — |

### status / feedback
| 组件 | 状态 | 实现位置 |
|---|---|---|
| Badge | ✅ | `.pill`（B10 发光状态） |
| Status | ✅ | `.pill` + `.badge` |
| Toast | ✅ | `.dl-toast`（B10 右下角） |
| Modal | ✅ | `.dl-modal-overlay` + `.dl-modal`（B10 玻璃） |
| Drawer | ✅ | `.dl-drawer`（B10 右滑 280ms） |
| Tooltip | ❌ | — |
| Popover | ❌ | — |
| ContextMenu | ❌ | — |
| Empty | ✅ | `.view-hint` / `.items li.view-hint` |
| Loading | ✅ | `.view-loading` |
| Error | ✅ | `.error` |

## B10 专属组件

| 组件 | 位置 | 说明 |
|---|---|---|
| 品牌模块网格 | `.brand-module-grid`（2×4，B05 高保真） | 8 模块：Logo/Color/Typography/Icon/Graphic Language/Templates/Applications/Assets |
| 品牌模块画布 | `.brand-module-canvas` + `.brand-module-ring` + `.brand-module-frame` | 环 + 框图形语言（CSS 渐变发光） |
| 工具 Adapter 网格 | `.tool-grid` + `.tool-card` | 2 Adapter（Illustrator/Photoshop）+ 状态 pill |
| 交付格式 manifest | `.tool-grid`（9 格式卡） | Editable Source/PDF/PNG/SVG/PSD/AI/Video/3D/Archive |
| KPI count-up | `animateKpiCount`（850ms 缓动） | vm 安全（performance 缺失时 no-op） |
| 扫光 sweep | `.scan-line::after`（2.6s 循环） | 预检 B10 关键动画 |
| 状态机呼吸 | `.state-machine-step[data-state=approved/delivered]` | 3s pulse |
| ambient 光晕 | `body` 双 radial-gradient + 网格 mask | B10 环境光 |

## 未实现组件清单（诚实记录）

以下组件 B07 registry 有契约但 B10 最终版无视觉实现，需后续迭代：
- Breadcrumb / Tabs / MultiSelect / TagInput / DateRange / IconButton / Tree / Gallery / Review / Tooltip / Popover / ContextMenu

这些组件在当前产品阶段（本地单用户 + 真实 API readback）非必需。
多用户协作路由开放时按需实现。

## DESIGN-LAB 专属组件（CODEX 验收清单）

| 组件 | 状态 | 位置 |
|---|---|---|
| AssetGrid | ✅ | 品牌模块网格 + 工具网格 |
| ProjectCard | ✅ | `.brand-module` |
| DomainBadge | ✅ | `.pill` + `.state-machine-step` |
| ToolAdapterCard | ✅ | `.tool-card` |
| QualityScore | ✅ | `.kpi-card`（count-up + 发光） |
| PreflightIssue | ✅ | `.resource-table` + `.verdict-line` |
| Layer/Artboard locator | ❌ | 需宿主集成 |
| VersionPreview | ✅ | 设计层版本链 |
| DeliverableManifest | ✅ | 9 格式 `.tool-card` |
| EvidenceRecord | ✅ | `.resource-table`（4 KPI + 表） |
| ApprovalThread | ❌ | 需多用户协作路由 |
