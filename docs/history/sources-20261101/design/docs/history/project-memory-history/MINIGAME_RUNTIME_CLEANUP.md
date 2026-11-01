# MINIGAME Runtime Cleanup

## 目标

原 `MINIGAME` 已被吸收到 `DESIGN-LAB/fixtures/domains/game-visual/`。本目录现在不是主游戏开发仓库，而是 **Open Design 软件的游戏 UI / 运行落地参考样板**。

因此保留能辅助 Open Design 的内容，移除旧游戏系统里对当前定位无用或可再生成的内容。

## 保留内容

```text
src/                    游戏状态、动作、皮肤、归档、分析等参考实现
platform/               Canvas / mini-game runtime 参考
schemas/                skin schema
templates/              skin template
scripts/                构建、验证、Android/WebView 准备脚本
tests/                  行为/皮肤/平台/构建回归测试
android-webview/        Android WebView 工程壳，不含生成后的 assets 目录
android-minigame/       小型 Canvas 平台样板
wechat-minigame/        微信小游戏平台样板
assets/generated/       精简后的 Open Design 可用视觉资产
```

## 精简后的视觉资产策略

保留：

- 运行时实际引用的 6 个轻量 CCTV GIF：电梯、医院、安防、工厂、地铁、酒店。
- 运行时实际引用的 2 个面板纹理：`texture-control-panel.png`、`texture-hud-glass.png`。

删除：

- 未被运行时引用的候选 GIF/still。
- 大体积 native/full/scene loop 备选视频素材。
- 旧的临时 monitor/elevator 候选图。
- Open Design 参考用但非运行必需的生成 PNG stills / UI reference / overlay stills；后续需要时按 prompt 重新生成，不入库囤积。
- overlay/texture 的 loop 版本。
- 已吸收完毕的 `MINIGAME_V4_Starter_Pack.zip`。
- `android-webview/app/src/main/assets/` 下的生成资产副本；这些由 `scripts/prepare-android-webview.mjs` 可再生成。

## 为什么删除 Android WebView assets 副本

`android-webview/app/src/main/assets/` 是打包准备脚本生成的目录，内容来自：

```text
index.html
styles.css
build.js android
assets/generated/*
```

保留它会造成：

- 源码和生成物重复。
- CCTV GIF 在 `assets/generated/` 和 Android assets 中重复占用空间。
- 本仓库作为 Open Design 辅助增强仓库时变得臃肿。

需要时运行：

```bash
cd minigame-runtime
npm run android:prepare
```

即可重新生成。

## 当前判断

有用的留下：源码、测试、Schema、skins、脚本、平台样板、运行必需的轻量 GIF/纹理、文档。

没用的去掉：重复生成物、未引用候选资产、大体积备选动图、非运行必需的生成参考 PNG、旧 starter zip、本地 probe/cache。
