## 背景

W02 对 B07 **46 组件契约**的覆盖分析发现：B07 发布了 **7 个工具类**，实现 **0/7**。

`.responsive-grid` · `.desktop-only` · `.ui-motion-fast` · `.ui-motion-base` · `.ui-motion-slow` · `.focus-ring` · `.pressable`

`.responsive-grid` 还是 **B07 自己的 PageTemplate 示例**用来排页面的类 —— 所以这是闭合一份**已发布的契约**，不是猜测。

## **刻意不照搬**的两项

| 项 | 为什么不抄 |
|---|---|
| B07 `breakpoints.css` 里的 `.sidebar{display:none}`（≤767px） | 实现已有 760px（`.app-nav`）、B10 又有 840px（`.sidebar`）。再加就是**同仓第四套移动断点**，会把 X-3/X-4 冲突**固化进代码**；断点统一属 owner 裁决 |
| `component-contracts.md` 的 "Pressed: scale(0.99), **80ms**" | B07 自己的 `motion.css` **只写** `.pressable:active{transform:scale(.99)}`，**从未表达 80ms**。按 CSS 原稿实现，**不自行发明时长**（记为 X-8） |

## 记录原稿缺陷（不隐藏）

B07 **只**在三个媒体查询里给 `.responsive-grid` 一个 `grid-template-columns`，**从未声明 `display:grid`** → **发布的这个类无法独立工作**。本 PR 补上让它能生效的最小基类 `display:grid; gap:var(--space-4)`（16px 与实现既有的 `.kpi-grid/.two-col/.three-col` 一致）。

## 真实 Chromium computed-style 验证（1600 / 1000 / 600 px）

| 类 | 结果 |
|---|---|
| `.responsive-grid` | `display:grid`，gap 16px，**12 / 2 / 1 列**（严格对应 B07 的 ≥1200 / 768–1199 / ≤767） |
| `.desktop-only` | 600px `display:none`；1000/1600 可见 |
| `.focus-ring` | **真的匹配 `:focus-visible`**；`outline 2px solid`，`offset 2px` |
| `.pressable` | **真的匹配 `:active`**；`matrix(0.99,0,0,0.99,0,0)` = `scale(.99)` |
| `.ui-motion-fast` / `-slow` | `0.12s` / `0.28s` |
| CSP | 四条视图 **0 违规** |

**15/15 检查 PASS。**

> **诚实记录一个我自己的坑**：伪类**不能靠 grep 或读未按下元素的 computed style**。第一版 harness 因此报了 **3 个假 FAIL**（未聚焦元素合法地报 `outline "3px none"`，未按下报 `transform "none"`）。现已真实聚焦+按下。**若当初反着写，就会得到一个假 PASS。**

## 同一批原稿的其它发现（本 PR 未处理，需 owner 裁决）

| 契约 | B07 | 实现 |
|---|---|---|
| Hover | **120ms** | 200ms |
| Focus ring | **2px** | 3px |
| Modal | **220ms** | 未表达 |
| Toast | **4s** | 1900ms |
| **`folder-structure.md` 推荐栈** | React + React Router + Zustand + TanStack Query + Radix + Tailwind | **与 AUTHORITY §3 及任务包"继承 Vanilla TS/Vite"直接冲突 → 按 Authority 优先，列为 `REFERENCE_ONLY`，不采纳** |

## 本地门禁

`tsc --noEmit` / `vite build` / `tests/unit.mjs` / `tests/appshell.mjs` 全绿；`apps/workbench/build` 无漂移（bundle 不依赖 CSS）。
