## 一个**真实的 1:1 视觉偏离**（Chromium 实测确认）

legacy 规则 `button:hover{background:var(--accent-hover);box-shadow:var(--glow)}` **早于 B10 外壳且从未作用域化**。B10 的 `.ghost-btn:hover` **刻意只改** transform / border-color / box-shadow，**不重新声明 background** —— 于是 legacy 规则赢下了背景：

**每个 ghost 按钮 hover 时都会变成实心 accent 蓝**，而不是保持 B10 的浅色调。

修复前实测（真实 Chromium，顶栏「通知」与 dashboard「导出周报」）：

| 状态 | background |
|---|---|
| rest | `color(srgb 0.0667 0.0941 0.1647 / 0.62)`（B10 色调） |
| **hover** | **`rgb(37, 88, 219)`**（legacy `#2558DB`） |

影响面正是 **1:1 复刻被检验的那个界面**：顶栏「通知 / 工作区」+ 路由态 B10 外壳里的每一个 ghost 动作按钮。

## 根因修，不是打补丁

与先前修的 `header/main/footer` 泄漏**同一根因**：pre-B10 的**元素选择器**规则伸进了 `.app`。现把该规则作用域限定到 legacy 区域 —— `body > header`、`body > main`、`body > footer` 以及扁平 `.app-nav` —— 于是 `.app` 内没有任何元素继承它。

**未改动任何 B10 声明，未新造 class。**

## 真实 Chromium 验证

| | 修复前 | 修复后 |
|---|---|---|
| `.ghost-btn` hover background | `rgb(37,88,219)` | `color(srgb 0.0667 0.0941 0.1647 / 0.62)` |
| hover transform | `matrix(1,0,0,1,0,-1)` | **不变**（交互反馈保留） |
| hover box-shadow | B10 `rgba(0,0,0,.15) 0 8px 28px` | **不变** |

## 回归检查 3/3 PASS

- **legacy 页面**（`/workbench`，无 dev 旁路，登录门）**仍然**得到 `rgb(37,88,219)` + glow → **legacy 行为逐字节不变**
- B10 ghost 按钮不再拿到 accent 色
- B10 ghost 按钮 hover 背景仍为**有色**（非透明）

## 本地门禁

`tsc --noEmit` / `vite build` / `tests/unit.mjs` / `tests/appshell.mjs` 全绿；`apps/workbench/build` 无漂移（bundle 不依赖 CSS）；CSS 括号平衡 281/281。

## 附：本轮的一次自我纠错

我最初的脚本报"`disabled` 状态 0/17、`focus` 仅 1/17"，**是误报** —— `button:disabled`（L154）与 `input:focus`（L140）是**元素级全局规则**，我的类级检查没看到它们。修正检查后才看清：真正缺的是 **hover 背景的正确性**，而不是状态缺失。**这直接引出了本 PR 的真缺陷。**
