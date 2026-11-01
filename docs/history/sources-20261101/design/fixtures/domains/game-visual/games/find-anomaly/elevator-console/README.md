# 找异常：异常电梯控制台

## fixture 路径

```text
MINIGAME / games / find-anomaly / elevator-console
```

## 游戏定位

这是 MINIGAME 游戏视觉设计 fixture 中的首发参考样板，视觉归类为 **找异常（异常电梯控制台）**。

玩家不是单纯模拟电梯操作员，而是在 CCTV、状态 HUD 和系统日志中寻找异常，并在倒计时内完成处置。

## 当前运行时映射

当前实现仍复用仓库根部运行时：

| 功能 | 当前路径 |
|---|---|
| H5 入口 | `index.html`, `styles.css`, `src/game.js` |
| 核心逻辑 | `src/state.js`, `src/actions.js`, `src/events.js`, `src/feedback.js` |
| 皮肤参考 | `src/skins/*/skin.json` |
| Canvas 小游戏 runtime | `platform/miniGameRuntime.js`, `platform/canvasRenderer.js` |
| 微信产物 | `wechat-minigame/` |
| Android WebView | `android-webview/` |

## 当前游戏资产

首发游戏专属资产统一放在本目录下的 `assets/`，不要放回合集根目录的 `assets/`。

| 资产包 | 路径 | 用途 |
|---|---|---|
| UI 组件包 | `assets/abnormal_elevator_ui_kit/` | 移动端控制台组件、按钮状态、组件 tokens、图标预览 |
| 视觉状态包 | `assets/abnormal_elevator_visual_assets/` | CCTV 状态图、移动端裁切图、按钮贴图、overlays、manifest |

当前 H5 / Android WebView 运行时代码仍引用仓库根部 `assets/generated/` 中的既有背景资源；新资产包已归档到游戏目录，后续接线时再按 manifest 替换运行时引用。

## 当前内容包

首发游戏已包含 5 套场景皮肤：

- `elevator`：异常电梯控制台
- `security`：安防监控室
- `factory`：工厂夜班控制室
- `subway`：地铁末班调度室
- `hospital`：深夜医院值班台

## 后续扩展

优先扩展：

1. `hotel`：无人酒店前台 / 午夜入住异常
2. 皮肤选择界面
3. 异常档案库图鉴化
4. 找异常分类下的第二个独立游戏

## 资源接入状态（历史）

早期制作小游戏所用的实际视觉资产（CCTV 状态图、移动端裁切图、按钮贴图、overlay、背景音乐）已随视觉资产清理移除。当前仅保留视觉状态清单（`platform/canvasAssets.js`）与运行时代码作为游戏视觉设计 fixture 参考。
