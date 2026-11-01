# W01 交付物 —— 原稿 → Token / 组件 / 路由 / 状态 矩阵与差异

**观察 SHA：** `d116b14995fcdbba1b165ec5bc3124f5daed3d15`
**性质：** 只读分析。**本轮未修改任何 tracked 文件。**
**原稿来源（仅 DESIGN-LAB 单项目包，已排除三项目混合全量包）：**

| 批次 | 归档 | archive sha256 | 解包文件 |
|---|---|---|---|
| B04 | `DESIGN-LAB_L4_组件系统_16张+Tokens.zip` | `4be8aff0a6d8e381…` | 19 |
| B07 | `DESIGN-LAB_L7_前端开发规范工程包.zip` | `6216465117297ba0…` | 23 |
| B10 | `design-lab_最终版_高保真可部署UI.zip` | `fa56e404d4f6edaa…` | 3 |

解包位置：`.project-local/task-artifacts/designlab-followup-taskpack-20260928/ui-originals/`
（逐文件 sha256 见同目录 `EXTRACTION-MANIFEST.json`；路径安全校验通过，未执行任何内容）

---

## 1. Token 承载矩阵（原稿 vs 实现）

实现侧：`apps/workbench/style.css` 的 `:root`

| 族 | 原稿定义数 | 实现承载数 | 缺失 |
|---|---|---|---|
| **color** | 12 | **12** | 无 ✅ |
| **radius**（md/lg） | 2 | **2** | 无 ✅ |
| **motion** | 4 | **4** | 无 ✅ |
| **space** | 8 | **0** | ❌ `--space-1/2/3/4/6/8/12/16` **全缺** |
| **font** | 6 | **0** | ❌ `--font-display/h1/h2/h3/body/caption` **全缺** |
| **breakpoint** | 3 | **0** | ❌ `--bp-mobile/tablet/desktop` **全缺** |
| **density**（仅 B04 有） | 3 | **0** | ❌ `comfortable 68 / default 56 / compact 44` |
| **radius.xl**（仅 B04 有） | 1 | **0** | ❌ `xl: 20` |

**判定：颜色与动效 100% 对齐；间距、字号、断点、密度四族完全未落到变量层。**
这不是"改配色"级别的问题，而是**实现绕过了 Token 体系**：
当前布局用的是 B10 的硬编码值（`padding:26px 28px 30px`、`gap:16px`、`font-size:32px`…），
而原稿要求走 `--space-*` / `--font-*` 标度。

**颜色逐项核对（12/12 一致）：**
`#060A14` bg · `#0D1221` surface · `#11182A` surface2 · `#213D66` border · `#316CFF` primary ·
`#4BAFFF` secondary · `#F5F7FC` text · `#9AA3B8` muted · `#2FC58D` success · `#F4B942` warning ·
`#F05252` error · `#4BAFFF` info —— B04 `design_tokens.json`、B07 `theme/tokens.css`、
实现 `:root` **三方同值**（Electric Blue 品牌延续 ✅，无跨项目串色 ✅）。

---

## 2. ⚠️ 原稿之间的自相矛盾（需 owner 裁决，不能我替定）

| # | 冲突 | B04 说 | B07 说 | 实现 | 影响 |
|---|---|---|---|---|---|
| **X-1** | **正文字号** | `body: 18` | `--font-body: 16px` | 无该变量（硬编码 `p{font-size:13px}`） | 正文密度基准不一致 |
| **X-2** | **caption 字号** | `caption: 14` | `--font-caption: 13px` | 无该变量 | 同上 |
| **X-3** | **移动断点** | — | `767px` | `760px` | 三套断点 |
| **X-4** | **B10 断点** | — | — | B10 CSS 用 `840px` / `1160px` | **同一仓库内三个不同移动断点：767 / 760 / 840** |
| **X-5** | **density** | 有（68/56/44） | **未承载** | 无 | B07 治理层漏了 B04 的一整族 |
| **X-6** | **radius.xl** | `xl: 20` | **未承载** | 无 | 同上 |

