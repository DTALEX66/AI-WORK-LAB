# MINIGAME｜Open Design 前端设计界面 + Hermes 主控设计工作流 V2

建议解压/合并到：

```text
D:\All projects\MINIGAME
```

本包已整理为独立 `Design-system` 工作区：Open Design 软件作为前端设计界面，Hermes 作为设计主控中枢，不会修改游戏代码，不接广告 SDK。

## 核心定位

本项目不以 Codex 为主控，而是：

> Hermes 主控，GPT / DeepSeek / Qwen / CC Switch / Codex 都是 Hermes 调用的能力模块。

## 新增核心目录

```text
05_DESIGN_COMMAND_CENTER
```

它负责：

- 平面设计工作流
- 游戏 UI 工作流
- Figma 主平台规则
- Penpot 开源备选规则
- OpenDesign 吸收规则
- UI Schema
- Design Tokens
- Codex UI 渲染门禁
- 设计记忆更新规则

## 前端设计界面 / 主窗口设计平台

```text
Open Design Desktop
```

Open Design 内置/包含 Figma 主窗口或类 Figma 画布设计能力，因此主窗口设计统一以 Open Design 为主。

推荐启动器：

```text
D:\Programs\Open Design\Open Design - GPT Codex Proxy.bat
```

项目入口：

```text
D:\All projects\Design-system\OPEN_DESIGN_START_HERE.md
```

## Figma 定位

```text
Figma
```

Figma 降级为外部协作/导入导出/精修交付备选，不再是本工作区的默认前端设计界面或主窗口设计入口。

## 开源备选

```text
Penpot
```

## Open Design 定位

是本工作区的前端设计界面，并继续吸收三类开放设计能力：

1. Mozilla OpenDesign：设计任务单结构
2. Open Design Kit：开放设计方法与协作流程
3. Open Design Framework：设计文件解析 / 自动化研究层
