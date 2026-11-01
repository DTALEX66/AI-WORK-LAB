# Open Design Frontend Interface

## 定位

Open Design 是本设计系统的前端设计界面和主窗口设计平台。它负责让设计需求可视化、可迭代、可导出，并把结果交还给 Hermes/Codex/MINIGAME。

Open Design 内置/包含 Figma 主窗口或类 Figma 画布能力，因此本项目的主窗口设计不再跳转到外部 Figma；默认在 Open Design 内完成。

## Open Design 输入

Open Design 每次任务应读取：

```text
DESIGN.md
05_DESIGN_COMMAND_CENTER/ui-schema/*.json
05_DESIGN_COMMAND_CENTER/design-tokens/*.json
05_DESIGN_COMMAND_CENTER/design-requests/*.md
```

## Open Design 输出

### UI 原型 / 主窗口设计

```text
09_SANDBOX/design-test/<task-id>/prototype.html
09_SANDBOX/design-test/<task-id>/design-notes.md
09_SANDBOX/design-test/<task-id>/screenshot.png
```

### 视觉资产

```text
05_DESIGN_ASSETS/exports/<task-id>/
05_DESIGN_ASSETS/ui/
05_DESIGN_ASSETS/posters/
05_DESIGN_ASSETS/douyin_covers/
05_DESIGN_ASSETS/xiaohongshu_covers/
```

### 设计协议回写

```text
05_DESIGN_COMMAND_CENTER/ui-schema/<screen>.schema.json
05_DESIGN_COMMAND_CENTER/design-tokens/<theme>.tokens.json
05_DESIGN_COMMAND_CENTER/reviews/<task-id>.scorecard.md
```

## 任务提示词模板

```text
你是 MINIGAME 的 Open Design 前端设计界面。
读取 DESIGN.md、当前 UI Schema 和 Design Tokens。
为 <任务目标> 生成 <尺寸/平台> 的高质量视觉原型。
风格必须是 Anomaly Monitor Dark：夜班、CCTV、异常监控、HUD、终端日志。
不要做成表单、后台管理页或调查问卷。
输出 HTML artifact，并给出可回写到 UI Schema / Tokens 的结构说明。
```

## Codex 交接规则

Open Design 产物不能直接等于最终游戏代码。交给 Codex 前必须明确：

1. 哪个 screen/schema 要实现。
2. 使用哪套 tokens。
3. 哪些图片/素材需要接入。
4. 哪些交互属于游戏状态机。
5. 哪些只是视觉装饰。

Codex 只实现，不重新设计。
