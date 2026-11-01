# 06｜OPEN DESIGN / FIGMA PLATFORM RULES

Open Design Desktop 是当前默认前端设计界面和主窗口设计平台。Open Design 内置/包含 Figma 主窗口或类 Figma 画布能力，因此主窗口设计统一以 Open Design 为主。外部 Figma 降级为外部协作、导入/导出、精修交付或团队共享备选。

## 主窗口优先级

```text
1. Open Design 主窗口 / Figma-like 画布能力
2. Open Design HTML artifact / prototype
3. 外部 Figma 协作或精修文件
4. Penpot 开源备选
```

如果任务提到“Figma 主窗口”“主窗口设计”“画布设计”“移动端 frame”，默认解释为：在 Open Design 里完成，而不是切到外部 Figma。

## Open Design 项目建议

```text
D:\All projects\Design-system
├─ DESIGN.md
├─ OPEN_DESIGN_START_HERE.md
├─ OPEN_DESIGN_WORKFLOW.md
├─ 05_DESIGN_COMMAND_CENTER
├─ 05_DESIGN_ASSETS
├─ 08_PROMPTS
└─ 09_SANDBOX/design-test
```

## Open Design Artifact 命名

monitor-main-v1、fail-popup-v1、revive-modal-v1、hidden-log-modal-v1、xhs-cover-v1、douyin-cover-v1、share-card-v1。

## Open Design 交付给 Codex 前必须包含

页面名称、artifact 路径、组件列表、颜色 tokens、字体规则、间距规则、状态变化规则、导出资源列表、UI Schema、设计验收标准。

## 外部 Figma 文件建议（仅备选）
```text
MINIGAME_DESIGN_SYSTEM.fig
├─ 01_STYLE_BOARD
├─ 02_DESIGN_TOKENS
├─ 03_COMPONENTS
├─ 04_GAME_UI
├─ 05_MARKETING_GRAPHICS
├─ 06_XIAOHONGSHU_TEMPLATES
├─ 07_DOUYIN_COVERS
├─ 08_EXPORTS
└─ 99_ARCHIVE
```

## Frame 命名
GAME_HOME_001、MONITOR_EVENT_001、FAIL_POPUP_001、REVIVE_AD_POPUP_001、XHS_COVER_001、DOUYIN_COVER_001、SHARE_CARD_001。

## Figma 交付给 Codex 前必须包含
页面名称、组件列表、颜色 tokens、字体规则、间距规则、状态变化规则、导出资源列表、UI Schema。


---

## 中立性勘误（DL-P0-001，2026-08-19）

本文为历史资料/参考文档。按 DESIGN-LAB 平台中立政策（NEUTRALITY_POLICY）：**Open Design 只能是可选 Adapter/宿主之一，不得作为默认绑定**。宿主选择（Open Design/Figma/Blender/ComfyUI/Adobe…）属于用户本地 profile 或项目级授权配置；产品契约不绑定默认宿主。
