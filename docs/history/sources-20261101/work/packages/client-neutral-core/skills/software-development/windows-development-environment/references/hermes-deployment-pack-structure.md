# Workflow-assistance 跨机器 Overlay 结构

## 当前契约

本仓库是 routing-neutral 的 Hermes/Codex/GitHub 工作流 overlay，不是
Hermes 应用安装器，也不是 Provider、认证、网络或桌面插件的迁移工具。

受管清单以 `config/managed-config-schema.yaml` 为唯一机器可读来源：

- 精确登记的 skill roots 与 `bin/` launcher paths；
- `config/SOUL.md → $HERMES_HOME/SOUL.md` 的单文件 mapping；
- isolated baseline verification 所需的 UI、memory、toolset、terminal hook 及
  `mcp_servers.owned_names` 结构契约；它们不授权写入真实 profile config。

同步器对这些文件执行 backup → staging → per-item atomic promotion →
rollback。它不整体替换 `skills/`、`bin/` 或 Hermes Home。

## 不属于 Overlay 的状态

以下内容始终由官方应用与当前用户保有：provider/model/base URL、认证、
API key、用户 MCP、用户插件、rules、sessions、memories 以及网络路由。
同步器不读取、不比较也不 promotion live `config.yaml`；因此没有 config-drift
检查与替换之间的竞态窗口。该文件只能在受控 project runtime 下的 empty isolated
Home 中构造，用于 portable compatibility verification。

## 跨机器使用

1. 用官方渠道安装或更新 Hermes/Codex；应用升级、schema migration 与
   Desktop layout 验收是独立步骤。
2. 在目标机运行同步器 dry-run，审查 schema 所列 exact managed inventory。
3. 只有用户明确批准后才执行 `--apply`；保留同步器创建的 backup 作为恢复
   证据。
4. 完成后分别验证结构、isolated runtime compatibility、hook trust 和
   Desktop cold-start；不要将其中任一项当成其它项的替代证据。

凭据文件、用户路由和应用私有状态不得读入、复制进或从本仓库恢复。
