# WORK-LAB 品牌资产（2026-10-25 起为 WORK 标志）

真源是 owner  supplied 的两份 Illustrator 矢量导出，已按原件归档在
`docs/history/owner-inputs/20261025/`：

| 原件 | SHA-256 | 内容 |
|---|---|---|
| `WORK-1.svg` | `f6cdb7f9b277ae57ec98248deebbe4c517d637592c30a9ce130e86570dc04f17` | 竖排：符号在上，`WORK-LAB / 工作流实验室` 在下（viewBox 305.22×305.02） |
| `WORK-2.svg` | `59ccd3899ec5b414e4aa88b00d33863e4d6bef129424d70d1e60168cc2dad92d` | 横排：符号在左，字标在右（viewBox 528×141.5） |

墨色 `#231815`（原件自带）。反白面 `#F4F1EC`。

## 实测几何

符号墨盒 = 272.79 × 143.82 viewBox 单位，比例 **1.8968**；同一符号在横排里的墨盒比例 1.8969——两个独立
切法给出同一个数，说明切点落在设计者留的位置上。界面两个槽位因此无需改尺寸：顶栏 42×22（1.9091）、
导轨 91×48（1.8958），都在 `tests/ci/test_brand_mark_is_the_real_logo.py` 的容差内。

## 重建

```
python scripts/brand/build_work_brand.py            # 重画全部 28 件资产
python scripts/brand/build_work_brand.py --check    # 只比对，不写；漂移即 exit 1
```

脚本不重绘任何曲线：它把原件按墨盒切出符号／字标／整排（`getBBox()` 经 `getCTM()` 换算到 viewBox 单位），
每个尺寸都从矢量按自身像素重新栅格化（项目 venv 没有图像库，也不为一个 LOGO 装 Pillow），
再按原件已用的容器格式重写 `icon.ico`（6 张 PNG 条目）与 `icon.icns`（6 条 PNG 条目）。
缺浏览器时打印 `BRAND_BUILD_NOT_RUN BROWSER_NOT_FOUND` 并 exit 3，不会静默产出旧图。

## 出货清单

| 路径 | 用途 |
|---|---|
| `work-lab-mark.png` | 顶栏与导轨的 mask 源（只有 alpha 起作用，颜色由主题 token 决定） |
| `work-lab-mark.svg` / `work-lab-wordmark.svg` / `work-lab-lockup.svg` / `work-lab-stacked.svg` | 矢量切法，重建与文档用的真源 |
| `work-lab-wordmark.png` / `work-lab-lockup.png` | 文档与展示用位图 |
| `work-lab-observer-symbol.svg` / `app-icon-512.png` | 应用图标（墨面 + 反白符号） |
| `work-lab-observer-tray.svg` | 托盘图标（浅色面 + 墨色符号，深色任务栏上仍可读） |
| `apps/observer/src-tauri/icons/*` | 窗口／安装包图标：`brand.svg`、15 个 PNG、`icon.ico`、`icon.icns` |

## 两处我替你做的决定（要改就一条命令）

1. **应用图标用反白**：原件是深墨色，直接放在透明底上，在深色任务栏／开始菜单里会看不见。所以图标是
   `#231815` 圆角面 + `#F4F1EC` 反白符号；托盘反过来（浅面 + 墨符号）。想换成"墨色符号放在浅色面"或
   完全透明底，改 `scripts/brand/build_work_brand.py` 里 `tile_svg(...)` 的 `field/glyph` 参数再重建即可。
2. **界面里只放符号，不放整排**：顶栏已经在符号右边打了 `WORK-LAB` 文字（`TopStatusBar.tsx` 的
   `.topbar-brand-word`），再放带字的横排就会出现两次品牌名。所以 mask 用的是切掉文字的符号。
