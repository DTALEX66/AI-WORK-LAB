# Product Design 产物索引 — Observer 紧凑 HUD

生成时间 2026-10-19。本目录是八个 `product-design` 技能在本仓库落地的**人读产物**；
机器上下文在 `.project-local/artifacts/product-design/`。

## 路径重映射（重要）

这些技能默认把产物写进各自的 `spark-output` 目录，但本仓约定是人读文档进 `reports/`、机器上下文进
`.project-local/artifacts/`。本轮**没有创建该默认目录**（避免出现第二套真值路径），
每个 JSON 内都有 `output_remap` 字段记录原路径与去向。下游若按默认路径找不到文件，
按 `output_remap` 取。

## 八个技能的状态

| 技能 | 状态 | 人读产物 | 机器产物 | 备注 |
| --- | --- | --- | --- | --- |
| `probe` | ⏳ 计划，未执行 | `probe-20261019.md` | `probe.json` | 只有 1 位 owner，n=1 冒烟测试，不冒充用户研究 |
| `bench` | ✅ 完成 | `bench-20261019.md` | `bench.json` | 只基于 2 张公开截图 + 实测日志；未做交互级体验 |
| `journey` | ✅ 完成 | `journey-20261019.html` | `journey.json` | **合成假设**（契约 + 实测），无访谈、无原话 |
| `flow-web` | ✅ 完成 | `flow-web-20261019.md` | `flow-web.json` | 现状 IA + 状态矩阵 + 4 个候选 |
| `board` | ✅ 完成（锁定板） | `board-20261019.md` | `board.json` | 不新造方向；记录一次被否决的霓虹青方案 |
| `pitch` | ✅ 完成 | `pitch-20261019.md` | `pitch.json` | 4 个 owner Asks |
| `poster` | ⛔ 拒绝（有理由） | `poster-20261019.md` | `poster.json` | 内部只读控制面，无营销渠道；给出 README hero 的替代条件 |
| `check` | ✅ 完成 | `check-20261019.md` | `check.json` | 0 blocker / 0 major / 4 minor |

## 证据基线（所有报告共用）

- 基线：`.project-local/runs/hud-preview/verify-20261019d.log`
  （440×680、topbar 63、content 617/617、panel bottom 630、`tinyText: []`、无控制台错误）
- 六态：`.project-local/runs/hud-preview/states-20261019e.log`
  （many / huge / unknown / zero / stale × dark / light）
- 截图：`.project-local/runs/hud-preview/shots/state-*-{dark,light}.png`
- 竞品参考：`.project-local/runs/agent-hud-ref/usage-statistics.webp`、`approvals.webp`

**引用规则**：数字必须带 rev（dark 1,988,012@293 / light 2,012,012@297，差异来自
live sidecar 前进，不是主题差异）。真实 Tauri WebView2 窗口本轮未复测，web 层结论不等于窗口层结论。

## 下一轮候选（按优先级）

1. **F-04** 面板固定最小高度 527px，消除 57px 高度跳动（CHK-02）。
2. **F-03** 命令面板空态显示 `搜索页面 / 命令 · Ctrl K`（CHK-04）。
3. **F-02** 状态胶囊 / `覆盖 3/4` 行加 title + aria（CHK-01，不改可见字符串）。
4. **F-01** 来源卡 → 完整视图对应项目行深链（需 owner 决策）。

## 本轮代码改动（供对照，不在此目录）

`apps/observer/frontend/src/views/CompactHUD.tsx`、`apps/observer/frontend/src/views/hudModel.ts`、
`apps/observer/frontend/src/skins/hud-phenotype.css`、`apps/observer/frontend/src/components/layout/TopStatusBar.tsx`、`apps/observer/frontend/src/main.tsx`、
`apps/observer/frontend/src/views/compactHudPhenotype.test.tsx`、`apps/observer/frontend/src/views/renderTruthContract.test.tsx`。
已随 2026-10-19 上传提交（`13ed879b`）；后续改动仍需 owner 明确授权。
