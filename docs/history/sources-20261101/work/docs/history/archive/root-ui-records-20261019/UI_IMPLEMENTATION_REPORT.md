# WORK-LAB 前端 UI 最终落地 · 实施报告（L10b / B10 完全复刻）
<!-- ROOT-DISPOSITION:BEGIN NON-NORMATIVE-HISTORICAL -->
> **NON-NORMATIVE-HISTORICAL / 历史记录，不派工**（2026-10-10 登记，WUI-17）：本文件不在权威链里，正文逐字保留未改（门会把它与提交字节逐字节比对）。现行权威顺序：`WORK-LAB-AUTHORITY.md` → `.project/governance/project-authority-index.json` → `taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md` → `taskpacks/current/OPEN-TASK-REGISTER.md`（2026-10-19 更新；旧 UI 包已 SUPERSEDED_20261019 / FROZEN，不再是 CURRENT）；根目录逐份处置见 `docs/current/DOCUMENT-CENSUS.md` §4 与 `.project/governance/root-document-dispositions.json`。
<!-- ROOT-DISPOSITION:END -->

> 本文件覆盖两个连续的执行：**L10（B10 收敛，已合并 PR #142）**与
> **L10b（B10 1:1 完全复刻，本分支）**。§1–§8 为 L10b 现状；§9 保留 L10 历史记录。

- L10b 分支：`p1/ui-l10-full-replica`（base `main` @ `f95baef`；父提交 `2255ddd` 皮肤层，`4da62a2` 交接）
- 执行模式：高自主串行主线（free-tier 子代理仍不可用）
- 权威顺序：**B10 单一文件 = 视觉/结构唯一事实源**；低批次仅补充细节，不推翻
- 数据源真值：sidecar v3 `SnapshotV3`（executions[] / tasks / governance.families / ci[] /
  workspace.plan / sourceRefs）；缺失一律 **UNKNOWN**，不伪造 KPI / 任务包 / 集成健康 / 审批态
- Observer §8 只读铁律：无 execute/approve/retry/apply/rollback/写 ledger
- 无鉴权铁律：零 lock / 访问令牌 / 密码 / OAuth / 鉴权入口（本地个人研究）

---

## 1. L10b 目标与达成

L10 已经把 12 页做成 B10 **风格**；L10b 把它做成 B10 **DOM 结构**：shell 与 12 页全部改
为 B10 单一文件里逐字存在的类（`.app` `.sidebar` `.nav` `.nav-dot` `.topbar` `.search`
`.content` `.page-head` `.panel` `.kpi` `.table` `.tag` `.list-item` `.graph-stage`
`.canvas` `.node` `.flow-svg` `.metric-row` `.status-stack` `.empty` `.mono` `.palette`
`.overlay` `.drawer` `.toast`），皮肤层 `src/skins/b10.css` 为 B10 `<style>` 块的逐字拷贝。

数据仍来自真实 v3 快照投影；测试锚点文案（CI 契约）逐字保留 —— **B10 赢在结构/样式，
锚点赢在文案**。

## 2. 皮肤层与 cascade 事实（先证明再改）

B10 皮肤是 **unlayered** 规则，`index.css` 的 Tailwind 位于 `@layer components/utilities`。
未分层规则优先级高于任何 `@layer`，因此 **B10 自动胜过 Tailwind**，无需 `!important`。
构建产物单文件 `dist/assets/index-*.css` 的规则偏移已回读验证
（Tailwind `.panel` 5,399 → B10 `.app` 20,303 → B10 `.canvas` 30,506 → L10b shell 38,410）。

新增 `src/skins/l10b-shell.css`（唯一非 B10 样式文件，逐条有理由）：rail 断点可见性、
compact 单列网格、`.toast-stack` 角落锚定、`.sr-only`、以及把 `.sidebar` 左右内边距从
18px 调到 16px 让 B10 品牌字标在 280px 栏内单行显示（B10 字体/字号/字距未改）。

## 3. 12 页 IA 映射（全部可达、全部 B10 DOM）

| # | 页 | registry lane | 组件 | B10 结构 |
|---|----|---------------|------|----------|
| 1 | Overview | `overview` | `OverviewView`（内联） | `.page-head` + `.kpi-grid`×4 `.panel.kpi` + `.two-col`(spark / `.metric-row`+`.status-stack`) + `.split`(`.list` / `.graph-stage` core+6 `.node-dot`) + 告警/任务包 |
| 2 | Workflows | `workflows` | `WorkflowsView` | `.toolbar`(`.input`+`.seg`) + `.panel > .table-wrap > .table` + `.empty` |
| 3 | **Workflow Editor（核心）** | `workflow-editor` | `WorkflowEditorView` + `WorkflowCanvas` | `.split`[`.panel > .canvas`(`.flow-svg` 动画虚线 + 可拖拽 `.node`) \| `.panel` 属性与运行配置 + 嵌套 部署说明] |
| 4 | Task Packs | `task-packs` | `TaskPacksView` | `.metric-row` 大数字 + `.table` 明细（真实 `snap.tasks`/`plan.tasks`） |
| 5 | Observer | `observer` | `ObserverView` + `NodeGraph` | `.split` + `.graph-stage`(核心 pulse + 6 `.node-dot`) + `.metric-row`；零可执行按钮 |
| 6 | Rules & Policy | `rules-policy` | `RulesPolicyView` | `.list-item` 家族行 + `.tag.ok/warn` 漂移真值 |
| 7 | Integrations / MCP | `integrations` | `IntegrationsView` | `.list-item` 适配器 + 7 客户端静态文档（非实时健康） |
| 8 | Memory Registry | `memory` | `MemoryView`（Views.tsx） | `.two-col` + `.list-item` 漂移真值 + 错误账本 |
| 9 | Audit Trail | `audit` | `AuditTrailView` | `.toolbar > .seg` + `.table` + `.mono` 来源引用；无重试/撤销 |
| 10 | Approval Center | `approvals` | `ApprovalsView` | `.table` 请求/风险/状态；**B10 演示的「审批」动作列刻意缺席**（只读），无批准/拒绝/撤销 |
| 11 | Settings | `settings` | `SettingsView`（Views.tsx） | `.split` + `.list-item` 数据源/版本/水位；**无令牌/无锁定/无鉴权入口** |
| 12 | Execution Detail | `execution-detail` | `ExecutionDetailView` | `.split`(执行列表 `.list-item` \| 详情 `.list-item` + 只读说明嵌套 `.panel`) |

其余可达 lane（Compact HUD 之外的 Work / Projects / Agents / Executions / Models /
Tools / Monitoring / Delivery / Trust / Software）同批迁移到 `.panel` / `.table` /
`.list-item` / `.tag`。

导航：`Sidebar` 的 7 组 `NAV_GROUPS`（首页/工作/智能体/项目/治理/集成/系统）保持
P1-01 不变式（22 lane 恰好归一组、无重复），改为 B10 `.nav button` + `.nav-dot`
（active = 渐变 + `::before` 青色→蓝色光条）。

## 4. 统一 Design System

- **原始层**：`src/skins/b10.css`（B10 `<style>` 逐字，533 行）—— `.panel` `.kpi`
  `.table` `.tag` `.list-item` `.canvas` `.node` `.flow-svg` `.graph-stage`
  `.metric-row` `.status-stack` `.empty` `.mono` `.palette` `.overlay` `.drawer`
  `.toast` `.primary-btn/.ghost-btn/.soft-btn/.danger-btn` 全部由它提供，组件只负责
  结构与数据。
- **壳层**：`src/skins/l10b-shell.css`（仅断点/角落/可见性，见 §2）。
- **组件层**：`components/ui/*`（button/card/badge/status/table/list/input/states/
  page-header/sparkline/progress/tooltip/modal/drawer/toast/command-palette/tag）
  与 `components/graph/*`（node-graph / workflow-canvas）不再自带视觉，改为挂 B10 类。
