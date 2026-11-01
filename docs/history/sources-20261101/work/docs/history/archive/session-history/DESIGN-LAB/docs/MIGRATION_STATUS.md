# Migration Status｜迁移到 DESIGN-LAB

## 当前主目录

```text
D:\All projects\DESIGN-LAB
```

## 当前云端仓库

```text
https://github.com/DTALEX66/DESIGN-LAB
```

## 当前项目定义

```text
DESIGN-LAB = 全面辅助增强 Open Design 软件的资料/样板/提示词/适配器仓库
Open Design 软件本体 = 实际设计流程、主窗口画布与 AI 调用入口
```

用户后续实际进行设计流程与 AI 调用时，以 Open Design 软件为主；本仓库只提供增强材料、参考实现、配置经验和落地样板。

## 迁移状态

```text
已完成：Design-system → design-system/
已完成：MINIGAME → minigame-runtime/
已完成：Open Design 增强层骨架 → design-lab/
已完成：吸收与迁移记录 → project-memory/
已完成：Open Design 默认项目位置 → DESIGN-LAB
```

## 新目录是唯一主仓库

从现在开始，和 Open Design 增强资料、提示词、样板、配置经验、参考实现、Schema/Tokens、视觉资产相关的内容，默认都在：

```text
D:\All projects\DESIGN-LAB
```

旧目录仅作为历史来源/临时备份，不再作为主开发入口：

```text
D:\All projects\Design-system
D:\All projects\MINIGAME
```

## 新目录内的职责

```text
design-lab/     Open Design 软件增强层：prompts / adapters / templates / usage notes
design-system/             被吸收的设计资产：DESIGN.md / Schema / Tokens / component rules
minigame-runtime/          被吸收并精简的游戏运行样板：源码 / 平台样板 / tests / 精选 assets
project-memory/            项目定义、吸收、迁移、清理、决策、边界记录
```

## 注意

- 不直接删除旧目录，除非用户明确要求。
- 不再从旧目录继续开发新功能。
- 如果旧目录后续出现新改动，需要先判断是否同步吸收到本主仓。
- 设计流程、AI 调用、主窗口设计以 Open Design 软件本体为主。
- 本仓库不再被定义为工作流中心或独立设计系统产品。
