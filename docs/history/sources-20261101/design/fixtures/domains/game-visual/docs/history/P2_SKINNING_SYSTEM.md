# P2 — 换皮系统 (Game Skinning System)

## 一、设计目标

将"异常电梯控制台"的所有内容文本抽取为 **皮肤 JSON**，游戏引擎只保留纯逻辑（状态机/事件系统/操作系统/广告循环），实现 **换皮 = 换 JSON**。

验证方式：用第二款皮肤（异常安防监控）证明只需改一个文件即可生成不同游戏。

---

## 二、皮肤格式 (`skins/<name>/skin.json`)

```json
{
  "meta": {
    "id": "elevator",
    "name": "异常电梯控制台",
    "subtitle": "ANOMALY SYSTEM SIM",
    "description": "操作一台不断出错的电梯控制台"
  },
  "monitor": {
    "initial": "监控画面稳定：1 层轿厢内有 1 名乘客。",
    "actions": {
      "openDoor": "监控：{floor} 层电梯门已打开。门外走廊光线异常。",
      "closeDoor": "监控：轿厢门闭合。画面存在轻微拖影。",
      "moveUp": "监控：电梯上行至 {floor} 层。乘客未看向摄像头。",
      "moveDown": "监控：电梯下行至 {floor} 层。楼层指示灯短暂闪烁。",
      "emergencyStop": "监控：电梯急停。轿厢灯光闪烁 3 次。",
      "restartSystem": "监控：系统重启后恢复画面。部分录像帧丢失。"
    }
  },
  "actions": [
    { "id": "openDoor", "label": "开门", "failWhen": { "moving": true }, "failMessage": "电梯移动中，禁止开门。" },
    { "id": "closeDoor", "label": "关门" },
    { "id": "moveUp", "label": "上行", "conditions": { "door": "closed" }, "failMessage": "门未关闭，禁止移动。" },
    { "id": "moveDown", "label": "下行", "conditions": { "door": "closed" }, "failMessage": "门未关闭，禁止移动。" },
    { "id": "emergencyStop", "label": "急停" },
    { "id": "restartSystem", "label": "系统重启" },
    { "id": "inspectLog", "label": "查看日志", "feedback": "操作员查看系统日志：最近 30 秒存在未授权楼层请求。" }
  ],
  "statusLabels": {
    "floor": "楼层",
    "door": "门状态",
    "direction": "方向",
    "passengers": "乘客",
    "power": "电源",
    "stability": "稳定度",
    "anomalyLevel": "异常等级",
    "reviveCount": "广告复活",
    "adHintsCount": "加密解码",
    "hiddenLogsCount": "待解码"
  },
  "anomalies": [
    {
      "id": "phantom_floor",
      "title": "不存在的楼层",
      "severity": 2,
      "monitor": "监控：电梯停在 13 层。建筑图纸中不存在该楼层。",
      "adHint": "当楼层显示 13 时，不要开门，先执行系统重启。",
      "effects": { "floor": 13, "anomalyLevel": "+2", "stability": "-10" }
    }
    // ... 其余 11 种
  ],
  "hiddenLogs": {
    "phantom_floor": {
      "title": "第13层施工记录",
      "content": "2019年施工记录：第13层..."
    }
    // ... 其余 11 条
  },
  "failureMessages": {
    "summaries": {
      "power": "电源耗尽",
      "stability": "稳定度归零",
      "anomalyLevel": "异常等级失控",
      "passengers": "乘客记录出现负数"
    },
    "defaultHint": "先关门，再重启系统，避免连续移动。"
  },
  "fakeEnding": {
    "title": "操作员关联异常",
    "text": "系统检测到操作员第 {count} 次系统崩溃。\n...",
    "truthAd": "这不是第一次，也不会是最后一次。\n..."
  },
  "labels": {
    "viewAd": "观看广告复活",
    "unlockAd": "解码加密记录",
    "restart": "重新开始",
    "revealTruth": "观看广告揭示真相",
    "adPlayed": "模拟广告播放完成。加密记录已解码。",
    "adRevive": "广告复活完成：回滚 {seconds} 秒，恢复至可控状态。"
  }
}
```

---

## 三、架构变更

```
之前:                          之后:
src/                           src/
├── gameConfig.js   (参数)     ├── gameConfig.js   (不变 — 纯参数)
├── state.js        (状态机)   ├── state.js        (不变)
├── actions.js      (操作)     ├── actions.js      (纯逻辑，文字来自 skin)
├── events.js       (事件)     ├── events.js       (纯逻辑，文字来自 skin)
├── feedback.js     (反馈)     ├── feedback.js     (纯逻辑，文字来自 skin)
├── game.js         (UI)       ├── game.js         (UI，文字来自 skin)
├── audio.js        (音效)     ├── audio.js        (不变)
└── gameConfig.js              ├── skinManager.js  (新增 — 皮肤加载器)
                               └── skins/
                                   ├── elevator/   (皮肤A：电梯控制台)
                                   │   └── skin.json
                                   └── security/   (皮肤B：安防监控)
                                       └── skin.json
```

### skinManager.js 职责

```js
// 单例，惰性加载
import elevatorSkin from './skins/elevator/skin.json';

let currentSkin = null;

export function loadSkin(skinData) {
  currentSkin = skinData;
}

export function t(key, params = {}) {
  // 模板字符串替换，支持嵌套 key 如 'monitor.actions.openDoor'
  const value = key.split('.').reduce((o, k) => o?.[k], currentSkin);
  if (typeof value === 'function') return value(params);
  return value.replace(/\{(\w+)\}/g, (_, k) => params[k] ?? `{${k}}`);
}

export function getSkin() { return currentSkin; }
export function getAnomalies() { return currentSkin.anomalies; }
export function getHiddenLog(anomalyId) { return currentSkin.hiddenLogs?.[anomalyId]; }
```

---

## 四、皮肤B：异常安防监控

快速验证换皮能力的第二款皮肤。不改任何逻辑代码，只改 JSON：

| 维度 | 皮肤A（电梯） | 皮肤B（安防） |
|---|---|---|
| 场景 | 夜班电梯控制台 | 夜班安防监控室 |
| 状态 | 楼层/门/方向/乘客 | 区域/门禁/巡逻/人员 |
| 操作 | 开门/关门/上行/下行 | 解锁/锁定/巡逻/回防 |
| 事件 | 楼层异常/监控延迟 | 门禁失效/摄像头盲区 |
| 倒计时 | 60秒值守 | 60秒值守 |
| 失败条件 | 电源/稳定度/异常等级 | 电力/安保等级/威胁等级 |
| 复活 | 广告复活 | 广告复活 |

因为 state 字段名不同（floor vs zone, door vs doorLock），需要皮肤能映射状态字段。

---

## 五、验收标准

- [ ] 皮肤A（电梯）加载后，游戏内容与当前完全一致
- [ ] 皮肤B（安防）加载后，游戏标题、状态、操作、事件全部替换
- [ ] 游戏引擎不包含任何硬编码内容字符串
- [ ] 换皮肤只需改一行 `loadSkin(skinData)`
- [ ] 所有测试通过
