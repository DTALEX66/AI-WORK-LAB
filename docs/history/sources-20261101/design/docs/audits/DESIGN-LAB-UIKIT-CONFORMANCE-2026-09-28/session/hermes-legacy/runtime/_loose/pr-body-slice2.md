## 范围

UI 套件 B04 权威视觉系统 + B07 12 路由 IA 在 DESIGN-LAB Workbench 的收敛落地，共 2 个 commit：

1. **`9014ed8` Slice 1 — 换肤**：`apps/workbench/style.css` 全色值切到 B04 Design Tokens（深黑 `#060A14` + Electric Blue `#316CFF`），新建 `design-lab/config/design-tokens.json`（库内单一事实源）
2. **`085a0f6` Slice 2 — AppShell IA**：左侧 12 路由导航（`routes.json` 权威）+ hash 路由；4 视图绑真实 API 读回（仪表盘 `/health`+`/projects`+`/design-systems`、品牌系统、预检QA `/task-preflight` fail-closed、系统设置 `/environment` 只读诊断）；7 个无后端路由的 IA 槽位诚实标"未开放+原因"；B07 域状态机 8 阶段契约可视化

## 契约与测试

- 前端三链 typecheck / build / test:unit 全绿；bundle 仍无顶层 import/export（classic-script 可载）
- `build/main.js` 53.87kB 提交（no-drift gate 新基准）
- 浏览器 E2E（真实 Chromium 1228 + 真实 loopback 服务）修复后重跑 PASS 2.9s，零回归
- 选择器超集：OLD=67 全保留，NEW=96，MISSING=0
- Python 全量契约套件 1584 tests OK（skipped=2）
- 视觉验收 4/4（效果图在 `.project-local/ui-kit/mockups/`，不入仓）

## 回滚

两 commit 均纯增量 + CSS 作用域化（`.dl-shell` 未挂载路径逐字节不变），revert 任一 commit 即回退。

## 候选 SHA

`085a0f6`（含 `9014ed8`）
