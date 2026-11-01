> [!DEPRECATED] 本文件记录迁移前/冻结前的旧定位口径（合集平台、IAA 变现）。
> 当前权威边界见 `docs/MINIGAME_FROZEN_BOUNDARY.md`；
> 本文件仅作历史参考，不用于指导新改动。

# MINIGAME 后续任务列表

> 2026-07-11 全面审计、首批 P0 修复与后续接手顺序见：[`PROJECT_AUDIT_HANDOFF_2026-07-11.md`](./PROJECT_AUDIT_HANDOFF_2026-07-11.md)。本文保留历史任务；如有冲突，以交接文档和当前测试为准。

> 当前基线以实际命令输出为准：本轮 `npm test` 已通过；微信 strict 为 0 blocker；Android APK build/inspect 依赖项目内便携 `.tools` 工具链，缺失时需要先恢复工具链；`npm run release:check` 在默认占位配置下预期失败。


## P0｜平台定位 / 目录治理

### 0. 小游戏合集平台目录已建立

当前定位已调整为：MINIGAME 是小游戏合集平台，首发游戏是：

```text
games/find-anomaly/elevator-console
```

当前只建立分类、manifest 和 runtime 映射，不移动 `src/` 源码，避免破坏 H5 / 微信 / Android 验收链。

下一步目录治理建议：

1. 玩家入口继续保持当前单游戏直进，不做合集首页/游戏选择页。
2. `games/`、manifest 和 runtime 映射先作为后台生产目录保留。
3. 新游戏一律先进入 `games/<category>/<game-id>/`，再决定是否复用现有 runtime。

## 已完成的近期地基

- P0：文档命令一致性测试 `tests/docsCommands.test.js`。
- P0：`npm run verify:summary` 简洁验收模式。
- P0：`npm test` 串行执行，避免生成包测试竞争。
- P3：`schemas/skin.schema.json`、`scripts/validate-skins.mjs`、`npm run skins:check`。
- P3：`templates/skin-template.json` 与 `docs/SKIN_AUTHORING_GUIDE.md`。
- P3：第 4 套皮肤 `src/skins/subway/skin.json`（地铁末班调度室）。
- P3：第 5 套皮肤 `src/skins/hospital/skin.json`（深夜医院值班台）。
- P3：皮肤生成脚本 `scripts/create-skin-from-template.mjs` 与 `npm run skin:new -- <id> [名称]`。
- P2：轻量埋点接口 `src/analytics.js`，已接入 H5 开始、失败、广告、操作、异常路径。
- P2：跨局异常档案库已按皮肤记录场次、遭遇异常、解锁日志和收集进度。
- P5：H5 Debug Console 的低清 CCTV 背景已由 `styles.css` 中当前仍被引用的生成资产提供；未接线旧候选图已清理。
- P5：图像生成提示词包已落地 `docs/IMAGE_GENERATION_PROMPT_PACK.md`，用于后续重做 UI/监控画面资产。
- P4：GitHub Actions verify workflow。
- P4：`npm run android:install` 真机/模拟器安装启动命令。

## P1｜发布前必须做：真实平台发布链

### 1. 填真实 `release.config.json` 并验证发布检查通过

当前 `npm run release:check` 默认会失败，因为仓库只提交安全占位配置。发布前在本机创建：

```bash
cp release.config.example.json release.config.json
```

填入真实值：

- 微信小游戏 AppID
- 复活广告位 `revive`
- 日志解锁广告位 `decode`
- 真相提示广告位 `truth`

验收：

```bash
node build.js wechat
npm run release:check
```

目标：

```text
release blocker(s): 0
```

注意：真实 AppID / adUnitId 不提交。

### 2. 微信开发者工具真实导入测试

当前仓库通过 bundle 静态检查证明微信 runtime 不含 DOM/window blocker，但还没有本机微信开发者工具导入实测记录。

任务：

- 安装/定位微信开发者工具。
- 用真实 AppID 打开 `wechat-minigame/`。
- 验证 Canvas 能启动。
- 验证触摸操作生效。
- 验证 `wx.createRewardedVideoAd` 路径可走。

产出：

- 记录截图/日志。
- 更新 `docs/WECHAT_REGRESSION_REPORT.md`。

### 3. 发布模式广告失败兜底复查

最新代码已有 release/dev 模式基础能力，后续需要真平台复查：

- 开发模式：广告失败不阻塞测试。
- 发布模式：广告失败提示重试/稍后再试，不无条件发奖励。
- 微信真机/开发者工具路径与 H5 mock 路径一致。

验收：

```bash
npm test
npm run release:check
```

## P2｜产品留存 / 变现增强

### 4. 局后复盘页继续产品化

已有 post-run summary 基础字段，下一步可以把它做成更明确的局后复盘体验。

展示：

- 存活秒数
- 触发异常数
- 最危险异常
- 解锁隐藏日志数
- 是否触发假结局
- 再试一次
- 看广告解锁异常档案

价值：增强循环、增加广告触点、提高重玩动机。

## P3｜批量复制 / 换皮生产系统

### 7. 第 6 套皮肤候选

可选题材：

1. 无人酒店前台
2. 海上钻井平台控制室
3. 校园广播室异常值班
4. 深夜高速收费站

建议下一套优先 **无人酒店前台**：空间直观，适合前台监控、房卡门禁、电梯厅 CCTV、午夜入住异常。

## P4｜平台工程 / CI

### 8. Android release APK / 签名流程

当前是 debug APK。

任务：

- 增加 release build 文档。
- 增加签名配置模板。
- 私有 keystore 不提交。
- 输出 `app-release.apk`。

### 9. GitHub Actions 增强

当前已有基础 verify workflow，后续可增强：

- 缓存 Android SDK。
- CI 构建 APK。
- 上传 APK artifact。
- release tag 自动上传 APK。

## P5｜体验打磨

### 10. 游戏内新手引导压缩

首局玩家可能还不知道每个按钮的风险。

任务：

- 首局前 10 秒高亮推荐操作。
- 第一次异常时提示“应该优先看监控/日志”。
- 第一次失败时解释复活逻辑。

### 11. 监控画面异常态继续拟真化

当前已有生成式 CCTV 背景、REC/时间码、多摄像头小窗、热源与 HUD。下一步只做异常态增强：

- 异常发生时短暂画面撕裂 / freeze frame
- 红外轮廓闪烁与信号雪花增强
- `data-anomaly="active"` 下才启用强干扰，正常状态保持可读
- 不同皮肤支持不同监控背景资产，例如医院病房 CCTV、地铁站台 CCTV

验收：浏览器截图 + Android WebView 截图都能看出正常态/异常态差异，且操作按钮不被遮挡。

### 12. 音效和震动反馈增强

已有 Web Audio 程序化音效，移动端可继续增加：

- 按钮点击短震
- 异常触发强震
- 失败低频噪声
- 广告复活成功提示音

微信/抖音需要平台能力抽象。

## 建议下一步执行顺序

1. P5-10：继续压缩首局体验，确保 10 秒内看见异常、知道推荐按键。
2. P2-4：局后复盘页继续产品化，强化复玩和广告复活循环。
3. P5-11：异常态监控撕裂 / freeze frame / 红外闪烁。
4. P4-8：Android release APK / 签名流程。
5. P3-7：第 6 套皮肤候选（建议无人酒店前台，等 Game001 单局体验更稳后再做）。
6. P1-2：微信开发者工具真实导入测试。
7. P4-9：GitHub Actions APK artifact 上传。
