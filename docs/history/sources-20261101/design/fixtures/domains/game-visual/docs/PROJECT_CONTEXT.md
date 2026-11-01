> [!DEPRECATED] 本文件记录迁移前/冻结前的旧定位口径（合集平台、IAA 变现）。
> 当前权威边界见 `docs/MINIGAME_FROZEN_BOUNDARY.md`；
> 本文件仅作历史参考，不用于指导新改动。

# PROJECT CONTEXT — SINGLE SOURCE OF TRUTH

## 一、项目本质（必须始终记住）

本项目不是单个游戏开发，而是：

> 一个面向微信/抖音/H5/Android WebView 的“小游戏合集平台 + AI 生产与变现系统”

核心目标：

- 用 AI + Codex + 开源底座快速开发多个小游戏
- 通过微信/抖音小游戏广告变现（IAA）
- 在极低成本下实现第一桶金
- 后续按分类批量复制小游戏（找异常、反应时机、轻解谜、放置升级、轻模拟经营）

---

## 二、当前已确定方向（禁止偏离）

### 1. 当前首发游戏方向

项目当前首发分类为：

> 找异常类小游戏（当前游戏：找异常：异常电梯控制台，目录：`games/find-anomaly/elevator-console/`）

首发游戏本质不是剧情游戏，而是：

- 状态系统（State Machine）
- 异常事件系统（Event System）
- 用户操作系统（Action System）
- 反馈系统（Feedback System）
- 广告循环系统（Ad Loop System）

---

### 2. 首发游戏体验定义（关键原则）

玩家不是在“看故事”，而是在：

> 从监控画面、HUD 状态和日志里找异常，并操作一个不断出错的系统

核心体验：

- 找异常 / 监控找茬
- 控制台 UI
- 电梯/监控/系统状态
- 异常事件触发
- 操作反馈
- 失败与复活循环

---

### 3. 变现模型（IAA）

收入结构：

- 失败 → 广告复活
- 隐藏内容 → 广告解锁
- 假结局 → 广告提示真相
- 重试循环 → 持续广告曝光

核心不是付费，而是：

> 循环驱动广告观看

---

## 二点五、平台目录

```text
games/
└── find-anomaly/
    └── elevator-console/
        ├── README.md
        ├── game.manifest.json
        └── runtime-map.md
```

- MINIGAME 平台定位见 `docs/PLATFORM_POSITIONING.md`。
- 目录分层见 `docs/DIRECTORY_MAP.md`。
- 当前运行时代码暂保留在 `src/`、`platform/`、`index.html`、`styles.css`，避免一次性搬动破坏构建链。

## 三、开发系统结构（AI协作体系）

### 1. AI角色分工（固定）

- Codex：唯一代码执行者（写逻辑/接UI/实现功能）
- CC Switch / Claude：架构审查 + 任务拆解
- Qwen：中文剧情/规则/日志文本生成
- DeepSeek：低成本批量生成（事件/文案草稿）
- Hermes/Hammers：系统记忆 + 决策记录 + 复盘
- ChatGPT：总产品决策（方向控制）

---

### 2. 工作流原则（强约束）

- Codex 只执行明确任务
- 不允许多个 AI 同时改代码
- 每次只做一个功能
- 先设计（Design Workflow），后开发（Codex）
- 所有修改必须可回滚（Git）

---

## 四、技术底座策略（非常关键）

### 1. 必须使用开源游戏底座

采用策略：

> 使用 Cocos / Godot / H5 Canvas 开源小游戏模板作为底座

原因：

- 避免重复造轮子（UI / 存档 / 广告 / 弹窗）
- 提升开发速度
- 降低技术风险
- 支持快速换皮复制

原则：

- 不修改底层引擎结构
- 只做内容层替换（剧情 / 状态 / 事件）

---

### 2. 技术分层

```text
AI层（Qwen / DeepSeek）
→ 生成剧情与事件

设计层（Design Workflow）
→ UI / 体验 / 去AI味

开发层（Codex + 开源底座）
→ 游戏实现

平台层（微信 / 抖音小游戏）
→ 发布与变现

商业层（IAA广告）
→ 收入循环
```
