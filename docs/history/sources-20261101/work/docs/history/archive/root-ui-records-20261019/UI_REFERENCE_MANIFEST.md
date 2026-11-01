# WORK-LAB · UI 最终落地参考清单（L10 / L10b Execution Reference Manifest）
<!-- ROOT-DISPOSITION:BEGIN NON-NORMATIVE-HISTORICAL -->
> **NON-NORMATIVE-HISTORICAL / 历史记录，不派工**（2026-10-10 登记，WUI-17）：本文件不在权威链里，正文逐字保留未改（门会把它与提交字节逐字节比对）。现行权威顺序：`WORK-LAB-AUTHORITY.md` → `.project/governance/project-authority-index.json` → `taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md` → `taskpacks/current/OPEN-TASK-REGISTER.md`（2026-10-19 更新；旧 UI 包已 SUPERSEDED_20261019 / FROZEN，不再是 CURRENT）；根目录逐份处置见 `docs/current/DOCUMENT-CENSUS.md` §4 与 `.project/governance/root-document-dispositions.json`。
<!-- ROOT-DISPOSITION:END -->

> 本清单是 L10 / L10b UI 工程落地执行（2026-09-27）的共享视觉事实源。所有页面/组件/
> 代理的工作必须锁定到本清单；发现与清单冲突时，按权威等级 B10 > B09 > B08 > B07 >
> B06 > B05 > B04 > B03 > B02 > B01 裁决，并把裁决记入 `UI_DECISIONS.md`。
>
> **L10b 追加锁定（2026-09-27）**：B10 不再只是「风格参考」，而是 **DOM/类名事实源**。
> 皮肤层 `apps/observer/frontend/src/skins/b10.css` 是 B10 单一文件 `<style>` 块的
> **逐字拷贝**；shell 与 12 页必须使用 B10 逐字存在的类名（见 §8 代码映射）。唯一
> 非 B10 样式文件是 `src/skins/l10b-shell.css`（断点/角落/可见性，逐条有理由，见 §11）。
>
> 参考资产根：`D:\All projects\UI套件`（用户授权只读源，**不得**把 zip/原图散进业务
> 源码；项目内引用走 `src/assets/generated/` 或组件/CSS token，见 §7 资产策略）。
> 解压工作区 / 视觉事实源：`.project-local/runs/ui-suite/`（gitignored，仅审计用）；
> B10 单一文件路径 `.project-local/runs/ui-suite/work-lab_最终版_高保真可部署UI/index.html`
> （43,685 字节：head+style L1-530 / body DOM L531-616 / JS L618-1029）。

## 1. 权威批次（WORK-LAB 相关条目，SHA 见 .project-local/runs/ui-suite/extraction-report.json）

| 批次 | 文件 | 类型 | 权威角色 | 是否最终权威 |
|---|---|---|---|---|
| B10 | 10_B10_.../work-lab_最终版_高保真可部署UI.zip | 可部署静态 UI（index.html 43KB） | 视觉/光效/动效/交互 最高权威 | ✅ 是 |
| B09 | 09_B09_.../work-lab_L9_交互式真实Demo.zip | 交互 Demo（interactive-demo.html） | 真实交互行为参考 | ✅ 是 |
| B08 | 08_B08_.../work-lab_L8_React_TypeScript_可运行原型.zip | React/TS 原型 + ui-core 包 | 工程结构与组件 API 参考 | ✅ 是 |
| B07 | 07_B07_.../WORK-LAB_L7_前端开发规范工程包.zip | 路由/权限/状态机/组件契约 | 前端治理规范 | ✅ 是 |
| B06 | 06_B06_.../WORK-LAB_L6_18张交互状态+Tokens.zip | 交互状态图 18 张 + interaction_tokens.json | 状态/响应式规范 | ✅ 是 |
| B05 | 05_B05_.../WORK-LAB_L5_12张高保真产品页面.zip | 12 张 1920×1080 产品页面 | 页面 IA 与内容模块 | ✅ 是 |
| B04 | 04_B04_.../WORK-LAB_L4_组件系统_16张+Tokens.zip | 组件系统 16 张 + design_tokens.json | 组件/token 规范 | ✅ 是 |
| B03 | 03_B03_.../WORK-LAB_10张页面级UI_统一体系.zip | 10 张页面级母版 | 页面母版关系 | 参考 |
| B02 | 02_B02_.../WORK-LAB_L2_VI+UI_36张细节图.zip | Logo 构造/图标/细节 | VI 细节 | 参考 |
| B01 | 01_B01_.../WORK-LAB_VI+UI_24张全套.zip | 品牌基础图 | 品牌/Logo | 参考 |

