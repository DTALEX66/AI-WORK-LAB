# Skin Authoring Guide

本文档说明如何为 MINIGAME 生产一套新的异常系统皮肤。目标不是只改标题，而是完整替换主题、异常、隐藏日志、HUD 文案和失败叙事，让同一个底座可以批量复制成不同题材的小游戏。

## 适用场景

当你要新增类似下面的题材时使用本流程：

- 地铁末班调度室
- 深夜医院值班台
- 无人酒店前台
- 海上钻井平台控制室
- 校园广播室异常值班

其中下一套推荐先做 **地铁末班调度室**，因为它和电梯一样天然适合控制台 / 监控 / 信号灯 / 站台 / 车厢异常。

## 文件位置

从模板开始：

```text
templates/skin-template.json
```

复制到新的皮肤目录：

```text
src/skins/<skin-id>/skin.json
```

示例：

```text
src/skins/subway/skin.json
```

## 最短生成步骤

1. 使用脚本从模板生成新皮肤：

   ```bash
   npm run skin:new -- subway 地铁末班调度室
   ```

   脚本会创建：

   ```text
   src/skins/subway/skin.json
   ```

   并自动写入 `meta.id` / `meta.name`。

   如果需要手动复制，也可以：

   ```bash
   mkdir -p src/skins/subway
   cp templates/skin-template.json src/skins/subway/skin.json
   ```

2. 修改 `meta.id`，必须和目录语义一致，例如：

   ```json
   {
     "meta": {
       "id": "subway",
       "name": "地铁末班调度室",
       "subtitle": "LAST TRAIN · ANOMALY DISPATCH"
     }
   }
   ```

3. 替换核心文案：

   - `monitor.initial`
   - `monitor.actions.*`
   - `actionLabels.*`
   - `statusLabels.*`
   - `canvasLabels.*`
   - `actionFeedback.*`
   - `actionLogMessages.*`
   - `failure.*`
   - `fakeEnding.*`
   - `ui.*`

4. 设计至少 `12` 个 `anomalies`。

5. 给每个 anomaly 补一条同 ID 的 `hiddenLogs`。

6. 跑验证：

   ```bash
   npm run skins:check
   npm test
   node build.js wechat
   ```

7. 如果涉及 H5 视觉或交互，还要启动浏览器预览：

   ```bash
   npm run serve
   ```

   浏览器里检查：控制台/HUD 是否仍有游戏感，不能像表单或问卷。

## 必填结构清单

### `meta`

- `meta.id`：英文短 ID，例如 `subway`。
- `meta.name`：显示名，例如 `地铁末班调度室`。
- `meta.subtitle`：副标题，建议带英文控制台感。

### `monitor`

写监控画面文案。不要写成普通系统提示，要像 CCTV / 值班终端看到的内容。

示例：

```json
{
  "initial": "CCTV-07：末班车停靠 02 站台。站台广播仍在循环。",
  "actions": {
    "openDoor": "监控：站台屏蔽门已开启。车厢内灯光闪烁。"
  }
}
```

### `actionLabels`

按钮必须符合当前皮肤，不要保留电梯词汇。

地铁示例：

```json
{
  "openDoor": "开屏蔽门",
  "closeDoor": "关屏蔽门",
  "moveUp": "上行发车",
  "moveDown": "返站调度",
  "emergencyStop": "紧急制动",
  "restartSystem": "重启信号"
}
```

### `statusLabels`

状态面板要像 HUD 仪表，不要像后台表格。

地铁示例：

- `floor` → `站台`
- `door` → `屏蔽门`
- `passengers` → `乘客`
- `power` → `供电`
- `stability` → `信号`
- `anomalyLevel` → `异常等级`

### `canvasLabels`

Canvas/微信小游戏也会使用这组文案。必须和 DOM/H5 保持同一套皮肤氛围。

重要字段：

- `monitorSignalStable`
- `monitorSignalUnstable`
- `monitorSignalCorrupted`
- `monitorThreat`
- `failureMetricStability`
- `failureMetricAnomaly`
- `failureMetricRemaining`

地铁可写成：

```json
{
  "monitorSignalStable": "SIGNAL: CLEAR",
  "monitorSignalUnstable": "SIGNAL: DELAYED",
  "monitorSignalCorrupted": "SIGNAL: LOST",
  "monitorThreat": "INCIDENT: {level}"
}
```

### `anomalies`

至少 `12` 条。每条必须有：

- `id`
- `title`
- `severity`
- `monitor`
- `adHint`
- `effects.anomalyLevel`

建议 severity：

- `1`：轻微干扰
- `2`：中等异常
- `3`：明显危险
- `4-5`：少量高危事件，谨慎使用

地铁异常方向示例：

1. `phantom_platform`：不存在的 13 站台
2. `cctv_delay`：站台 CCTV 延迟
3. `empty_train_heat`：空车厢出现热源
4. `signal_echo`：广播重复“不要上车”
5. `auto_departure`：无人下达发车指令
6. `brake_failure`：紧急制动失效
7. `negative_station`：站台编号显示 -1
8. `power_drain`：牵引供电异常下降
9. `door_refuse`：屏蔽门拒绝关闭
10. `passenger_mismatch`：闸机人数与车厢人数不一致
11. `station_jump`：列车跳站
12. `tunnel_lights`：隧道应急灯自行点亮

### `hiddenLogs`

每个 anomaly 必须有同 ID 的 hidden log：

```json
{
  "phantom_platform": {
    "title": "13 站台封存记录",
    "content": "内部记录：13 站台从公开线路图中删除，但信号系统仍能收到停靠请求。"
  }
}
```

要求：

- `hiddenLogs` 的 key 必须等于 anomaly 的 `id`。
- 内容要补世界观，不要只是重复 monitor。
- 适合用广告解锁，给玩家“多知道一点”的动机。

## 质量门槛

新皮肤不能只是替换几个按钮名，必须满足：

- 12 个异常都贴合题材。
- 12 条隐藏日志能组成一个小型悬疑背景。
- HUD 文案、失败文案、监控文案都像同一套系统。
- 不出现明显旧皮肤词汇，例如地铁皮肤里不要出现“电梯门”“楼层”“轿厢”。
- H5/Canvas 都不能退化成表单感或调查问卷感。

## 验证命令

结构验证：

```bash
npm run skins:check
```

完整测试：

```bash
npm test
```

微信包构建：

```bash
node build.js wechat
```

完整验收摘要：

```bash
npm run verify:summary
```

## 常见错误

1. **只改 DOM，不改 Canvas**  
   微信小游戏走 Canvas，`canvasLabels` 必须同步换皮。

2. **anomaly 没有 hidden log**  
   每个 `anomalies[i].id` 都要在 `hiddenLogs` 里存在同名 key。

3. **保留旧题材词汇**  
   新皮肤提交前搜索旧词，例如“电梯”“轿厢”“楼层”。如果不是刻意保留，必须替换。

4. **异常只是数值，不是故事**  
   `monitor` 负责当下画面，`hiddenLogs` 负责背景真相，二者要互相补充。

5. **测试并发污染生成包**  
   本项目 `npm test` 已通过 `--test-concurrency=1` 串行执行，避免多个测试同时写 `wechat-minigame/game.js`。
