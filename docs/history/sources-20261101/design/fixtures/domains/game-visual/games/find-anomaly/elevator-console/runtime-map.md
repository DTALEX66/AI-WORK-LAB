# Runtime Map — 找异常：异常电梯控制台

本文件记录当前游戏目录与现有代码的映射关系。当前阶段只建立分类和 manifest，不搬动运行时代码。

## 入口

| 目标 | 入口 |
|---|---|
| H5 预览 | `index.html` → `src/game.js` |
| 微信小游戏 | `build.js wechat` → `wechat-minigame/game.js` |
| 抖音小游戏 | `build.js douyin` → `douyin-minigame/game.js` |
| Android WebView | `scripts/prepare-android-webview.mjs` → `android-webview/app/src/main/assets/` |

## 核心模块

| 模块 | 路径 |
|---|---|
| 状态机 | `src/state.js` |
| 玩家动作 | `src/actions.js` |
| 异常事件 | `src/events.js` |
| 反馈/失败总结 | `src/feedback.js` |
| 运行时调度 | `src/runtimeSession.js` |
| 皮肤管理 | `src/skinManager.js` |
| 皮肤文案/UI 标签 | `src/uiLabels.js` |
| 档案库 | `src/archive.js` |
| 埋点 | `src/analytics.js` |

## 资产映射

| 层级 | 当前路径 | 状态 |
|---|---|---|
| 兼容背景资源 | `assets/generated/` | 仍供其它皮肤和旧生成图使用，暂不整体迁移 |
| 首发游戏 UI 组件资产包 | `games/find-anomaly/elevator-console/assets/abnormal_elevator_ui_kit/` | 已归档到游戏目录，作为组件参考和 tokens，不直接覆盖当前可玩 UI |
| 首发游戏 CCTV / 按钮 / overlay 视觉资产包 | `games/find-anomaly/elevator-console/assets/abnormal_elevator_visual_assets/` | 已接入 H5、移动端 CSS 和 Android WebView 打包链路 |

移动资产后的影响：新资产包不再位于合集级 `assets/`，H5 运行时从 `games/find-anomaly/elevator-console/assets/` 引用；Android WebView 由 `scripts/prepare-android-webview.mjs` 复制到包内 `assets/abnormal_elevator_visual_assets/` 并重写 CSS 路径。当前兼容图仍保留在 `assets/generated/`，用于其它皮肤和旧链路。

## 当前接入范围

- `src/visualState.js`：根据门、电力、移动方向、异常和冷却状态输出 `cctvState`。
- `src/game.js`：把 `visual.cctvState` 写入 `#monitor[data-cctv-state]`。
- `styles.css`：接入 24 张桌面 CCTV 状态图、24 张移动裁切图、8 个按钮 sprite 和 6 个 overlay。
- `scripts/prepare-android-webview.mjs`：复制视觉资源包并重写 WebView 内 CSS 路径。
- `abnormal_elevator_ui_kit/`：保持为设计参考，不直接导入运行时，避免破坏现有可玩 UI。
