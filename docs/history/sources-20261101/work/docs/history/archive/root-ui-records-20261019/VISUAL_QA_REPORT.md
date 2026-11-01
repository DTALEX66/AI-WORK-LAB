# WORK-LAB 前端 UI · Visual QA 报告（L10 / L10b）
<!-- ROOT-DISPOSITION:BEGIN NON-NORMATIVE-HISTORICAL -->
> **NON-NORMATIVE-HISTORICAL / 历史记录，不派工**（2026-10-10 登记，WUI-17）：本文件不在权威链里，正文逐字保留未改（门会把它与提交字节逐字节比对）。现行权威顺序：`WORK-LAB-AUTHORITY.md` → `.project/governance/project-authority-index.json` → `taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md` → `taskpacks/current/OPEN-TASK-REGISTER.md`（2026-10-19 更新；旧 UI 包已 SUPERSEDED_20261019 / FROZEN，不再是 CURRENT）；根目录逐份处置见 `docs/current/DOCUMENT-CENSUS.md` §4 与 `.project/governance/root-document-dispositions.json`。
<!-- ROOT-DISPOSITION:END -->

- L10b 分支：`p1/ui-l10-full-replica`（base `main` @ `f95baef`）
- 依据：9/27 任务书的 Visual QA 优先级 **结构 > 比例 > 布局 > 颜色 > 组件 > 字体 > 细节 > 光效 > 动效**
- 证据分级（诚实）：每层标注 VERIFIED（有真实回读）或 UNVERIFIED（缺证据，不宣称闭环）。
  **L10b 首次让「像素层」进入 VERIFIED** —— L10 当时的截图通道缺口已闭环。

---

## 1. 结构（VERIFIED）

- `vitest run` → **11 文件 / 72 测试全绿**（真实组件挂载 + 渲染文本断言，本地回读）。
- 12 页全部经 `viewRegistry` 可达；`Sidebar` 的 7 组 `NAV_GROUPS` 恰好覆盖全部 22 lane、
  无重复（P1-01 不变式）。
- 每页首元素为 B10 `.page-head`（逐字结构）；页内容器统一 B10 `.panel`。
- **DOM 逐字对齐 B10**：shell 为 `.app > (.ambient, .grid-bg, aside.sidebar, main.main >
  header.topbar + section.content)`；overlay 为 `.overlay#modal > .modal`、`.drawer`、
  `.palette`、`.toast`；页面为 `.kpi-grid` / `.two-col` / `.split` / `.toolbar` /
  `.table-wrap > .table` / `.list` / `.graph-stage` / `.canvas`。
- 核心页 Workflow Editor 为**交互式**画布：`l10-views.test.tsx` 断言添加节点/选择/
  删除 + 发布/运行 在契约接入前禁用（10 测试全绿）。
- Observer / Execution Detail / Audit / Approvals / WorkView 断言**零可执行写按钮**。

## 2. 比例 / 布局（VERIFIED）

- B10 网格：`.app{grid-template-columns:280px 1fr}`；`.topbar` 78px；`.search`
  `min(620px,54vw)`；`.content{padding:26px 28px 30px}`；`.kpi-grid` 4 列；
  `.two-col{1.2fr 1fr}`；`.split{1.35fr .95fr}`；`.metric-row` 4 列；`.canvas` 520px；
  `.graph-stage` 380px；`.table{min-width:720px}`；`.panel` 18px 圆角 / 18px 内边距。
  以上全部来自 b10.css（逐字），非本次新增。
- 响应式：B10 1160px（KPI 2 列、多列塌单列）+ 840px（隐藏 rail/`.top-actions`）
  由 `l10b-shell.css` 承接 rail 可见性（B10 自身 `.sidebar{display:flex}` 会覆盖其
  自带的 840px 隐藏规则）。
- compact：`?layout=compact` / `?view=compact` → 单列（`.app-compact`），无 rail。

## 3. 颜色（VERIFIED）

- 品牌锁：`#050D16` 深海军蓝 / `#07111C` sidebar / `#081420` surface / `#0C1B2A` surface2 /
  `#17435D` 边框 / `#EEF6FC` 文本 / `#8EABBC` 弱化 / `#2A91FF` 电光蓝 / `#20CDE1` 青色
  —— 全部由 b10.css 的 `:root` 逐字提供。
