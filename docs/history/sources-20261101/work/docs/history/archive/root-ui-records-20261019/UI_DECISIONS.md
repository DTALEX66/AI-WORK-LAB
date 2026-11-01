# UI_DECISIONS — L10 冲突裁决记录
<!-- ROOT-DISPOSITION:BEGIN NON-NORMATIVE-HISTORICAL -->
> **NON-NORMATIVE-HISTORICAL / 历史记录，不派工**（2026-10-10 登记，WUI-17）：本文件不在权威链里，正文逐字保留未改（门会把它与提交字节逐字节比对）。现行权威顺序：`WORK-LAB-AUTHORITY.md` → `.project/governance/project-authority-index.json` → `taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md` → `taskpacks/current/OPEN-TASK-REGISTER.md`（2026-10-19 更新；旧 UI 包已 SUPERSEDED_20261019 / FROZEN，不再是 CURRENT）；根目录逐份处置见 `docs/current/DOCUMENT-CENSUS.md` §4 与 `.project/governance/root-document-dispositions.json`。
<!-- ROOT-DISPOSITION:END -->

> 权威等级（`00_批次顺序_文件映射_权威规则.md`）：B10 > B09 > B08 > B07 > B06 >
> B05 > B04 > B03 > B02 > B01。低批次只补细节，不推翻高批次已定事实。
> 本文件记录 L10 执行（2026-09-27）中出现的冲突与裁决。

## D-01 · 路由形态：B07 路径路由 vs 仓内 lane 制
- **冲突**：B07 route-matrix 给的是 `/workflows`、`/workflows/:id/edit` 等路径路由；
  仓内现状是 `?view=` lane 深链 + `viewRegistry`（仓内无 react-router 依赖，Tauri
  桌面壳注入 `?view=`/`?api=` 参数，已有契约测试锁定）。
- **裁决**：保持 lane 制（B10 自身也是 `location.hash` 路由，非路径路由；仓内 Tauri
  契约优先）。B07 的 12 路由语义映射为 12 个 lane（见 UI_REFERENCE_MANIFEST §3 代码
  映射表），页面 IA 与 B07 一致；不引入 router 依赖（工程铁律：不为视觉重构破坏
  现有壳层契约）。

## D-02 · 侧边栏宽度 280 vs 260
- **冲突**：B10 `.app` 网格 `grid-template-columns:280px 1fr`；L7 component-overrides
  写 `Sidebar width 260`；B07 AppShell 示例未给宽度。
- **裁决**：**B10 赢（280px）**——B10 是最高视觉权威；L7 属 B07（低于 B10）。
  折叠宽保持 L7 的 72px（L7 唯一明确的折叠值，B10 未定义折叠态）。

## D-03 · TopBar 高度 78 vs 72
- **冲突**：B10 `.topbar{height:78px}`；L7 `Topbar height 72`。
- **裁决**：**B10 赢（78px）**。搜索栏形态 1:1 B10（`min(620px,54vw)`、14px 圆角、
  inset 高光）；状态真值（LIVE/传输/新鲜度/revision）保留仓内真实投影，不取 B10
  demo 的假数值。

## D-04 · 圆角：L4 radius lg=16 vs B10 面板 18px
- **冲突**：L4 design_tokens `radius: sm4/md10/lg16/xl22`；B10 `.panel{border-radius:18px}`
  、`.node{16px}`、`.modal{22px}`。
- **裁决**：**token 层保留 L4 值（4/10/16/22，CI 断言于 tokens.test.ts）**；B10 18px
  面板圆角通过 B10 面板视觉类的局部 radius 表达（`.wl-*` 类内联），不改全局 token——
  两者都是权威，不动被 CI 锁定的单一真值源。

## D-05 · 总览 KPI 数值：B10 demo 数字 vs 仓内真值纪律
- **冲突**：B10 `kpiCard("12","运行中工作流")` 等是演示数据；仓内铁律（U07/B5）
  "UNKNOWN ≠ 0，不伪造 KPI"。
- **裁决**：**布局 1:1 B10（4 列 KPI 卡 + count-up 大数字 + glow），数值全部来自
  v3 snapshot 真实投影；无数据 ⇒ UNKNOWN。** B10 数字只作视觉参照，不进运行时。

## D-06 · 审批/运行按钮：B10 可操作形态 vs Observer §8 只读铁律
- **冲突**：B10 审批中心有可点 `approveBtn`、编辑器有"保存并发布/运行"；
  AGENTS.md §8 只读铁律 + views.test.tsx 断言"无 批准/拒绝/撤销 按钮"。
- **裁决**：**页面结构与视觉 1:1 B10（风险 pill/上下文/审计记录行）；交互语义服从
  只读铁律**——无真实审批契约时整页渲染 UnknownState + 契约缺口说明；编辑器
  "发布/运行" 按钮渲染但 disabled + tooltip 说明"真实 workflow 执行契约未接入"，
  画布拖拽/连线/缩放为本地编辑模型（B10 localStorage 同款行为，允许）。

## D-07 · 趋势图数据源：B10 sparkline 序列 vs 无真实序列
- **冲突**：B10 `sparkline([18,26,...])` 为硬编码；v3 snapshot 不携带执行趋势序列。
- **裁决**：趋势图 1:1 B10 组件形态（渐变 stroke SVG），**数据缺失 ⇒ 空图占位 +
  "无趋势数据（UNKNOWN）"**，不用 B10 假序列冒充真值（Sparkline 组件已按此实现）。

## D-08 · 光效强度：B10 ambient blur 80px vs §八"禁止玻璃效果泛滥"
- **冲突**：B10 `.ambient` blur(80px) + `.sidebar backdrop-filter:blur(18px)`。
- **裁决**：**B10 赢**——§八 禁止的是"泛滥/霓虹/全页发光"，B10 的 3 团微弱环境光
  （opacity .45、blur 80px、12s 缓浮）正是"微弱蓝色环境光"的要求值，1:1 保留；
  不做全页发光、不加 extra neon。

