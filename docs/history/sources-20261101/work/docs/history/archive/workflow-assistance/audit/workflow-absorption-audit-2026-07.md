# Workflow Absorption Audit — 2026-07

> **状态：current。** 本文记录已被当前 portable workflow 采用的方法；历史
> 验证不等于当前机器仍可用，运行时状态必须重新执行 doctor/marker。

## 已吸收的可迁移能力

| 类型 | 吸收资产 | 当前策略 |
|---|---|---|
| Provider 切换 | `scripts/workflow/switch_model.py` + `skills/model-switch` | 三模型线；配置回滚、写后校验、可选 live marker |
| 工作流体检 | `scripts/workflow/hermes_workflow_doctor.py` | 结构检查与真实推理分层 |
| MCP 稳定性 | `bin/hermes-npx*` | 默认固定官方 Context7 包版本；候选 MCP 另行执行 pinned provenance 审计 |
| MCP 候选治理 | `mcp_candidate_audit.py` | 候选元数据通过不等于默认启用 |
| Agent 规则 | AGENTS/CODEX/SECURITY/DESIGN 模板 | 单写者、路径边界、验证闭环 |
| 安全审计 | `scan_agent_rules.py` | 扫描可提交工作流资产，不读取凭据 |
| 模型 UX | portable `model_picker` / `quick_commands` | 同步 picker、快捷命令、streaming、tokens/reasoning 策略，保留 live route/credentials |

## 明确不吸收 / 不默认启用

- `public-apis`、`sequential-thinking`：历史 MCP，不再是默认栈；由 web/native skills 覆盖。
- Playwright、filesystem、memory MCP：与 Hermes 原生工具重叠，必须按任务审计。
- `.env`、`auth.json`、OAuth refresh token、cookie、Credential Manager：永不读取、复制或提交。
- 第三方源码 vendoring：不做，除非完成许可证、供应链和维护边界审查。

## 当前默认 MCP

```text
context7
```

验证：

```bash
hermes mcp test context7
```