- 全 `src` 检索禁用色倾向（橙/金/米白主调/紫主调/暖科技）：零命中。原 `WorkView` 的
  `amber-400` 源缺口标记已改为品牌 warning 色 + 青色指示点。
- 玻璃效果未泛滥：仅 B10 规定的 `.topbar`/`.sidebar` `backdrop-filter:blur(18px)` 与
  `.overlay` 的 modal 模糊背板。

## 4. 组件（VERIFIED）

- B10 皮肤类成为唯一视觉来源：`.panel` `.kpi` `.table` `.tag` `.list-item`
  `.metric-box` `.status-stack` `.empty` `.mono` `.progress` `.spark` `.canvas`
  `.node` `.flow-svg` `.graph-stage` `.palette` `.overlay` `.modal` `.drawer` `.toast`
  `.primary-btn/.ghost-btn/.soft-btn/.danger-btn` `.toolbar/.seg/.input` —— 组件只提供
  结构与数据。
- Tailwind 仅承担布局 flex/grid/gap 与无障碍（focus ring、sr-only 由壳层提供）。
- cascade 已回读证明：构建单文件 CSS 中 Tailwind `.panel` 在 5,399 偏移、B10 `.app` 在
  20,303、B10 `.canvas` 30,506、L10b 壳层 38,410 ⇒ B10 胜 Tailwind，壳层胜两者。

## 5. 字体（VERIFIED）

- B10 字体栈 `Inter,"Segoe UI","PingFang SC","Microsoft YaHei","Noto Sans SC",system-ui`
  逐字；字号层级来自 b10.css：KPI `35px`、page-head `h2 32px`、panel `h3 15px`、
  `.tag` 12px/700、`.table` 13px、`.list-item small` muted、`.mono`
  `ui-monospace,SFMono-Regular,Menlo`。

## 6. 细节 / 光效 / 动效（VERIFIED，本轮含像素层）

- **像素层 VERIFIED**：17 张 1600×1050 headless 截图（Chromium 1228 headless-shell），
  经应用自身 `?api=` 权威描述符从本地 preview 读取 v3 形状快照，真实走
  fetch → 投影 → 组件渲染链路：

  | 截图 | 目检结论 |
  |---|---|
  | `shot-overview.png` | `.kpi-grid` 4 × `.panel.kpi`（1 / 1 / 170k / LIVE，主色 35px 数字）、`.two-col`（无趋势数据 UNKNOWN + `.metric-row` 4 格 + `.status-stack` 3 枚 `.tag`）、`.split`（`.list-item` 执行行 + `.graph-stage` 核心脉冲 + 6 个 `.node-dot` 带标签） |
  | `shot-observer.png` | `.split` + `.graph-stage` 径向拓扑（青色晕环、连接线、核心 pulse）+ `.metric-row`（LIVE / FRESH / 8/8 · lanes / 42）+ 只读 pill；页面零写按钮 |
  | `shot-workflows.png` | `.toolbar`（`.input` 搜索 + `.seg` 四档，active 渐变）+ `.panel > .table-wrap > .table`（6 列表头）+ `.empty`（64px 主色圆环图标） |
  | `shot-editor.png` | `.toolbar .seg` 8 个节点类型（色点）+ 缩放/适应/删除 ghost 按钮、`.canvas` 30px 网格 + 主色径向洗光、`.node` 150px 圆角块（`触发器/校验/Hermes Agent/审批门/产出` + `.meta`）、`.flow-svg` 虚线边、右侧属性面板 + 嵌套部署说明 panel、底部 运行/保存并发布 呈禁用态 |
  | `shot-execution-detail.png` | `.split` 左列表（`.list-item` + `.tag.ok/info`）+ 右详情 `.list-item` 行 + 嵌套只读说明 panel |
  | `shot-approvals.png` | `.table` 请求/风险/状态三列（`APPR-1` + `UNKNOWN` 风险 + `pending` warn 标签）；**无审批动作列** |
  | `shot-audit.png` | `.seg` 四档筛选 + `.table` 五列（`work-lab-gate @ … · run …` / `EX-1 · hermes`）+ `.mono` 来源引用块 |
  | `shot-task-packs.png` | `.metric-row`（rules 3 / memory 1 / skills 2 大数字）+ `.table` 计划明细（`TASK-1`） |
  | `shot-rules-policy.png` | `.list-item` 四家族 + `.tag.ok 干净` / `.tag.warn 漂移`（技能=2）/ `.tag.info` 携带真实明细 |
  | `shot-integrations.png` | `.list-item` 适配器族（`.tag.ok CLEAN`）+ 7 行客户端（`受控（无实时状态投影）`） |
  | `shot-software.png` | 嵌套 `.panel` + `.list-item` 身份行 + `.tag.ok 单一·已验证` |
  | `shot-memory.png` `shot-work.png` `shot-settings.png` | 其余 lane 的真实投影渲染正常 |
  | `shot-compact.png` | compact HUD：B10 `.topbar` + 4 × `.panel.kpi` + 真值行；无 rail |
  | `shot-light.png` | `?theme=light` 下壳层背景翻转；B10 表面保持 B10 深色（见 §9 边界） |

