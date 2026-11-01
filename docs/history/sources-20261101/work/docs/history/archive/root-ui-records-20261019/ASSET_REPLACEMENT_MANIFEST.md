# ASSET_REPLACEMENT_MANIFEST — WORK-LAB L10 / L10b UI 落地
<!-- ROOT-DISPOSITION:BEGIN NON-NORMATIVE-HISTORICAL -->
> **NON-NORMATIVE-HISTORICAL / 历史记录，不派工**（2026-10-10 登记，WUI-17）：本文件不在权威链里，正文逐字保留未改（门会把它与提交字节逐字节比对）。现行权威顺序：`WORK-LAB-AUTHORITY.md` → `.project/governance/project-authority-index.json` → `taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md` → `taskpacks/current/OPEN-TASK-REGISTER.md`（2026-10-19 更新；旧 UI 包已 SUPERSEDED_20261019 / FROZEN，不再是 CURRENT）；根目录逐份处置见 `docs/current/DOCUMENT-CENSUS.md` §4 与 `.project/governance/root-document-dispositions.json`。
<!-- ROOT-DISPOSITION:END -->

> 执行原则：所有参考资产先做「可否直接使用」判定；能直接用 ⇒ 直接复刻（CSS/组件），
> 不能直接进运行时 ⇒ 1:1 重生成并登记。本清单记录全部判定。
>
> **L10b 追加结论（2026-09-27）**：B10 的「视觉」现在以 **逐字皮肤层**
> `apps/observer/frontend/src/skins/b10.css`（B10 单一文件 `<style>` 块 533 行的
> 逐字拷贝，43,685 字节源文件 L1–530）落地；不需要、也没有新增任何位图资产。

## 判定总则（参考图 B01–B10 vs 运行时资产边界）

- 参考 zip 内的 1920×1080 页面图 / VI 图 = **审计对照源**（`.project-local/runs/ui-suite/`，
  gitignored），**不**作为运行时位图进 `src/`（避免 230MB 参考资产进仓库、避免低分辨率
  被拉伸、避免与品牌 token 双份真值）。
- 运行时视觉全部由 B10 逐字 CSS（`skins/b10.css`）+ 少量壳层规则 + 组件结构生成
  （可无限分辨率、可 CI 断言、可与 B10 单一文件逐类比对）——这比位图更强。

## 逐项判定

