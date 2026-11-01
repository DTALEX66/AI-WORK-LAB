# DESIGN-LAB UI 商业级 Workbench — COMPLETION_REPORT
任务包：DESIGN-LAB_UI_FRONTEND_TASKPACK_20260930
分支：feat/ui-commercial-workbench-20260930（基线 main @ 1acbfa1，LIVE 读回）
范围裁决：前端商业级能力 + 闭环验证（实现 + 单测 + 构建 + E2E 静态门）。
宿主自动化任务不执行（用户裁决："闭环，但不操作和自动化任务，确保底层能力打好"）。

## 完成项

### 1. 兼容性矩阵（改码前生成）
- `.project-local/task-runtime/compat-matrix-20260930.md`
  - 12 route 全保留（hash 不改）；B10 sidebar 11 项 + workbench 默认页 = E2E 冻结
    `.app-nav-item === 12` 不变。
  - API 只消费不新增路由（34 fullmatch + 5 eq）；host 探测 = /environment + /health
    读回，无后端路由处诚实标注 BLOCKED/UNKNOWN。
  - 冻结 selector 清单（#login…#design-*、.app-nav、.kpi 等）全部原样保留。

### 2. Lite/Home 仪表盘（#/dashboard）
真实读回驱动的六区（无假 KPI）：
- 继续项目（本机 recency，既有）
- 最近项目 / 质量趋势（既有 B10 序列，标「演示序列·非业务指标」）
- 待审 / 失败（job_store 词表判定，OUTCOME_UNKNOWN 计入待审不计失败）
- **活跃生产**（in_flight 任务；服务不可达时显式「未读回」不显示 0）
- **最近交付**（/api/projects/:id/bundles 真实读回；NOT_REVIEWED 标 warn）
- **Host / Capability 状态**（宿主 UNKNOWN 诚实标注 + /environment shared_inputs
  真实状态 + 未来能力卡）
- **Quick Launch**（工作台 / 项目 / 创作工具 / 预检 一行直达）
- blueprint 能力卡（research / design-domains / 协作，PLANNED 状态 + 接入点）

### 3. 项目详情页固定创作流（#/projects/:id）
- **横向阶段导航**：Brief → References → Research → Directions → Design System →
  Production → Versions → Review/Preflight → Handoff → Evidence。
  每个阶段节点绑定到已渲染 panel 的 id 锚点，点击 scrollIntoView；
  Research / Handoff 无后端路由的阶段标 PLANNED + tooltip 引用能力登记表，不造假。
- **右侧可折叠 Inspector**：方向版本环（data-driven SVG，选中版本高亮，
  不遮罩 artwork、不宣称进度）+ 活动绑定摘要 + 设计系统登记；sticky，
  768px 断点折叠为单列。

### 4. 创作工具页（#/tools）
- + Host / Capability 状态卡（宿主 UNKNOWN + 共享输入真实读回 +
  host-adapter-live / mcp-diagnostics 能力卡，BLOCKED 状态诚实标注）。

### 5. 交付中心页（#/deliverables）
- + 真实 /bundles 读回面板（交付包列表 + "在项目页下载" 跳转 + hash fail-closed 说明）；
  KPI「交付包」数来自真实读回，非占位。

### 6. 证据系统页（#/evidence）
- + 证据绑定链面板（项目 → brief 版本链 → 选定方向 → 交付包，全部真实读回）。

### 7. 未来能力契约登记表（UI 层单一来源）
- `CAPABILITY_REGISTRY`（shell.ts）：5 条记录，字段 = capabilityId / domain / source /
  owner / route / contractRef / implementationState (PLANNED|BLOCKED) / permission /
  reason / nextAction。无后端接入前 UI 只标注 BLOCKED/UNKNOWN；接入后由 /api 路由
  读回替换。**不建第二账本。**

### 8. 动态 VI 组件
- `buildVersionRing`：方向版本环（orbit + 版本节点，选中高亮，title 提示状态）。
  纯数据驱动（layer.directions 读回），不遮罩 artwork，不宣称进度。
- `sparkSvg`（既有）质量趋势折线。

### 9. 可访问性 / 动效
- 全部新组件用既有 B10 CSS 自定义属性（--surface-2 / --border / --accent / --glow）。
- `prefers-reduced-motion`：既有全局 override 覆盖新 transition（`.stage-nav-btn` 等）。
- `prefers-contrast: more`：新增描边加粗增强。
- 版本环 `role="img"` + `aria-label`；阶段导航 `aria-current="step"`；Inspector
  `aria-expanded` 折叠状态。