- 动画（`floatGlow` / `dashMove` / `pulse` / `scanSweep`）在构建产物中存在且由
  `prefers-reduced-motion` 停机块覆盖（b10.css 尾部）。
- L10 当时的「像素 UNVERIFIED」缺口已由本轮截图闭环。

## 7. 无鉴权 UI 复核（VERIFIED）

- 全 `src/**/*.tsx` 检索
  `password|passwd|api[-_ ]?key|access[-_ ]?token|Bearer|Authorization|登录|令牌|密码|鉴权`
  → **2 处命中，全部是「声明不存在」的说明文案**（`App.tsx` 工作区抽屉、`Views.tsx`
  设置页描述）。
- 无锁屏、无令牌输入、无凭证弹窗、无审批理由输入、无 OAuth 门。约束「本地个人研究、
  禁止加锁/访问令牌」**满足**。

## 8. 只读铁律复核（VERIFIED）

- `grep '批准|拒绝|撤销|重试|回滚|重放'` over `src/**/*.tsx` → 全部命中均为说明性文案、
  测试断言或审批/审计页的只读声明；无任何只读页渲染对应按钮。
- `ErrorState` 的可选 `重试` 动作**已删除**，从结构上保证状态组件不能给只读页递出重试入口。
- 字节级检查：`WorkView` 渲染结果不含 `<button>` / `<input>` / `<textarea>`（测试断言）。

## 9. 构建回读（VERIFIED，本地）

- `tsc -p tsconfig.json --noEmit` → 干净（exit 0）。
- `vitest run` → 11 files / **72 tests passed**。
- `vite build` → 绿；`dist/assets/index-*.css 39.31 kB (gzip 8.83)`、
  `index-*.js 267.72 kB (gzip 82.46)`。
- 验证 harness：`.project-local/runs/ui-suite/l10b-verify/verify.mjs`（tsc → vitest →
  build，输出写入 UTF-8 日志；原因是 PowerShell→Python 包装器用 GBK 解码子进程 stderr，
  遇到 CJK UI 输出会抛 `UnicodeDecodeError`）。
- 根因修复记录（L10 期）：`index.css` 注释内 `--glow-*/--grid-line` 的 `*/` 提前闭合
  注释致 postcss 崩溃 → 注释措辞修正。L10b 新增的 `l10b-shell.css` 已复查无同类问题
  （b10.css 亦已在 L10b 校验为干净）。

## 10. 结论

- 结构 / 比例 / 布局 / 颜色 / 组件 / 字体 / 细节 / 光效 / 动效 / 无鉴权 / 只读 —— **全部 VERIFIED**
  （代码 + 测试 + 构建产物 cascade 回读 + 17 张像素截图）。
- **已知边界（诚实，不宣称闭环）**：
  1. **浅色主题为部分实现**：`b10.css` 逐字编码 B10 深色调色板（无令牌间接化），故
     `html.light` 下壳层背景翻转而 B10 表面保持深色。修复需重写皮肤 ⇒ 不再是逐字复刻，
     故记录而不静默修补。深色为品牌锁与主用主题。
  2. `.graph-stage` 卫星标签锚点相对 B10 演示偏移约 4px（真实容器尺寸下 B10 的圆心
     锚点会压住节点）；B10 结构/样式不变，仅标签位置换取真实实体名可读。
  3. 像素 QA 走 loopback preview + v3 形状快照，证明渲染路径与结构/样式，不等于生产
     sidecar 实时回读（实时链路由 sidecar 自身 gate 与 lane 测试覆盖）。
- 本地绿 ≠ CI 绿：exact-SHA 结论以 GitHub Actions 在该 SHA 的 terminal-success 为准
  （交付后回填，ERR-089 纪律）。