- **dashboard 层**：`KPICard`（`.panel.kpi` + `.kpi-number` 锚点）、`ExecutionTable`
  （`.panel > .table-wrap > .table`）、`ProjectPanel`/`TokenPanel`（`.list-item`）。
- **动效**：全部来自 B10 关键帧（`floatGlow` / `dashMove` / `pulse` / `scanSweep`）
  + `b10.css` 末尾的 `prefers-reduced-motion` 停机块。

## 5. 无鉴权铁律（用户 verbatim：「都是本地个人研究使用的 禁止加锁，加访问令牌等」）

全 `src/**/*.tsx` 检索 `password|passwd|api[-_ ]?key|access[-_ ]?token|Bearer|Authorization|登录|令牌|密码|鉴权`
→ **2 处命中，全部是「声明不存在」的说明文案**（`App.tsx` 工作区抽屉、`Views.tsx` 设置页）。
无锁屏、无令牌输入、无凭证弹窗、无审批理由输入、无 OAuth 门。

## 6. 诚实态 / 只读纪律

- 缺失 → `.empty` / `UnknownState` / `UNKNOWN`；不伪造 0、不伪造「全部干净」、不伪造
  任务包运行态、不伪造集成健康、不伪造已审批。
- 审批页不渲染批准/拒绝/撤销；审计页不渲染重试/撤销/重放；Observer / Execution
  Detail / Work 页零写操作控件。`ErrorState` 的 `重试` 动作已**删除**，使任何状态组件
  都无法给只读页递出重试入口。
- 真实值才显示：KPI 第 4 格绑定真实 transport 词（LIVE 契约），趋势行仅在真实存在时渲染，
  B10 演示里的 `↑ 18%` 无真实来源 ⇒ 不渲染。

## 7. 验证回读（本地真实输出）

- `tsc -p tsconfig.json --noEmit` → 干净（exit 0）
- `vitest run` → **Test Files 11 passed / Tests 72 passed**（全部 HANDOFF §3 锚点）
- `vite build` → 绿（dist JS 267.72 kB / gzip 82.46 kB；CSS 39.31 kB）
- 构建产物 cascade 偏移回读见 §2
- 像素层：17 张 headless 截图（真实渲染路径，`?api=` 指向本地 preview 服务的
  v3 形状快照），覆盖 overview/observer/workflows/editor/execution-detail/approvals/
  audit/task-packs/rules-policy/integrations/software/memory/work/settings/compact/light
- 本地测试 ≠ CI：exact-SHA 结论以 GitHub Actions 在该 SHA 的 terminal-success 为准
  （交付后回填；ERR-089 纪律）

## 8. 交付物与边界

| 文件 | 位置 | 说明 |
|------|------|------|
| `UI_IMPLEMENTATION_REPORT.md` | 仓库根 | 本文件（L10b + L10 历史） |
| `UI_REFERENCE_MANIFEST.md` | 仓库根 | 参考清单 + L10b 代码映射 |
| `ASSET_REPLACEMENT_MANIFEST.md` | 仓库根 | 资产判定（含 L10b 判定） |
| `VISUAL_QA_REPORT.md` | 仓库根 | 视觉验收（像素层本轮已 VERIFIED） |
| `.project-local/runs/ui-suite/l10b-closeout.md` | 本地（gitignored） | 完整 closeout 证据 |
| `.project-local/runs/ui-suite/l10b-verify/` | 本地（gitignored） | 验证 harness + 日志 + 17 张截图 |

已知边界（诚实分级，详见 closeout §4）：浅色主题只做到「壳层翻转 + B10 表面保持深色」
（`b10.css` 逐字编码了 B10 深色调色板，不做令牌间接化）；编辑器画布为本地编辑模型，
发布/运行在真实契约接入前保持禁用；`graph-stage` 卫星标签锚点相对 B10 演示偏移约 4px
（真实容器尺寸下会压住节点，改为贴圆外侧，B10 结构/样式不变）。

---

## 9. 历史记录：L10（B10 风格收敛，PR #142）

- 分支 `p1/ui-final-l10`（base `c8b948d`），已 squash-merge 到 `main` @ `f95baef`，CI 7/7 绿。
- 产出：12 页 IA 重组（B07 页面矩阵）+ 交互式 Workflow Editor + Observer 只读拓扑 +
  `index.css` 的 `--glow-*` / `--grid-line` token 与 B10 关键帧 + 30+ 共享组件 +
  `l10-views.test.tsx` 10 测试。
- 当时边界：像素级截图通道不可用 ⇒ VISUAL_QA 的光效/动效层标记 **UNVERIFIED**。
  **L10b 已用 headless Chromium 截图闭环该缺口**（见 §7 与 `VISUAL_QA_REPORT.md`）。
- 当时根因修复：`index.css` 注释内 `--glow-*/--grid-line` 的 `*/` 提前闭合 CSS 注释
  导致 postcss 崩溃 → 注释措辞修正。L10b 新增的 `l10b-shell.css` 已复查无同类问题。

## 10. 2026-10-07 再基线（接手 CODEX UI 交接后的只读复核）

**先撤回一处我自己的错判。** 本节初稿写"现有 tokens 是蓝紫 `#6F95FF`/`#B087FF`，与提示词方向不一致，需要校准"。
实测否定：应用真正的 token 单一来源 `src/theme/tokens.ts` 的 `DARK` 就是
bg `#050D16` / sidebar `#07111C` / panel `#081420` / panel2 `#0C1B2A` / border `#17435D` /
ink `#EEF6FC` / muted `#8EABBC` / **primaryHex `#2A91FF`** / **secondary `#20CDE1`**，
且 `src/theme/tokens.test.ts` 已在断言 `accents.primary = "42 145 255" // #2A91FF`、
`accents.secondary = "32 205 225" // cyan, NOT purple`、`colors.bg = "#050D16"`，radius/density 也有断言。
蓝紫只存在于两处**未被应用消费**的档案物：`src/assets/brand/design-tokens.json`（v2.0.0 "Liquid Glass"，
grep 全树 0 import，仅 `tokens.ts:137` 一句注释提到它给外部消费者）与
`work-lab-observer-symbol.svg`（997 B，实测含 `#223a92/#6F95FF/#A878FF`）。所以"校准品牌色"不是 UI 缺口，
而是**两件被 digest 钉住的品牌档案 vs 应用真值**的一致性问题，改它们会撞 `test_recovered_source_registry`
的漂移门禁，属 owner 决策，不在 UI 实施里偷改。

### 10.1 基底更正

CODEX 记的 `origin/main = cd4daa83e107…` / tree `a36e97ecbcb9…` / `ui-taskpack-e-20260930 == main` 仍成立；
其 worktree 也确认**无任何未提交内容**（`git -C … status --porcelain` 空），且 `cd4daa83` 已是本分支祖先
（`git rev-list --count 285704a..cd4daa83 = 0`），**并入即 no-op**——不存在可吸收的 Codex UI 提交。
但 `apps/observer/web` 在 main 上 **24 文件**、在 `285704a` 上 **0 文件**（重复树已退役），`apps/observer/frontend`
69→83 文件。故 UI 工作分支 `ui-commercial-polish-20261007` 必须（也已）从 `285704a` 起。CODEX 报的
`Permission denied` 是其沙箱限制，不是 worktree 属性。

### 10.2 任务包文本层与验收清单实测

从 `WORK-LAB_UI开发资料总包_按批次.zip` 抽出可读层（B07 tokens.css/json/motion.css、B04/B06 tokens、
B08 原型、B10 终版、00 清单；图像批次不膨胀）。B07 `tokens.css` 与 `src/theme/tokens.ts` **逐项相等**
（`#050D16/#081420/#0C1B2A/#17435D/#2A91FF/#20CDE1/#EEF6FC/#8EABBC/#22C55E/#F59E0B/#EF4444/#3882F6`，
radius 10/16），说明应用已对齐 L4/L7。

