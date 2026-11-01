---
name: sleep-mode
description: "为当前项目启动、恢复或停止可持续自动推进的单写者任务队列；由用户说‘开启睡眠模式’和‘停止任务’触发。"
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [sleep-mode, durable-queue, cron, autonomous, project-workflow, evidence]
    related_skills: [hermes-agent, agent-workflow-fortress, plan, project-data-boundary]
---

# 项目睡眠模式（持久自动推进）

## Trigger

- **Start:** 用户说“开启睡眠模式”“自动推进当前项目”“一直执行直到停止任务”。
- **Stop:** 用户说“停止任务”“停止睡眠模式”“暂停当前项目任务”。
- **Status:** 用户问“睡眠模式状态/进度”。

“当前项目”必须是当前工作目录的 Git 根目录；若不是 Git 仓库，先创建或询问项目路径。每个项目只允许一条活跃写队列。

## Durable state contract

所有控制产物只可写入 Git 忽略的项目目录；任何测试、缓存、日志或 review 产物还必须经 `project-data-boundary` 的 wrapper 落入 `.hermes/task-runtime/`：

```text
.hermes/sleep-mode/
  README.md
  state.json
  activity.jsonl
```

`state.json` 至少包括：

```json
{
  "schema_version": 1,
  "project_root": "...",
  "mode": "active|paused|blocked|stopped|completed",
  "job_id": null,
  "run_id": null,
  "active_task": null,
  "last_completed_task": null,
  "baseline_head": null,
  "last_head": null,
  "last_evidence": null,
  "failure_streak": 0,
  "stop_reason": null,
  "updated_at": "ISO-8601"
}
```

每次状态迁移都向 `activity.jsonl` 追加一条精简、脱敏的 JSON；不得写入凭据、原始日志或用户数据。

## 启动协议

1. **先发现，后调度。** 读取项目规则、Git 状态/分支/HEAD/远端关系、活跃 writer 进程、路线图或 handoff、失败的 CI/测试，以及已有 `.hermes/sleep-mode/state.json`。
2. **拒绝并发 writer。** checkout 脏、有旧任务运行、其他 Agent 拥有 checkout，或 state 为 `blocked` 时，不得再启动第二个 writer；报告精确阻塞原因。
3. **创建或更新状态。** 记录项目根目录、baseline HEAD、时间戳，并将 mode 设为 `active`。
4. **启用持久调度。** 仅在用户明确请求睡眠模式时，若 Hermes Gateway 未运行则安装/启动其用户服务。每个项目只创建一条循环 cron job（推荐 `every 30m`），带 `workdir=<project root>`、`attach_to_session=true`，并要求新会话先读取状态账本。
5. **每轮契约。** 每个 cron cycle 必须：
   - 验证自己仍拥有 checkout 且 mode 为 `active`；
   - 基于 live Git/CI/roadmap 选择**恰好一个**依赖就绪、真实且有证据的任务；
   - 加载相关 skill，只实现或调查该有界任务；
   - 运行对应测试/门禁并写入证据；
   - 仅当项目策略和用户授权允许时 checkpoint/commit/push；
   - 原子更新 state 与 activity；
   - 首个未解决门禁失败时 stop/block。
6. **可见证明。** 立即报告项目路径、job ID、首个任务、baseline HEAD 与状态文件路径。job ID 本身不是运行证明；须同时给出首个真实任务/证据。

## 从本地睡眠引擎吸收的通用安全契约

以下是可跨项目复用的治理规则，而不是移植某个项目的 FastAPI/SQLite/PM2 实现：

