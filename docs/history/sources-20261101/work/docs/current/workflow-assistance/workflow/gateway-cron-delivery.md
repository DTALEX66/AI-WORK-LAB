# Gateway、Cron 与 Sleep Mode 投递边界

本文记录 Workflow-assistance 对 Hermes Gateway、cron job 与 sleep-mode 的投递/通知边界。目标是避免把“Gateway 进程运行”“消息平台已配置”“当前 TUI 会收到通知”混为一谈。

## 状态分层

| 层级 | 能证明什么 | 不能证明什么 | 常用检查 |
|---|---|---|---|
| Gateway process running | Gateway 进程在跑；cron/kanban dispatcher 可借此运行 | Telegram/Discord/Email 等外部消息通道已可用 | `hermes gateway status`、`hermes status --all` |
| Messaging platform configured | 至少一个外部平台有 token/allowlist/policy 配置 | 当前 cron 一定会发到该平台 | `hermes gateway setup`、`/platforms`、gateway 日志 |
| Cron job active | scheduler 中有 job；可按 schedule 执行 | 当前 TUI/桌面会话会收到实时推送 | `hermes cron list`、`cronjob(action="list")` |
| Sleep mode state active | 项目账本声明队列活跃 | job 一定存在或正在运行 | `.project-local/sleep-mode/state.json` + `hermes cron list` |
| TUI current session loaded | 当前对话可继续交互 | 后台 job 会自动回到这个窗口 | `/status`、`/agents`、session 状态 |

## TUI / Desktop 本地使用

在 Hermes TUI 或 Desktop 中，若没有配置任何消息平台，Gateway 仍可能正常运行：

```text
Gateway process running
No messaging platforms enabled
Gateway will continue running for cron job execution
```

这不是错误。它表示：

- Gateway 可以为 cron、kanban dispatcher 等后台系统服务；
- 没有 Telegram/Discord/Slack/Email 等外部投递目标；
- 本地 TUI 不是可靠的 cron delivery channel；
- cron 或 sleep-mode 的结果应从 job 输出、项目账本或日志读取。

本仓库运行在 Hermes TUI 时，不要承诺 `deliver=origin` 或默认 delivery 会实时发回当前 TUI 窗口。

## Cron delivery 规则

| 目标 | 推荐配置 | 说明 |
|---|---|---|
| 只需本机保存结果 | `deliver` 省略或 local-only | TUI 中默认不会实时弹回当前对话；用 `hermes cron list` / `cronjob list` 查输出 |
| 需要手机/群聊提醒 | 配置 Gateway 平台后设置 `deliver='telegram'` / `deliver='discord'` / `deliver='all'` | 必须先完成平台 token、allowlist、policy 配置 |
| 需要后续可对话 | `attach_to_session=true` | 仅对有投递会话的 gateway 平台最有意义；TUI local-only 仍以 job/state 为准 |
| 项目长期推进 | sleep-mode 创建项目级 cron job | 每轮只做一个 bounded task，结果写入 `.project-local/sleep-mode/` 与 `.project-local/artifacts/` |

## Sleep mode 输出位置

`sleep-mode` 不以聊天窗口作为唯一状态源。每个项目必须保留自己的账本：

```text
<project>/.project-local/sleep-mode/
  state.json
  activity.jsonl

<project>/.project-local/artifacts/
  ...核验证据、handoff、报告...
```

恢复或排查时按这个顺序看：

1. `git status --short --branch` 确认 checkout 状态；
2. `.project-local/sleep-mode/state.json` 确认 mode、job_id、baseline/head；
3. `.project-local/sleep-mode/activity.jsonl` 看最近状态迁移；
4. `hermes cron list` 或 `cronjob(action="list")` 确认 scheduler 里是否还有对应 job；
5. `.project-local/artifacts/` 查真实证据；
6. Gateway 日志只用于确认投递/平台问题，不作为任务完成证明。

## Gateway setup 什么时候需要

不需要配置消息平台的情况：

- 只在本机 TUI/Desktop 里交互；
- 只需要 cron 在本地保存输出；
- 只需要 sleep-mode 通过项目账本恢复；
- 不需要手机、群聊或邮件提醒。

需要配置消息平台的情况：

- 希望 sleep-mode / cron 主动通知你；
- 希望远程发消息给 Hermes；
- 希望 job delivery 进入 Telegram/Discord/Slack/Email 等通道；
- 希望 `attach_to_session=true` 的 recurring job 能在同一外部会话里继续对话。

配置入口：

```bash
hermes gateway setup
hermes gateway status
```

配置完成后在对应平台内运行 `/platforms` 或发送一条测试消息确认 routing。不要把 bot token、平台 token、allowed user id 或 webhook secret 写入本仓库；真实值只放 live `.env` / 平台配置。

## 忙时输入策略

Workflow-assistance portable config 固化：

```yaml
display:
  busy_input_mode: queue
```

含义：当前 Hermes 忙时，新输入默认排队到下一回合，而不是打断当前 turn。需要取消时显式使用：

```text
/interrupt
```

这个设置只能降低“忙时新输入打断”的概率；它不会把普通前台 turn 变成持久任务。跨新会话/重启仍需要 cron、sleep-mode 或独立后台进程。

## 标准说法

- “Gateway running” 不等于“Gateway setup complete”。
- “Cron job active” 不等于“当前 TUI 会收到消息”。
- “Sleep mode active” 必须同时有 project state 与 scheduler/job 证据。
- “任务完成” 必须有测试、日志、artifact、Git/CI 或项目账本证据；delivery 成功不是完成证据。
