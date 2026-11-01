# DESIGN-LAB UI 商业级 Workbench — VISUAL_QA（视觉验收记录）
任务包：DESIGN-LAB_UI_FRONTEND_TASKPACK_20260930 · 分支 feat/ui-commercial-workbench-20260930

## 设计语言一致性（对照 B10 token 体系）

### 颜色（零新增 custom property，全部引用既有）
- 面板背景：`--surface-2`（#11182A）；边框：`--border`（#213D66）；
  文字：`--text`（#F5F7FC）/ `--muted`（#9AA3B8）；强调：`--accent`（#316CFF）；
  发光：`--glow`（0 0 14px rgba(49,108,255,.30)）。
- 状态 tag：.tag.ok（成功绿 #2FC58D）/ .tag.warn（#F4B942）/ .tag.bad
  （#F05252）/ .tag.info（#4BAFFF）—— 全部复用既有 B10 tag 规则。

### 动效
- 新组件 transition 仅 `border-color / background` @ `--motion-fast`（120ms），
  无位移/缩放/旋转；`prefers-reduced-motion: reduce` 时既有全局
  `*{transition:none!important}` 覆盖，动效完全停用。
- 版本环节点 hover 仅改 fill（--accent → --secondary），无动画。

### 密度与间距
- 阶段导航：padding 7px 14px，gap 6px，min-height 38px（单行可横滚，
  移动端 390px 宽度下 overflow-x:auto 不撑破布局）。
- Inspector：sticky top 16px，max-height calc(100vh - 32px) 内部滚动，
  不遮罩主区内容；768px 以下单列 + order:-1（Inspector 上移）。

### 可访问性
- 版本环 `role="img"` + `aria-label="方向版本环：N 个版本"`；节点 title
  提示 `vN（选定）· 已被取代`。
- 阶段导航 `aria-current="step"`（当前阶段）；PLANNED 节点 title 说明原因。
- Inspector 折叠按钮 `aria-expanded`；键盘可达（原生 button，无 role 伪装）。
- `prefers-contrast: more`：阶段导航/版本环/Inspector 描边 1px→2px。

## 假元素排查（铁律：不出现假按钮 / 假 KPI / 假可用）
- 宿主在线状态：全部 `UNKNOWN` 标注 + 说明「后端无路由，不假报可用」；
  无「连接 Illustrator」按钮。
- MCP 诊断：`BLOCKED` 能力卡，nextAction 明确「后端路由提供后 UI 接入」。
- 研究洞察 / 设计领域 / 协作：`PLANNED` 能力卡 + 未来接入点，无入口按钮。
- KPI：项目数 / 设计系统数 / 交付包数 / 服务状态全部真实读回；
  质量趋势 sparkline 显式标注「B10 演示序列 · 非业务指标」。
- 服务不可达时：活跃生产 / 待审 / 失败 显示「未读回」而非 0。

## 截图清单（本分支状态）
- IMPLEMENTED：2026-10-05 用 `scripts/capture_workbench_screenshots.py` 真实执行，
  5 视口（390×844 / 768×1024 / 1280×800 / 1920×1080 / 2560×1440）× 8 页面 =
  **40 张 PNG**，落在 `docs/UI-CONVERGENCE-20260930/screenshot/`，
  逐张 SHA-256 + 视口 + URL + 时间戳 + exact commit + bundle hash 记录在
  `screenshot/screenshot-manifest.json`，表格见 `SCREENSHOTS.md`。
- 浏览器：本机 Chromium 149.0.7827.55（`chromium-1228/chrome-win64/chrome.exe`，
  非 headless-shell），真实服务读回数据，无 mock。
- 证据等级：E1 结构 + E2 受控运行时。视觉验收（E4 人工）仍未执行，
  本文件不构成人工验收判定。
- 截图过程暴露并修复 2 个真实缺陷（KPI count-up 把 `0.1.0-alpha.0` 渲染成 `0.1`；
  count-up 中间帧被拍进证据），详见 `SCREENSHOTS.md`「本轮截图暴露并修复的真实缺陷」。

## 与 E2E 冻结面的关系
- `.app-nav-item` 数量 12、移动端布局测量（fontSize / navLeft / navWidth /
  navHeight / overflowX）、`#design-*` 选择器、build/main.js 契约 token
  （startTask / cancelTask / 不代表制作成功 等）：全部未触碰，E2E 回归不变。
