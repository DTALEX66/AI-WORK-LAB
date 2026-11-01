# Content Pack Spec

本文件吸收自 `MINIGAME_V4_Starter_Pack.zip`，用于定义 MINIGAME 小游戏合集平台的内容包协议。当前首发分类是 `find-anomaly`。

## 目标

内容包负责题材、玩法配置和广告钩子，平台底座负责运行、构建和发布。

```text
content-pack.json → 当前 skin.json / anomaly catalog / hidden logs / ad slots / marketing hooks
```

内容包不直接绑定某个引擎，不依赖 H5、微信、抖音或 Cocos 的具体实现。

## 必填字段

```json
{
  "packId": "monitor_anomaly",
  "title": "异常监控室",
  "targetUser": "小红书悬疑/怪谈/心理测试用户 + 微信/抖音超休闲小游戏用户",
  "coreMechanic": "find_anomaly_and_survive",
  "states": {},
  "events": [],
  "actions": [],
  "feedback": {},
  "adSlots": {},
  "shareText": [],
  "xiaohongshuHooks": [],
  "platformNotes": {}
}
```

## 字段说明

### packId

稳定 ID，用于文件夹、构建、数据上报和营销素材关联。

示例：

```json
"monitor_anomaly"
```

### title

玩家可见的内容包中文名。

示例：

```json
"异常监控室"
```

### targetUser

目标用户，不是泛泛写“所有人”。应明确平台和内容兴趣。

示例：

```text
小红书悬疑 / 怪谈 / 心理测试用户 + 微信 / 抖音超休闲小游戏用户
```

### coreMechanic

核心机制，不写剧情简介。

示例：

```json
"find_anomaly_and_survive"
```

### states

内容包初始状态。当前项目可映射到 `createInitialState()` 或 skin 初始配置。

Starter Pack 示例：

```json
{
  "anomalyLevel": 0,
  "truthFragments": 0,
  "mistakes": 0,
  "round": 1
}
```

当前项目已有类似状态：

```text
power / stability / anomalyLevel / hiddenLogs / adRevivesUsed / fakeEnding counters
```

### events

异常事件列表。每个事件至少包含：

```json
{
  "id": "event_001",
  "type": "monitor_find_anomaly",
  "alarmCode": "CAM-04-217",
  "scene": "4号电梯监控画面",
  "rule": "画面中不应出现第二名乘客。",
  "prompt": "监控显示电梯内只有一名住户，但人数检测为2。",
  "actions": []
}
```

当前项目可映射到 skin 中的：

```text
anomalies[].id
anomalies[].title
anomalies[].monitor
anomalies[].hint
anomalies[].effects
hiddenLogs[]
```

### actions

内容包级操作定义。当前项目已有共享动作选择器：

```text
getAvailableActions()
```

短期不重复定义动作；只有在新内容包需要新交互类型时再扩展。

### feedback

玩家可见反馈文案，必须可换皮。不要把失败、未知操作、异常提示硬编码到逻辑里。

当前项目应继续放在：

```text
src/skins/*/skin.json
```

### adSlots

广告点定义。当前长期支持：

```json
{
  "revive": true,
  "unlockClue": true,
  "fakeEndingHint": true,
  "unlockNextMonitor": false
}
```

当前项目映射：

```text
revive → 失败复活
unlockClue → 解锁隐藏日志 / 加密记录
fakeEndingHint → 假结局真相揭示
unlockNextMonitor → 后续内容扩展点
```

第一阶段只使用模拟广告，不接真实 SDK。

### shareText

小游戏分享文案和社交裂变文案。

示例：

```json
[
  "这段监控你能看出哪里不对吗？",
  "90%的人第一关就点错了",
  "电梯里明明只有一个人，系统为什么显示两个？"
]
```

### xiaohongshuHooks

小红书标题 / 图文引流钩子。

示例：

```json
[
  "我做了一个异常监控小游戏，第一关你能过吗？",
  "这张监控图有一个地方不对，评论区别剧透",
  "如果你是夜班保安，你敢开门吗？"
]
```

### platformNotes

平台适配备注。

示例：

```json
{
  "wechat": "适合广告复活和隐藏线索",
  "douyin": "适合15秒短视频展示找异常过程",
  "xiaohongshu": "适合图文悬疑互动引流"
}
```

## 当前项目映射建议

| Content Pack | 当前项目 |
|---|---|
| `packId` | skin meta id / build target id |
| `title` | `meta.name` |
| `targetUser` | docs / marketing notes |
| `coreMechanic` | docs / game config |
| `states` | `createInitialState()` / config |
| `events` | `anomalies` + `hiddenLogs` |
| `actions` | `getAvailableActions()` |
| `feedback` | `failure`, `actionFeedback`, `ui`, `fakeEnding` |
| `adSlots` | `CONFIG.adUnits` + platform ad abstraction |
| `shareText` | future marketing/share module |
| `xiaohongshuHooks` | future marketing docs |
| `platformNotes` | docs / platform adaptation |

## 验收要求

未来真正接入 content-pack 时必须满足：

1. 内容包字段有契约测试。
2. 同一内容包可生成 / 映射到当前 skin 数据。
3. DOM 与 Canvas 继续共享同一文案来源。
4. 广告点只走平台广告抽象，不在 UI 里直接发奖励。
5. 浏览器预览必须验证 UI 美观和游戏感。
