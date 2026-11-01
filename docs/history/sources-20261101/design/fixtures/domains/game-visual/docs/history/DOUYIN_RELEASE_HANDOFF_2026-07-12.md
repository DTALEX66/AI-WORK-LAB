# 抖音小游戏直接发布交付规格

> 目标：仓库可一键生成能被抖音开发者工具直接导入、预览、真机测试和上传的原生 Canvas 小游戏；公开仓库不含 AppID、广告位、账号或签名凭据。

## 1. 官方基线（2026-07-12 核验）

权威来源：

- 开发指南：<https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/develop/guide/dev-guide/>
- 小游戏配置：<https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/develop/framework/mini-game-configuration>
- 激励视频：<https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/develop/api/ads/tt-create-rewarded-video-ad>
- 侧边栏复访（必接）：<https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/operation1/user-ops/-retention/sidebar>
- 审核规范：<https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/operation1/agreement-and-norms/norms/standard>
- 开发者工具下载：<https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/develop/dev-tools/developer-instrument-update-and-download>

官方明确要求：

1. 根目录至少包含 `game.js`、`game.json`、`project.config.json`。
2. 真机运行环境没有 DOM/BOM，使用 `tt.createCanvas`、`tt.onTouchStart` 等 API。
3. 普通未分包小游戏总包不超过 20MB；配置分包后整体仍不超过 20MB，主包不超过 4MB。
4. 小游戏需要处理 `tt.onHide` / `tt.onShow`，后台时间不能误算进本局。
5. 上传预检会扫描必接能力；侧边栏复访必须存在真实的 `tt.navigateToScene` 调用。
6. 广告奖励必须以完整观看回调为准，加载/展示失败不得发奖。
7. 实际发布仍需要开发者账号、小游戏 AppID、广告位、隐私政策与平台审核材料。

## 2. 交付目录

```text
douyin-minigame/
├── game.js
├── game.json
├── project.config.json
├── audio/
│   ├── click.wav
│   ├── anomaly.wav
│   └── result.wav
└── project.private.config.json  # 本地私有，ignored
```

公开 `project.config.json` 使用安全游客/占位 AppID；真实 AppID 由 `release.config.json` 生成到 ignored 的 `project.private.config.json`。

## 3. 构建与门禁

```bash
npm run douyin:build
npm run douyin:check
npm run douyin:compliance
npm run verify
npm run douyin:release:check
npm run douyin:package
```

- `douyin:build`：确定性生成项目三件套。
- `douyin:check`：检查目录结构、竖屏、Canvas runtime、`tt` API、侧边栏、生命周期、无 DOM/window、文件类型和包体。
- `douyin:compliance`：检查隐私/适龄/数据清单/审核素材，扫描未声明敏感 API、自建网络上传和非激励广告。
- `verify`：把抖音构建、真实生成 bundle VM 冒烟、strict 与合规检查加入全项目开发验收。
- `douyin:release:check`：只检查抖音发布所需 AppID、抖音广告位、releaseMode 和 strict bundle，不再错误要求微信 AppID。
- `douyin:package`：仅在发布门禁全绿后生成本地发布 ZIP、SHA-256 和 manifest。

## 4. 运行时发布契约

### 开始与触摸

- Canvas 端增加显式“开始值守”门禁，倒计时不得在用户尚未接管时消耗。
- 开始按钮触控目标至少 44 CSS px。
- 触摸坐标按真实 `windowWidth/windowHeight` 映射到设计画布。
- Canvas 高度按真实设备宽高比计算，避免全面屏拉伸。
- `safeArea.top` 转为设计坐标后用于顶栏与内容偏移。

### 找异常决策链

- 接管后的第一班是正常基线，玩家在实际画面中点击“放行”；教学期间误点不扣分且保留本题。
- 第二班固定展示明确的画面楼层/主控楼层矛盾，引导点击“封锁”；教学期间误点同样不惩罚。
- 第三班撤掉“点这里”和答案高亮，由玩家独立判断。
- 基础 60 秒模式的可操作判断输入始终只有“放行 / 封锁”；非巡检与自动处置期间改为不可点击的“等待下一班 / 系统处置中”状态，不提供第二层操作。
- 正确判断增加分数和连击；正式局误判或超时会断连击并降低安全值。
- 真实生成的 `game.js` VM 冒烟会依次完成正常教学、异常教学和自动处置验证。

### 音频与本地偏好

- boot / release / lockdown / motor / wrong 等语义音效均为仓库内本地 WAV，不依赖网络或第三方素材。
- 正常、封锁、错误和移动分别使用不同声光与震动反馈，但判断规则不依赖声音。
- 开始层和局内均提供声音开关；静音偏好仅用 `tt.setStorageSync` 本地保存。
- `onHide` 停止当前声音，恢复前台不覆盖用户静音选择。

### 生命周期

- `onHide`：暂停状态推进。
- `onShow`：恢复并重置 tick 基准，不追赶后台秒数。
- 暂停期间仍可绘制明确的暂停遮罩，但不触发异常、结算或广告奖励。

### 侧边栏复访

- 开始层提供“侧边栏入口”次按钮。
- 仅在 `tt.navigateToScene` 可用时启用。
- 调用 `tt.navigateToScene({ scene: 'sidebar' })`，失败只提示，不修改游戏状态或发奖励。
- 不虚构“已完成任务”或奖励；是否从侧边栏返回必须以平台 launch/show scene 为准。

### 广告

- revive / decode / truth 三个点位使用抖音私有广告位。
- 每次展示独立 attempt，完整观看才发奖。
- 重开后旧回调、重复 close/error、加载失败和展示失败均不发奖。

## 5. 发布素材

仓库保留非运行时提交素材：

```text
release-assets/douyin/
├── icon-512.png
├── icon-1024.png
├── screenshots/
├── PRIVACY_POLICY_TEMPLATE.md
├── DATA_AND_SDK_INVENTORY.md
├── AGE_RATING.md
├── STORE_LISTING.md
└── REVIEW_NOTES.md
```

正式上传前，平台后台仍需人工填写：名称、简介、类目、隐私政策 URL、主体与备案/软著信息（以控制台实时要求为准）。

## 6. 自动完成与外部阻塞边界

### 本仓库可完成

- 项目三件套、Canvas runtime、生命周期、侧边栏调用、广告失败关闭、包体检查、发布 ZIP、提交素材、自动测试和文档。

### 必须由账号/平台完成

- 创建抖音小游戏并取得真实 AppID。
- 实名主体、备案/软著及类目资质。
- 创建三个真实激励广告位。
- 在抖音开发者工具登录、真机二维码测试、上传版本。
- 控制台填写隐私政策和提审资料，提交审核。

## 7. 当前开发者工具状态

- 官方 Windows 开发者工具 4.5.3 已下载并解包到 ignored `.tools/douyin-devtools/`。
- 远程调试检查已确认程序能启动；当前停在“手机登录 / 邮箱登录 / 抖音 APP 扫码登录”页面。
- 因没有账号登录会话，尚未完成模拟器预览、真机二维码、三个真实广告位或上传；浏览器截图衍生素材不能冒充真机截图。

在这些真实值和账号操作完成前，不能诚实宣称“已发布上线”；可以交付的是**可直接导入、并在真实私有配置就绪后上传的发布工程**。
