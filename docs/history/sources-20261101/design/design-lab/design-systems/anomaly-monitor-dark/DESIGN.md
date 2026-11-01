---
version: alpha
name: Anomaly Monitor Dark
description: MINIGAME 的夜班 CCTV 异常监控控制台视觉合同，面向 Open Design、Hermes 与 Codex 共同消费。
colors:
  primary: "#080B0F"
  secondary: "#101720"
  tertiary: "#46C2FF"
  neutral: "#D8DEE9"
  danger: "#FF3B3B"
  warning: "#F5B942"
  success: "#29FF8A"
  muted: "#7B8794"
  border: "#243447"
typography:
  h1:
    fontFamily: system-ui
    fontSize: 28px
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: "-0.02em"
  body-md:
    fontFamily: system-ui
    fontSize: 15px
    fontWeight: 500
    lineHeight: 1.5
  mono-label:
    fontFamily: monospace
    fontSize: 12px
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.08em"
rounded:
  sm: 6px
  md: 10px
  lg: 16px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
components:
  panel:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.neutral}"
    rounded: "{rounded.md}"
    padding: 16px
  button-primary:
    backgroundColor: "{colors.tertiary}"
    textColor: "#001018"
    rounded: "{rounded.sm}"
    padding: 12px
  button-danger:
    backgroundColor: "{colors.danger}"
    textColor: "#FFFFFF"
    rounded: "{rounded.sm}"
    padding: 12px
  status-warning:
    backgroundColor: "#1D1A10"
    textColor: "{colors.warning}"
    rounded: "{rounded.sm}"
    padding: 8px
---

## Overview

Anomaly Monitor Dark 是 MINIGAME 异常监控类小游戏的第一套主视觉。它不是普通 SaaS 后台，也不是调查问卷界面；它必须像玩家正在接管一个夜班监控终端：低清 CCTV、系统日志、危险灯、噪声层、扫描线和可操作的控制按钮共同构成游戏感。

Open Design 是本项目的前端设计界面和主窗口设计平台。Open Design 内置/包含 Figma 主窗口或类 Figma 画布能力，因此主窗口设计以 Open Design 为准；外部 Figma 只作为协作、导入/导出或精修备选。所有 Open Design 生成的 artifact、图片、海报、移动端 UI 原型，都必须遵守本文件。

## Colors

- **Primary `#080B0F`**：接近黑色的夜班背景，用作整屏底色。
- **Secondary `#101720`**：面板和模块底色。
- **Tertiary `#46C2FF`**：冷蓝主交互、扫描线、焦点框。
- **Danger `#FF3B3B`**：异常、失败、警报、危险按钮。
- **Warning `#F5B942`**：倒计时、注意、系统警告。
- **Success `#29FF8A`**：恢复、稳定、连接正常。
- **Muted `#7B8794`**：辅助标签、次级说明。
- **Border `#243447`**：面板边框和 HUD 分隔线。

## Typography

标题使用厚重 system-ui，尽量短促、像设备标签。小标签、编号、日志、状态码优先使用 monospace，形成终端感。中文文案避免营销腔，使用系统提示、监控日志和夜班记录口吻。

## Layout

移动端优先，默认按 390x844 或微信小游戏竖屏比例设计。主界面建议四段式：

1. `status_bar`：系统时间、告警编号、异常等级。
2. `monitor_view`：CCTV 主画面、噪声层、目标标记。
3. `log_panel`：规则、异常日志、系统警告。
4. `action_panel`：玩家操作按钮。

布局要像控制台，不要像表单。按钮应靠近底部，便于单手操作。

## Elevation & Depth

用边框、微弱蓝光、暗红警报光和内阴影制造层级。不要使用明亮卡片阴影或普通 Web2.0 白底卡片。

## Shapes

圆角克制，默认 6px 到 16px。CCTV 框、终端窗口、警报条可以使用切角、细边框、角标线增强设备感。

## Components

- **Panel**：深色底、细边框、轻微噪声或扫描线。
- **Monitor View**：必须包含 CCTV 画面感，不能只是纯色方块。
- **Status Bar**：像仪表盘，不像普通导航栏。
- **Log Panel**：像终端输出，支持时间戳、错误码、异常描述。
- **Action Button**：像控制台按钮，状态明确，危险操作必须可辨识。
- **Modal**：失败/复活/解锁弹窗要像系统警告窗，不像网页表单。

## Do's and Don'ts

Do:

- 做成夜班 CCTV 控制台。
- 使用扫描线、噪声、时间戳、状态码。
- 保持冷蓝 + 暗红 + 深色底的统一气质。
- 输出 artifact 后回写 Schema/Tokens。

Don't:

- 不要做成问卷、设置页、普通后台、白底表单。
- 不要让 Codex 自行决定颜色和布局。
- 不要把玩家文案硬编码在 UI 代码里。
- 不要用大量不可控字体包或过重素材。