`04_CODEX_UI统一验收清单.md` 逐条实测（只读，未改代码前）：

| 清单项 | 实测 | 判定 |
|---|---|---|
| 先审计真实仓库，不以 Demo 替代 | 本节即产物；B08/B10 原型只作参考，未进生产 | ✅ |
| 正式页面接现有路由/数据/API | 21 注册泳道 + 内联总览 = 22；`api.ts` 白名单只放 `/api/v1/(snapshot\|events)` | ✅ |
| Loading/Empty/Error/Permission/Offline 齐全 | Loading 与 OFFLINE **已实现**：`App.tsx:292 loadingStrip`（`!snap && !error` 时显示「首次快照未到达，数值保持 UNKNOWN，不预填任何数据」，渲染于 316/365）＋ `App.tsx:203-209` aria-live 播报 LOADING/OFFLINE；`EmptyState`/`ErrorState`/`OfflineState`/`UnknownState` 在 `states.tsx` 齐备（离线在视图侧由 `CompactHUD:46`、`ObserverView:57`、`OverviewView:65` 的徽标承载）。**真缺口收窄为**：没有 `PermissionState`（`OfflineState` 组件 0 处被调用），写动作缺「按权限/后端未实现 → disabled ＋原因」的逐动作呈现（views/layout 合计仅 9 处 `disabled`） | ⚠️ **G1（收窄）** |
| Ctrl/Cmd+K、Esc、键盘焦点 | `App.tsx:104` 绑 `ctrl\|meta + k`；`command-palette`/`modal`/`drawer` 有 Esc + `aria-modal`；`drawer.tsx:36` 注记 M-3 "aria-modal without a trap is a false promise" 并已实现 trap | ✅ |
| Modal/Drawer Focus Trap | 同上 | ✅ |
| Reduced Motion | `index.css:237`、`skins/b10.css:529` 均 `prefers-reduced-motion: reduce` | ✅ |
| Build/typecheck/lint/smoke | 待在本工作区跑（`frontend/node_modules` 只在主 checkout 存在，先按只读复用主 checkout 验基线） | ⏳ |
| 不散落硬编码品牌色 | `.tsx` 中品牌 hex 字面量 **0**（色值经 `theme/tokens.ts`）；例外：`TopStatusBar.tsx:62` 有一处 `#F59E0B` 告警色字面量 | ❌ **G2** |
| 不跨项目串色/串 Logo | 无 AAOS 珍珠白/星环；`三项目`/AAOS 命名命中均在 owner 材料根，未进仓库 | ✅ |
| Workflow Editor 可用且不破真实 Schema | `workflow-editor` 泳道 + `WorkflowCanvas`；schema 合同由既有门禁覆盖（U03 行在册） | ⏳ 逐动作复核 |
| Observer 明确只读 | `verify_observer_readonly_boundary.py` 在册；`design-tokens.json` 亦声明 `readOnly:true` | ✅ |
| 深黑蓝 + 电蓝/青，无橙金暖色 | 主题即 `#2A91FF/#20CDE1`；`#F59E0B` 仅出现 2 处且为**告警语义**（`tokens.ts:79` 定义、`TopStatusBar.tsx:62` 字面量），非装饰暖色 | ✅（含 G2 收尾） |

### 10.3 组件采纳门（提示词步骤 3）实测结论：不装新包

现有栈已含 `class-variance-authority`、`clsx`、`tailwind-merge`、`lucide-react`、`recharts`、
`@testing-library/*`，`src/components/ui/` 有 20 个自研 primitive（`button/card/input/table/modal/drawer/
command-palette/states/status/tag/toast/tooltip/progress/sparkline/list/page-header/lane-error-boundary` …）；
**无 Radix、无动效库**。采纳计划把 WL 第一候选定为"shadcn 源码模式 + 一个可访问 primitive 供体（若已有 Radix 则延用）"，
其吸收门第 1-3 步要求先确认现状再决定是否装。实测：计划点名要试的三件（Table / Approval Dialog / Command palette）
在仓库里都已有对应实现与测试 → **当前无能力缺口，不新增依赖、不装包**；补的是上表 G1/G2 两项自研缺口。

### 10.4 已排期的实施缺口

- **G1（收窄后）** 补 `PermissionState` 与「动作级禁用解释」：后端合同未实现的写动作必须 `disabled` ＋说明原因；`OfflineState` 要么被用要么删，不留无人调用的壳。配 vitest 断言（不得把缺数据渲染成绿色）。Loading 已由 load strip 实现，不新增组件。
- **G2** `TopStatusBar.tsx` 去字面量色（改走 token），并决定顶栏品牌图形：用 `currentColor` 的 tray 几何或**内联 SVG/CSS 构造**，**不修改被 digest 钉住的 `work-lab-observer-symbol.svg`**（紫蓝渐变因此继续保持档案原状，不进 UI）。
- **G3**（阶段 7，任务 #19）把既有 `scripts/audit/topbar_geometry_via_cdp.py`、`cdp_layout_probe.mjs` 接成真实布局门禁。**断言必须是几何而非存在性**：量矩形与重叠面积、用 `elementFromPoint` 做命中测试（含「覆盖层是否遮住它自己的开关」）、偏移量实测而非硬编码期望值——一次顶栏明显坏掉的界面曾在 presence/class/aria 断言下全绿。改动前先取一次快照，用来证伪自己的改动。

未提交、未推送、未开 PR；回滚 = 删除本 worktree 与分支 `ui-commercial-polish-20261007`。


## 11. 桌面优先收敛（owner 2026-10-07 指令：优先跑通全量执行桌面端电脑端 UI，先删除手机端其他端）

基底仍是本工作区分支 `ui-commercial-polish-20261007` @ `285704a`；本轮全部改动只在本隔离工作区，未提交、未推送、未合并。

### 删除的手机端面（清单，逐条可核）

| 位置 | 删除内容 |
|---|---|
| `src/App.tsx` | `mobileNavOpen` 状态、`Sidebar` 的 `mobileOpen/onCloseMobile` 传参、`TopStatusBar` 的 `onOpenMobileNav` 传参 |
| `src/components/layout/Sidebar.tsx` | 移动端遮罩抽屉整块 JSX（含"打开/关闭导航"按钮）、`SidebarProps.mobileOpen/onCloseMobile`、`Nav.onAfterSelect`、不再使用的 `X` 图标导入 |
| `src/components/layout/TopStatusBar.tsx` | 汉堡触发按钮与 `onOpenMobileNav` 形参 |
| `src/skins/l10b-shell.css` | `.mobile-nav` / `.topbar-mobile` / `.mobile-nav-panel` 规则；`@media (min-width:841px)` 门（把导航栏与双轨栅格改为无条件声明） |
| `apps/observer/src-tauri/tauri.conf.json` | 主窗口 `minWidth 320→900`、`minHeight 480→600`（320 是手机形状遗留） |

保留的两件事有证据理由，不是遗漏：`?view=compact` 悬浮面板（`panel` 窗口 440×780、`resizable:false`，是 Tauri 声明的桌面端第二面，不是手机端）；`@media (max-width:1000/1240px)` 与 `<=840/<=560` 的压缩规则（本机 125% 缩放下 1024 物理像素≈819 CSS 像素，这些宽度是真实桌面窗口，2026-10-07 由 CDP 实测过；删掉它们会让动作行重新被裁）。`src/skins/b10.css` 按 D-11 逐字未动——≤840 的 `.sidebar{display:none}` 仍在，shell 层用双类选择器无条件覆盖，这一点也被门禁钉住。

### G1 动作级禁用与理由（已补）

