# Open Design Start Here｜MINIGAME 设计界面入口

你正在使用 Open Design 作为 MINIGAME 的前端设计界面与主窗口设计平台。

## 主窗口规则

Open Design 内置/包含 Figma 主窗口或类 Figma 的画布设计能力，因此：

```text
主窗口设计以 Open Design 为主。
不要再把外部 Figma 当作默认主设计入口。
Figma 只作为 Open Design 之外的协作、导入/导出或精修备选。
```

后续所有主界面、主窗口、HUD、监控画面、移动端 UI 原型，优先在 Open Design 里完成。

## 当前目标

把 MINIGAME 的设计生产从“临时口头描述”升级为：

```text
Design Request → Open Design 视觉产物 → UI Schema / Tokens → Codex 实现 → 浏览器视觉验收 → MINIGAME 接入
```

## 角色分工

| 角色 | 职责 |
|---|---|
| Open Design | 前端设计界面与主窗口设计平台，使用内置 Figma-like 画布能力生成原型、视觉方案、图片、Deck、HTML artifact |
| Hermes | 主控，判断任务类型，维护设计规则，验收与归档 |
| Codex/GPT | 执行器，按 Schema/Tokens 生成代码或 artifact |
| MINIGAME | 最终运行项目，承载 Canvas/H5/小游戏实现 |

## Open Design 默认上下文

每次在 Open Design 里做 MINIGAME 设计任务，优先读取：

1. `DESIGN.md`
2. `05_DESIGN_COMMAND_CENTER/00_HERMES_MASTER_DESIGN_COMMAND.md`
3. `05_DESIGN_COMMAND_CENTER/01_TASK_ROUTER.md`
4. `05_DESIGN_COMMAND_CENTER/05_GAME_UI_PIPELINE.md`
5. `05_DESIGN_COMMAND_CENTER/ui-schema/monitor_main.schema.json`
6. `05_DESIGN_COMMAND_CENTER/design-tokens/anomaly_monitor_dark.tokens.json`

## 任务类型路由

### 游戏 UI

关键词：主界面、按钮、弹窗、状态栏、CCTV、监控窗口、失败页、复活广告、结算页。

输出：

```text
09_SANDBOX/design-test/<task-id>/prototype.html
05_DESIGN_COMMAND_CENTER/ui-schema/<screen>.schema.json
05_DESIGN_COMMAND_CENTER/design-tokens/<theme>.tokens.json
05_DESIGN_COMMAND_CENTER/reviews/<task-id>.scorecard.md
```

### 平面设计

关键词：海报、封面、小红书、抖音、KV、宣传图、长图、素材。

输出：

```text
05_DESIGN_ASSETS/posters/
05_DESIGN_ASSETS/xiaohongshu_covers/
05_DESIGN_ASSETS/douyin_covers/
05_DESIGN_ASSETS/exports/
```

### 设计系统更新

关键词：主题、tokens、组件、UI Schema、视觉规范、风格统一。

输出：

```text
DESIGN.md
05_DESIGN_COMMAND_CENTER/design-tokens/
05_DESIGN_COMMAND_CENTER/ui-schema/
05_DESIGN_COMMAND_CENTER/examples/
```

## 设计硬规则

1. 不要把游戏 UI 做成表单/调查问卷。
2. 所有主界面必须像 HUD / 控制台 / 监控终端。
3. Codex 不自由设计；只按 Schema、Tokens、Component Rules 实现。
4. Open Design 可以生成视觉，但最终结构要回写到 Schema/Tokens。
5. 所有最终视觉必须经过 scorecard 验收。
6. 需要接入 MINIGAME 时，必须做浏览器视觉验收。

## 首个推荐任务

在 Open Design 中输入：

```text
读取 DESIGN.md 和 monitor_main.schema.json，基于 Anomaly Monitor Dark 风格，为异常监控小游戏生成一个 390x844 移动端主界面 HTML 原型。界面要像夜班 CCTV 控制台，不要像表单。输出到 09_SANDBOX/design-test/monitor-main-v1/prototype.html，并附设计说明。
```
