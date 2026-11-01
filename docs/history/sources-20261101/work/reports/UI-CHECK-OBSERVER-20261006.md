# WORK-LAB Observer 界面结构/布局框架 设计走查报告

**走查目标**：`apps/observer/frontend/src`（React + Tauri 正式 UI；`App.tsx` 壳层、`components/layout/{Sidebar,TopStatusBar}.tsx`、`components/ui/*`、`views/*` 22 条 lane、`skins/b10.css`(533) + `skins/l10b-shell.css`(75) + `index.css`）
**走查时间**：2026-10-06
**走查模式**：模式 A（代码自动走查）。未读到链式 Brief/Flow 上下文（本仓无 `spark-output/`），改以项目自有权威 `UI_DECISIONS.md`（D-01…D-16）作为附加一致性检查基线。
**边界**：只读审计，本次未修改任何源文件。

## 总览

| 严重度 | 数量 |
| --- | --- |
| 🔴 Blocker | 2 |
| 🟠 Major | 7 |
| 🟡 Minor | 3 |

10 个类别全部有发现（无整类通过）。

## Findings（按严重度排序）

### 🔴 Blocker

**B-1 · 响应式（7.1/7.2）— 窄屏壳层把 4 个动作变成不可达**
≤840px 时 `skins/b10.css:519-527` 直接 `.top-actions{display:none}`，而 `components/layout/TopStatusBar.tsx:125` 的主题切换、full/compact 切换、工作区抽屉、通知都只存在于 `.top-actions` 内。移动抽屉 `Sidebar.tsx:160-171` 只有 lane 列表 + 关闭按钮，不含这 4 个入口；唯一替代路径 Ctrl/Cmd+K（`App.tsx:83`）需要物理键盘。结论：触屏/窄屏用户无法换主题、无法进紧凑布局、无法打开 Context 抽屉。
**出现位置**：`skins/b10.css:519`、`components/layout/TopStatusBar.tsx:125`、`components/layout/Sidebar.tsx:160-171`
**修复建议**：在 mobile-nav-panel 页脚复用 `onCycleTheme/onCycleLayout/onOpenDrawer`，或 ≤840px 保留图标精简版 `.top-actions`；补一条断点契约测试，断言窄屏下这 4 个动作仍可触达（当前无任何测试覆盖窄屏可达性）。

**B-2 · 链路通畅性（1.3）— 非法深链在 render 期改状态，并先渲染空白**
`App.tsx:206-216` 在构造 `mainContent` 的 IIFE（即 render 体内）调用 `setView(OVERVIEW_ID)`，同时 `return null`。React 会报 "Cannot update a component while rendering a different component"，用户先看到一帧空白内容区，且永远得不到"该链接 lane 无效"的提示——只静默跳回总览。
**出现位置**：`App.tsx:211-212`
**修复建议**：把 view id 归一化移到 `readInitialView()`/`useEffect`（渲染期只读），空白帧替换为 `UnknownState` 并写明"未知 lane，已回到总览"。

### 🟠 Major

**M-1 · 组件使用（3.1/3.3/3.4）— 两套 CSS 权威靠 `!important` 博弈**
`UI_DECISIONS` D-11 把 533 行 B10 皮肤作为**未分层**规则逐字引入以胜过 Tailwind `@layer`；后果在 `l10b-shell.css` 里可见：`.sidebar-slot{display:none!important}`（第 27 行）与 `.sr-only` 的 8 条 `!important`（第 63-73 行），并且壳层必须反向重述 `@media (min-width:841px)` 来补 B10 自身"媒体查询被同文件基础规则覆盖"的缺陷（D-12 已承认该缺陷源头）。断点阈值 840/841 分散在两个文件，任一侧改动都会静默失配。
**出现位置**：`skins/l10b-shell.css:12-34,63-73`、`skins/b10.css:519`
**修复建议**：把可见性/断点收敛到单一壳层来源（一个 `--shell-breakpoint` 常量 + 一处 display 规则），`sr-only` 交回分层 utilities；长期按 D-16 的思路把皮肤令牌化并进 `@layer skins`，去掉 `!important`。

**M-2 · 异常态覆盖（5.2）— 全仓没有加载态**
`grep -ci 'loading|加载'` 在 6 个主要视图文件（OverviewView / CompactHUD / SoftwareView / ObserverView / Views / WorkView）全部为 **0**。首帧快照未到达时（`snap==null && !error`，`App.tsx:189` 不成立）整页直接以 UNKNOWN 呈现，用户无法区分"正在取数"与"确实无数据"。`states.tsx` 有状态组件但无调用方。
**修复建议**：给首帧一次性骨架屏（或 `LoadingState`），并把 LOADING / STALE / OFFLINE / UNKNOWN 四态在 UI 与 a11y 播报（`App.tsx:178-186` 现在只播后三种）里区分开。

