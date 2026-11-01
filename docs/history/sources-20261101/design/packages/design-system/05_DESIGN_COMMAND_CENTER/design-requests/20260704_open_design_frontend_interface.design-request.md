# Design Request｜Open Design 作为 MINIGAME 前端设计界面

## 背景

MINIGAME 需要把 Open Design 软件纳入设计生产链路，作为前端设计界面和视觉产物工作台。

## 目标

建立一个独立的 Design-system 工作区，让 Open Design 能直接读取：

- 视觉合同 `DESIGN.md`
- UI Schema
- Design Tokens
- Component Rules
- Design Request
- Scorecard

并产出可交给 MINIGAME 前端实现的 HTML artifact、素材和设计协议。

## 约束

1. Hermes 仍然是主控。
2. Open Design 是设计界面，不是最终游戏运行时。
3. Codex 只按 Schema/Tokens 实现，不自由设计。
4. 游戏 UI 必须像控制台/HUD/CCTV，不像表单。
5. 所有产物必须可归档、可复用、可接入 MINIGAME。

## 交付物

- `README.md`
- `OPEN_DESIGN_START_HERE.md`
- `OPEN_DESIGN_WORKFLOW.md`
- `DESIGN.md`
- Open Design prompt
- Component Rules JSON
- 本 Design Request

## 下一步

用 Open Design 生成 `monitor-main-v1` 移动端 HTML 原型，并通过浏览器视觉验收。
