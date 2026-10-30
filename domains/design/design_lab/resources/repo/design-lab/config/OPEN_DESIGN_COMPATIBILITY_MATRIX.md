# Open Design Compatibility Matrix（ODA4-0302）

- 版本基线：Open Design `0.18.1`（当前已测基线；`compatibility-baseline.json` 为 SSOT）
- 历史记录：`0.13.0` 于 2026-08-07 在就地升级前观测，仅作历史，不作为支持基线
- 证据：E2（结构/隔离验证）；Open Design live runtime 注册需 Phase 3 的 E3 证据
- 版本协商策略：不将实现永久锁死到单一版本；新接口以官方 `--help`/schema/运行时回读为准现场发现

## 插件 / Bundle 兼容清单

| 资产 | 类型 | 版本 | schema | license | 状态 |
|---|---|---|---|---|---|
| commercial-design-core | bundle | 0.2.0 | plugin.v1.json | MIT | ✅ 官方 schema |
| visual-quality-core | bundle | 0.2.2 | plugin.v1.json | MIT | ✅ |
| production-handoff | bundle | 0.1.0 | plugin.v1.json | MIT | ✅ |
| uiux-layout-director | plugin | 0.1.0 | plugin.v1.json | MIT | ✅ |
| graphic-design-director | plugin | 0.1.0 | plugin.v1.json | MIT | ✅ |
| brand-visual-director | plugin | 0.1.0 | plugin.v1.json | MIT | ✅ |
| design-qa-critic | plugin | 0.1.0 | plugin.v1.json | MIT | ✅ |
| spatial-exhibition-director | plugin | 0.1.0 | plugin.v1.json | MIT | ✅ |
| minigame-ui-director | plugin | 0.1.0 | plugin.v1.json | MIT | ✅ |
| anomaly-monitor-hud | plugin | 0.1.0 | plugin.v1.json | MIT | ✅ |

**全部 10 个 manifest** 均引用官方 `https://open-design.ai/schemas/plugin.v1.json`、合法 JSON、MIT。

## 兼容矩阵（Open Design 0.18.1）

| 契约 | 当前状态 | 说明 |
|---|---|---|
| plugin schema (plugin.v1.json) | ✅ 对齐 | 10 manifest 全部引用官方 schema |
| 插件入口 (open-design.json) | ✅ 对齐 | specVersion 1.0.0 |
| Scenario/Atom/Bundle 运行 | ⏳ ODA4-0303 | 需 live runtime 注册验证 |
| MCP/CLI | ⏳ ODA4-0303 | daemon-cli.mjs 待验证 |
| 版本回读 | ⏳ ODA4-0303 | runtime ID/version 待回读 |

## 规则
- **不编造 CLI 参数**：所有 MCP/CLI 用法必须来自本机官方 daemon 实测，不臆造。
- 旧入口有兼容测试（`tests/test_oda4_0203_entrypoints.py` 覆盖三入口收敛）。

## 边界
- 不读取认证/私有状态；不修改 Open Design 私有配置。
- 未 live 验证的能力状态保持 `UNVERIFIED`，不冒充可用。
