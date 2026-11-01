# Hermes 运行目录、迁移与升级准则

## 不可替代的数据边界

`%LOCALAPPDATA%\\hermes` （下文记作 `$HERMES_HOME`）是本机 Hermes 服务根，不是项目临时目录。以下内容是
跨项目共享状态，迁移或清理前必须停止 Hermes，并使用官方命令或已验证的备份；不得
由同步脚本、清理脚本或手工批量删除处理：

- `config.yaml`、`.env`、`auth.json`：运行配置和认证；仓库只保存无密钥模板。
- `state.db`、`$HERMES_HOME/sessions/`：全部会话索引和会话内容；不可按项目拆分或直接删库。
- `$HERMES_HOME/skills/`：已安装技能；可由本仓库同步的部分有版本来源，其余用户技能必须保留。
- `$HERMES_HOME/state-snapshots/`、显式 `pre-update-*` 备份：恢复证据，除非已完成新的可验证备份。

项目任务数据必须留在 `<project>/.project-local/`，并通过
`hermes-project-data.py --project . run -- <command>` 产生。收尾只清理
`<project>/.project-local/runs/`，绝不清理 Hermes Home 的会话或认证目录。

## 目录角色

| 角色 | 位置 | 处理原则 |
| --- | --- | --- |
| 便携源 | `Workflow-assistance` Git 仓库 | 唯一可提交、可复制的工作流定义；不含密钥或会话。 |
| 活动运行时 | Hermes Python 环境和当前桌面包 | 保持单一活动版本；桌面快捷方式只指向当前包。 |
| 用户状态 | Hermes Home 的配置、认证、会话、用户技能与运行入口 | 配置/认证/会话、非仓库负责的 `$HERMES_HOME/skills/` 和非仓库负责的 `$HERMES_HOME/bin/` 入口原样保留；仓库负责的 13 个 skill 子树和 6 个 binary 按权威源逐项替换。 |
| 同步回滚 | `backups/workflow-assistance-sync-*` | 同步器只保留最近两份，并且只会清理自己创建的目录。 |
| 人工升级备份 | `pre-update-*`、`$HERMES_HOME/state-snapshots/` | 不自动删除；完成恢复演练后再由用户决定保留期。 |

源代码检出、Python venv、Node modules 和桌面构建包是可再生运行物，但不能在
桌面仍使用它们时删除。升级完成且新快捷方式、会话打开、模型调用三项均验证通过后，
才能把旧包移入可恢复备份；不得用删除全目录的方式“清理”。

## 标准升级顺序

1. 运行 `packages/client-neutral-core/scripts/verify_portable_install.py`，确认仓库可安装到隔离空目录，且不复制凭据。
2. 使用官方 `hermes update` 把 managed checkout、依赖、bundled skills 和 Desktop 恢复到当前官方基线；不得在活动 venv 被占用时使用 `--force-venv`。
3. 使用 `sync_hermes_workflow_assets.py --apply` 部署仓库所拥有的配置、技能和工具；该脚本保留活动模型、provider、API 配置、自定义 MCP 和非仓库负责的 skills，并精确替换仓库负责的 skill 子树。
4. 用 `hermes config check`、skill provenance 和 `hermes_workflow_doctor.py` 验证结构；只有显式要求 live 网络验证时才运行 `--live`。
5. 启动当前桌面快捷方式，确认日志出现 `Hermes backend is ready. Finalizing desktop startup`，并打开一个新会话。旧版日志的历史错误不能当作本次启动失败。
6. 仅在第 1–5 步均通过后，处理明确已退役的桌面包或可再生缓存；会话、认证、配置、非仓库负责的技能和人工备份不在此步骤内。

## 迁移与恢复

迁移到新机器时，先复制 Git 仓库并执行隔离安装验证，再迁移 Hermes Home 的受保护数据。
迁移时保持配置、认证、`state.db`、`$HERMES_HOME/sessions/` 和用户技能的相对关系；凭据不得进入
Git、压缩日志或项目文档。恢复后先运行 `hermes config check`、`hermes auth list` 和
workflow doctor，再启动桌面。

若桌面启动异常，优先检查快捷方式是否指向当前包、是否只有一个 Hermes 父进程以及
后端端口是否监听在 `127.0.0.1`。不要通过删除 `%APPDATA%\\Hermes`、会话库或
`%LOCALAPPDATA%\\hermes` 来“重置”；先创建带日期的可恢复副本，再定位问题。