## 2. 视觉锁死（B10 + L4 tokens.json + L7 tokens.json，三方一致，已 CI 断言于 tokens.test.ts）

- 深黑 `#050D16` · 深海军 sidebar `#07111C` · surface `#081420` · surface2 `#0C1B2A`
- 边框 `#17435D` · 文本 `#EEF6FC` · 弱化 `#8EABBC`
- 主交互 Electric Blue `#2A91FF` · 信号/连线 Cyan `#20CDE1`（**只用于信号与辅助高亮**）
- 状态色：success `#22C55E` / warning `#F59E0B` / error `#EF4444` / info `#3882F6`
- 半径 4/10/16/22 · 阴影 `0 20px 80px rgba(0,0,0,.35)` · 玻璃模糊 18px
- 动效：hover 120ms / base 180ms / modal 220ms / drawer 280ms / emphasis 420ms / pressed 80ms
- 密度：comfortable 68 / default 56 / compact 44
- **禁止**：橙色/金色/米白主色、浅色企业 SaaS、大面积紫、玻璃泛滥、霓虹夜店。
  光效 = 系统状态语言（节点发光、活动 pulse、选中 glow、hover 边缘高亮），非装饰。

## 3. 产品信息架构（B07 routes.json + B10 导航，12 路由）

| 路由 | 页 | 页面组件（本仓落位） | 数据真值（v3 snapshot 投影） |
|---|---|---|---|
| `/` | 总览 Overview | `OverviewView`（App 内联 overview 重写） | KPI(执行态统计)/最近执行/Observer 信号图/系统状态/告警/最近任务包 |
| `/workflows` | 工作流 | `WorkflowsView`（新 `views/WorkflowsView.tsx`） | 搜索/筛选/状态/负责人/版本/最后执行 |
| `/workflows/:id/edit` | 工作流编辑器 | `WorkflowEditorView`（新 `views/WorkflowEditorView.tsx` + `components/graph/`） | 节点画布(Trigger/Validate/Agent/Tool/Approval/Condition/Deploy/Output) 缩放/平移/拖动/选择/连线/删除/属性/保存/发布/运行 |
| `/task-packs` | 任务包 | `TaskPacksView`（重写） | 真实 tasks 计数 + plan.tasks 明细 |
| `/observer` | 观察者 | `ObserverView`（新 `views/ObserverView.tsx`，替换旧 graph 位） | 拓扑(Agent/Workflow/Tool/MCP/Memory/TaskPack/异常) + 指标 + 趋势 + **严格只读**（§8） |
| `/policies` | 规则与策略 | `RulesPolicyView`（重写） | governance.families 真值 |
| `/integrations` | 集成 / MCP | `IntegrationsView`（重写） | adapters 族 + 7 客户端 registry（文档位，非实时健康） |
| `/memory` | 记忆管理 | `MemoryView`（重写，views/MemoryRegistryView.tsx 合并） | governance memory 族 + workspace.history |
| `/audit` | 审计追踪 | `AuditTrailView`（重写） | CI runs + executions + sourceRefs，只读可筛选 |
| `/approvals` | 审批中心 | `ApprovalsView`（重写） | workspace.plan.approvals；**无真实审批契约 ⇒ 缺字段显式 UNKNOWN，不伪造可操作按钮** |
| `/settings` | 系统设置 | `SettingsView`（重写） | 数据源 descriptor/传输真值/版本 |
| `/executions/:id` | 执行详情 | `ExecutionDetailView`（新） | 单执行真值 + 项目/token/git 关联 |

侧边栏 280px（可折叠 72px；移动端 Sheet）、顶部 78px（全局搜索/Ctrl+K 面板/状态/通知/账户区）、
面包屑、搜索、状态栏、用户区与 B10 结构一致。

## 4. UI Core（统一组件层，禁止页面内大量 hardcode）

