# Agent 行为评估

本文记录 Workflow-assistance 对 Agent 行为回归评估的 portable 规则。目标是吸收 promptfoo 等开源评估工具的**声明式用例、断言和 CI 友好**方法，但不把任何外部评估运行时、模型 Provider、API Key 或遥测服务设为默认依赖。

## 目标

`Workflow-assistance` 是全局 Hermes Agent + CC Switch + Codex 工作流增强包。Agent 行为评估用于检查这条全局工作流是否仍遵守关键契约：

- 会分清 repo 已更新、live 已同步、当前会话已加载；
- Gateway process running 不会被误说成 messaging platform configured；
- 本地 TUI cron / sleep-mode delivery 不会被误说成实时消息投递；
- 忙时输入默认 queue，但持久任务仍需 sleep-mode、cron 或后台进程；
- 中断的 delegation 结果不得被当作有效审查结论；
- PowerShell 任务优先 `pwsh` 7，只有兼容问题才回退 `powershell.exe` 5.1；
- 没有真实验证证据时，不宣称完成；
- 不打印或迁移 `.env`、OAuth、tokens、auth、session、logs、cache、state.db。

## 吸收来源

| 来源 | 许可证 | 吸收内容 | 默认依赖 |
|---|---|---|---|
| `promptfoo/promptfoo` | MIT | 声明式 test case、expected behavior、assertion、CI-friendly eval 文件布局 | 不安装、不默认运行 |

本仓库只吸收方法和模板，不 vendor 上游源码，不新增 npm package，不配置 hosted provider，不上传 trace，不保存真实 prompt/response 数据。

## 模板

默认模板：

```text
packages/client-neutral-core/templates/evals/agent-behavior-smoke.yaml
```

这个文件是 promptfoo 风格的 YAML 模板，用于描述 Agent 行为 smoke cases。它刻意保持：

- provider 为占位符；
- prompts 为占位符；
- assertions 只检查公开、非敏感的行为边界；
- 不包含真实 token、API Key、OAuth 状态、私有项目内容或模型服务配置。

## 运行策略

当前阶段不把 promptfoo 加入默认安装或 CI。需要运行时，必须由用户明确选择执行器和 Provider，然后把输出写到项目内：

```text
.project-local/artifacts/evals/
```

建议的执行边界：

1. 先复制模板到当前项目 `.project-local/artifacts/evals/` 或项目自己的 `<project>/tests/evals/`；
2. 替换占位 provider/prompt，不写入密钥；
3. 使用明确的外部 runner 执行；
4. 保存 summary、exit code、runner version、config hash；
5. 不把原始私密对话、失败请求 dump、headers、tokens 或 trace 上传到仓库。

## 默认不做

- 不默认安装 `promptfoo`；
- 不默认把 eval 加入 GitHub Actions；
- 不默认发起模型请求；
- 不默认接入 Langfuse/Phoenix/OpenLIT 等观测平台；
- 不把 eval 结果当成安全证明；
- 不用 eval 替代真实工具执行、测试、MCP smoke 或 exact-tree review。

## 最小验收

新增或修改 Agent 行为评估资产时，至少验证：

```bash
python tests/workflow-assistance/test_workflow_governance.py -v
python packages/client-neutral-core/scripts/security/scan_agent_rules.py templates skills docs scripts README.md
```

如果只改模板/文档且系统要求 fresh evidence，可创建 `C:\Users\admin\AppData\Local\Temp\hermes-verify-*` 临时脚本做 focused ad-hoc verification，并明确说明它不是完整测试套件 green。
