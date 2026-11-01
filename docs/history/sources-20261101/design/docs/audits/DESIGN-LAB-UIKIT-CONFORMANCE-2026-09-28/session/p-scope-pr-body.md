## 同一根因的**第二次泄漏**

legacy 规则 `p{line-height:1.65;color:var(--muted);font-size:13px}` **从未作用域化**。而 **B10 根本没有 p 规则**（只有 `.page-head p` 与 `.muted`）→ `.app` 内的段落本应回落到浏览器默认，实际被压成 **13px 而非 16px**。

## 在同一浏览器里与 **B10 原稿**对照实测

探针同时加载 **DESIGN-LAB 专属 B10 原稿**与 workbench，逐元素 diff computed style（14 元素 × 5 属性）。**修复前 6 项不同**：

| 元素 | 属性 | B10 | 修复前 |
|---|---|---|---|
| `.page-head p` | font-size | 16px | **13px** |
| `.page-head p` | line-height | 24.8px | **20.15px** |
| `.muted` | font-size | 16px | **13px** |
| `.muted` | line-height | normal | **21.45px** |
| `.muted` | margin-top | 0px | **13px** |
| `.muted` | margin-bottom | 0px | **13px** |

**修复后**：所有可比的 font-size / line-height / color 全部一致 —— `.page-head h2` 32px、`.panel h3` 15px、`.kpi strong` 35px、`.tag` 12px、`.brand h1` 17px、`.nav` 16px、`.search` 16px、`.ghost-btn` 16px。

**剩余 2 项是探针伪差异，不是缺陷**：B10 侧 `.muted` 首个匹配是 `<div>`，实现侧是 `<p>`（dev 模式的离线提示），**不同元素的默认 margin 不可比**。已在探针里加了 tag 输出以证实这一点。

## 根因修，不是打补丁

与先前修的 `header/main/footer` 与 `button:hover` **同一根因**：pre-B10 的**元素选择器**伸进 `.app`。现限定到 `body > header p`、`body > main p`、`body > footer p`。**未改任何 B10 声明，未新造 class。**

## 本地门禁

`tsc --noEmit` / `vite build` / `tests/unit.mjs` / `tests/appshell.mjs` 全绿；`apps/workbench/build` 无漂移；CSS 括号 281/281。

## 这已是同一根因的第 3 处

`header/main/footer`（结构）→ `button:hover`（hover 变蓝）→ `p`（字号缩小）。三处都是「pre-B10 元素选择器伸进 `.app`」。**剩余同类候选**：`button`（基础 padding/背景，已被 class 覆盖）、`input,select`、`label`、`form`、`h2`（已被 `.page-head h2` 覆盖）。已逐一核对，目前未发现第 4 处可见偏离。