`components/ui/states.tsx` 新增 `PermissionState`（`blocked / reason / stillAvailable`，`role=status`，内部零按钮），用于"值可能已知但本面无权行动"——与 `UnknownState`（投影无数值）语义不同。消费者：`views/ApprovalsView.tsx` 在有审批行时给出"裁决由后端审批契约与 Permission Gate 持有"，并断言页面上不存在批准/拒绝/撤销按钮。`components/graph/workflow-canvas.tsx` 的"运行/保存并发布"：`disabled` 控件既拿不到焦点也收不到指针事件，所以理由不再只放在 hover Tooltip 里，改为可见 `role=note` 说明 + `aria-describedby` 绑定 + `aria-disabled` + `title`。

### G2 品牌与单一色彩来源（已补）

顶栏此前零品牌引用。新增 `.topbar-brand`（B10 `.brand-mark` 几何缩到 22px + 字标），悬浮面板只留标记。颜色取自皮肤变量 `var(--primary)/var(--secondary)`，组件内无字面量；`TopStatusBar` 的传输状态点改用 `THEMES[theme].colors.{success,error,warning,muted}Hex`，删掉了原先的 4 个字面 hex（含 `#F59E0B`）。

### 门禁与实测数字

- `node node_modules/vitest/vitest.mjs run` → Test Files 20 passed (20)，Tests 123 passed (123)（本轮新增 `desktopShell.contract.test.tsx` 2 项、`permissionContract.test.tsx` 3 项、`brandContract.test.tsx` 3 项）。
- `npm run build`（`tsc -b && vite build`）退出 0：`dist/assets/index-B-X912c3.js` 278.81 kB（gzip 86.94 kB），`dist/assets/index-BolzaFyq.css` 44.35 kB（gzip 9.88 kB）。
- `python -m pytest tests/ci/test_desktop_only_shell.py` → 8 passed：手机端痕迹全树清零、导航栏与双轨栅格无条件、b10 逐字仍在且被覆盖、窗口合同 900×600/440×780、调色板单源。其 `has_not` 检测器带一条"能看见才允许声称看不见"的反控。
- 源码扫描断言的自检：临时放入 `src/__falsify_probe.ts`（同时含调色板字面量与 `mobile-nav`）后两道扫描都报警，随后删除文件。不做这一步，"全树干净"只是我的推断。
- 桌面几何门禁：见收敛线 `GEOMETRY-GATE-20261007`。判定函数 12 项单测通过，但本机 Chrome 154 的 `/json/list` 在本会话超时不返回，未拿到一次真实 `GEOMETRY_GATE_PASS`，所以 G3 仍是 owed，不接成 CI 必需步骤。

### 未完成（不粉饰）

1. 未在真实 Tauri 桌面窗口完成本轮改造后的目测/几何读回（需要 `cargo build --release`，本机 cargo 不在 PATH；且属"真人确认"类，按指令先跳过）。
2. G3 几何证据缺口同上。
3. 每泳道 Loading/Empty/Offline/Permission 的覆盖清单尚未逐页量完；`OfflineState` 仍无消费者。
4. 命令面板、抽屉、Toast 的键盘/焦点回归由既有测试覆盖，缩放（Ctrl +/−）与 Reduced Motion 的几何断言仍依赖上面那条浏览器读回。

### 回滚

本工作区全部改动可用 `git -C <worktree> checkout -- .` 回到 `285704a`，或删工作区+分支整面撤销；收敛线不受影响。


## 12. UI 轮已并入收敛线（owner 2026-10-07：继续完成UI任务，不管是合并迁移等）

`71b1ae8`（分支 `ui-commercial-polish-20261007`）合入收敛线 `85545b3`，交付纪律变更见
`taskpacks/current/WORK-LAB-UI-PROMPT-PACK-EXECUTION-TASKCARD-20261007.md` 第 8 节与登记行
`UI-PRODUCT-PROMPT-20261007` 的当日更新。合并后在本体继续补齐提示词验收门里剩下的两项可静默验证的门：

- 每泳道诚实态穷举：`src/laneTruth.sweep.test.tsx` 用 `VIEW_REGISTRY` 逐泳道以 `snap=null` 挂载，
  断言无 `.tag.ok` 成功徽标、KPI/metric 槽不出现 `0`/`0/0`/`0.0`、文本必含声明式缺失词
  （UNKNOWN/无数据/暂无/不可用/未接入/STALE/PARTIAL/ERROR/OFFLINE）。同文件带一条正控：
  手工渲染 `Badge variant="success"` + 假 `0`，证明探测器真的能看见被禁止的东西——
  没有这条正控，"20 条泳道全绿"只是空选择器的假象。
- 键盘/焦点回归：`components/ui/command-palette.tsx` 打开时记录 opener，关闭时把焦点交还给它
  （此前焦点留在已卸载的对话框输入框里，下一次 Tab 从文档顶部重来）。
  `src/keyboardFocus.contract.test.tsx` 3 项断言 Esc 关闭并返回焦点、Enter 执行后同样返回、
  方向键在面板内移动选择。
- `OfflineState` 由"有定义无消费者"变为有消费者：`App.tsx` 在 `error && !snap`（传输确证失败、
  也没有 last-good）的面板里渲染它，与投影无数值的 UNKNOWN 区分开。

合并后本体实测：`npm run build`（`tsc -b && vite build`）退出 0，`node node_modules/vitest/vitest.mjs run`
＝ 22 files / 150 tests 全过；`python -m pytest tests/ci/test_desktop_only_shell.py tests/ci/test_topbar_geometry_gate.py`
＝ 21 passed（桌面唯一性合同现在在收敛线上跑，不再只活在 worktree）。

仍未闭合（不粉饰）：G3 的真实桌面几何读回——本机 Chrome 154 headless 的 `/json/list` 在本会话从不
应答（同一实例旁测：urllib 与"裸 socket＋User-Agent＋无端口 Host"曾返回 200，u19 原形状超时；
`--remote-debugging-port=0` 只公布 ws 端口不服务 HTTP），所以几何门禁仍未接入 CI 必需步骤；
真实 Tauri 窗口的目测属需真人确认类，按指令跳过。

## 13. 2026-10-07 runner 侧读回（更正 §12 的最后一段）

§12 写"几何门禁仍未接入 CI 必需步骤"时它是事实；此后本机 CDP 仪器被修到能自己报错（ERR-145/146/147：
恒定绿色的 main()、硬编码 ROOT、`endswith("200")`、读到 EOF、无端口 ws URL 回显 Host、
用桌面宽度量紧凑窗），并在真实 PASS 之后重新接成 observer 作业的必需步骤
（`.github/workflows/work-lab-gate.yml:224`）。本节以 runner 读数为准，不再用本地推断：

- exact SHA `17eb5b6`、run `37579527214`（work-lab-gate）的 observer 作业三步全部 `success`：
  `Build the real Tauri desktop binary (MSVC, for U19 E2E)` →
  `U19 real-WebView E2E readback (WINDOWS_TAURI_E2E)` →
  `Desktop geometry gate (CDP measurement of the built shell)`。
- 也就是说：真实 Tauri 二进制在 Windows runner 上编出来、WebView2 里的页面被 CDP 读回非 about:blank、
  顶栏几何按 full/compact 两档各自的 `WIN_SIZE`+`MAX_HEIGHT` 判过 9 项。这正是 §12 当时缺的那块证据，
  现在由 runner 而不是我的本机提供。

仍未闭合（保持未知）：真实窗口的**人眼**目测仍按 owner 指令跳过——上面证明的是渲染链与几何合同可测且通过，
不证明审美与可用性验收；本机 headless CDP 的 `/json/list` 仍不应答，所以本地无法复算 runner 的读数，
只能引用 run id。

## 14. 2026-10-07 runner 几何读数原文（把"通过"换成数字）

run `37585453264` / head `8847cdc` / observer 作业第 12 步（必需步骤）逐项读数：

- 桌面档：`scrollWidth=1264 innerWidth=1264`（无横向溢出）· 顶栏 `height=129`（上限 140）· 品牌位
  `brand=91` · 动作区 `display=flex` · 窗控 `clipped=[]` · 动作行右余量 `gap=731.1` ·
  导轨 `rail=214.9`（下限 200）· `left=0`。
