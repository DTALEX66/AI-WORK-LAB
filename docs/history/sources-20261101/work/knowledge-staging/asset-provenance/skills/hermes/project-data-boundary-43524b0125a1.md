---
name: project-data-boundary
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/project-data-boundary/SKILL.md
---

---
name: project-data-boundary
description: "将 Agent 任务的临时文件、缓存、日志与产物锁定在当前 Git 项目的忽略目录；用于执行、审查、睡眠模式和修复任务。"
version: 1.2.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [project-boundary, task-data, temp, cache, containment, hooks]
    related_skills: [sleep-mode, agent-workflow-fortress, hermes-agent]
---

# 项目任务数据边界

## 触发条件

当任务会生成临时文件、缓存、测试环境、日志、评审报告、下载物或运行时产物时加载。先判定数据所有权，再选择路径；**当前 Git 项目只有在数据确实属于该项目时才是目标**。Hermes/Codex/CC Switch/GitHub 编排数据属于工作流基础设施，不因文件名包含项目名而迁移进业务项目；归属不明的外部文件不得删除或移动。

## 强制边界

1. 先确定 Git 根目录；没有 Git 根目录则停止，不猜测输出位置。
2. 所有可再生产出的任务数据都必须落入：

   ```text
   <project>/.hermes/task-runtime/
     tmp/
     cache/
     logs/
     artifacts/
     pip-cache/
     pycache/
   ```

3. `.hermes/` 必须被 Git 忽略；否则 helper fail-closed，先由项目维护者加入忽略规则或在本地 Git exclude 中显式隔离。
4. 禁止把项目产物写到 `%TEMP%`、`~/.cache`、`~/.hermes/tmp`、桌面、用户 Home 或另一个项目。Hermes 的认证、会话数据库、配置、全局技能和 scheduler 元数据仍是**全局运行时状态**，不是项目产物，不能移动或删除。
5. Hermes Kanban 原生支持 `HERMES_KANBAN_HOME`，因此项目任务板不是全局状态：必须经本 helper 运行，固定落入 `<project>/.hermes/`；不得直接使用未固定 board root 的 `hermes kanban`。
6. 显式绝对路径会绕过任何环境变量；执行前必须拒绝项目根外的 output/cache/log 参数。此 helper 不是 OS sandbox，不能把任意恶意/错误子进程伪装成安全。
7. Windows 上先由 wrapper 把临时文件、缓存、构建输出和日志重定向到当前项目的 `.hermes/task-runtime/`；`D:\\\\a`、`D:\\\\d`、`D:\\\\dev`、`D:\\\\tmp` 只是历史外溢/暂存根，不是新输出位置。只有显式硬编码这些路径、绕过项目环境注入时才 fail-closed，并提示改用项目目录。
8. `E:\\` 是用户保护的数据区：默认禁止枚举、读取、复制、写入、移动、重命名或删除其任何数据。只有用户在**当前请求**中明确给出精确路径和操作范围时才可访问；授权按路径和本次任务限定，读权限不等于写/移动/删除权限，任务结束即失效。

## Hermes terminal gate

默认 profile 的 `hooks.pre_tool_call` 应匹配 `terminal` 并指向 `$HERMES_HOME/bin/hermes-project-terminal-guard.py`。该 hook 必须 fail-closed：要求每个 terminal call 有显式 Git-project `workdir`，且只有单个 `hermes-project-data.py --project . <subcommand>` 调用可通过；拒绝 raw command、非 Git workdir、错误 project 参数和 shell chaining。

配置/脚本变更后执行 `hermes hooks doctor`。若提示 hook 脚本在授权后变化，先 `hermes hooks revoke <command>`，再用 `hermes --accept-hooks` 启动一次新会话重新授权。Desktop/Gateway 已运行进程需 `/reset` 或重启才能注册新 hook。

### guard.py 正则防护三坑（2026-08-14 已修，PR #89/#90）

`hermes-project-terminal-guard.py` 的正则防护有系统性缺陷，多维度测试时暴露：

1. **路径穿越绕过（严重）**：`RAW_PARENT_TRAVERSAL` 用 lookbehind `(?<=[\s"'=<>:([{])` 要求 `..` 前面是空白，导致路径**中间**的 `../`（`scripts/../../secret.txt`、`./../x`、`ls ..`、`cat ..`）漏检。修复：去掉 lookbehind，改 `\.\.(?:[\\/]|(?=[\s"']|$))`。
2. **含空格路径误拦**：`[^\s"']+` 遇空格截断，把项目内 `"D:/All projects/WORK-LAB/x.py"` 截成 `D:/All`、`/All` 误判越界。修复：`external_raw_*` 对"candidate 是项目字符前缀"跳过，`external_child_path` 优先用 shlex 完整 token 精确判断（注意 `Path.is_relative_to` 是路径段判断，含空格前缀要用字符串 `startswith`）。
3. **scheme:// URL 误拦**：盘符正则 `[A-Za-z]:[\\/]` 把 `https://` 的 `s://` 误当 `s:\` 盘符；`ABSOLUTE_PATH` 分支3 缺 `(?!/)` 且 lookbehind 含 `:`，把 `https:` 后的 `/` 当 POSIX 路径。修复：盘符正则后加 `(?!/)`，分支3 对齐 `RAW_POSIX` 补 `(?!/)`。