- 布局：`AppShell` `Sidebar` `TopBar` `Breadcrumb` `PageHeader` `ResponsiveGrid` `SplitPane`
- 输入：`Button` `IconButton` `Input` `Select` `Tabs` `Search`
- 数据：`Card` `KPI` `Table` `Tree` `List` `Timeline` `Graph` `Badge` `Status` `Progress`
- 反馈：`Modal` `Drawer` `Tooltip` `Popover` `ContextMenu` `Toast` `Alert` `Empty` `Loading` `Error`
- 治理：`Permission` `Approval` `VersionCompare`
- 命令：`CommandPalette`（已存在，保持契约）
- 新增落位：`src/components/ui/`（基础）与 `src/components/graph/`（NodeGraph/Timeline，B10 光效版）。

## 5. 光效（B10 关键帧 1:1，落 CSS 变量 + 类，不逐页写）

- 环境光：微弱蓝色 ambient（`--glow-ambient` 40% primary blur）+ 32px 网格底纹（`.grid-bg`）
- 面板：hover 边框 primary 44% + `--glow-card`（0 18px 44px rgba(0,0,0,.22)）
- 节点/连线：`--glow-node` drop-shadow primary 40%；连线虚线 `dashMove` 3.6s linear 无限流
- 活动核心：`pulse` 3s ease-in-out（scale 1→1.05, opacity 1→.86）
- KPI 大数字：`text-shadow: 0 0 24px primary/32%`（`.big-number`）
- 扫描线（观测面板）：`scanSweep` 2.4s
- 全部动效尊重 `prefers-reduced-motion`（已有 `@media` 降级块，新动效必须并入）

## 6. 真值纪律（WORK-LAB Observer §8 只读铁律 + 前端 UNKNOWN 纪律）

- Observer = 只读投影：无 execute/approve/retry/apply/rollback/state-write/telemetry-ledger-write。
- 快照缺字段 ⇒ 显式 `UNKNOWN` / EmptyState，**禁止** 伪造 0、假 LIVE、假健康度、假 KPI。
- 审批中心：真实 `workspace.plan.approvals` 有数据才渲染行；无数据渲染 UnknownState +
  说明"审批契约未接入"，不提供可操作的批准/拒绝按钮（B10 的按钮形态仅作视觉参考，
  实际按钮在契约接入前是禁用态 + tooltip 说明，或整页 UnknownState）。
- Workflow Editor：节点/连线/属性为本地编辑模型（localStorage 或组件 state），
  "发布/运行" 动作在真实 workflow schema 契约接入前渲染为禁用 + 说明，不伪造成功。

## 7. 资产策略（B10 直接可用 ⇒ 直接使用；不可提取 ⇒ 1:1 重生成并登记）

- 品牌 Logo：优先使用 B02 `VI/03_03_主标志_Primary_Logo.png` 语义（几何构造）；
  本仓现有 "WL" 字标（B10 brand-mark 48px 渐变圆角方 + WL 900）已是 B10 最终形态 ⇒ 直接保留，
  不重设计 Logo。
- 背景纹理/网格：B10 纯 CSS（`.grid-bg` + ambient）直接复刻，无需位图。
- 页面级参考图（L5 12 张 / L3 10 张）：**仅审计对照用**，不作为运行时位图进 src/assets
  （避免 230MB 参考资产进仓库）。运行时视觉全部来自 CSS token + 组件。
- 若后续需真实位图（如 hero/星球/控制平面壁纸）：重生成放 `src/assets/generated/`，
  并在 `ASSET_REPLACEMENT_MANIFEST.md` 登记（原参考/为何不能直接用/新位置/用途/尺寸/差异）。

## 8. 代码映射（参考 → 本仓实现）

### 8.1 L10b 现状（B10 1:1 DOM，已达成）

