# WeChat Mini-game Regression Report

本报告记录 r10「微信包构建和预览体验回归检查」的真实结果。

## 结论

当前 `wechat-minigame/` 可以完成构建和语法检查，但**不应宣称已可直接在微信小游戏运行**。

原因：当前 `build.js wechat` 仍把浏览器 DOM 入口 `src/game.js` 打进微信包，而微信小游戏运行时没有 `document` / DOM。

## 已通过项目

- `node --check build.js` 通过。
- `node build.js wechat` 可生成 `wechat-minigame/game.js`。
- `node --check wechat-minigame/game.js` 通过。
- `wechat-minigame/game.json` 保持：
  - `deviceOrientation: portrait`
  - `showStatusBar: false`
- `wechat-minigame/project.config.json` 保持：
  - `compileType: game`

## 当前阻塞项

### 1. 微信包仍包含 DOM API

构建产物中仍有：

```text
document.querySelector
document.createElement
window.addEventListener
```

真实微信小游戏环境中会触发类似：

```text
ReferenceError: document is not defined
```

### 2. 微信包未使用 Canvas runtime 主线

当前 `build.js` 的入口仍包含：

```text
src/game.js
```

但没有把 `platform/canvasRenderer.js` 作为真正小游戏入口。

### 3. 构建产物仍有 import alias 风险

构建产物中仍存在：

```text
_getHiddenLog(...)
```

这是从 ESM alias import 剥离后留下的风险点。

### 4. AppID 仍是占位

`wechat-minigame/project.config.json` 仍为：

```text
请替换为你的微信小游戏 AppID
```

正式导入微信开发者工具前必须替换，或使用测试号能力。

## 新增检查脚本

新增：

```bash
node scripts/check-wechat-bundle.mjs
```

输出 PASS / WARNING / BLOCKER，但默认不失败，便于每轮快速看状态。

严格模式：

```bash
node scripts/check-wechat-bundle.mjs --strict
```

如果仍有微信运行时阻塞项，会以非零退出码失败。

## r10 验收命令

```bash
node --check build.js
node build.js wechat
node --check wechat-minigame/game.js
node scripts/check-wechat-bundle.mjs
npm test
```

## 后续修复方向

微信小游戏真实可运行版本应作为后续专门任务处理：

1. 新增小游戏专用 Canvas runtime 入口。
2. `build.js wechat` 不再打包 DOM 入口 `src/game.js`。
3. 打包 `platform/canvasRenderer.js` 和平台触摸/广告适配。
4. 新增严格测试：构建产物不包含 `document.querySelector` / `document.createElement` / `window.addEventListener`。
5. 在 mock `wx` 环境下启动 `wechat-minigame/game.js` 冒烟测试。

## 与 APK 转换的关系

APK 方向更适合先走 H5 WebView 包装：当前浏览器 H5 已可运行，UI 已完成桌面/移动端视觉回归。微信 Canvas runtime 修复可以后续独立推进，不阻塞 Android APK WebView 包装验证。
