# Absorption Record｜吸收原内容到 DESIGN-LAB

## 用户决策

用户新建云端仓库：

```text
DTALEX66/DESIGN-LAB
```

本地目录：

```text
D:\All projects\DESIGN-LAB
```

最新项目定义：

```text
全面辅助增强 Open Design 软件
```

也就是说：设计流程、主窗口画布、AI 调用、设计生成都在 Open Design 软件本体内完成。本仓库吸收原来的游戏系统、设计系统、Open Design 配置经验，是为了给 Open Design 提供更好的上下文、样板、提示词、适配器和落地参考。

## 吸收原则

1. **Open Design 软件本体是主入口**：用户去 Open Design 里做设计流程和 AI 调用。
2. **本仓库只做辅助增强**：不再定义自己为工作流中心、独立设计系统产品或替代设计界面。
3. **不覆盖原仓库**：`D:\All projects\MINIGAME` 和 `D:\All projects\Design-system` 原目录不删除、不重写。
4. **保留可运行样板**：原 MINIGAME 源码、测试、H5/Android/微信样板、skins、schemas、docs、generated assets 进入 `minigame-runtime/`。
5. **保留设计资产**：原 Design-system 整体进入 `design-system/`，作为 Open Design 的设计上下文和 Schema/Tokens 参考。
6. **排除本地缓存/工具链**：`.git`、`.gradle`、`.tools`、`.tmp`、`.hermes`、`node_modules` 等不进入 Git。

## 当前结构

```text
DESIGN-LAB/
├─ README.md
├─ design-lab/
│  ├─ README.md
│  └─ prompts/
├─ design-system/
│  ├─ DESIGN.md
│  ├─ OPEN_DESIGN_START_HERE.md
│  └─ 05_DESIGN_COMMAND_CENTER/
├─ minigame-runtime/
│  ├─ src/
│  ├─ assets/
│  ├─ docs/
│  ├─ tests/
│  ├─ android-webview/
│  ├─ wechat-minigame/
│  └─ package.json
└─ project-memory/
   ├─ PROJECT_DEFINITION.md
   ├─ MIGRATION_STATUS.md
   └─ ABSORPTION_PLAN.md
```

## 吸收后的角色

### design-lab/

后续主开发区。用于沉淀 Open Design 软件的增强材料：

- prompts
- adapters
- templates
- usage notes
- agent/Codex 集成说明
- Open Design 输出落地到运行样板的说明

### design-system/

已吸收资产。现在是 Open Design 的设计上下文、Schema/Tokens 参考和视觉合同样板。

### minigame-runtime/

已吸收样板。现在是 Open Design 生成游戏 UI、验证落地、检查平台适配时的运行参考。

## 当前吸收边界

纳入：源码、docs、schemas、skins、tests、scripts、platform samples、generated visual assets、Design-system 文档与 JSON 协议。

不纳入：本地构建缓存、SDK/toolchain、Hermes 附件缓存、Git 历史目录、node_modules、coverage/test-output。