| B10 参考元素 | 本仓实现位 | 差距 |
|---|---|---|
| `.app` / `.ambient` / `.grid-bg` / `.main` / `.content` | `App.tsx` | 零差异（元素与层级逐字对应） |
| `.sidebar` / `.brand` / `.brand-mark` / `.nav` / `.nav button.active::before` / `.nav-dot` / `.sidebar-footer` / `.avatar` | `components/layout/Sidebar.tsx` | 零差异（`aria-label="侧边导航"` 锚点保留；7 组 `NAV_GROUPS` 以组标题 + B10 按钮呈现） |
| `.topbar` / `.search` / `.top-actions` / `.ghost-btn` | `components/layout/TopStatusBar.tsx` | 结构零差异；搜索框文案 `搜索或命令…` + `Ctrl K` 为 CI 锚点，逐字保留 |
| `.overlay` / `.modal` / `.body` / `.actions` | `components/ui/modal.tsx` | 结构零差异；closed 不挂载（仓内组件契约）；`role=dialog`/`aria-modal`/`aria-label` 保留 |
| `.palette` / `.palette input` / `.palette .item` | `components/ui/command-palette.tsx` | 结构零差异；closed 时面板挂载但内容不渲染（避免复制导航文案） |
| `.drawer` / `.toast(.show)` | `components/ui/drawer.tsx` / `toast.tsx` | 结构零差异；B10 `.toast` 为单元素，仓内保留小栈（每项仍是 `.toast.show`） |
| `.page-head` / `.page-head h2` / `.page-head p` / `.page-actions` | `components/ui/page-header.tsx` | 零差异（h2 32px 由 b10.css 提供） |
| `.panel` / `.panel h3` | `components/ui/card.tsx` | 零差异（18px 圆角 + 表面渐变 + inset 高光 + hover 边缘光） |
| `.primary-btn` / `.ghost-btn` / `.soft-btn` / `.danger-btn` | `components/ui/button.tsx` | 零差异（半径/内边距/渐变/光晕/位移由 B10 类提供） |
| `.tag` / `.ok` / `.warn` / `.bad` / `.info` | `components/ui/badge.tsx` + `status.tsx` | 零差异（`Tag` 组件与 Badge 共用同一实现） |
| `.table-wrap` / `.table` | `components/ui/table.tsx` + audit/approvals/workflows/Views/dashboard | 零差异（密度档仅保留接口，内边距由 `.table` 决定） |
| `.list` / `.list-item` / `small` | `components/ui/list.tsx` + lane views | 零差异（`item.active` 为仓内选中态附加类） |
| `.kpi` / `.kpi strong` / `.kpi small` / `.trend up\|warn` | `components/dashboard/KPICard.tsx` | 零差异；`.kpi-number` 锚点保留在 `<strong>` 上 |
| `.metric-row` / `.metric-box` | `OverviewView` / `ObserverView` / `TaskPacksView` / `CompactHUD` | 零差异 |
| `.empty` / `.empty .icon` | `components/ui/states.tsx`（Empty/Unknown/Error/Offline 共用） | 零差异；`ErrorState` 的 `重试` 动作已移除（只读铁律） |
| `.graph-stage` / `.core` / `circle.node-dot` | `components/graph/node-graph.tsx` | 结构零差异；卫星标签锚点贴圆外侧（B10 演示在圆心，真实容器尺寸下会压住节点） |
| `.canvas` / `.flow-svg` / `.node` / `.title` / `.meta` | `components/graph/workflow-canvas.tsx` | 零差异（节点坐标来自本地编辑模型，内联 `left/top`） |
| `.toolbar` / `.seg` / `.input` / `.progress` / `.spark` / `.status-stack` / `.mono` | 各 lane + `sparkline.tsx` / `progress.tsx` | 零差异 |

### 8.2 L10 历史差距记录（已由 L10b 关闭）

| 参考位 | L10 当时实现位 | 当时差距 |
|---|---|---|
| B10 AppShell/Sidebar/Topbar | `components/layout/*` + `App.tsx` | Sidebar 260px 无 B10 active 光条/组头；TopBar 56px 无 B10 78px 搜索栏形态 |
| B10 Overview | `App.tsx` 内联 overview | 无趋势图/Observer 信号图/告警/系统状态卡 |
| B10 Editor | 无 | 新增 `WorkflowEditorView` + `components/graph/` |
| B05 12 页 | `views/*.tsx` | IA 重组为 B07 路由矩阵 |
| L4 组件系统 | `components/ui/*` | 缺 Table/Tree/Timeline/Graph/Tooltip/Popover/ContextMenu/Status/Progress |
| L6 交互 token | `index.css` | 并入 B10 dashMove/scanSweep/节点 glow |
| L7 路由/权限/状态机 | `lib/viewRegistry.ts` | 保持 lane 制（仓内无 router 依赖）；NAV_GROUPS 按 B07 重组 |

