# P3 — 小游戏平台适配（微信/抖音）

## 一、目标

将 H5 游戏适配为微信小游戏和抖音小游戏，核心目标：
1. 游戏逻辑（state/actions/events/feedback）零修改
2. UI 渲染从 DOM 迁移到 Canvas（小游戏无 DOM）
3. IAA 激励视频广告接入
4. 一套代码，多平台运行

## 二、架构

```
src/                       ← 核心逻辑（不变）
├── state.js
├── actions.js
├── events.js
├── feedback.js
├── gameConfig.js
├── audio.js
├── skinManager.js
├── skins/
│
platform/                  ← 平台抽象层（新增）
├── platform.js            ← 统一 API 封装
├── canvasRenderer.js      ← Canvas 渲染器
│
wechat-minigame/           ← 微信小游戏项目
├── game.js                ← 入口（打包后）
├── game.json              ← 微信配置
└── project.config.json    ← IDE 配置

build.js                   ← 打包脚本（ESM → 单文件）
```

## 三、platform.js 抽象层

```js
// 统一平台 API
export const PLATFORM = {
  // 环境检测
  isWechat: typeof wx !== 'undefined',
  isDouyin: typeof tt !== 'undefined',
  isBrowser: typeof window !== 'undefined',
  
  // 广告
  createRewardedVideoAd(options) {
    if (isWechat) return wx.createRewardedVideoAd(options);
    if (isDouyin) return tt.createRewardedVideoAd(options);
    return mockAd(); // 浏览器中模拟
  },
  
  // 存储
  getStorageSync(key) { ... },
  setStorageSync(key, val) { ... },
  
  // Canvas
  getCanvas() { ... },    // 获取主画布
  getContext() { ... },   // 获取 2D 上下文
}
```

## 四、Canvas 渲染器

替代 index.html + styles.css 的所有 DOM 渲染。

```js
canvasRenderer.js
├── render(state)          ← 主渲染函数（每帧调用）
│   ├── drawBackground()
│   ├── drawStatusPanel()  ← 电梯状态
│   ├── drawMonitor()      ← 监控画面
│   ├── drawActions()      ← 操作按钮
│   ├── drawLogs()         ← 系统日志
│   └── drawOverlay()      ← 失败/假结局弹窗
│
├── handleClick(x, y)      ← 触摸/点击事件
└── init(canvas)           ← 初始化
```

渲染示意（Canvas 坐标系，750 设计宽度）：

```
┌─────────────────────────────────┐
│ MINIGAME · ANOMALY SYSTEM SIM   │
│ 异常电梯控制台       值守: 60   │  ← 顶栏
├──────────────┬──────────────────┤
│ 楼层: 1      │  监控画面区域     │
│ 门状态: 关闭 │  (文字+扫描线)    │
│ 方向: 待机   │                  │
│ 乘客: 1      │                  │
│ 电源: ████   │                  │
│ 稳定度: ████ │                  │
│ 异常等级: 0  │                  │
├──────────────┴──────────────────┤
│ 开门 │ 关门 │ 上行 │ 下行       │  ← 操作按钮
│ 急停 │ 重启 │ 日志 │ 解码       │
├─────────────────────────────────┤
│ [00:12] 系统日志                │  ← 日志区域
│ [00:14] 异常事件                │
└─────────────────────────────────┘
```

## 五、微信小游戏项目结构

```
wechat-minigame/
├── game.js             ← 打包后的入口
├── game.json           ← {
│                           "deviceOrientation": "portrait",
│                           "showStatusBar": false,
│                           "networkTimeout": { "request": 5000 }
│                         }
├── project.config.json ← IDE 配置
└── images/             ← UI 素材（按钮/背景）
```

## 六、IAA 广告集成

### 激励视频广告点位

| 场景 | Ad Unit ID (占位) | 触发时机 |
|---|---|---|
| 失败复活 | `adunit-xxxxx_revive` | 失败弹窗→点击复活 |
| 解码隐藏日志 | `adunit-xxxxx_decode` | 点击解码加密记录 |
| 假结局真相 | `adunit-xxxxx_truth` | 假结局→点击揭示真相 |

### 伪代码

```js
function showRewardedAd(adUnitId, onReward) {
  if (PLATFORM.isBrowser) {
    // 模拟 2 秒广告
    setTimeout(onReward, 2000);
    return;
  }
  const ad = PLATFORM.createRewardedVideoAd({ adUnitId });
  ad.onClose((res) => {
    if (res.isEnded) onReward();  // 完整观看
  });
  ad.show().catch(() => {
    // 广告加载失败，直接给予奖励
    onReward();
  });
}
```

## 七、验收标准

- [ ] H5 浏览器模式：游戏完全正常（DOM 渲染不变）
- [ ] Canvas 渲染模式：所有 UI 元素正确绘制
- [ ] 微信小游戏：可打开，可玩完整一局
- [ ] 激励视频广告：模拟广告在浏览器中工作
- [ ] 换皮系统兼容：皮肤A/B 在 Canvas 下均正常
- [ ] 点击/触摸交互正确