- 紧凑档：`scrollWidth=500 innerWidth=500` · 顶栏 `height=111`（上限 260）· `brand=22` · `gap=130` ·
  `rail=None`（紧凑态不渲染导轨）· `viewport=500x629`。
- 结尾 `GEOMETRY_GATE_PASS`，并如实报出两个删不掉的临时 user-data 目录（`GEOMETRY_GATE_RESIDUE`，
  PermissionError 13）；一次性 runner 上不判失败，但名字被打出来而不是咽下去。

两条不粉饰的边界：**紧凑档实测视口 500×629 ≠ `tauri.conf.json` 声明的 440×780**，所以这条步骤证明的是
"窄内容区不溢出、顶栏不堆叠、无导轨"，不是"面板窗像素级等于声明值"；后者要从 Tauri 侧读回窗口内部尺寸才能钉。
另修一处会误导人的文案：日志里 `topbar_measured PASS no .topbar element` 的详情字符串是写死的失败文案，
元素其实已测到（下一行就报高度）。现在通过时详情报 `height=<实测> element=found`，缺元素时报 `MISSING`
并判失败，`tests/ci/test_topbar_geometry_gate.py::test_a_passing_detail_says_what_was_measured` 双向钉住。


## 15. 2026-10-07 L 轮实测：泳道 × 诚实态矩阵（更正 §11「未完成」第 3 条）

§11 第 3 条写着「`OfflineState` 仍无消费者」。**这条是错的**，本轮逐文件量过：五个诚实态组件每一个都有消费者，
因此「要么被用要么删」的处置前提不成立。实测（`.project-local/runs/convergence-20261007-k/measure_lane_state_matrix.py`
与一次 `grep -rl` 全 src 反查，排除定义文件本身 `src/components/ui/states.tsx`）：

| 组件 | 消费者（除定义文件 `states.tsx` 外；测试引用另注） |
|---|---|
| `ErrorState` | `src/components/ui/lane-error-boundary.tsx` |
| `OfflineState` | `src/App.tsx`（第 224 行，`error && !snap` 的硬错误面板） |
| `EmptyState` | `src/lib/viewRegistry.ts`、`views/AuditTrailView.tsx`、`views/IntegrationsView.tsx`、`views/RulesPolicyView.tsx`、`views/TaskPacksView.tsx`（另有 `components/ui/components.test.tsx`、`views/views.test.tsx`） |
| `PermissionState` | `src/views/ApprovalsView.tsx`（另有 `views/permissionContract.test.tsx`） |
| `UnknownState` | `src/App.tsx`、`src/lib/viewRegistry.ts`、`views/ApprovalsView.tsx`、`views/WorkflowsView.tsx`、`views/ExecutionDetailView.tsx`（另有 `components/ui/components.test.tsx`、`views/l10-views.test.tsx`、`views/views.test.tsx`） |

按注册表泳道看组件归属（21 条带组件的泳道，静态解析 `viewRegistry.ts` 的 import 链，0 条未解析）：

- 直接引用诚实态组件的泳道：`rules-policy`/`audit`/`integrations`/`task-packs`（`EmptyState`）、
  `approvals`（`UnknownState`+`PermissionState`）、`workflows`/`execution-detail`（`UnknownState`）。
- `agents`/`projects`/`executions`/`models`/`memory`/`tools`/`monitoring`/`delivery`/`trust`/`settings`
  十条共用 `src/views/Views.tsx`，因此**静态归属无法逐泳道区分它们**；
  `work`/`software`/`workflow-editor`/`observer` 四个模块本轮未量到诚实态组件引用。

要点：静态矩阵只能说明"谁引用了组件"，不能证明"渲染出来的是诚实态"。逐页的**渲染**证据在
`src/laneTruth.sweep.test.tsx`：它遍历 `VIEW_REGISTRY` 里每条带组件的泳道，以 `snap={null}` 挂载后断言
①无 `.tag.ok`／`[data-tone="success"]`（无数据却给出健康配色即为伪造），②KPI 槽不出现伪造的 `0`/`0/0`，
③文本里必须出现声明过的缺失标记（`UNKNOWN｜无数据｜暂无｜不可用｜未接入｜—｜STALE｜PARTIAL｜ERROR｜OFFLINE`），
并且先跑一个**探测器自检**（人造的成功徽标与人造的 0 必须被抓到）——否则"全绿"只是探测器看不见。
门禁由 `scripts/ci/required_groups.json` 的 `observer-frontend-typecheck` 组执行（`npm ci`→typecheck→build→
`npm run test`＝`vitest run`），CI 在 `work-lab-gate.yml` 里跑这个组，所以这些断言不是装饰。

因此 §11 第 3 条的正确表述是：**逐泳道渲染诚实态已有 CI 强制覆盖；缺的是"每泳道 × 四种场景
（Loading／Empty／Offline／Permission）"的渲染矩阵**——它不能靠静态归属凑出来，也不能靠给十条共用
`Views.tsx` 的泳道编造逐条差异。这一项保持未完成，不改口径。

### 15.1 同日追加（30 分钟后）：场景矩阵量出来了，而且它先推翻了我准备写的断言

上面那句"保持未完成"只维持了 30 分钟。用一次性探针把 21 条泳道 × 4 个传输场景全渲染一遍
（`LIVE／OFFLINE+STALE／CONNECTING+UNKNOWN／EMPTY`），把每条泳道出现的状态词、成功配色 pill 的**文字**、
零值槽位数全部打表之后，结论是：

1. **我原本打算写的断言是错的。** 文本层扫描报了三个"传输已 OFFLINE 却说 LIVE/实时"的嫌疑：
   `integrations`（`实时` 出现在"**非**实时健康度"这句否定说明里）、`monitoring`（`LIVE,DELAYED,OFFLINE`
   是它在复述 live-gate 规则原文）、`delivery` 与 `monitoring` 在 EMPTY 场景仍亮绿 pill——把 pill 的文字打出来
   才知道是 `MATCH`/`LIVE · 只读`，而 `git.matchState` 与 transport 在我这份快照里**确实**是 `MATCH`/`LIVE`。
   三条全是误报。若直接把它们写进门禁，就会用一条假失败去腐蚀一条真绿灯。
2. **因此落地的断言是元素级的**，新文件 `apps/observer/frontend/src/laneTransportTruth.sweep.test.tsx`
   （11 例，`vitest run` 全绿；整套 23 文件 / 161 例）钉住三件事：
   ① 任何泳道都不得在传输非 LIVE 时渲染一个写着 `LIVE` 的成功 pill；② 主题就是传输的 5 条泳道
   （`executions／trust／observer／settings／monitoring`）必须把快照自己的状态词 surface 出来，
   并且这 5 条若从注册表消失，测试会因"覆盖面自己缩水"而红；③ 空集合场景不得出现伪造的 `0`/`0/0`。
   另有**探测器自检**：人造一个对着 OFFLINE 快照的 `LIVE` 成功 pill，断言它必须被抓到。
3. **场景矩阵的实际读数**（可用于后续对照）：传输真值会翻转的泳道是上面那 5 条；其余泳道只投影数据，
   与传输状态无关，因此对它们*不*要求出现状态词——这条区分是量出来的，不是规定的。
4. 顺带把快照 fixture 抽成 `src/test/snapshotFixture.ts` 并让 `renderTruthContract.test.tsx` 改用它：
   两处各留一份 `mkSnap` 的话，"什么算健康快照"就会有两种定义。

仍未完成的部分照登：Loading 与 Permission 两维**没有**进入这次的场景矩阵（探针只覆盖传输与空集合），
每条泳道的动作级禁用解释也只有 `approvals` 一条有 `PermissionState` 消费者。

