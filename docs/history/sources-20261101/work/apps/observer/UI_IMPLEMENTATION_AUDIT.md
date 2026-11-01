# UI_IMPLEMENTATION_AUDIT — WORK-LAB Observer 前端（UI套件 入库前审计）

> 按 `01_WORK-LAB_UI开发提示词_CODEX.md` 第 0 节要求：先审计仓库真实前端，再实施。
> 资产来源：`D:\All projects\UI套件`（三项目 UI 总套件），WORK-LAB 相关批次已提取入
> `.ui-reference/WORK-LAB/`（gitignored，含 146 张图 + L7 规范包 + L4/L6 tokens + B10 最终版
> + CODEX 提示词 + 权威规则 + SHA256 提取清单 `_meta/extraction_manifest.json`）。
> 审计基线：u17 分支 head `00f45a1` 的 `apps/observer/frontend` 现状。

## 1. 现有技术栈（现状盘点，REAL）

| 维度 | 现状 |
|---|---|
| 框架 | React 18.3 + TypeScript 5.6 + Vite 5.4（`apps/observer/frontend`） |
| 样式 | Tailwind 3.4 + CSS 变量双主题（`:root` dark 默认 / `html.light`）；`rgb(var(--X-rgb) / <alpha-value>)` 通道形式 |
| 组件 | `class-variance-authority` + `clsx` + `tailwind-merge` + `lucide-react` + `recharts` |
| 路由 | **无 react-router**：URL `?view=` 参数 + `viewRegistry.ts`（10 lane）+ `OVERVIEW_ID` 合成 lane |
| 数据 | `useLiveSnapshot()`（poll + SSE last-good）；类型 `types.ts::SnapshotV3` 镜像后端真实契约 |
| 测试 | vitest + @testing-library/react；已 18+ 行为测试 |
| 纪律 | UNKNOWN 不伪造（cost/token/quota/agent 全部诚实态）；Compact HUD 320px 安全；`prefers-reduced-motion` 已处理 |

## 2. 权威 vs 现状差距（本次升级目标）

### 2.1 色板违规（最高优先）
- 权威（B10 index.html = L4 tokens = L7 tokens 三处一致）：
  `--bg:#050D16 --sidebar:#07111C --surface:#081420 --surface2:#0C1B2A --border:#17435D
   --primary:#2A91FF --secondary:#20CDE1 --text:#EEF6FC --muted:#8EABBC
   success:#22C55E warning:#F59E0B error:#EF4444 radius:18/12 blur:18`
- 现状 `index.css`：**secondary = `#7C6CF0` 紫色 / `124 108 240`（light 也是 `109 94 240` 紫）**
  → 违反 CODEX 提示词第 3 节"禁紫/禁三项目混色"；`--color-bg:#0d1117`（GitHub 风）偏离 `#050D16`
  深海军蓝。radius 仅 6px 硬编码，无 radius/shadow/blur/motion/density token。
- 判定：**换皮级差距，全部可修**。

### 2.2 信息架构（L7 12 路由 vs 现状 10 lane）
L7 `routes.json` 12 路由：`/ /workflows /workflows/:id /workflows/:id/edit /task-packs
/observer /policies /integrations /memory /audit /approvals /settings`。
现状 lane：agents/executions/models/memory/tools/monitoring/delivery/trust/software/settings
（+overview 合成）。
映射结论（不新增 npm 依赖，沿用 `?view=` 机制）：
- 已覆盖：overview≈`/`、executions≈`/workflows`、monitoring≈`/observer`、memory、settings
- 需新建 5 view（诚实空态纪律：后端无对应数组时渲染 EMPTY/UNKNOWN，不编数据）：
  `rules-policy`（←`governance.families` 真实字段）/ `audit`（←`ci[]`+`executions[]`+`sourceRefs`）/
  `approvals`（←`workspace.plan.approvals`，无则 UNKNOWN）/ `integrations`（←`governance.families.adapters`
  + registry 说明）/ `task-packs`（←`tasks` 计数 + `workspace.plan.tasks`）
- `workflow-detail` / `workflow-editor` 属 U19 之后的执行域（后端无 workflow schema，禁造数据）。

### 2.3 组件契约缺口（L7 shared-ui-core 24 组件 vs 现状 2）
现状仅 `badge.tsx` / `card.tsx`。需新建：Button / Input+Search / Modal(220ms,Esc) /
Drawer(280ms) / Toast(4s) / CommandPalette(Ctrl+K) / EmptyState / LoadingSkeleton /
ErrorState / OfflineState。交互 token（L6）：hover 120ms / focus ring 2px offset 2px /
pressed scale .99 / modal backdrop .62 / toast stack gap 12 / 断点 tablet1024 mobile767。

