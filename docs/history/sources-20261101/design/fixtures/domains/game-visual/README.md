# MINIGAME — 游戏视觉设计 Fixture / Runtime Reference

> **DESIGN-LAB 的游戏视觉设计参考样板与运行时 fixture（冻结边界）**

本目录是 `DESIGN-LAB` 内的**游戏 UI/HUD 视觉设计参考 fixture**：HUD、UI、图标、皮肤、交互反馈、场景氛围、动态视觉、资产规范、跨端可视化回归，以及可运行视觉 fixture 的安全/构建/测试维护。

**它不是游戏平台产品、独立产品线、发行渠道，也不承载广告/IAA/变现/运营/新玩法系统/内容包扩张。**

## 新合同（H1）

```text
minigame-runtime = Game Visual Design Fixture / Runtime Reference

允许：HUD、UI、图标、皮肤、交互反馈、场景氛围、动态视觉、资产规范、
      跨端可视化回归、可运行视觉 fixture 的安全/构建/测试维护。
禁止：游戏平台产品线、发行渠道、广告/IAA/变现、运营、
      新玩法系统、内容包扩张、发布/增长路线图。
```

## 当前首发 fixture

**找异常：异常电梯控制台**（`games/find-anomaly/elevator-console/`）

该 fixture 提供游戏 UI/HUD 视觉设计的**规范骨架与运行时参考**：视觉状态清单（CCTV 状态、按钮组件、overlay 组件族）、皮肤文案、内容调度与多端构建/回归测试。早期制作小游戏所用的实际视觉资产（CCTV 状态图、循环 GIF、背景音乐、发行审核素材）已移除，仅保留可再生成的视觉设计规范与运行时代码。

## 快速开始

```bash
npm install
npm run serve        # 本地 H5 预览
npm test             # 测试
npm run verify       # 视觉回归 + 构建检查
```

`npm run verify` 是 fail-closed acceptance gate：如果项目内 portable Android
toolchain（JDK 17 + Android SDK + Gradle）不存在，Android build/metadata 会
报告 `BLOCKED` 并以非零退出；不能把 `SKIP` 当作验收通过。只需要 H5/小游戏
fixture 检查时，可单独运行 `npm test`、bundle strict checks、skins 和 V5
content checks。

## 多端构建（仅视觉回归读回，非可发行产物）

多端 build 保留为**视觉工作在 H5/Canvas/WebView 的兼容和回归读回**，不是可发行产物：

```bash
node build.js wechat                          # 微信小游戏视觉 bundle 构建
node scripts/check-wechat-bundle.mjs --strict # strict 检查
npm run android:build                         # Android WebView debug APK（视觉回归用）
npm run android:inspect                       # APK 元数据检查
```

Android APK 产物：

```text
android-webview/app/build/outputs/apk/debug/app-debug.apk
```

## 常用命令

```bash
npm run serve            # 本地 H5 预览
npm test                 # 测试（测试数以实际输出为准）
npm run verify           # 一键视觉回归验收
npm run android:build    # 构建 Android WebView debug APK（视觉回归）
npm run android:inspect  # 检查 APK 元数据
npm run android:install  # 安装并启动 Android debug APK（需 adb 设备在线）
npm run skin:new -- <id> [名称]  # 从模板生成新视觉皮肤
node build.js wechat     # 构建微信小游戏视觉 bundle
```

## 文档

- `docs/GAME_DESIGN.md`：异常电梯控制台设计总纲（视觉/交互设计）
- `docs/IMAGE_GENERATION_PROMPT_PACK.md`：CCTV / 控制台 / HUD 材质生成词汇
- `docs/UI_V3_FULL_REDESIGN_2026-07-12.md`：UI 视觉重设计
- `docs/MOBILE_GAMEPLAY_UI_V4.md`：移动端 gameplay UI 参考
- `docs/history/`：旧平台/变现/发布/内容包文档（不可执行历史资料，仅供追溯）

## 开发原则

- 每次只做一个功能；所有修改必须可回滚
- 不偏离"游戏视觉设计 fixture / runtime reference"的冻结边界（见 `docs/MINIGAME_FROZEN_BOUNDARY.md`）
- 禁止把 fixture 重新推成活动游戏产品；防漂移测试必须通过