## 16. 2026-10-07 L 轮：G1 的"禁用＋理由"此前只对鼠标成立（台账 **ERR-156**）

接着上面那条未完成项量下去，把 21 条泳道的可交互控件全部枚举出来，结论是 **17 条泳道一个控件都不渲染**
（21 减去下面列出控件的 4 条；只读投影本应如此），控件集中在这几处：`audit` 4 个筛选（全部／CI 运行／执行／失败）、
`observer` 6 个跳转、`workflows` 5 个（其中 `新建工作流` 为禁用）、`workflow-editor` 24 个（其中 3 个禁用）。

**四个禁用动作的理由全都只能靠鼠标读到**：`Button` 走原生 `disabled` 且带
`disabled:pointer-events-none`，所以它不接受焦点；`Tooltip` 只有 `group-hover/tt:opacity-100` 一条显露路径。
理由文本在 DOM 里其实有两份（外层 span 的 `aria-label` 与 `role="tooltip"` 的 span），
但外层是个没有 tabindex 的普通 span，键盘与读屏用户既走不到那个控件、也读不到它的解释。
§11 里"G1 动作级禁用与理由（已补）"这句因此只对一半的输入模态成立——这条口径由 ERR-156 更正。

修复在 `src/components/ui/tooltip.tsx`（`e5f9756`）：提示同时响应焦点显露（`group-focus-within/tt:opacity-100`），
并且**只有当它裹着一个无法获得焦点的禁用控件时**，外层才自己成为 tab stop（`tabIndex=0`＋`role="note"`），
以免给每个 tooltip 都加一个停靠点；递归是因为调用点把按钮包在定位用的 `<span>` 里。
契约测试 `src/components/ui/tooltip.contract.test.tsx` 4 例，证伪 4/4
（删掉焦点显露、把 tab stop 无条件加上、完全不加、丢掉 `aria-label`），改完源码逐字节复原。
全套 `npm run test` 24 文件 / 165 例全绿，`tsc --noEmit` 干净。

**尚未证明的**：jsdom 只证属性与 class 契约，证不了真实 WebView2 里的焦点顺序、透明度过渡与焦点环落点；
这四个禁用动作的实际 Tab 到达仍欠一次桌面读回。样式不变也只是我对 diff 的读法，不是渲染证明。

## 17. 2026-10-07 产品审计跟进（当前工作树 `cda4165`）

审计发现工作区抽屉把 `Motion Effects` 固定显示为 `Enabled`，但用户启用系统减少动态效果时，B10 的抽屉、Toast、翻卡和若干过渡仍继续移动。产品表示与实际样式均不符合 §6 的 Reduced Motion 要求。修复如下：

- `apps/observer/frontend/src/skins/l10b-shell.css` 在最终壳层增加 `prefers-reduced-motion: reduce` 规则，统一关闭动画、过渡与平滑滚动。
- `apps/observer/frontend/src/App.tsx` 将静态的 `Enabled` 改为“遵循系统设置”，不再声称动态效果始终开启。
- `src/reducedMotion.contract.test.ts` 覆盖壳层规则；`App.behavior.test.tsx` 覆盖抽屉文案。

复验：Observer 前端 25 文件 / 167 项通过；`tsc -p tsconfig.json --noEmit` 退出 0；Vite production build 退出 0，输出写入 `.project-local/runs/ui-audit-20261007-cda-build/`。没有安装依赖。

整仓 `python services/orchestration/run_quality_gate.py verify` **FAIL / 本地环境未能完成**：治理批次运行 2,184 项，出现 22 个 `test_project_terminal_guard` 断言失败和 `test_clean_with_unpushed_commit` 错误；前一组的失败值集中为 Windows `Path.resolve(strict=True)` 对 `.project-local/runs/tmp` 子目录返回 `PermissionError`，后一组的本地 bare-repository `git push` 返回 `Could not read from remote repository`。这些结果不能记作门禁 PASS；受限环境下也未绕过路径或 Git 写入限制。`--changed apps/observer/frontend/src` 安全回退到完整验证，因此同样止于治理批次。

**【2026-10-07 当日更正，原文保留不改】** 上面那段 FAIL 在换一台主机后被证伪：同一棵树（HEAD `cda4165`）用声明工具链 `.project-local/toolchains/wl-py311/Scripts/python.exe` 重跑整仓 `verify`，得到 `QUALITY_GATE_GOVERNANCE_PASS modules=207 executed=2175 ran=2185 skipped=10`、47 门全部执行、退出 0，1,021 行日志里 `FAILED`/`Traceback`/`PermissionError` 各 0 处（`.project-local/runs/qoder-20261007-a/gate-verify.log`、`gate-exit.txt`）。`test_project_terminal_guard` 的 22 项与 `test_clean_with_unpushed_commit` 的 1 项在这一侧全绿，所以它们是**上一会话沙箱对 `.project-local/runs/tmp` 的权限**与该会话自身的 Git 写入限制，不是产品缺陷，也不是工具链缺失。据此也不得反过来宣称"整仓已验证"：GATE_SEMANTICS 同日仍明写 `RUNTIME_CANARY_PENDING`、`TAURI_WINDOWS_PENDING`（真实桌面 WebView2 未跑）、`EXACT_SHA_CI_UNVERIFIED`（本地不冒充 exact-SHA CI），`skipped=10` 是具名隐私跳过，照常保留。

隐私边界复核另发现两处治理测试曾在机器本地素材存在时读取其字节计算摘要。已移除这类读取；两个测试现在以具名 `skipTest` 明示机器本地素材未复核，tracked registry / pin 仍做结构检查。此前那次全仓批次发生在修正前，聚合日志未包含素材正文，但无法从聚合输出判定条件摘要是否触发；它不作为这两项隐私边界修正的验证证据。

修正后定向验证：`test_recovered_source_registry.py` + `test_ag19_record_root_pin_test.py` 为 **26 passed / 2 skipped**；两项 skip 都逐字说明机器本地原件的字节未打开。Python 进程退出后另有已知 `pyreadline3` destructor `OSError`，pytest 退出码仍为 0。

审计边界：本分支为 `task-decomposition/atlas-gap-archive-20261001`，HEAD `cda416523deb108d721feada367f02aa77ef01cb`。本地 `origin/main` 跟踪值为 `cd4daa83e107afab8438c0e85f63a10e75314d5a`；远端读取失败，当前远端 main 的 SHA 未核实。**【2026-10-07 当日更正】** 同一会话的远端读取阻塞在下一会话的可信 Shell 里不存在：`git ls-remote origin refs/heads/main` 实测返回 `cd4daa83e107afab8438c0e85f63a10e75314d5a`，与本地跟踪值一致，远端 main 已核实为该 SHA（不是"UNKNOWN"，也不是猜测）。顶层结构检查 `verify_project_authority_reference.py` 与 `verify_error_ledger.py` 均通过。当前项目仍有已登记的 U02、U18 未完成范围；UI 的逐泳道 Loading/Permission 矩阵及非审批泳道的动作级权限说明仍按 §15.1 保持未完成。本轮修改限于 Observer UI、其登记状态与两项机器本地读取边界测试；没有增加登录、令牌、密钥或防护机制。回滚时逐项撤销本节 App/CSS/测试更改、恢复 U03 登记行并删除本节；不需要改写提交历史。

对照产品路线卡，仍有两项功能缺口：P1-02 的 `taskId` / `executionId` URL 定位尚未实现（当前 URL 仅接收 `view`、`theme`、`layout`）；P1-03 的 Codex/Hermes/DSH 原生能力卡尚未实现（当前 Agents 页只按真实执行记录显示 agent、状态、会话和工作区）。这些字段没有当前 Snapshot 合同来源，继续显示 UNKNOWN 比伪造值更准确；本轮未新增 placeholder 卡片或隐藏路由。

