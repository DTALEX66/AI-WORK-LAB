# COMMAND_CENTER_2_DESIGN — WL-OBS-UI-DSH-20260816

> 状态：IMPLEMENTED · 2026-08-16 · baseline SHA `bc5c17b482`

## 设计决策

### 1. 信息架构（6 稳定层级）
| 层级 | 组件 | 回答 |
|---|---|---|
| 01 Global Command | renderGlobalCommand | WORK-LAB 当前正常吗（≤6 KPI） |
| 02 Projects | renderProjectGrid | 哪些项目在跑、在哪平台、Git 状态 |
| 03 Activity | renderActivity | 谁在执行什么（真实 executions 才显示） |
| 04 Telemetry | renderTelemetry | Token/成本（后端提供才显示） |
| 05 Delivery | renderDelivery | Git/CI 统一表 |
| 06 Governance+Trust | renderGovernance + renderDataTrust | 治理健康 + 数据可信度 |

### 2. 关键决策
- **单一项目视图**：消除旧 projectOverview/runtimeMatrix/projectHealth 三重复 → 一个 Project Grid；
- **状态统一**：statusMeta() 单一来源（success/warning/critical/muted/unknown），所有状态经它映射；
- **TRUTH-FIRST**：无 token 样本 → 'No token samples yet' 空态；无 executions → Activity 隐藏；`Number(null)=0` bug 已修；
- **Typography scale**：Display 30 / Section 17 / Card 14 / Meta 11.5 / Code 11；
- **Sidebar SVG 图标**：复用 index.html icon sprite（i-projects/i-ci/i-usage/i-branch/i-layer/i-sha）；
- **Compact 重定义**：真实小窗（状态+项目+token+覆盖），非 Full 缩水版；
- **无障碍**：role/aria-live/focus-visible/reduced-motion/status 非颜色唯一；
- **Frozen Zone**：api.js/state.js 未改（LIVE/OFFLINE/last-good/loopback/GET-only 语义保留）。

## 视觉语言
参考 SigNoz/HyperDX/Linear/Vercel，但收敛为 WORK-LAB 自有的：近黑蓝灰底 + 冷蓝 primary + 状态色 token + 弱边框 + mono 数据。禁止 Card Soup/霓虹/Cyberpunk。