**机制**：guard.py 是每次 terminal 调用时 spawn 的独立进程（从磁盘重读），改脚本**即时生效、无需重启**；与 `web_server.py start_server()` 里注册 hook 的补丁（需重启进程）不同。

**测试铁律**：改 guard 正则后必须跑"应拦 + 应放"双向矩阵（E盘/外溢/穿越/串联/裸命令应拦；git/pytest/项目内脚本/含空格路径/scheme URL 应放），单方向测试会漏掉"误拦正常操作"。

## 标准执行器

部署包会把 `bin/hermes-project-data.py` 同步到 `$HERMES_HOME/bin/`。对会产生数据的命令，先检查再经 wrapper 启动：

```bash
python "$HERMES_HOME/bin/hermes-project-data.py" --project . check
python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- python -m pytest
```

`run` 会在子进程启动前创建并注入项目本地路径：`TMP`、`TEMP`、`TMPDIR`、`XDG_CACHE_HOME`、`PIP_CACHE_DIR`、`UV_CACHE_DIR`、npm/yarn、Playwright、`CARGO_HOME`、`CARGO_TARGET_DIR`、Rust target、Ruff/mypy/pre-commit cache、`PYTHONPYCACHEPREFIX`、`HERMES_KANBAN_HOME`、`HERMES_PROJECT_RUNTIME_ROOT`、`HERMES_PROJECT_ARTIFACTS`、`HERMES_PROJECT_LOGS`。子工具不应自行选择用户级或根目录临时路径。

初始化策略并运行项目本地 Kanban：

```bash
python "$HERMES_HOME/bin/hermes-project-data.py" --project . init
python "$HERMES_HOME/bin/hermes-project-data.py" --project . kanban -- boards list
```

## 审计与恢复

- 开始长任务前运行 `check`；它会验证 Git 根和 ignore 边界，并创建受控目录。
- 成功任务收尾：先将必要 handoff、review 和恢复证据写入同项目 `.hermes/task-artifacts/`，然后运行 `python "$HERMES_HOME/bin/hermes-project-data.py" --project . cleanup`。默认清除 `tmp/logs/artifacts/pycache`，保留依赖缓存；仅在确认无须加速缓存时传 `--all-regenerable`。
- 失败任务不得自动擦除现场；其项目内 runtime data 是可审计、可恢复的，不应因“自动清理”丢失根因证据。
- 外部遗留物先按内容、Git workdir、任务名称和时间追踪归属；先复制并校验 hash，再删除原路径。无法可靠归属的内容不得移动到错误项目，也不得删除。
- 外部恢复必须在 `<owner>/.hermes/task-artifacts/external-recovery-<date>/` 生成 `HANDOFF.md` 和机器可读 manifest；不得覆盖目标，不得跟随 symlink、junction 或 Windows reparse point；只有逐文件大小与 SHA-256 回读通过后才能删除精确源路径。
- Cargo target、Python runtime、`pycache`、pytest 临时树和工具缓存属于可再生数据，不是持久交接证据；仅在活跃进程检查和精确删除后复扫均通过时清理。普通删除遇到深路径错误时，可对已证明安全的精确根使用 Win32 extended-length (`\\?\\`) 路径，但不得绕过 ACL 或跟随 reparse point。
- 若发现全局 Hermes Home 中已有明确归属项目的 Kanban board：先确认 Gateway 已停止、board 没有 running task/worker；复制到 `<project>/.hermes/kanban/`，逐文件校验大小和 SHA-256，使用 `hermes-project-data.py kanban` 实读 board/task 后，才删除全局副本与其 stale current 指针。迁移 manifest 必须留在项目 `.hermes/task-artifacts/`。

- cron 的 Hermes 原生 job 元数据/输出由 Hermes Home 管理；项目任务应在 prompt 中使用 `workdir=<project>`，并将任务证据写回项目 `.hermes/`。不要直接篡改 Hermes cron 数据库；启用有限 `cron.output_retention`，并按项目归档确定归属的孤儿输出。
- `state.db` 是跨项目桌面会话与搜索的共享库，不能按项目拆分或盲删；使用官方 session retention/auto-prune 管理结束会话。同步器产生的备份只可清理其自身有命名前缀的已验证旧副本，必须保留至少两份，绝不触碰用户 pre-update/recovery backup。