**【2026-10-08 当日更正】** 上面这句里 P1-02 已经不再成立，P1-03 仍然成立。P1-02 按 合同 → 后端投影 → 一致性 → UI → 行为验证 落地：`snapshot_api.project_task_record()` + `taskRecords` 字段（缺席≠空列表）+ `snapshot_validator` 逐条校 + `types.ts` 的 `TaskRecord` + `lib/recordFocus.ts` 的封闭标识校验 + Work 泳道行链接与详情卡；`?view=work&taskId=…` 刷新、前进/后退、复制地址落同一条记录，找不到就说找不到，不回退到第一条。验证：vitest 26 files / 194 tests、tsc 0、vite build 0、Python 13 项新门；仍欠真实 WebView2 里的同一条深链读回。

## 18. 2026-10-08 Control Surface 落地（批次 C 首条真实写链）

独立写边界第一次以代码存在，不再只是路线登记：`services/control/control_service.py`（loopback-only、动态端口、把监听点写进运行根 `control-endpoint.json`）+ `apps/control-surface/`（零依赖零构建薄壳，同源提供，CSP `default-src 'none'; script-src 'self'`，页面上没有任何登录/令牌/密钥控件——测试扫的是 `<input>` 控件而不是散文）。合同 `control-operation` / `control-operation-result` 已登记 catalog（37→39）、`tests/workflow-assistance/test_core_schemas.py` 的钉住集合与 `scripts/ci/verify_contract_catalog.py` 的清单（**两处**登记是刻意的：合同出现必须是一次被审阅的决定）。

12 个操作里只有两个真的实现：`work-unit.create`（写唯一 canonical store 的 tasks 表并读回）与 `config.diff`（`plan_only:true, written:false`）。其余十个 NOT_IMPLEMENTED，各自带 reason_code 与下一步，且合同规定这类回答必须 receipt=null——不可用动作不可能伪装成成功。

> **2026-10-08 追正（上一句写下时的读数已被实测超越）**：注册表现为 13 个操作、已实现 3 个——`work-unit.create`、`work-unit.materialize`（消费已授权的 PlanningCandidate，授权在服务端重算，客户端自称不作数）、`config.diff`；未实现 10 个。合同 `control-operation` 的 operation 封闭枚举与注册表两侧零漂移（实测 `ENUM_MINUS_REGISTRY=[]`、`REGISTRY_MINUS_ENUM=[]`）。控制面守卫从 23 项增至 60 项（`test_control_service` 29 + `test_planning_candidate_handoff` 31，本机实跑）。上一句原文保留：这条记录的价值在于显示它被追正过，而不是被改写得看起来一直就对。

真实读回（`.project-local/runs/qoder-20261007-a/prove_control_to_observer.py`，两个真进程、项目内运行根）：写入 WL-E2E-CONTROL-1 → ACCEPTED + digest 回执 → Observer 的 `/api/v1/snapshot` 实测含该记录（QUEUED、checkpoint 键名与摘要、无正文）→ 对 sidecar 的 POST 实测 **405**。证据等级封顶 SYNTHETIC，`completion_authority_reached:false`。

**实测到但没有抹平的三个缺口**：(1) `revision_before=0 / revision_after=0`，关 worker 与开 worker（tick 1s）两次都一样——写的内容能在下一次全量快照读到，但没有推进 revision，因此不会作为推送事件到达正打开的 Observer，“同一任务新 revision 可见”只完成一半，下一步查 `LiveProjection`/`start_live_updates` 的 canonical fingerprint 为何没因新任务行而变；**【2026-10-08 当日更正，原文保留】缺口 (1) 判定作废：那是我的探针在写入与 watcher 下一次 tick 之间抓快照，抄下了还没 bump 的旧 revision。给探针补上“内容出现后继续等 revision”重跑得 `0 → 1`（等待 0.25s，两个真进程、同一项目内运行根、真实 `/api/v1/snapshot`）。同一形状已升为永久回归 `tests/workflow-assistance/test_sidecar_publishes_cross_process_write.py`（跨连接写必须在有界时间内推进 Observer revision 且 `transport.freshnessState=FRESH`；重启后的 sidecar 不得发出比已发布游标更低的种子）。教训：内容可见与 revision 推进是两个保证，仪器提前读数不等于产品缺陷。**(2) checkpoint 正文只在 store，UI 详情卡的 Goal/Revision/Attempt/Planner/Agent Routes/Execution Timeline/Diff/Tests/CI/Receipts/Approval/Handoff 全是显式来源缺口，其中 task↔execution 外键确实不存在；(3) 我自己在这一轮里制造并被门抓住的两次：stdout 未 flush 导致 launcher 读不到端口、以及合同登记只改了一处清单。


## 19. 2026-10-08 续轮：能力卡、区间读、逐泳道状态矩阵与影响分析器

owner 追加「继续」后按批次推进的四件事，全部有可失败的门，不以登记代替实现。

**P1-03 Agents 原生能力卡。** 七层阶梯（Registered→Installed→Loaded/Connected→Qualified→
Enabled for Task→Native Projection→Observed in Execution）此前只在蓝图 §6 的散文里，没有任何东西阻止界面
把一个清单条目说成「已安装」或「已原生验证」。现在它是机器可校验的合同：唯一投影
`packages/client-neutral-core/scripts/adapter_capability_projection.py` 决定每层状态，
`snapshot_validator` 强制 MET 必须带来源且证据等级不得是 NO_EVIDENCE、NOT_PROBED 必须写明缺什么、
层名不得重复、`nativeStatus=NATIVELY_VERIFIED` 只有在 OBSERVED_IN_EXECUTION 层 MET 时才合法。
本机真实读回 10 张卡：deepseek-harness 的 INSTALLED 因 `SINGLE_VERIFIED` 而成立；cc-switch / open-design
因实测未安装而是 NOT_SUPPORTED（测出来的缺失不等于没测）；hermes / codex / github / openhuman 因软件身份
发现给出 UNKNOWN 而是 NOT_PROBED；所有卡 nativeStatus=NOT_IMPLEMENTED，理由与 AG-06/G06 一致。
第一次我把能力清单绑到了 `capability-conformance.json` 的条目上，但那些条目是**协议**（adapter-interface /
acp-compat-layer / repo-managed-skills / context7…）不是客户端，照它画卡就是画一张没有源的卡；每客户端事实
一律改自 `capability-matrix.json#clients[]`。registry 与 matrix 动词不一致时两处都列并标注不一致，不替
owner 选真值。界面在 `views/AdapterCapabilityCards.tsx`，零交互控件。

**REQ-RANGE 大产物精确区间读。** 证据链早有 sha256 与成本预算，但读取只有整读或 `_truncate(limit=4000)`
式前缀；前缀不是切片，读者不知道停在哪、后面还有没有、给出的字节是否仍属于被记录的摘要。
`evidence_range_reader.py` 补上：绝对句柄必须解析进本仓库、4 MiB 上限超限拒绝而不静默截断、回报
offset/limit/endOffset/eof/`sliceDigest`（对返回字节本身求摘要）。一致性只与调用方给的 `wholeDigest` 比对，
缺来源即 DIGEST_UNAVAILABLE —— 这条设计就是「区间读不会偷偷变成整读」的可证形式。8,388,614 B 的项目内
日志实测整读 0.0023s 对照区间读 0.000420s（比值 0.000488）。只读 sidecar 暴露
`GET /api/v1/evidence-range`，同路由 POST 实测 405，坏参数 400。UI 落点仍欠，且欠因已具体化：快照还没有
把 Evidence Store 的 `artifact` 句柄投影成可点列表，在那之前不做让用户手填路径的假入口。

