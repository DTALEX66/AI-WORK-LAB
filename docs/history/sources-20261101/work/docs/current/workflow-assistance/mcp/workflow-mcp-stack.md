# Workflow MCP Stack

目标是少量、稳定、可验证，并避免与 Hermes 原生工具或模型能力重复。

## 默认启用：Context7

- 包名与版本：`@upstash/context7-mcp@3.2.2`（portable baseline 固定版本）
- 价值：查询公开库的当前文档，降低过期 API 用法风险。
- 传输：Hermes `hermes-npx` wrapper，优先 bundled Node。
- 隐私：查询会发送到外部服务；不得包含私有代码、密钥、客户数据或内部项目名。

验证配置而不是直接启动一个旁路进程：

```bash
hermes mcp test context7
```

## 不默认启用

| 能力 | 原因 | 替代 |
|---|---|---|
| sequential-thinking | 与模型原生推理、plan/TDD/debug skills 重复并增加 tool schema | 原生推理 + 对应 skill |
| public-apis | 单一公共 API 目录，低频且可搜索 | `web_search` / GitHub public-apis |
| Playwright MCP | 与 `browser` / `computer_use` 重叠，权限面更大 | Hermes 原生浏览器工具 |
| filesystem MCP | 与 Hermes `file` 重叠 | Hermes `file` toolset |
| memory MCP | 与 Hermes `memory` 重叠 | Hermes `memory` toolset |

如果具体任务证明原生能力不足，先用 `packages/client-neutral-core/scripts/mcp_candidate_audit.py` 记录候选边界，再使用 `hermes mcp add/configure/test` 按需启用，并在新会话验证；不要把临时选择重新写回默认 portable config。

候选审计细则见 `docs/current/workflow-assistance/mcp/mcp-catalog-governance.md`。

## 变更门禁

新增默认 MCP 候选（不含当前 Context7 portable baseline 的官方包名例外）必须同时满足：

1. 有原生工具无法覆盖的明确增益；
2. candidate audit 中固定版本和许可证/来源检查；portable baseline 同样固定官方 Context7 包版本；
3. `hermes mcp test <name>` 通过；
4. 记录外发数据、文件/网络权限和密钥需求；
5. 测量 `hermes prompt-size --json` 的工具 schema 增量；
6. 同步更新 `config/config.yaml` 与治理测试。

候选阶段可以通过：

```bash
python packages/client-neutral-core/scripts/mcp_candidate_audit.py --write-template .project-local/artifacts/mcp-candidate.yaml
python packages/client-neutral-core/scripts/mcp_candidate_audit.py .project-local/artifacts/mcp-candidate.yaml
```

审计通过只表示候选元数据完整；不等于 server 已配置、已运行、已安全或已默认启用。

默认 MCP baseline 的内容来源是 `config/config.yaml`；`config/managed-config-schema.yaml`
中的 `mcp_servers.owned_names` 仅定义 isolated verifier 构造该 baseline 时的结构
所有权，不授权同步器替换或移除真实 Hermes Home 中的 MCP。新增默认 MCP 时必须同步
更新两者；本文只解释选择理由。
