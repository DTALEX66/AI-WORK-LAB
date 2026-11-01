<!-- freshness: sourceCommit=f1af77e sourceTree=2941412 generatedAt=2026-08-26T16:00:00Z evidenceLevel=E0 expiry=2026-09-26T16:00:00Z status=CURRENT -->
# 软件兼容矩阵（SOFTWARE_COMPATIBILITY_MATRIX · 2026-08-19）

| 软件 | 类别 | 官方源 | Adapter | 兼容状态 | 管理方式 |
|---|---|---|---|---|---|
| Hermes | agent-harness | desktop-shortcut | hermes | registered | official baseline + user overlay |
| Codex | agent-runtime | cli | codex | registered | wrapper + rules overlay |
| DeepSeek Harness (DSH Desktop 2.0.2) | agent-runtime | community-desktop | deepseek-harness | active | managed (external, D:\All projects\DSH; community Electron, local build removed) |
| CC Switch | provider-switch | desktop-shortcut | — | legacy_observe | LEGACY_OBSERVE (observe-only per WLR-010; no active writes) |
| Open Design | design-client | desktop-shortcut | open-design | registered | client adapter (design domain owned by DESIGN-LAB) |
| OpenHuman | agent-harness | desktop-shortcut | — | registered | registration only |
| GitHub | platform | api | github | registered | delivery platform |
| Dagu (2.15.3) | workflow-engine | npm-global | — | active | upstream baseline (Web UI :8080, DAG execution) |
| TokenTelemetry (1.0.0) | observability | local-install | — | active | upstream baseline (Token/Cost dashboard :3001) |

## 原则

- 全部为注册数据（software-registry.json），不进入核心产品身份
- 配置基线变更需 Diff/Approval/Apply/Readback/Drift/Rollback（config_control_plane.py）
- 版本更新不自动提升 Compatibility Baseline