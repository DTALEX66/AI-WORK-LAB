# MINIGAME Design-system｜Open Design 前端设计工作区

本目录是 MINIGAME 的独立设计系统工作区，以 **Open Design 软件** 作为前端设计界面，Hermes 作为设计主控，Codex/GPT 作为实现与生成执行器。

## 一句话定位

```text
Open Design = 前端设计界面 / 主窗口设计平台 / 视觉产物工作台
Hermes      = 设计主控 / 任务路由 / 规则维护
Codex GPT   = 代码与生成执行器
MINIGAME    = 最终游戏运行项目
```

本项目不直接替代 `D:\All projects\MINIGAME` 的游戏代码；它负责输出可被 MINIGAME 消费的设计协议、UI Schema、Design Tokens、设计任务单、Open Design 提示词和视觉验收标准。

## 推荐启动方式

从桌面快捷方式启动 Open Design：

```text
C:\Users\admin\Desktop\Open Design - GPT Codex Proxy.lnk
```

或直接运行：

```text
D:\Programs\Open Design\Open Design - GPT Codex Proxy.bat
```

该启动器会带代理，并已配置 Open Design 通过本地 Codex CLI 使用 ChatGPT/Codex 订阅登录态。

## Open Design 中打开本项目

在 Open Design 里选择/导入目录：

```text
D:\All projects\Design-system
```

首读文件：

```text
OPEN_DESIGN_START_HERE.md
```

品牌/视觉合同文件：

```text
DESIGN.md
```

## 工作流

1. 在 Open Design 里写设计需求或选择设计任务单。
2. 参考 `DESIGN.md`、`05_DESIGN_COMMAND_CENTER/ui-schema/` 和 `05_DESIGN_COMMAND_CENTER/design-tokens/`。
3. 生成前端视觉方案、HTML 原型、海报、封面或 UI 结构。
4. 产物放入 `05_DESIGN_ASSETS/exports/` 或 `09_SANDBOX/design-test/`。
5. 通过 `05_DESIGN_COMMAND_CENTER/reviews/DESIGN_SCORECARD_TEMPLATE.md` 做验收。
6. 需要接入游戏时，把 Schema/Tokens/素材交给 `D:\All projects\MINIGAME` 前端实现。

## 核心目录

```text
00_START_HERE/                  启动说明
05_DESIGN_COMMAND_CENTER/       Hermes 设计主控中枢
05_DESIGN_ASSETS/               设计素材、参考图、导出产物
08_PROMPTS/                     Hermes / Codex / Open Design 提示词
09_SANDBOX/design-test/         Open Design 原型与临时试验
OPEN_DESIGN_START_HERE.md       Open Design 项目入口
DESIGN.md                       Open Design / Coding Agent 可读的视觉合同
OPEN_DESIGN_WORKFLOW.md         端到端流程
```

## 当前视觉主线

```text
Anomaly Monitor Dark
```

关键词：夜班、CCTV、异常监控、冷蓝、暗红、终端 HUD、低清噪声、告警、系统日志、可复用、低成本换皮。