- **完成必须有证据。** `done` 只能在实际工具结果含可核验路径、测试/lint 结果、检索条目/计数、Git/CI artifact 等证据时写入；`echo`、心跳、上下文构建、任务生成、dry-run、preview 和重复旧报告都不计入进度。
- **有界执行。** 每轮只处理一个有依赖证据的任务；默认不重复种子任务。必须限制单任务超时、重试次数、衍生任务数量和总运行时长，避免无界队列或无限循环。
- **失败熔断。** 单任务先按有限次数重试；连续失败达到项目预设阈值、任务超时、账本不可写、资源异常或高风险门禁时，原子标记 `blocked` 并暂停对应 cron，而不是继续制造失败输出。
- **失败保留现场。** 不自动删除项目内失败日志、TaskPack、状态和证据；只清除确认可再生的 `task-runtime` 数据。成功任务在归档必要证据后执行项目 wrapper 的 `cleanup`。
- **禁止自产生永久工作。** 队列清空应进入 `completed`，除非用户明确声明重复/持续目标，并同时给出最大轮次或时间上限。

不要迁入项目特有的 HTTP endpoint、SQLite 表、PM2 daemon、`kb_search/mk_search/safe_write` executor 名称、产品数据路径或项目专属风险正则。Hermes 睡眠模式的唯一调度器仍是原生 cron，不增加第二个常驻 worker。

## 默认边界

可自动执行：live-state 对账、只读审查、范围明确的低风险实现、定向测试/lint、项目本地文档；只有当项目既定工作流允许时才创建 checkpoint commit。

必须阻塞并等待用户或独立门禁：凭据处理、破坏性清理、force push/历史重写、merge、生产写入、数据库/Schema migration、权限或认证变更、依赖变更、部署/发布、GitHub approval，以及任何影响不明确的任务。

## Cron worker prompt 必备项

循环任务 prompt 必须自包含以下边界：

- 精确项目根目录和 state 文件路径；
- 不得访问项目根目录以外的路径，不得读取用户 Vault 或无关仓库；
- one writer, one bounded task per cycle；
- 由 live Git/CI/roadmap 证据决定下一任务；过期任务清单仅可作为输入；
- 将任务选择、文件路径、命令结果、HEAD、证据和 stop/block 原因写入账本；
- 若 `mode != active`、发现并发 writer、接管前 checkout 已脏、证据不充分，或出现高风险门禁，立即停止；
- 不得伪造完成；未经用户明确授权不得 merge/release/执行破坏性 Git 操作。

## DAG 编排（多任务依赖，2026-08-12 吸收）

单写者队列是所有权纪律，不禁止有依赖的并行。任务多且有显式依赖时按 DAG 推进：

1. 任务卡声明 `depends_on: [task-id]`（显式依赖，禁止隐式顺序猜测）。
2. 调度器按拓扑序推进：无依赖的任务分支可并行（各占独立 worktree，
   沿用隔离 writer 机制）；有依赖的任务等依赖 verdict 落账后才开始。
3. 依赖未落账不算满足（"看起来相关"不是依赖边）。
4. 并行分支以 PR squash 顺序合入 main，绝不并发 push。
5. 会话心跳：活跃 writer 注册 owner/pid/heartbeat；超时回收，
   不因陈旧锁判定他人死锁。

## 停止协议

用户说“停止任务”或同义表达时：

1. 读取项目 `state.json`，用其中 `job_id` pause/remove 对应 cron job。
2. 不得盲目 kill 正在运行的 writer。先取得 run/session 状态并请求优雅停止，再以精确 reason 标注 `paused` 或 `stopped`。
3. 保留所有未提交工作并报告 Git status；停止流程中不得 reset/clean/restore。
4. 用 `hermes cron list` 验证该项目没有活跃 job。

## /reset 后恢复

读取 `state.json`、`activity.jsonl` 尾部、项目 handoff、Git status/HEAD/远端关系和 `hermes cron list`。不得仅凭旧 job ID 推断队列仍活跃。若 state 为 active 但 job 不存在，应报告 `paused: scheduler missing`，不得静默创建重复任务。

## 完成标准

单轮完成必须在账本中记录真实证据：变更路径加测试/lint 结果、已核验的报告路径，或精确 Git/CI artifact。整体队列只在用户明确停止、被阻塞，或已无证据支持的下一真实任务时结束。
