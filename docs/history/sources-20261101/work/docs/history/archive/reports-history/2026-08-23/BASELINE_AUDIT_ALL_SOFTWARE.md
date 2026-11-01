# 全工作流软件五维基线审计（2026-08-23）

> 对照 AGENTS.md 五维基线（官方标准格式 = 唯一入口）。全部实测验证。

## 审计结果

| 软件 | ① 唯一入口（官方标准）| ② 桌面链路 | ③ 官方基线 | 状态 |
|---|---|---|---|---|
| Hermes | Hermes.lnk → win-unpacked\Hermes.exe（官方 Electron）+ hermes CLI | Test-Path True | 官方 0.20.5 @ fd760435 | ✅ |
| Codex | codex.cmd wrapper → **Windows Store OpenAI.Codex 官方 runtime**（SHA 校验）| CLI 工具（无桌面需求）| 官方商店版 | ✅ |
| CC Switch | CC Switch.lnk → D:\Programs\CC Switch\cc-switch.exe | True | 官方 exe | ✅ |
| OpenHuman | OpenHuman.lnk → Local\OpenHuman\OpenHuman.exe | True | 官方 exe | ✅ |
| Open Design | Open Design.lnk → D:\Programs\Open Design\Open Design.exe | True | 官方 exe | ✅ |
| GitHub CLI | gh 2.95.0（官方发布）| CLI | 官方 | ✅ |
| DSH | web 3080（运行中）+ DSH CLI | 官方入口 | 官方 | ✅ |

## 逐维确认

- ① 唯一入口：全部官方标准格式（无自定义 launcher/无两套系统）
- ② 桌面入口：所有 GUI 快捷方式目标 Test-Path True（Hermes/CC Switch/OpenHuman/Open Design）
- ③ 官方基线：Hermes 官方 0.20.5（官方安装器）；Codex 官方商店 runtime（wrapper SHA 校验）；其余官方安装 exe；gh 官方发布
- ④ 无阻塞开销：WORK-LAB 管理 skills 全部 <10KB；官方自带 skills 不干预（官方优先）
- ⑤ 全功率模型：cost_multiplier=1.0（默认），无 cap/降级

## 附注

- Codex wrapper 声明 Store 版拥有 runtime——官方标准（wrapper 不替代官方）
- 所有更新遵循 2026-08-23 用户规则：官方发布为准，禁私自本地打包