## 验证（本地，本 PR 内）

| 门 | 结果 |
|---|---|
| tsc --noEmit -p apps/workbench（strict） | PASS（2026-10-05 复跑） |
| vite build（4 modules，157.75 kB / 157747 B） | PASS，build/main.js 已随 KPI 修复重建 |
| node tests/unit.mjs（classic-script 契约） | PASS（2026-10-05 复跑） |
| node tests/appshell.mjs（路由/连接/读回竞争） | PASS（2026-10-05 复跑） |
| test_service_http + test_design_layer_http（47 tests） | PASS（2026-10-05 复跑） |
| design-lab/scripts/verify_design_lab.py（V3 verifier 全链） | PASS（2026-10-05） |
| scripts/verify_top_level_authority.py（10 checks） | PASS（2026-10-05） |
| design-lab/scripts/verify_project_drift.py | PASS（2026-10-05） |
| scripts/verify_path_refs.py（10 checks） | PASS（2026-10-05） |
| design-lab/scripts/verify_identity_gate.py | PASS（2026-10-05） |
| design-lab/scripts/verify_workbench_packaging.py（5 checks） | PASS（2026-10-05） |
| git diff --exit-code -- apps/workbench/build | CLEAN（2026-10-05 重建后无 drift） |
| 视口截图（真实服务 + 真实 Chromium，40 张） | PASS，零 pageerror / console error |
| 全量 unittest（1762 tests） | CI `Python gate` 对 exact SHA `84ffc19` = **SUCCESS**；本机在 `694ad2d` 跑到 `Ran 1762 tests / failures=1`，唯一失败项 `test_aggregate_verify_runs` → `verify_asset_governance`，即 sidecar 权利记录问题，已由 `84ffc19` 修复并单独复验为 `ASSET_GOVERNANCE=OK` |

## 明确不做（边界）

- **UI08（Spectrum）/ UI09（Web Awesome Core）不采用**：本仓构建是 classic-script
  单 bundle（D004）+ CSP `style-src 'self'` 无 unsafe-inline + vm 单测驱动 bundle。
  Web Components（shadow DOM / ES module imports）与三条硬合同直接冲突，引入需拆
  D003/D004 构建合同 → 按任务包「最多采用一个，失败继续现有组件」裁决：
  **不采用，继续现有 B10 class 体系**（本项为决策记录，非缺陷）。
- 不新增后端路由（host 探测 / MCP 诊断均为 BLOCKED 标注，等待后端接入）。
- 不动 main 保护、不 tag、不 release（任务包范围外 + 用户范围裁决）。
- 宿主实操任务（PS/AI/Figma/Penpot/ComfyUI/Blender 真实驱动）不在本分支执行。

## 待办（合并前）
- ~~全量 unittest discover 1762 tests~~ → **CI 已判绿**（`Python gate` @ `84ffc19` = SUCCESS）
- ~~Playwright 截图（1280/1920/2560/窄屏）~~ → **已完成**：
  `scripts/capture_workbench_screenshots.py` 真实执行 5 视口 × 8 页面 = 40 张，
  逐张 hash 见 `screenshot/screenshot-manifest.json` 与 `SCREENSHOTS.md`。
  注意：本文件此前与 `SCREENSHOTS.md` 状态互相矛盾（一边 DEFERRED、一边声称已生成），
  已统一为真实状态。
- 7 份报告生成（本文件 + FINAL_IA + VISUAL_QA + HOST_UI_MATRIX +
  ASSET_MANIFEST.json + GOLDEN_FLOWS + MERGE_READY_HANDOFF）— 已完成并互相对齐

## 证据（exact SHA）
- 基线 main：`1acbfa15a8c036907aadbdc6938b8706c91b5d3e`
- 截图证据基线：`fbe94ac217c52965c19b11ebdddd4bebb37d5829`（本分支）
- build/main.js SHA-256：`f58a8e1f9776e2c9769629f83cb8cea2c2452b3ef02466463060ee4bbcc05d21`
  （157747 bytes，vite build 4 modules；`8036439` 修复 KPI count-up 后重建）
- 见 `ASSET_MANIFEST.json` 各文件 SHA-256（CI 重建后回读校验 byte-determinism）。