**结论：B04（设计 Token）与 B07（前端治理）本身不同步**，实现又各自偏离。
按包内规则「原件缺失/冲突不声明 1:1」——
**当前状态不满足"Token 基线已固定"，W01 不能自行宣告完成。**

---

## 3. 组件契约：**B07 自带 45 个组件的注册表**（这条改变 W02 的选型依据）

`B07/shared-ui-core/component-registry.json` 声明 **45 个组件**，每个带
`family / states[4] / responsive / themeable`：

| family | 数量 | 组件 |
|---|---|---|
| navigation | 6 | AppShell, Sidebar, Topbar, Breadcrumb, Tabs, CommandPalette |
| inputs | 8 | Button, IconButton, Input, SearchInput, Select, MultiSelect, TagInput, DateRange |
| data | 10 | Card, KPI, Table, List, Tree, Timeline, Graph, Badge, Avatar, Progress |
| feedback | 6 | Toast, InlineAlert, EmptyState, LoadingSkeleton, ErrorState, **OfflineState** |
| overlay | 6 | Modal, Drawer, Popover, ContextMenu, Tooltip, ConfirmDialog |
| workflow | 5 | ApprovalStep, VersionCompare, ConflictResolver, PermissionGate, AuditEvent |
| layout | 5 | PageHeader, Section, SplitPane, ResizablePanel, ResponsiveGrid |

每个组件的 `states` 统一为 `['default','hover','focus','disabled']`。

**关键含义：** B07 已经**自己声明了一套 45 组件契约**。
所以 W02「引入一个主组件体系」的裁决**不应直接从 Spectrum Web Components 开始**，而应先问：
**这套 45 组件 + 4 态能否用现有 CSS 体系表达？** 若不能，再评估外部库能否覆盖这 45 个契约项
（而非按库的热门程度选）。这是**内部基线优先**，也符合 AUTHORITY §9 REUSE-FIRST。

另注 B07 `breakpoints.css` 引用了未在实现中出现的类：`.responsive-grid`、`.desktop-only`。

---

## 4. 路由矩阵（B07 12 条 vs 实现 11 条）

| B07 routes.json | 实现 `shell.ts` | 差异 |
|---|---|---|
| `/` dashboard | `#/dashboard` | ✅ |
| `/projects` | `#/projects` | ✅ |
| **`/projects/:id` project-detail** | **—** | ❌ **缺失** |
| `/research` | `#/research` | ✅ |
| `/brand-systems` | `#/brand-systems` | ✅ |
| `/domains` design-domains | `#/domains` | ✅ |
| `/tools` creative-tools | `#/tools` | ✅ |
| `/preflight` preflight-qa | `#/preflight` | ✅ |
| `/deliverables` | `#/deliverables` | ✅ |
| `/evidence` | `#/evidence` | ✅ |
| `/collaboration` | `#/collaboration` | ✅ |
| `/settings` | `#/settings` | ✅ |

**唯一缺口：`project-detail`（项目详情 `/projects/:id`）未实现** —— 而这恰好是 W03「项目中心」的核心动作。
B07 `pages/page-map.json` 还为每页声明了 `shell: AppShell` + `layout: PageHeader + ResponsiveGrid`
与 5 态 `['loading','empty','error','permission-denied','ready']`。

---

## 5. 状态机：**原稿与实现一致** ✅

B07 `state/domain-state-machine.json`：
`brief → research → designing → review → qa → approved → delivered → archived`（NEXT/BACK 双向）

实现 `shell.ts` 的 `stateMachineStepper()` stages：
`['brief','research','designing','review','qa','approved','delivered','archived']` —— **完全一致**。

---

## 6. W01 差异清单（交付给 W02/W03）

