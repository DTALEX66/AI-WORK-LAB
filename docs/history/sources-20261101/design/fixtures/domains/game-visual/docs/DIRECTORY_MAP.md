# MINIGAME 目录分层

## 当前目录结构

```text
MINIGAME/
├── games/                         # 小游戏合集目录：分类、游戏 manifest、运行时映射
│   └── find-anomaly/              # 分类：找异常 / 监控找茬 / 异常处置
│       └── elevator-console/      # 当前首发游戏：找异常：异常电梯控制台
├── src/                           # 当前可运行游戏的共享逻辑与首发实现
│   └── skins/                     # 找异常内容包/场景皮肤
├── platform/                      # 小游戏 Canvas runtime、平台适配层
├── assets/generated/              # 当前游戏与后续皮肤可复用的生成视觉资产
├── schemas/                       # 内容包 / 皮肤 schema
├── templates/                     # 新皮肤 / 内容包模板
├── docs/                          # 平台、玩法、发布、工作流文档
├── tests/                         # Node 测试与结构约束
├── wechat-minigame/               # 微信小游戏构建产物
├── android-webview/               # Android WebView 包装工程
├── index.html / styles.css        # H5 预览入口
└── build.js                       # H5/微信/抖音/Android WebView bundle 构建入口
```

## 分类目录规范

```text
games/<category>/<game-id>/
├── README.md
├── game.manifest.json
└── runtime-map.md
```

### category 命名

| 分类 ID | 中文 | 说明 |
|---|---|---|
| `find-anomaly` | 找异常 | 监控找茬、异常识别、异常处置、怪谈观察类小游戏 |
| `timing-reflex` | 反应时机 | 点击时机、躲避、节奏、短局失败复活类 |
| `puzzle-logic` | 轻解谜 | 低门槛逻辑题、排序、连接、机关类 |
| `idle-upgrade` | 放置升级 | 合成、升级、数值成长、广告加速类 |
| `simulation-management` | 轻模拟经营 | 值班、调度、排队、资源管理类 |

## 当前迁移边界

本次只重分“平台定位、分类和目录索引”，不移动 `src/` 运行时代码，避免破坏当前 H5 / 微信 / Android 验收链。

后续如果要把运行时拆到游戏目录，建议分三步：

1. 先把游戏配置和皮肤入口抽成 manifest 驱动。
2. 再把 `src/` 拆成 `src/shared/` 与 `games/find-anomaly/elevator-console/runtime/`。
3. 最后更新 build/test 脚本，让不同 game manifest 能选择不同入口。

## 资产归属规则

`D:\All projects\MINIGAME` 是小游戏合集总目录。只属于合集平台、跨游戏复用、构建/发布/模板/通用运行时的内容，才能放在总目录层级。

首发游戏“找异常：异常电梯控制台”的专属内容，统一放入：

```text
games/find-anomaly/elevator-console/
```

其中，首发游戏专属 UI、CCTV、按钮、overlay、spritesheet、状态图等视觉资产统一放入：

```text
games/find-anomaly/elevator-console/assets/
```

后续新增游戏遵循同一规则：游戏专属内容放入 `games/<category>/<game-id>/`；只有确定可跨多个游戏复用的内容，才提升到合集总目录或共享目录。

Open Design 工作区只作为临时传输、预览和交付空间。确认采用的正式项目资产必须同步到 `D:\All projects\MINIGAME` 对应目录；Open Design 工作区或根目录不得长期保留正式资产副本。
