> [!DEPRECATED] 本文件记录迁移前/冻结前的旧定位口径（合集平台、IAA 变现）。
> 当前权威边界见 `docs/MINIGAME_FROZEN_BOUNDARY.md`；
> 本文件仅作历史参考，不用于指导新改动。

# MINIGAME 平台定位

## 新定位

MINIGAME 是面向微信小游戏、抖音小游戏、H5 和 Android WebView 的 **小游戏合集平台 + AI 生产系统**。

它不是单个游戏仓库，也不是只围绕“异常电梯控制台”的项目；当前仓库要沉淀的是：

- 多游戏分类目录
- 可复制的内容包协议
- 可复用的 H5 / Canvas / 微信 / 抖音 / Android WebView 发布链
- 可换皮、可变现、可批量扩展的小游戏生产工作流

## 当前首发游戏

当前已实现的首发游戏属于：

```text
games/find-anomaly/elevator-console
```

游戏名称：**找异常：异常电梯控制台**

核心玩法不是传统电梯模拟，而是“找异常 / 监控找茬 / 异常处置”：

- 玩家观察 CCTV / HUD / 系统日志中的异常线索。
- 在倒计时和系统压力下执行处置动作。
- 通过失败复活、加密日志解锁、假结局真相提示形成 IAA 广告循环。
- 同一玩法类型后续可扩展为酒店、医院、地铁、工厂、安防等不同场景。

## 平台层与游戏层分工

| 层级 | 目录 | 职责 |
|---|---|---|
| 平台定位 / 分类 | `docs/PLATFORM_POSITIONING.md`, `docs/DIRECTORY_MAP.md`, `games/README.md` | 定义合集平台、游戏分类、当前游戏归属 |
| 当前游戏目录 | `games/find-anomaly/elevator-console/` | 当前首发游戏的 manifest、说明、运行时映射 |
| 共享运行时源码 | `src/`, `platform/`, `index.html`, `styles.css` | 当前 H5/Canvas 游戏实现，后续逐步平台化 |
| 内容包 / 皮肤 | `src/skins/`, `templates/`, `schemas/` | 当前找异常游戏的场景包和皮肤数据 |
| 发布目标 | `wechat-minigame/`, `android-webview/` | 微信 / Android WebView 产物与包装 |

## 后续目录演进原则

1. 新游戏先进入 `games/<category>/<game-id>/`，至少包含 `game.manifest.json` 和 `README.md`。
2. 能复用当前找异常运行时的，先作为内容包/皮肤扩展；不要复制整套源码。
3. 需要新玩法系统时，再从 `src/` 抽出共享平台层，建立独立 runtime。
4. 平台适配、广告、发布、测试能力应尽量沉淀为共享能力，而不是每个游戏重写。
