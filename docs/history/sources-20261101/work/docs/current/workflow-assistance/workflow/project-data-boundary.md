# 项目任务数据边界

## 目的

先判定真实数据所有权，再判定存储路径。属于项目的临时文件、缓存、日志、测试环境和可再生产物必须随项目保存，避免泄漏到 Windows `%TEMP%`、用户目录、桌面或 `Hermes Home`。Hermes/Codex/CC Switch/GitHub 编排数据属于工作流基础设施；仅凭项目名、文件名或 prompt 不能证明归属，归属不明的外部文件不得删除或移动。项目数据标准根目录是：

```text
<git-project>/.project-local/runs/
```

此目录必须被 Git 忽略。长期恢复证据使用同项目的 `.project-local/artifacts/`，而不是另建用户目录。

`E:\` 是用户保护的数据区。默认禁止枚举、读取、复制、写入、移动、重命名或删除其任何内容；只有当前请求中明确给出的精确路径与操作范围可获一次性授权，且读取授权不包含写入、移动或删除。

## 可部署执行器与强制 gate

仓库的 `packages/client-neutral-core/bin/hermes-project-data.py` 与 `packages/client-neutral-core/bin/hermes-project-terminal-guard.py` 会随 `sync_hermes_workflow_assets.py --apply` 部署到 `$HERMES_HOME/bin/`。

默认 Hermes profile 配置了官方 `pre_tool_call` shell hook：对于 `terminal` 工具，它会 fail-closed 地拒绝以下情况：缺少显式 `workdir`、workdir 不是 Git 项目、未通过 wrapper 启动、wrapper 未以 `--project .` 固定到 workdir，或 shell 链式命令。新 Desktop/Gateway/CLI 会话生效；现有进程需 `/reset` 或重启。

所有可写命令必须使用：

```bash
python "$HERMES_HOME/bin/hermes-project-data.py" --project . check
python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- python -m pytest
```

该 helper 会：

- 以 `git rev-parse --show-toplevel` 确定实际项目根；
- 用 `git check-ignore --no-index` 验证 `.project-local/runs/` 被忽略，不满足则 fail-closed；
- 拒绝解析后落在项目根外的 helper 路径及符号链接逃逸；
- 在子进程启动前创建并注入项目内 `TMP`/`TEMP`/`TMPDIR`、Python bytecode、pip、uv、npm/yarn、Playwright、Cargo home/target、Rust target、Ruff/mypy/pre-commit cache 位置；
- 提供受控的 `.project-local/runs/logs/`、`.project-local/artifacts/` 目录供脚本显式使用；
- 将 `HERMES_KANBAN_HOME` 固定到 `<project>/.project-local/`。

```bash
python "$HERMES_HOME/bin/hermes-project-data.py" --project . init
python "$HERMES_HOME/bin/hermes-project-data.py" --project . kanban -- boards list
```

### 收尾清理

任务成功后，先把需要长期保留的 handoff、审查结果和验证证据移入同项目 `.project-local/artifacts/`，再运行：

```bash
python "$HERMES_HOME/bin/hermes-project-data.py" --project . cleanup
```

默认只清除 `task-runtime` 中的 `tmp`、`logs`、`artifacts` 和 Python bytecode，保留项目内依赖缓存以避免每一轮重新下载。确认不再需要加速缓存时，才使用：

```bash
python "$HERMES_HOME/bin/hermes-project-data.py" --project . cleanup --all-regenerable
```

失败任务不得自动擦除现场；应保留项目内证据，修复或人工确认后再清理。

## 边界与例外

这是一层 Hermes 工具调用 gate 和子进程环境隔离，不是 OS sandbox。正常路径是启动前把工具环境绑定到项目目录；只有独立于 Hermes 启动、绕过 `terminal` 工具或硬编码项目外绝对路径的程序才会脱离这层绑定，guard 对已知历史外溢路径提供 fail-closed 兜底。若需要对不可信程序提供真正的文件系统隔离，必须使用隔离 Windows 账户、Windows Sandbox/VM 或配置完成并验证的容器后端；本机当前未安装 Docker，不能把容器隔离虚报为已启用。

以下内容属于 Hermes 自身的全局服务状态，不能为了“归档项目数据”而移动或删除：认证/凭据、`state.db` 会话库、全局配置、全局技能、原生 cron 调度元数据和已安装运行时。`state.db` 是当前桌面会话与跨项目搜索的共享事实库，必须通过官方 session retention/auto-prune 维护，不能将每个项目会话库粗暴拆分。

Kanban 是例外：Hermes 原生支持 `HERMES_KANBAN_HOME`，因此所有项目 task board 都必须经本 helper 启动并落入 `<project>/.project-local/`。Cron job 定义与其调度输出当前由 Hermes Home 统一管理；每个项目 cron 的 `workdir` 和执行命令仍必须指向项目，并使用本 helper 写入项目内 evidence。无活动 cron job 时，已确认归属某项目的孤儿输出可以先复制、hash 校验后归档至该项目 `.project-local/artifacts/`。

## 迁移规则

1. 先确认没有活动 writer、后台任务或活动 cron job。
2. 以文件名、Git workdir、内容中的项目路径、时间和 hash 追踪归属。
3. 对需要保留的 handoff、review、package 或 cron output：复制到所属项目 `.project-local/artifacts/`，逐文件校验大小和 SHA-256 后才删除原件。
4. 对 venv、wheel、临时 clone、pytest cache、test container 和诊断临时文件：记录大小/归属后直接清理，不把可再生数 GB 副本迁入项目。
5. 无法归属或涉及秘密的数据不移动；先人工判定。

## 项目模板要求

新项目的 `.gitignore` 必须含 `.project-local/`；`packages/client-neutral-core/templates/agent-rules/AGENTS.md` 与 `CODEX.md` 要求 Agent 在产生运行数据时使用上述 wrapper。
