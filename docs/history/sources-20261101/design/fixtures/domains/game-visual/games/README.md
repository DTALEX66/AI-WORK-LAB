# MINIGAME 游戏视觉 fixture 目录

本目录用于管理 MINIGAME 游戏视觉 fixture 的分类和本地 manifest。

MINIGAME 当前定位：**游戏视觉设计 fixture 集合**。每个游戏 fixture 不是产品单元，而是视觉/HUD/交互设计参考样板，仅用于 DESIGN-LAB 的游戏视觉回归与设计参考。

## 分类

| 分类 | 目录 | 当前状态 |
|---|---|---|
| 找异常 | `find-anomaly/` | 已有首发游戏：异常电梯控制台 |
| 反应时机 | `timing-reflex/` | 规划中 |
| 轻解谜 | `puzzle-logic/` | 规划中 |
| 放置升级 | `idle-upgrade/` | 规划中 |
| 轻模拟经营 | `simulation-management/` | 规划中 |

## 当前已接入游戏

- `find-anomaly/elevator-console` — 找异常：异常电梯控制台

## 接入新游戏的最低要求

每个新游戏目录至少包含：

- `README.md`：视觉/交互设计参考说明、fixture 目标
- `game.manifest.json`：稳定 ID、分类、入口、构建目标、fixture 视觉目标
- `runtime-map.md`：当前代码入口和资源映射（fixture 参考）
