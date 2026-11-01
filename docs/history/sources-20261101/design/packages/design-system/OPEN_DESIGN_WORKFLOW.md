# Open Design Workflow｜MINIGAME 端到端设计流程

## 0. 启动

使用代理启动器：

```text
D:\Programs\Open Design\Open Design - GPT Codex Proxy.bat
```

Open Design 已通过 Codex CLI 连接 GPT 订阅，不需要 OpenAI API Key。

Open Design 内有 Figma 主窗口/类 Figma 画布能力，本流程中所有主窗口设计默认在 Open Design 内完成；外部 Figma 仅作为协作或导入/导出备选。

## 1. 需求进入 Design Request

所有设计任务先落到：

```text
05_DESIGN_COMMAND_CENTER/design-requests/
```

命名建议：

```text
YYYYMMDD_<surface>_<goal>.design-request.md
```

例如：

```text
20260704_monitor_main_mobile_console.design-request.md
```

## 2. Open Design 主窗口生成视觉产物

Open Design 负责：

- 主窗口 / 画布式 UI 设计
- Figma-like 结构化 frame 设计
- HTML artifact
- 移动端 UI 原型
- 海报/封面/社媒图
- 可导出的视觉方案
- 设计说明

产物进入：

```text
09_SANDBOX/design-test/<task-id>/
05_DESIGN_ASSETS/exports/
```

## 3. 回写设计协议

视觉产物通过后，必须回写以下至少一类：

```text
DESIGN.md                                           品牌/视觉合同
05_DESIGN_COMMAND_CENTER/design-tokens/*.json       颜色/字体/间距/组件 tokens
05_DESIGN_COMMAND_CENTER/ui-schema/*.json           UI 结构
05_DESIGN_COMMAND_CENTER/examples/                  示例 artifact
```

## 4. Codex 实现门禁

只有当以下文件齐备时，才调用 Codex 改 MINIGAME 前端：

- Design Request
- UI Schema
- Design Tokens
- 组件规则或 Open Design artifact
- 验收标准

Codex 的任务应该是：

```text
按指定 schema/tokens 实现，不新增玩法，不自行换颜色，不重构无关代码。
```

## 5. MINIGAME 接入

MINIGAME 前端建议消费：

```text
Design-system/05_DESIGN_COMMAND_CENTER/design-tokens/*.json
Design-system/05_DESIGN_COMMAND_CENTER/ui-schema/*.json
Design-system/05_DESIGN_ASSETS/exports/*
```

接入策略：

```text
Schema-driven Canvas UI + Design Tokens + Skin JSON + Platform Adapter
```

## 6. 验收

必须包含：

1. JSON 校验
2. 浏览器打开原型或游戏页面
3. 检查 Console
4. 视觉审查：是否有游戏感/控制台感/监控感
5. 至少一次核心交互点击
6. Scorecard 归档

## 7. 完成归档

最终归档到：

```text
05_DESIGN_COMMAND_CENTER/reviews/<task-id>.scorecard.md
05_DESIGN_ASSETS/exports/<task-id>/
```

必要时把经验沉淀回：

```text
05_DESIGN_COMMAND_CENTER/14_DESIGN_MEMORY_UPDATE_RULES.md
```