| 原参考 | 判定 | 原因 | 运行时位置 | 差异说明 |
|---|---|---|---|---|
| B02 `VI/03_03_主标志_Primary_Logo.png`（WL 几何构造） | **不直接嵌入**；1:1 以 B10 `brand-mark` 形态实现 | B10 最终版已把 Logo 定为 48px 渐变圆角方 + `WL` 900 字标 + 主色投影；位图 Logo 无法随主题翻转、无法走 token 体系 | `Sidebar.tsx` → `.brand > .brand-mark`（B10 同款 radial+linear 渐变与 `0 10px 30px primary/38%` 投影，由 b10.css 提供） | 零差异：品牌色/几何/字重与 B10 一致；比位图多了主题自适配 |
| B10 `.grid-bg` 32px 网格 + `.ambient` 三团光 | **直接复刻**（纯 CSS，无需位图） | B10 本身即用 CSS 实现（`.ambient` + `::before`/`::after`），无位图资产 | `App.tsx` → `<div class="ambient">` + `<div class="grid-bg">`；样式在 `skins/b10.css`（逐字） | 零差异；blur 80px / opacity .45 / floatGlow 12s / 32px 网格 / radial mask 全部照抄 |
| B10 `.node` / `.flow-svg path` / `.core` pulse / `.scan-line` 光效 | **直接复刻**（B10 类 + 组件） | 光效 = 系统状态语言，B10 参数固定 | `workflow-canvas.tsx`（`.canvas`/`.flow-svg`/`.node`）、`node-graph.tsx`（`.graph-stage`/`.core`/`.node-dot`）；样式在 `skins/b10.css` | 零差异（drop-shadow / dasharray / 关键帧时长照抄）；旧 L10 的 `--glow-*` token 版本已被 B10 类取代 |
| B10 `.panel` / `.kpi` / `.table` / `.tag` / `.list-item` / `.metric-*` / `.empty` / `.mono` / `.palette` / `.overlay` / `.drawer` / `.toast` 皮肤 | **直接复刻（逐字）** | B10 可部署 UI 的样式即为最终权威 | `apps/observer/frontend/src/skins/b10.css`（533 行逐字）+ `main.tsx` 加载顺序 | 零差异：本文件不新增、不改写任何 B10 声明 |
| B10 响应式断点（1160px / 840px） | **直接复刻 + 壳层补齐** | B10 的 `@media(max-width:840px){.sidebar{display:none}}` 会被自身未分层的 `.sidebar{display:flex}` 覆盖，需壳层承接 | `src/skins/l10b-shell.css`（`@media(min-width:841px)` / `max-width:840px`） | 意图一致；实现位置不同（已在 `UI_REFERENCE_MANIFEST.md` §11 逐条登记） |
| B05 12 张 / B03 10 张页面级 1920×1080 PNG | **不进运行时**；作为 Visual QA 对照图 | 页面在真实 React 组件中渲染，比静态 PNG 保真且可交互；PNG 仅用于逐页比对（结构>比例>布局>颜色>组件>字体>细节>光效>动效） | `VISUAL_QA_REPORT.md` 逐页记录 + 17 张 headless 截图 | 运行时 = 组件化真实现，非截图贴皮 |
| B01 品牌应用/壁纸（`VI/18_18_品牌应用_UI纹理与壁纸.png`） | **不生成位图壁纸**；纹理由 `.grid-bg` + `.ambient` 承担 | B10 最终版未使用位图壁纸；用位图会引入不可主题翻转的第二视觉真值 | 同上 | 与 B10 一致（B10 无壁纸层） |
| 图标 | **不重生成**；用 `lucide-react`（已有依赖）线性图标 | B02 图标系统两组为品牌图示；UI 功能图标按 B07 契约用既有图标库保持线性/密度一致 | 各 view 现有 `lucide-react` 用法 | 功能图标 1:1；品牌图形（Logo/网格）走 CSS |
| 页面 hero/星球/控制平面视觉 | **不存在于 B10 参考**；不生成 | B10 视觉语言 = 深海军蓝控制台 + 微弱蓝色环境光 + 网格，无 hero 位图；自生成会违反「禁止重新设计」 | 无 | 无差异（参考里就没有） |

## 生成资产目录（全部轮次实际生成）

- **位图资产：无**（`src/assets/generated/` 未创建）。B10 可部署 UI 的全部视觉均由
  逐字 CSS + 组件结构实现，直接复刻即达 1:1，且优于位图（可测试 / 可无限分辨率 /
  与 B10 单一文件逐类可比对）。
- **新增样式文件（非位图）**：`src/skins/l10b-shell.css` —— 仅断点/角落锚定/可见性辅助，
  不含任何 B10 视觉声明（逐条理由见 `UI_REFERENCE_MANIFEST.md` §11）。
- 若后续授权接入真实 workflow schema 后端并需要节点类型位图，再按本清单流程生成并补登。

## 视觉 QA 证据资产（本地，gitignored）

- `.project-local/runs/ui-suite/l10b-verify/shot-*.png` —— 17 张 1600×1050 headless 截图，
  覆盖 12 页 + compact + light；由 `chrome-headless-shell`（Playwright 捆绑 Chromium 1228）
  对 `dist/` 的 loopback preview 拍摄，数据经应用自身的 `?api=` 权威描述符读取。
- 这些文件是**本地证据**，不进仓库（`.project-local/` 已 gitignored）。