| # | 差异 | 类型 | 落点 |
|---|---|---|---|
| G-1 | spacing 8 项未变量化 | 补实现 | `apps/workbench/style.css` `:root` |
| G-2 | typography 6 项未变量化 | 补实现 | 同上 |
| G-3 | breakpoint 3 项未变量化 | 补实现 | 同上 |
| G-4 | B04 density 3 项未承载 | 补实现（先定 X-5） | 同上 |
| G-5 | B04 `radius.xl` 未承载 | 补实现 | 同上 |
| G-6 | **断点三套并存 767/760/840** | **需裁决（X-3/X-4）** | 全局 |
| G-7 | **B04 与 B07 字号矛盾（X-1/X-2）** | **需裁决** | 全局 |
| G-8 | 45 组件契约无实现层 | W02 裁决对象 | `packages/design-system` 或新组件层 |
| G-9 | `project-detail` 路由缺失 | 补实现 | `shell.ts`（W03） |
| G-10 | `.responsive-grid` / `.desktop-only` 类未实现 | 补实现 | `style.css` |

**W01 状态：`PARTIAL`。** 已完成的：原稿定位、来源完整性验证（B10 逐字节）、Token 三方核对、
组件契约提取、路由/状态机对比。**未完成**：视觉差异的**像素级**核对（16 张 B04 组件图未做人眼比对）、
X-1…X-6 的裁决。**在 X 系列裁决前，不得声明 Token 基线已固定。**

---

## 7. 本轮（round 3）已闭环：G-1/G-2/G-3/G-4/G-5 落变量层

**PR #176 已合并，main = `cac30c7aa83e701d9ad851fa6669231bea4b7199`。**

按原稿**精确值**补齐为变量（纯新增，零行为变更）：

| 族 | 修复前 | 修复后 |
|---|---|---|
| space | 0/8 | **8/8** ✅ |
| font | 0/6 | **6/6** ✅ |
| breakpoint | 0/3 | **3/3** ✅ |
| density | 0/3 | **3/3** ✅ |
| radius.xl | 0/1 | **1/1** ✅ |
| color / radius(md,lg) / motion | 已 100% | 保持 |

**新增第 7 项原稿矛盾 X-7（本轮实测发现）：**
`--radius-sm` 已被 **B10 桥接块**定义为 `12px`（`style.css:355`），而 B04 `radius.sm = 4`。
**同名冲突** → 为不破坏 B10 层，**未重定义**（合并后仍只有 1 处定义，已验证）。

**仍未做（明确边界）：**
- 变量**未应用到元素**（那会触发 X-1…X-7 的裁决，需 owner 决定）
- 断点三套并存（X-3/X-4）未统一
- 16 张 B04 组件图的像素级人眼比对未做

---

## 8. 更新后的差异清单状态

| # | 差异 | 状态 |
|---|---|---|
| G-1 spacing 未变量化 | ✅ **已修**（PR #176） |
| G-2 typography 未变量化 | ✅ **已修** |
| G-3 breakpoint 未变量化 | ✅ **已修** |
| G-4 B04 density 未承载 | ✅ **已修** |
| G-5 B04 radius.xl 未承载 | ✅ **已修** |
| G-6 断点三套并存 767/760/840 | ⏳ 需裁决（X-3/X-4） |
| G-7 B04 与 B07 字号矛盾 | ⏳ 需裁决（X-1/X-2） |
| G-8 46 组件契约缺 11 项 | ⏳ W02 裁决中（见 `W02-COMPONENT-DECISION.md`） |
| G-9 `project-detail` 路由缺失 | ⏳ 待 W03 |
| G-10 `.responsive-grid` / `.desktop-only` 未实现 | ⏳ 待 W02/W03 |

**新发现：X-7 `--radius-sm` 名称冲突（B10 `12px` vs B04 `4`）。**


---

**END — W01 交付物。本轮只读分析，未修改仓库。**