**M-3 · 无障碍（9.3）— `aria-modal` 声明了但没有焦点包含**
`drawer.tsx:47-48`、`command-palette.tsx:104-105` 都声明 `role="dialog" aria-modal="true"`，但全仓只有 `modal.tsx:39` 保存 `previouslyFocused`；drawer/palette 既无 Tab 循环、也无关闭回焦。屏幕阅读器/键盘用户可 Tab 进被 `aria-modal` 逻辑上屏蔽的背景内容。
**修复建议**：抽共享 `useFocusTrap(active, ref)`（Tab 循环 + Esc + 关闭回焦），drawer / command-palette / modal 三处复用；加 RTL 测试断言第 N 次 Tab 回到首个可聚焦元素。

**M-4 · 反馈（8.2）— 错误提示 1.8 秒消失且不可暂停**
`App.tsx:73` 全局 `useToaster(1800)`，`toast.tsx:48` 对所有 variant 使用 `role="status"`，error 型同样 1800ms 自动消失（`toast.tsx:79`），hover 只改边框色不暂停。错误来不及读、来不及跟随。
**修复建议**：`variant==='error'` 用 `role="alert"` + 不自动消失（或 ≥10s 且 hover/focus 暂停），保留 info/success 的 1800ms。

**M-5 · 与权威文档一致性（10.3/10.4）— D-02 声明的折叠态在实现中不存在**
`UI_DECISIONS` D-02 锁定"折叠宽保持 L7 的 72px"，但 `Sidebar.tsx` 与两个皮肤文件中 `collaps|72px|fold` **0 命中**（唯一命中是 `b10.css:264` 表格 `min-width:720px`，无关）。窄屏实际行为是整条 rail `display:none` + 抽屉。这是"权威声明了、设计没做"的缺口，而非实现偏差。
**修复建议**：二选一并落到文档——实现 rail 折叠（72px 图标态），或把 D-02 该句显式标注"未实现/已放弃"。教训同源：`HANDOFF-UI-L10B.md` 的过期行曾让三个会话把已完成任务当未做需求重做。

**M-6 · 信息架构（2.3/3.2）— 3 条 lane 有双渲染路径**
`monitoring`/`trust`/`settings` 既在 `VIEW_REGISTRY`（`viewRegistry.ts:75,77,81`）注册 component，又在 `App.tsx:199-204` 被硬编码分支抢先渲染。注册表是 U04 定的唯一 SSOT，双路径会让"新增 lane 只改注册表"的约定失真。
**修复建议**：删掉 App 内三条分支，统一 `VIEW_REGISTRY.find(...)`；加测试断言"任何 lane 的组件只能由注册表解析"。

**M-7 · 信息架构（2.1）— lane 数量口径与治理文档漂移**
`Sidebar.tsx:54` 注释与注册表现为 **22 条 lane / 7 组**，而 `OPEN-TASK-REGISTER` P1-01 行与 10-06 审计结论仍写"16 reachable lanes / 15 lane → 7 nav"。后续会话按旧数字断言会把正常状态误判成回归（本次任务输入里我给的"16 条 lane"就是被这个陈旧口径带偏的）。
**修复建议**：lane 计数由 `viewRegistry` 测试生成、不在文档手写；在 register 追加带日期的更正说明（不改写历史原文）。

### 🟡 Minor

**N-1 · 视觉层级（4.x）— 面板里"总览"label 有第二个来源**
`App.tsx:102` 硬编码 `{label:'总览'}`，与 `OVERVIEW_ID` 的注册标签并存；改名会出现导航与命令面板不一致。建议从注册元数据取 label。

**N-2 · 响应式（7.2）— "320px-safe" 只是注释，没有锁**
`App.tsx:260` 声明 compact 是 320px-safe，但 CompactHUD 未走 `.kpi-grid`（唯一在 ≤840 收 1 列的规则），全仓 320–375px 无契约测试。建议加 320px 视口断言把声明升级为可验证。

**N-3 · 内容文案（6.3）— 中英状态词混用**
同一抽屉里 `数据源未接入（UNKNOWN）` / `Read-only` / `Local State` / `Rendering` / `Motion Effects` 混排（`App.tsx:236-253`）。建议定术语表并统一 tag 词表。

## 修复优先级建议

- **必须修复**（主流程/可达性）：B-1、B-2、M-2、M-3、M-4 —— 共 5 项
- **建议修复**（结构一致性）：M-1、M-5、M-6、M-7 —— 共 4 项
- **可延后**：N-1、N-2、N-3 —— 共 3 项

## 本次未覆盖

- 未做真实像素/视口渲染核查（本机 `app.exe` 的 WebView2 E2E 正在另一条 P0 任务上跑）。
- 未做完整 WCAG 2.1 AA 审计（无障碍类发现是抽样，专项请用 Access）。
- 未核查 Token Monitor 与 Observer 的收敛（`UI_DECISIONS` 未覆盖该面）。
