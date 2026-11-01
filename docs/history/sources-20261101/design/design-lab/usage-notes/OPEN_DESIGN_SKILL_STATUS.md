# Open Design 技能/连接器可用性状态

本记录用于区分 Open Design / Codex 当前能确认的能力状态，避免把“文件存在”“连接器可见”“系统技能已自动触发”混为一谈。

> 证据边界：本文是历史只读记录，不是当前 live Host 运行证据。文中外部路径、端口、配置和技能枚举均需在对应 Host 启动后重新验证；本轮仅审计 DESIGN-LAB 仓库，未访问这些外部路径、未启动 Open Design、未执行真实任务。

记录日期：2026-07-04（历史记录；当前状态以 live requalification 为准）

## 结论摘要

不能说“全部都已作为正式技能自动调用”。当前应分三类描述：

| 类别 | 状态 | 当前可说法 |
|---|---|---|
| 当前会话可用连接器/工具 | 已可用 | 可以按当前会话暴露能力调用 |
| 本地 `.od-skills` 技能文件 | 存在且可读 | 可以确认文件存在、内容可读、权限根已覆盖 |
| Codex 自动技能注册/自动触发 | 未确认 | 不能宣称已经像系统技能一样自动触发 |

## 1. 已在当前会话可用的连接器/工具

这些能力按当前会话暴露状态可归为“可用”：

```text
imagegen
openai-docs
browser:control-in-app-browser
GitHub 连接器
AnyPDF 连接器
node_repl
```

注意：这些是当前会话/运行环境暴露能力，不等同于 Open Design daemon API 已重新枚举出的注册表。

## 2. 本地已存在且可读取的 `.od-skills`

当前发现并确认可读的 `.od-skills` 路径：

```text
D:\All projects\35d917c5-aef6-4c4f-b0d4-8d36c07dcc28\.od-skills
D:\All projects\Obsidian-Assistance\Obsidian - Front-end Assistance\.od-skills
```

这些目录下发现的技能：

```text
creative-director
impeccable-design-polish
```

当前可确认：

- `.od-skills` 目录存在。
- 对应技能目录存在。
- `SKILL.md` 文件可读取。
- Codex 权限根已覆盖到 `D:\All projects` 和自动发现到的 `.od-skills` 精确路径。
- PowerShell 使用环境变量 + `-LiteralPath` 可以只读读取这些目录。

当前不能确认：

- 它们已经被当前 Codex 会话注册为正式系统技能。
- 它们会像 Hermes skill / 系统 tool 一样自动触发。
- Open Design daemon 已把它们加载进运行时技能注册表。

## 3. 尚未确认自动注册/自动触发的原因

检查时 Open Design 本地 daemon 端口未开放：

```text
5294 unreachable
5499 unreachable
```

因此无法通过本地 API 读取运行时技能/插件/连接器注册表。

只读探测已确认 Open Design app config 的关键项正常：

```text
agentId = codex
agentModels.codex.model = gpt-5.5
agentCliEnv.codex = CODEX_BIN + CODEX_HOME
projectLocations 包含 D:\All projects
projectLocations 包含 D:\All projects\DESIGN-LAB
defaultProjectLocationId = loc_open_design_assistance
```

## 建议表述

推荐说法：

> Open Design / Codex 的基础调用链和目录权限基本恢复；`.od-skills` 里的 `creative-director` 与 `impeccable-design-polish` 本地存在且可读。但目前不能宣称它们已经作为当前 Codex 会话的正式自动技能注册并自动触发。需要在 Open Design 启动后，通过 daemon/API 或一次真实任务调用确认。

不要说：

> 全部 Open Design 新技能已经作为正式技能自动调用。

## 后续确认步骤

1. 用代理启动器打开 Open Design：

```text
D:\Programs\Open Design\Open Design - GPT Codex Proxy.bat
```

2. 找到 daemon 端口，常见为：

```text
5294
5499
```

3. 查询 app config 和可能的运行时注册端点：

```bash
curl http://127.0.0.1:<port>/api/app-config
curl http://127.0.0.1:<port>/api/skills
curl http://127.0.0.1:<port>/api/plugins
curl http://127.0.0.1:<port>/api/connectors
```

4. 如果 API 没有技能注册表端点，则通过一次真实 Open Design → Codex 任务确认：

```text
请使用 creative-director 评估当前画布，并给出 3 个视觉方向。
请使用 impeccable-design-polish 对当前 UI 做最后 20% 精修建议。
```

只有出现明确的运行时加载/调用证据后，才能把对应项从“本地可读”升级为“运行时已注册/可自动触发”。

## PowerShell `.od-skills` 读取注意

不要裸写带空格路径：

```powershell
Get-ChildItem D:\All projects\xxx\.od-skills
```

推荐：

```powershell
$env:OD_SKILLS_PATH = 'D:\All projects\xxx\.od-skills'
Get-ChildItem -LiteralPath $env:OD_SKILLS_PATH -Force
```

Node 只读 fallback：

```bash
node -e "const fs=require('fs'); console.log(fs.readdirSync(process.env.OD_SKILLS_PATH))"
```
