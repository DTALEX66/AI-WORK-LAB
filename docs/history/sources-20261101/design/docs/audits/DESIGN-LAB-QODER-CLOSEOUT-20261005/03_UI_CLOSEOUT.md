# 03 — C0 商业级 Workbench UI 收口

分支：`feat/ui-commercial-workbench-20260930`
起点 `0fbb67439755d9ded181ded6c061711f23343dc9`（= PR #213 head，与任务书读数一致）
收口后本地 HEAD：见 `git log`（本分支新增 6 个 commit，未 push）

## 做了什么

| commit | 内容 |
|---|---|
| `8036439` | `fix(ui)`：KPI count-up 只允许纯数字，修掉服务版本卡显示 `0.1` 的假值 |
| `ab193e6` | `test(ui)`：新增真实服务 + 真实 Chromium 视口截图采集器 |
| `13fa81e` | `test(ui)`：截图记录绑定已提交 bundle 的 hash，并在 bundle 与 HEAD 有 drift 时拒绝采集 |
| `fbe94ac` | `test(ui)`：每张截图产出 REUSE `.license` sidecar + 驱动补 SPDX 头 |
| `893a3ec` | `docs(ui)`：40 张真实截图 + 文档真值对齐 |
| `694ad2d` | `docs(ui)`：带 sidecar 重采并刷新证据引用 |

## C0.1 截图 Evidence Truth 缺陷（已修，方案 A：真做）

原状：`SCREENSHOTS.md`（commit `0fbb674`）声称 12 张截图已生成、真实渲染、hash 已记录，
但 `docs/UI-CONVERGENCE-20260930/screenshot/` 不存在，表格全是占位符，
且写的路由 `#home` / `#/project/:id` / `#/host-tools` 与代码真实路由不符
（实际 `#/dashboard` / `#/projects/:id` / `#/tools`）。同目录另两份文档写 DEFERRED。

处置：
- 新增 `scripts/capture_workbench_screenshots.py` + `design-lab/tests/e2e/capture_workbench_screenshots.mjs`；
- 真实 `ProjectService` + `make_server`（OS 分配端口、临时项目根、内存 64-hex token）；
- 真实 Chromium 149.0.7827.55（`chromium-1228/chrome-win64/chrome.exe`，非 headless-shell）；
- 数据由 UI 写入：建项目 → 导入真实参考图（`design-lab/evals/.../poster-sunrise-001/reference.png`）
  → 简报 → 方向 → 选定 → 绑定设计系统；
- 5 视口 × 8 页面 = **40 张 PNG**，逐张 SHA-256 + 视口 + URL + 时间戳 + exact commit
  + bundle SHA-256 落在 `screenshot/screenshot-manifest.json`；
- 采集器 fail-closed：node/Playwright/Chromium 缺一即 `CAP_BLOCKED`；bundle 与 HEAD 有 drift 即拒绝；
  任一 `pageerror`/`console.error` 即整轮失败；截图前等待 KPI 数值稳定。

结果：`docs/UI-CONVERGENCE-20260930/screenshot/` 40 PNG + 40 `.license` + manifest，
绑定 commit `fbe94ac…`，合计 5,120,249 bytes，零浏览器诊断错误。

## 截图暴露的真实缺陷

1. `animateKpiCount` 用 `parseFloat` 解析 `data-count`，把 `0.1.0-alpha.0` 当成 `0.1`，
   仪表盘「服务版本」KPI 长期显示错误值（真值读回被动画改写）。已修 `8036439`。
2. count-up 是 JS 驱动，Playwright `animations: 'disabled'` 对它无效，
   首拍把「设计系统 3」（真实 4）的中间帧写进了证据。已改为等待数值收敛后再拍。

## C0.2 文档对齐

`COMPLETION_REPORT.md` / `VISUAL_QA.md` / `SCREENSHOTS.md` / `ASSET_MANIFEST.json` /
`MERGE_READY_HANDOFF.md` 统一到同一状态词表与同一组 SHA；
`FINAL_IA.md` / `HOST_UI_MATRIX.md` / `GOLDEN_FLOWS.md` 复核后与代码一致，未改。

## C0.3 IA 未横向扩张（复核结论）

- `ROUTE_VIEWS` 仍 12 项（浏览器 E2E 冻结 `.app-nav-item === 12`）；
  `#/projects/:id` 仍走参数化路由不入 nav。
- 项目详情阶段导航 10 节点，与任务书链路一致：
  Brief → References → Research(PLANNED) → Directions → Design System → Production →
  Versions → Review/Preflight → Handoff(PLANNED) → Evidence。
- 无后端槽位（research / domains / collaboration / settings 的部分面板）保持
  PLANNED / BLOCKED / UNKNOWN 文案 + 能力登记表 `CAPABILITY_REGISTRY`，无假按钮、无假 KPI。

## C0.4 合并判定

本地门：tsc / vite build / unit.mjs / appshell.mjs / 47 HTTP 用例 /
verify_design_lab / top-authority / drift / path-refs / identity / packaging /
license coverage / sbom / anti-slop / browser E2E（no-skip，`E2E_REQUIRED=1`）/
MiniGame node 300 用例 + android drift —— 全绿；
`git diff --exit-code -- apps/workbench/build` CLEAN。
全量 Python 套件结果记在 `00_FINAL_STATUS.md`（含 1 failure / 2 errors 的定位）。

结论：`UI_MERGE_READY` 的本地条件成立；PR #213 仍是 **DRAFT** 且新 commit 未 push，
因此停在 **`READY_FOR_OWNER_MERGE`**。push / un-draft / merge / 删分支需 owner 授权。

## 已知限制

- 截图是 E1/E2 视觉证据，不是宿主 E3，也不是人工视觉验收 E4。
- `.license` sidecar 声明的权利范围限于「本仓自有 UI + 一方 MIT 参考图 + 本机系统字体的
  渲染输出」；系统字体的再分发权利未做独立法务确认，`modelInputAllowed=false`。
- `893a3ec` 的 commit message 把 Chromium 误写为 `149.0.7827.57`，
  权威读数以 manifest 为准：`149.0.7827.55`。
