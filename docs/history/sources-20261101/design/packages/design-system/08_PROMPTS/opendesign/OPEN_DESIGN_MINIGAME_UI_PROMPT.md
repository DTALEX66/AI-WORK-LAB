# Open Design Prompt｜MINIGAME UI 原型生成

```text
你是 MINIGAME 项目的 Open Design 前端设计界面。
Open Design 内置/包含 Figma 主窗口或类 Figma 画布能力；本任务的主窗口设计必须以 Open Design 为主，不要切到外部 Figma。

请读取以下上下文：
- DESIGN.md
- 05_DESIGN_COMMAND_CENTER/00_HERMES_MASTER_DESIGN_COMMAND.md
- 05_DESIGN_COMMAND_CENTER/ui-schema/monitor_main.schema.json
- 05_DESIGN_COMMAND_CENTER/design-tokens/anomaly_monitor_dark.tokens.json
- 05_DESIGN_COMMAND_CENTER/component-rules/monitor_console.components.json

任务：
为异常监控小游戏生成一个移动端主界面 HTML 原型。

规格：
- 画布尺寸：390x844
- 风格：Anomaly Monitor Dark
- 氛围：夜班 CCTV、异常监控、系统终端、冷蓝、暗红、低清噪声
- 必须包含：status_bar、monitor_view、log_panel、action_panel
- 不允许：表单感、调查问卷感、普通后台感、白底卡片感

输出：
1. HTML artifact：09_SANDBOX/design-test/monitor-main-v1/prototype.html
2. 设计说明：09_SANDBOX/design-test/monitor-main-v1/design-notes.md
3. 可回写到 UI Schema / Tokens 的变更建议

验收标准：
- 第一眼像游戏控制台，不像网页表单
- CCTV 区域是真正视觉焦点
- 按钮像可操作控制器
- 日志像系统输出
- 颜色严格遵守 DESIGN.md / tokens
```
