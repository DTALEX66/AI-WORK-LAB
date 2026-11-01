# W02 —— `.app` 与 pre-B10 遗留 CSS 的耦合审计（本轮）

**观察基线：** `main` = `553b0ca444d11a0c5a78df6b6b1dfe187bdac786`（PR #182 已合并）
**本轮修复：** PR #183 `3b0821f3dc808ce0df64b536204497559e21b0c5`
**证据：** `W02-LEAK-SWEEP.txt`（本次运行的完整输出）
**harness：** `.project-local/task-artifacts/external-recovery-2026-09-27/w02-legacy-leak-sweep.mjs`

---

## 1. 问题

B10 套件**全部按 class 定样式**（元素级只声明 `button,input,textarea,select{font:inherit}`、
`button{cursor:pointer}`、`a{...}`）。而 `apps/workbench/style.css` 顶部仍留有**早期单页版**
的元素级规则（`h2`、`label`、`input,select`、`button`、`button:disabled`、
`input:focus,select:focus,button:focus-visible`、`form`、`form label`）。

由于 class 规则(0,1,0) 永远高于裸元素规则(0,0,1)，这些遗留规则**不可能覆盖** B10 的外观，
但会**悄悄为 B10 未声明的属性兜底**。本会话此前已经因此修过 3 次
（1240px 正文宽度上限 / ghost 按钮 hover 变蓝 / 段落 13px）。本轮把它**系统性测量**掉。

## 2. 方法：删除即测量（不做特异性推理）

对全部 computed longhand（`getComputedStyle` 自身的索引表，不手写属性清单）：

1. 标记 `#route-view` 内所有 `h1..h4,p,label,input,select,textarea,button,a,ul,li`；
2. 快照；
3. 通过 CSSOM **删除**所有"纯元素选择器"规则；
4. 跨任务读取快照；
5. 逐属性 diff —— 任何变化的属性，就是在由遗留规则提供。

覆盖：**12 条路由 + 默认（空 hash）视图 + 登录/连接屏**，`.app` 内 328 个元素。

## 3. 结果

| 范围 | 修复前 | 修复后 |
|---|---|---|
| **`.app` 内**（B10 shell，1:1 主体） | **8** 处绑定 | **0** |
| `.app` 外（遗留 chrome） | 1923 处绑定 | 1923（不变） |

**8 处的具体身份：** `#/research` 与 `#/collaboration` 的占位标题
`h2<div.route-view`，其 `margin-top:0 / margin-bottom:14px` 来自遗留
`h2{margin:0 0 14px}`；删掉遗留规则后回落到 UA 默认 `19.92px`。
（`font-size` 没有泄漏，因为 `.route-view h2{font-size:24px}` 已经声明了它。）

**修复：** 在 `.route-view h2` 上补声明 `margin:0 0 14px` ——
取值**就是**修复前的实测值，所以浏览器绘制结果不变。这是**解除隐式依赖**，不是改版。

**刻意没做的事：** `.route-view h2` 的 24px 与 B10 自己的页面标题
`.page-head h2{font-size:32px;margin:0 0 6px}` 不一致。这属于 W01 字体尺度问题，
且牵涉 owner 未决的 **X-1 / X-2**，本轮**不擅自"顺手修好"**。

## 4. 边界结论（重要，影响后续 W03/W14）

`.app` 外的 **1923** 处绑定不是本 shell 的缺陷：**登录/连接屏、`#workspace`、
`nav.app-nav` 是遗留应用，B10 并不治理它们**（`login.hidden = showWorkbench ? connected : true`，
空 hash + 未连接时才显示）。

因此——

> **之前"把遗留元素规则统一 scope 到 `body > …`"的方案是错的**，
> 那会直接打断登录屏与 `#workspace`。后续若要退役遗留 chrome，必须先迁移这些表单，
> 再动元素级规则；不能先动规则。

## 5. harness 自身的 3 个错误（已记录，均曾产生假结论）

| # | 错误 | 后果 | 修法 |
|---|---|---|---|
| 1 | `.app-nav-item` 是 `<button data-route>`，不是 `<a href>` | `href` 全为 `null` → URL 变成 `?dev=1null` → dev 模式从未生效，**一直在扫登录屏** | 读 `data-route`；发现不足 12 条或非法则**直接中止** |
| 2 | 只有 hash 不同的 `goto` 是**同文档导航**，不重新加载 | 路由之间互相污染，且扫的是半挂载状态 | 每条路由加唯一 query 强制真实加载 |
| 3 | **同任务内** `getComputedStyle` 读到的是**变更前**的值 | 实测：规则数 10→8 且规则确已删除，但 before/after 逐字节相同 → **会漏报泄漏** | prepare 与 read 拆成两个任务 |

因为上述 3 条都曾给出过假结果，本 harness 现在自带**端到端正对照**：
注入 `button{word-spacing:9px !important;...}`，必须 (a) 插入后跨任务读到生效、
(b) 被过滤器收集、(c) 表里确实消失、(d) 被 diff 报出——四条全过才认为检测器可信。
本轮 **CONTROL PASS**。

## 6. 本轮另一个已知冲突（未处理）

`.route-view h2` 用 24px 已是**既存的**非 B10 值；B10 原稿为 32px。
与本文件 §3 同属 X-1/X-2 待裁决，不重复开单。
