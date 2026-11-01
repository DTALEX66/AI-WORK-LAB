# 前端单一化架构 Gate（WLR-810）

> 决定：React frontend/ 为唯一生产前端。legacy web/ 转 archive（不再生产入口）。

| 维度 | React frontend/ | legacy web/ |
|---|---|---|
| 生产状态 | 生产（Tauri frontendDist 指向 frontend/dist）| ARCHIVE（保留历史）|
| 数据 | 真实 snapshot + Prometheus（WLR-130 truth-first）| 旧静态 |
| 维护 | 构建 + TS | 不再作为生产 |

## 依据

- WLR-810 要求单一生产前端（truth tests/Tauri 构建/维护性）
- React 已接入真实数据 + truth-first（未知不转 0）+ 动态 endpoint
- web/ 保留为历史归档（不删除——任务包：不删除历史）

## 后续

- WLR-900：CI 构建 React + cargo check（当前 CI 仍 FAILED，首要修复）