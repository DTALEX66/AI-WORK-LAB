## 背景

W01 把 **DESIGN-LAB 专属原稿**（B04 `design_tokens.json` + B07 `shared-ui-core/base-tokens.css`）与 `apps/workbench/style.css` 逐族比对，结果是：

| 族 | 原稿 | 实现承载 |
|---|---|---|
| color | 12 | **12** ✅ |
| radius (md/lg) | 2 | **2** ✅ |
| motion | 4 | **4** ✅ |
| **space** | 8 | **0** ❌ |
| **font** | 6 | **0** ❌ |
| **breakpoint** | 3 | **0** ❌ |
| **density**(B04) | 3 | **0** ❌ |
| **radius.xl**(B04) | 1 | **0** ❌ |

即：**颜色与动效 100% 对齐；间距、字号、断点、密度四族完全没落到变量层**——当前布局用的是 B10 硬编码值（`padding:26px 28px 30px`、`gap:16px`…），**绕过了原稿定义的 Token 体系**。

## 本 PR

按原稿**精确值**补齐缺失族为变量（8 space / 6 font / 3 breakpoint / 3 density / 1 radius.xl）。

## **刻意不裁决**原稿之间的矛盾

原稿之间存在互相矛盾，**留给你决定**，只在代码块注释中记录：

| # | 冲突 | B04 | B07 |
|---|---|---|---|
| **X-1** | 正文字号 | `body=18` | `--font-body=16px` |
| **X-2** | caption | `caption=14` | `--font-caption=13px` |
| **X-3/X-4** | 移动断点 | — | `767px`（实现 760px、B10 840px，**同仓三套**） |
| **X-7** | `--radius-sm` | `sm=4` | **已被 B10 桥接块定义为 `12px`** |

X-1/X-2 暂取 **B07（前端治理层）** 值；因当前无任何规则消费这些变量，**取哪一侧都不产生视觉差异**。
X-7 **不重定义** `--radius-sm`（会破坏 B10 层），保持现状。

## 性质与验证

**纯新增**：无任何规则消费这些变量 → 视觉与行为**零变化**。

| 门 | 结果 |
|---|---|
| `tsc --noEmit` | exit 0 |
| `vite build` | exit 0 |
| `tests/unit.mjs` | all checks passed |
| `tests/appshell.mjs` | all checks passed |
| `apps/workbench/build` | 无漂移（build 不依赖 CSS） |

## 未做（明确边界）

- **不**把变量应用到元素上（那会触发 X-1…X-7 的裁决）
- **不**改 `--radius-sm`
- **不**触碰 `ROUTES`（下一 PR 的范围）
