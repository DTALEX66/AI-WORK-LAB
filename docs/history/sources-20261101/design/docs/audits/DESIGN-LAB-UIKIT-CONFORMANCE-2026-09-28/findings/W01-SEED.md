# W01 起点 —— 视觉资产与 Token 基线

**状态：** 已开工（本轮完成盘点与来源验证，矩阵待建）
**观察 SHA：** `d116b14995fcdbba1b165ec5bc3124f5daed3d15`

---

## 1. 原稿来源定位（包内要求："读取仅 DESIGN-LAB 的原 UI 套件"）

`D:\All projects\UI套件` 是**按项目分卷**的，每个关键批次同时存在：

- **单项目包**：`ArcheAxis_*` / `DESIGN-LAB_*` / `WORK-LAB_*`
- **三项目全量包**：`三个项目_*_全量包.zip`

> ⚠️ **必须只用单项目包。** 全量包混入 ArcheAxis 与 WORK-LAB 素材，
> 用它做 DESIGN-LAB 1:1 会串色/串规范。包内对此的警告（"不拿 AAOS/WORK-LAB 素材替代"）**成立**。
> 另注：`03_B03_页面级UI与AAOS配色纠正_L3` 的 AAOS 是**另一个项目**，不是 DESIGN-LAB。

| 批次 | DESIGN-LAB 专属原稿 | 大小 |
|---|---|---|
| **B04** 组件系统与 DesignTokens | `04_B04_组件系统与DesignTokens_L4\DESIGN-LAB_L4_组件系统_16张+Tokens.zip` | 1545.9 KB |
| **B07** 前端开发规范 | `07_B07_前端开发规范_L7\DESIGN-LAB_L7_前端开发规范工程包.zip` | 10.5 KB |
| **B10** 最终版高保真可部署 UI | `10_B10_最终版高保真可部署UI\design-lab_最终版_高保真可部署UI.zip` | 11.4 KB |
| B01/B02/B03/B05/B06/B08/B09 | 同目录下 `DESIGN-LAB_*` / `design-lab_*` | — |
| 索引 | `00_索引与说明`（3 文件） | — |

**原稿全部是 ZIP 归档** → 需安全解包到 `.project-local/` 后才能读（本轮未解包 B04/B07）。

---

## 2. ✅ 来源完整性验证（本轮已完成的关键一步）

我上一轮的 B10 1:1 复刻，参考文件是本会话既有的提取件
`.project-local/b10-1to1-handoff/ui-suite-extract/B10/`。**必须确认它取自 DESIGN-LAB 专属原稿**，
否则整轮复刻可能做在别的项目的原稿上。

| 文件 | sha256 | bytes |
|---|---|---|
| `design-lab_最终版_高保真可部署UI.zip` 内 `index.html` | `bcecffe937febce4409c69c6d2db962d22762fd3cabc0079b30a16afe2c2e51b` | 40684 |
| 我上一轮所用 `.project-local/b10-1to1-handoff/ui-suite-extract/B10/index.html` | `bcecffe937febce4409c69c6d2db962d22762fd3cabc0079b30a16afe2c2e51b` | 40684 |
| 同目录 `extracted-style.css` | `d7354185c36d419aef9c3ffecbe9cdadf9b44714beb04bbc9e6ed5c8316fd4d0` | 20154 |

**结论：逐字节相同 → 上一轮 B10 1:1 复刻基于 DESIGN-LAB 专属原稿，来源正确。**
同时该 zip 只含 `README.md` + `index.html` + `打开页面_Windows.bat` 三件，
与既有提取件一致，无遗漏。

---

## 3. 待建：`原稿 → 页面 → 组件 → Token → 当前实现 → 差异` 矩阵

W01 的正式产出。来源两侧：
- **原稿侧**：上述 DESIGN-LAB 专属 zip（B04 Tokens/16 组件、B07 前端规范、B10 可部署 UI）
- **实现侧**：`apps/workbench/style.css`（已含 B10 CSS 块）、`packages/design-system`、`apps/workbench/shell.ts`

**必须分域**（包内要求）：
- **工作台 Token**（品牌）＝ `apps/workbench/style.css` 的 `:root`（`#060A14` / `#0D1221` / `#316CFF`）
- **项目 DesignSystem**（客户资产）＝ `packages/design-system` + 后端 design-system 记录
- **两者不得互相覆盖**

**缺失处理**（包内要求）：原件缺失标 `MISSING_SOURCE`；能用 SVG/CSS 精确重建的才重建并保留来源与差异；
**用户视觉验收前不声明 1:1 完成**。

---

**END — W01 起点。本轮未解包 B04/B07，未修改 tracked 文件。**