### 2.4 App Shell
现状 Sidebar 固定（无 260↔72 折叠、无分组）；TopStatusBar 无全局搜索入口；无 Command
Palette。L7 要求：260px 侧栏可折叠 72px、72px topbar、Ctrl/Cmd+K、页面五态契约。

### 2.5 可复用 / 不动
`types.ts` 契约、`useLiveSnapshot`、ExecutionTable/KPICard/ProjectPanel/TokenPanel、
SoftwareView、CompactHUD、a11y live-region —— 全部保留（后端契约与 a11y 纪律不回退）。

## 3. 实施边界（冻结 scope）
- 不新增 npm 依赖（禁 react-router；lockfile 冻结）；改动全部在 `apps/observer/frontend`。
- `.ui-reference/` 仅参考资产，不入 git；不得把三项目皮肤合并；色板唯一真值 = 2.1 权威值。
- 每个页面 loading/empty/error/permission/ready 五态；禁 fake KPI；危险态不出现写操作按钮
  （Observer 严格只读，WLR-100）。

## 4. 验收（CODEX 提示词第 9 节）
`tsc --noEmit` + `vite build` + vitest 全绿 + 新 view smoke 测试 + `VISUAL_QA.md`
（对照 B10/B06/B05 逐项）；检查无 AAOS 金青 / DESIGN-LAB 紫蓝混入。

## 5. 实施与验收结论（20260921）

### 实施（4 份 spec 全部落地；免费池限流子代理全 429/503，由 mainline 串行完成）
- **SPEC-A Design Tokens**：`src/index.css` 全量重写为 B10/L4/L7 三源一致的权威值
  （深海军蓝 #050D16 + 电光蓝 #2A91FF + 青 #20CDE1，违规紫 #7C6CF0 清零）；
  `src/theme/tokens.ts` 为 CI 可断言的单一数值真值；`tailwind.config.js` 扩展
  sidebar/muted/info + radius 4/10/16/22 + shadow + motion 120/180/220/280/420。
- **SPEC-B 共享组件**：新建 `components/ui/` 下 button/input/tag/modal/drawer/
  toast/states/command-palette（L6 交互参数，无新依赖）。
- **SPEC-C 诚实空态 5 视图 + 路由**：RulesPolicy/AuditTrail/Approvals/Integrations/
  TaskPacks，viewRegistry 新增 5 lane（共 15）；数据取自 SnapshotV3 真实字段，
  缺失即 EmptyState/UnknownState，禁编造 KPI。
- **SPEC-D App Shell**：Sidebar 260↔72px 折叠 + 4 分组（概览/执行/洞察/治理）+
  移动端 overlay；TopStatusBar 全局搜索（Ctrl+K）；App 全局 Ctrl/Cmd+K 命令面板 + 深链写回。
- **根因修复**：TokenPanel.tsx 与 Views.tsx 图表 series 硬编码旧色
  （#00d4ff/#7c6cf0）改为 `rgb(var(--primary-rgb))`/`rgb(var(--secondary-rgb))`。

### 验证证据（分层）
| 层 | 结果 |
|---|---|
| `tsc --noEmit` | PASS |
| vitest 全量（8 文件） | 47 passed / 0 fail |
| `vite build` 生产构建 | PASS（1598 模块） |
| dist 产物色板核验 | 权威 token 全部入 dist；紫/旧色残留 = 0 |
| 真实 WebView 渲染（dist 起 :54321 + 浏览器截图对照 B10） | 深海军蓝控制台、4 分组侧栏、审计页诚实空态，无紫残留、布局规整 |

> build PASS ≠ runtime PASS：已真实加载 dist 产物逐页核对（overview / audit），
> 离线后端时全部诚实显示 UNKNOWN，未伪造任何 KPI。临时静态服务 :54321 已停。

## 6. 边界与留待后续
- `.ui-reference/WORK-LAB/` = UI套件 提取的设计参考资产，gitignored 不入 git、不进 dist。
- 早期收敛工作流改动（taskpack 归档、governance/config/CI）仍在 worktree，排在 UI 之后，本次不裹挟。
- workflow-detail / workflow-editor 属执行域（后端无 schema），留待后续（D3 决策）。
