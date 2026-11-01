# DESIGN-LAB 资产替换清单（ASSET_REPLACEMENT_MANIFEST）

日期：2026-09-27

## 结论：无缺失外部资产

B10 最终版视觉系统使用 **CSS 图形语言**（渐变 / ring / frame / grid）替代外部图片占位，
与 B02 VI 图形语言规范一致。无需下载或生成任何 1:1 图片资产。

## 已自生成资产（CSS/SVG 层，已内嵌 style.css + shell.ts）

| 资产 | 形式 | 位置 | 参考来源 |
|---|---|---|---|
| 品牌模块环（ring） | CSS `border-radius:50%` + glow | `style.css` `.brand-module-ring` | B05 品牌系统高保真图 |
| 品牌模块框（frame） | CSS 圆角矩形 + glow | `style.css` `.brand-module-frame` | B05 品牌系统高保真图 |
| 质量趋势折线（sparkline） | SVG `<polyline>` + 渐变 + drop-shadow | `shell.ts` `sparkSvg()` | B10 sparkline |
| Logo 标记（DL） | CSS 渐变方块 + 光晕 | `style.css` `.mark` / B10 `.brand-mark` | B02 VI 主标志 |
| 扫光效果（sweep） | CSS `@keyframes` + 渐变 | `style.css` `.scan-line::after` | B10 预检动画 |

## 未使用的外部参考图（保留在 UI 套件 ZIP，不入仓）

- B01/B02/B03 基础/细节/页面级图（39+ 张）
- B05 12 张高保真页 PNG
- B04 16 张组件 PNG
- B06 18 张交互状态 PNG

这些是 **视觉参考源**，不是需要 1:1 替换进仓的资产。
DESIGN-LAB 产品 UI 不展示参考图，而是 **实现** 它们描述的视觉。