**E5 逐泳道 Loading/Permission 矩阵。** `laneStateMatrix.sweep.test.tsx` 遍历 21 条注册泳道 × 2 种快照并
打印实测矩阵：无快照时 21/21 无成功色 pill、21/21 带 UNKNOWN/未接入/来源缺口措辞、12/21 另有显式空态、
整页塌成裸 `0` 判失败、OFFLINE 下任何泳道不得自称在线。权限态是**双向**规则：以 `PermissionState` 自己的
默认标题「此界面只读」为签名，有审批行时 approvals 必须给出 blocked/reason/stillAvailable，没有行时不得
凭空立一块权限牌；其余 20 条只读泳道出现权限块即失败（伪造权限控件等于宣称一个不存在的动作）。
这一项里我自己的仪器错过两次：第一版断言查 `[data-permission-state]`，而生产组件根本没有这个属性，于是
「双向」退化成长年为真的单向假绿；第二版写了 `result.cleanup()`，被 tsc 当场拒绝。

**P2-04 影响分析器。** 先用一次真实调用证明 fail-open 存在（不是读代码猜）：module root 命中但该 module
没有同名 gate 时 `required_gates=[]`、risk 仍是 medium —— 一份读起来像便宜 PASS 的计划。修三处：
`load_profile` 拒绝无 gate 的 module；`build_plan` 对「有变更但零选择」升级 critical；
`unknown` 的定义从「只看 module 命中」改为「既不匹配 module 也不匹配任何 gate 的 paths」—— 后者曾把
`packages/contracts/README.md` 这种**已被 gate 明确分类**的路径说成未分类。profile 里 services/ 与
integrations/ 归到 workflow 作业、packages/contracts/ 同时归 workflow+integration；刻意不新增 gate id
（会破坏 `aggregate_gate.PLAN_GATES` 不变量，现在有测试直接读它的源码比对这条不变量）。
local `--changed` 接上唯一 planner，planner 不可用/计划为空一律回全门，且打印本次实际执行范围。

**本轮三次「 inherited 说法 vs 实测」的更正**：上轮我登记为缺口的「Control 写不推进 revision」经补完
等待后是 `0 → 1`（0.25s），是我自己的探针在写入与 watcher 下一次 tick 之间抓快照抄了旧值 —— 已就地更正并
升为永久回归 `test_sidecar_publishes_cross_process_write.py`（含重启后不得发出更低游标）。
区间读的边界测试第一版把系统 temp 当「仓库外」，本地全绿、进门就红 3 项：canonical runner 会把
`TMP/TEMP/TMPDIR` 绑到 `.project-local/runs/tmp`，门内系统 temp 在仓库里；探针改为引用上一级一个永不创建
的路径并断言前后都不存在（读取器在打开任何东西之前判定边界）。教训：探针的「外部」不能靠常识，要按被测
runner 的模式量一遍。

**末次验证**：Python `QUALITY_GATE_GOVERNANCE_PASS modules=214 executed=2277 ran=2287 skipped=10`
（10 项 skip 全是具名隐私跳过）、`CI_ROOT_GOVERNANCE_PASS modules=23`、整门 `GATE_EXIT=0`；
前端 tsc 退出 0、vitest 28 files / 207 tests、vite build 退出 0。
本轮不申请也不执行：提交、推送、PR、合并、发布、安装、改全局配置、跨项目写。

> **2026-10-08 更正（§19 末句已过期）**：owner 随后给出「全部授权」，提交与推送**已被授权并已执行**；
> 未被这次授权覆盖、仍然不做的仍是：合并、tag/release、安装到用户系统、改全局配置、跨项目写真值、
> 付费调用、跨 Provider 传私人数据、访问 `E:\`/`F:\`、批量删除，以及 force push／reset --hard／改写历史。

## 20. 2026-10-08 交付轮：分片提交、绑定、以及一次在 push 前拦住我的复核

**提交分片按"为什么这样切"而不是按文件数量**：`34b324e` 仪表与边界残留、`7b7a2e9` 读投影（任务记录＋能力阶梯＋
深链焦点）、`449829d` 全站 reduced-motion 地板、`a279f54` Control 后端与薄壳、`07e76ed` `--changed` 接回 canonical
规划器、`e70c04c` 证据字节区间读、`efb6a19` CDP 画像目录释放、`fcc40df` 记录、`7fadfcd` 台账绑定、
`2f04622` 被打断的两份审计重发布、`62a8ebf` ERR-166、`936e597` 授权变更与本节。

**加一条记录不是免费动作（本轮新学）**：`LEDGER_REGRESSION_COMMAND_TARGETS` 把记录数与由每条记录标签算出的
`stateDigest` 钉死，`TOOL_INVENTORY` 描述跟踪工具集。写完三条 PASS 绑定后整门仍红，报的是
`160 != 163` 与两份分布不一致；再加 ERR-166 又红一次。结论不是"门禁太严"，而是**记录与它打断的审计必须在同一次
提交里落地**，否则中间任何一个 head 都不可绿。两次都由工具自身重发布（人不改写审计），随后 39 项目标测试转绿。

**绑定采用两步**：先提交修复，再在后续提交里把 `fixedCommit` 写成真实 SHA（ERR-163→e70c04c、ERR-164→a279f54、
ERR-165→efb6a19），`verifiedCommit` 一律留空——它只能来自 push 之后 exact-SHA 的 Actions 读数，由
`scripts/audit/stamp_record_verification.py` 自己核对"修提交是它的祖先且该 head 全绿"再写。
ERR-166 反过来：修提交在记录之前已存在，所以按门禁规则**建记录即绑定**，不留未绑 PASS。

**复核在 push 之前发现真缺陷（ERR-166，已修 6d20d28）**：新的 `GET /api/v1/evidence-range` 只把"路径不出仓库"
当边界，而这个项目的凭证就住在仓库里。复核实测三处返回内容——恢复安装前的 `hermes/config.yaml`（31 KB，本来就在
证据根下）、`config/config.yaml`、`.hermes/task-runtime/**/canonical.sqlite`（221 KB 任务/会话库）。
文档字符串写着"绝不把句柄带出项目"，这句是真的，同时也是无关的：唯一被我自己实现的边界保护不了任何东西。
修复分三层且顺序固定：先按名字拒绝（凭证形状即使在证据根下也拒绝），再要求句柄落在
`project-data-boundary.json` 声明的证据面上（而不是我另写一份意见），显式空面拒绝一切；路由另外要求对端是
字面环回地址，而不是今天解析到环回、明天可被 HOSTS 改走的主机名。改后实测：上述三处加 `sidecar.py`、
`.git/config`、治理机读文件全部 REFUSED 且不返回内容，`.project-local/runs` 下真实运行日志仍按区间读出；
25 项测试通过，其中 6 项是新增负向控制。一次 HTTP 200 不是完成，一次全门绿也不是安全边界——push 因此推迟。

**同一次复核报出但尚未修的 Control 面五处**（已在任务清单挂住，等并发写作者释放
`services/control/control_service.py`）：`PermissionGate(Policy())` 空策略令两个已实现操作自动 ALLOW；
门禁 `target` 传的是操作名，于是门禁里针对 `.env`/credential 的 CRITICAL 升级结构上不可能命中；
`_scope_failure` 只在"绝对且带盘符"时做包含检查，UNC `\\host\C$\x` 与盘相对 `E:secrets` 会被当作已授予范围写入
台账；盲目 upsert 可覆盖在活的 lease holder 并使 fencing token 倒退；`--runtime-root` 一给即把证据上限抬成
INTEGRATED。这些是"已定位到行、未修、不称闭合"的状态，不是已完成。

**并行在飞（互斥路径，未到结果不称完成）**：真实 WebView2 键盘/焦点读回、Tauri 侧窗口内部尺寸读回（补
440×780 声明与 500×629 CDP 仿真的差额，这是 E9 唯一真欠项）、PlanningCandidate 终点消费者、测试侧裸
`mkdtemp` 收口、Inspector 完备性与证据三列视图、适配器逐动词证据、快照 `artifactHandles` 投影（正是 REQ-RANGE
UI 落点的欠因）、以及 AGENTS.md 五维基线第 1/2 维的入口链读回。