## 9. 验收（对齐 prompt §16 + B07 acceptance-checklist）

build / typecheck / vitest 全绿；12 路由全部可达；Editor 可交互（缩放/平移/拖/选/连/删/属性）；
Observer 可展示真实拓扑且只读；Approval/Audit 完整且真值诚实；统一 token（无散落品牌色）；
光效/动效/状态/响应式/可访问性（焦点环、44px 命中、对比度、reduced-motion）完成；
产出 `UI_IMPLEMENTATION_REPORT.md` / `ASSET_REPLACEMENT_MANIFEST.md` / `VISUAL_QA_REPORT.md`。

**L10b 追加验收（已回读）**

- 全 12 页 + shell 的 DOM 使用 B10 逐字类名；皮肤层为 B10 `<style>` 块逐字拷贝。
- HANDOFF §3 列出的**全部测试锚点仍绿**（11 文件 / 72 测试）；锚点文案逐字未改。
- `tsc --noEmit` 干净 · `vitest run` 72/72 · `vite build` 绿。
- 无鉴权扫描零命中（唯一 2 处为「声明不存在」的说明文案）。
- 只读扫描：只读页零 批准/拒绝/撤销/重试/回滚 控件；`ErrorState` 重试动作已删除。
- 像素层：17 张 headless 截图（真实渲染路径，`?api=` → 本地 preview 的 v3 形状快照），
  覆盖 12 页 + compact + light；结构/比例/布局/颜色/组件/字体/光效全部目检通过。

## 10. 品牌锁（不可协商）

`#050D16` 深海军蓝底 + `#2A91FF` 电光蓝主交互 + `#20CDE1` 青色信号/连线。
禁用：橙色/金色/米白主色、浅色企业 SaaS、大面积紫、玻璃泛滥、霓虹夜店。
光效 = 系统状态语言（节点发光、活动 pulse、选中 glow、hover 边缘高亮），非装饰。
L10b 全量对比度/色相审查：零禁用色引入（原 `WorkView` 的 amber 源缺口标记已改为
品牌 warning 色 + 青色点）。

## 11. `src/skins/l10b-shell.css` 逐条理由（唯一非 B10 样式文件）

| 规则 | 为什么必需 |
|---|---|
| `.sidebar-slot`（≥841px flex / ≤840px none） | B10 `.sidebar{display:flex}` 未分层，Tailwind `hidden md:flex` 无法表达断点 |
| `.app-compact{grid-template-columns:1fr}` | compact 布局无 rail，B10 `.app` 的 `280px 1fr` 必须塌成单列 |
| `.mobile-nav` / `.topbar-mobile` 可见性 | 移动端抽屉与 nav trigger 的断点切换 |
| `.sidebar{padding-left/right:16px}` | B10 品牌字标（10px/.12em）在 280px 栏内单行显示；B10 字体/字距未改 |
| `.toast-stack` | B10 `.toast` 是单个 fixed 元素；仓内保留小栈，每项仍是 `.toast.show` |
| `.sr-only` | Tailwind `sr-only` 位于 `@layer`，不能与未分层皮肤共存（Workflows 的隐藏原生 select 需要） |

## 12. 已知边界（诚实）

1. **浅色主题为部分实现**：`b10.css` 逐字编码 B10 深色调色板（无令牌间接化），故
   `html.light` 下壳层背景随 `index.css` 翻转，而 B10 表面（`.sidebar`/`.panel`/`.topbar`/
   `.table`/`.tag`）保持 B10 深色。修复需重写皮肤为令牌间接化 ⇒ 不再是逐字复刻，
   故记录而不静默修补。深色为品牌锁与主用主题。
2. **编辑器画布为本地编辑模型**（localStorage 持久化）；发布/运行在真实契约接入前禁用。
3. **`graph-stage` 卫星标签锚点**相对 B10 演示偏移约 4px（真实容器尺寸下会压住节点）。
4. 像素 QA 使用 loopback preview + v3 形状快照，证明渲染路径与 B10 结构/样式，不等于
   生产 sidecar 实时回读。
