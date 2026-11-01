# Workflow-assistance 阶段交接（2026-07-23）

> 这是 `Workflow-assistance` 的无密恢复摘要。它记录已验证的工作流资产与恢复顺序，不保存 API key、OAuth、`.env`、auth 文件、会话数据库、日志或用户数据。恢复时以当前用户意图、现场 Git、live Hermes 和 GitHub CI 为准。

## 项目身份与边界

- 本地仓库：`D:\All projects\Workflow-assistance`
- 云端仓库：`DTALEX66/Workflow-assistance`
- 职责：Hermes Agent、CC Switch、Codex、GitHub 的可迁移工作流增强资产 source-of-truth；GitHub 同时是跨设备 SSOT、发布与 exact-SHA CI 证据面。
- 不承担：Hermes/CC Switch/Codex 安装主体、业务项目 runtime、业务数据、凭据、会话或日志。
- E 盘：默认禁止访问、读取、移动、修改或删除；必须由用户在当前请求精确授权路径与操作。
- 项目执行数据：必须留在 `<project>/.project-local/` 下的受忽略目录；禁止把 cache、测试输出、日志、artifact、任务状态写到项目根外或用户 Temp。

## 当前已发布基线

交接文档中的静态 SHA 会在下一次提交后失效，因此不把它当作恢复事实。GitHub `main` 是跨设备 SSOT；恢复前必须执行：

```bash
git fetch --prune origin
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
```

只有本地 HEAD 与 `origin/main` 相同、工作树状态符合当前任务时，才能把该事实当作有效基线。

## 已落地的增强

### 安全与项目数据边界

- `project-data-boundary` 规则要求项目任务 runtime、cache、logs、artifacts、测试输出均锁在项目内 `.project-local/`。
- 显式项目根外 output/cache/log 参数 fail-closed。
- E 盘保护已写入 skill、模板、测试与同步资产。
- 清理遵循：验证 → 发布 → exact-SHA CI → 目标分支确认 → 摘要 → 清理；不按目录名、体积或日期盲删。

### 可移植工作流

- `run_taskpack_agent.py` 要求显式 `--remote-ref`。
- TaskPack 默认不发布；只有 `--publish` 才允许 commit/push/PR/CI。
- `sync_hermes_workflow_assets.py` 是 repo → live Hermes 的唯一受控同步路径；先运行不带 `--apply` 的 dry-run，审查 ownership/drift 和目标路径，再在明确授权后 `--apply`。它保留 live provider/model、凭据、私有 MCP 与用户命令，不得用手工复制替代。
- 默认 MCP 为 Context7；其他 MCP 只在完成审计与 smoke 后按需启用。

### 模型与 Windows 环境

- 当前受控模型 lanes：Kimi K3/K2.7 Code/K2.7 HighSpeed，DeepSeek V4 Pro/V4 Flash，ChatGPT 5.6 Sol/Terra/Luna。
- Windows 不得假设 `python` 与 `python3` 指向同一解释器；仓库工作流使用 `python` 或显式 venv 解释器。
- `windows-development-environment` 只负责 Windows shell、解释器、路径、编码、子进程、本地服务器、Git 和 canonical workflow deployment 边界；便携 Scoop/Rust 工具链迁移不属于该 skill。

### 清理与运行时状态

- 已删除引用退休 `cognitive-loop-os` skill 的暂停 sleep cron；恢复时不要重建项目专属全局 cron。
- live managed skills 已通过 source-to-live 文件哈希比对；后续同步或运行环境变化后必须重新验证。


## 推荐恢复顺序

1. 阅读本文件、当前 `AGENTS.md` 与 `docs/workflow/project-definition.md`。
2. 复核现场 Git/远端关系；不要依据旧会话声称分支或 CI 仍然有效。
3. 对修改先读取相关 source 与测试；禁止读取或输出凭据文件。
4. 对本仓库改动运行：

   ```bash
   python scripts/workflow/run_quality_gate.py verify
   git diff --check
   ```

5. 对需部署到 live Hermes 的受控资产，先运行 dry-run：

   ```bash
   REPO_ROOT="$(git rev-parse --show-toplevel)"
   HERMES_HOME="${HERMES_HOME:?Set HERMES_HOME to the intended Hermes Home}"
   python scripts/workflow/sync_hermes_workflow_assets.py \
     --repo "$REPO_ROOT" --home "$HERMES_HOME"
   ```

   只有 dry-run、drift 审查和 backup 确认通过，并获得明确授权后，才运行 `--apply`；apply 后执行 `hermes config check` 和定向 runtime 验证。

6. 用户要求上传时：扫描暂存候选中的 secrets/二进制/runtime 文件，记录 `git write-tree`，提交、推送、核验 `origin/main` exact SHA，并等待对应 GitHub Actions。

## 会话与上下文卫生

- 长上下文先生成这类无密、项目内的交接文档；不要把 `state.db`、完整日志或原始会话转存进仓库。
- 当前会话的上下文压缩只能由当前 Hermes UI/会话触发；使用 `/compress`，或新开会话并以本交接文档为恢复入口。
- 不要把磁盘清理误认为能缩小当前模型上下文；它们是不同问题。
- `.project-local/artifacts/` 是受忽略的项目内运行区。仅在证据不再被测试、发布、CI、恢复或活跃任务引用后，才可清理其中可再生产物。