## D-09 · Overview 与 Work lane（D3 已验收）
- **裁决**：总览按 B10 重构（KPI/趋势/Observer Map/系统状态/告警/最近执行）；
  D3 的 `work` lane 及其 B5 文案（"数据源未接入"等）原样保留，不并入总览——
  两 lane 并存，Nav 分组归位（主线接线决定）。

## D-10 · 资产策略（详见 ASSET_REPLACEMENT_MANIFEST.md）
- **裁决**：Logo 保留 B10 "WL" 渐变字标（不重设计）；网格/环境光/节点光效纯 CSS
  1:1 复刻；1920×1080 参考图仅 QA 对照，不进运行时；本轮**零新增位图资产**。

---

# L10b 裁决记录（B10 1:1 DOM 复刻，2026-09-27 · PR #143）

## D-11 · 皮肤来源：逐字 B10 CSS vs token 化重写
- **冲突**：L10 用 `index.css` 的 `--glow-*` token 近似表达 B10 光效；L10b 要求 1:1。
- **裁决**：**B10 逐字胜** —— `src/skins/b10.css` 为 B10 `<style>` 块（533 行）的逐字
  拷贝，加载在 `index.css` 之后。B10 皮肤是 **未分层** 规则，未分层优先级高于任何
  `@layer`，因此自动胜过 Tailwind 的 `@layer components/utilities`，无需 `!important`。
  构建产物偏移已回读证明（Tailwind `.panel` @5399 → B10 `.app` @20303 → B10 `.canvas`
  @30506 → L10b 壳层 @38410）。L10 的 `--glow-*` token 仍保留在 `index.css` 供
  未迁移的兼容层使用，但不再是 12 页的视觉来源。

## D-12 · 未分层皮肤导致的响应式缺口：壳层补齐 vs 改 B10 皮肤
- **冲突**：B10 自带 `@media (max-width:840px){.sidebar{display:none}}`，但同一文件里
  未分层的 `.sidebar{display:flex}` 在源码顺序上位于该媒体查询之前，且媒体查询不提升
  优先级 ⇒ B10 自身的窄屏隐藏规则被自己的基础规则覆盖（B10 单一文件里真实存在的
  缺陷）。同时 Tailwind 的 `hidden md:flex` 位于 `@layer`，无法再表达断点。
- **裁决**：**不改 B10 皮肤（保持逐字），新增壳层 `src/skins/l10b-shell.css`** 承接
  断点可见性 / compact 单列 / `.toast-stack` 角落 / `.sr-only` / `.sidebar` 左右内边距
  18→16px（让 B10 品牌字标在 280px 栏内单行；字体/字号/字距未改）。逐条理由登记在
  `UI_REFERENCE_MANIFEST.md` §11。

## D-13 · B10 圆点卫星标签锚点 vs 真实实体名可读
- **冲突**：B10 `.graph-stage` 在 `<circle class="node-dot">` 的**圆心**印 3.8px 标签，
  基于 demo 的硬编码几何；本仓把真实实体名（Agent/Workflow/Tool/MCP/Memory/Task Pack）
  放在同一 100×100 viewBox 的响应式容器里，圆心锚点会被圆点压住。
- **裁决**：**B10 结构/样式胜，标签位置局部让步** —— `circle.node-dot`/`.core`/连接线/
  脉动全部 B10 逐字；标签改为沿径向贴圆外侧（5px 字号），偏移约 4px。理由：B10 赢在
  结构/样式，真实可读的实体名属于数据层正确性。

## D-14 · 只读铁律 vs 组件库自带的重试入口
- **冲突**：`states.tsx` 的 `ErrorState` 带可选 `onRetry`，可渲染「重试」按钮；Observer
  只读铁律要求只读页零 重试/撤销/批准/拒绝/回滚 控件。
- **裁决**：**只读铁律胜** —— 删除 `ErrorState` 的可选 `重试` 动作（当前无调用方）。
  这样任何状态组件都无法给只读页递出重试入口。审批页同样刻意不渲染 B10 演示里的
  「审批」动作列（只保留 请求/风险/状态）。

## D-15 · 品牌锁 vs 原 WorkView 的 amber 源缺口标记
- **冲突**：L10 的 `WorkView` 用 `text-amber-400/90` + amber 圆点表达「来源缺口」，
  与品牌锁（禁橙/金/米白）冲突。
- **裁决**：**品牌锁胜** —— 改为品牌 warning 色文本 + 青色（`--secondary`）指示点，
  B10 `.list-item` 结构不变；「来源缺口」文案与非伪造纪律逐字保留。

## D-16 · 浅色主题：重写 B10 皮肤为令牌间接化 vs 保持逐字复刻
- **冲突**：`b10.css` 逐字编码 B10 深色调色板（`.sidebar`/`.panel`/`.topbar`/`.table`/
  `.tag` 等使用字面色值，无 `var()` 间接），因此 `html.light` 下只有壳层背景翻转，
  B10 表面保持深色；若要真正浅色主题，必须把皮肤改为令牌间接化。
- **裁决**：**保持逐字复刻**（L10b 的核心交付就是 1:1），浅色主题记录为**已知边界**
  （`VISUAL_QA_REPORT.md` §10.1 与 `UI_REFERENCE_MANIFEST.md` §12.1），不静默修补。
  深色是品牌锁与主用主题；`html.light` + `colorScheme=light` 的既有契约测试继续通过。
  若后续需要完整浅色主题，应作为独立任务：以令牌重写皮肤并同步更新「逐字」声明。

