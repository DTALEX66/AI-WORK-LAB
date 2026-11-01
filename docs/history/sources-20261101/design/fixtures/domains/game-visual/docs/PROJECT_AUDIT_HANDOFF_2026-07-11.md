# MINIGAME 全面审计与初步修复交接（2026-07-11）

> 仓库：`DTALEX66/MINIGAME`
> 本地：`D:\All projects\MINIGAME`
> 审计起始基线：`main` / `d744c1a`；交付前已同步远端视觉资源提交 `ddd1ee1`
> 本文将工具/测试证据与产品判断分开记录；完成度百分比是审计估算，不是可自动证明的验收结果。测试通过也不等于真机或发布验收完成。

## 1. 结论先行

当前仓库的准确定位是：

> **一款已具备 H5、微信 Canvas、Android WebView 构建链和多套主题数据的“异常电梯”可玩原型，而不是已经完成的小游戏合集平台。**

本轮已完成第一批 P0 修复，重点解决结算、广告发奖、移动端布局和异常视觉基线问题；尚未补齐“合集平台”“真正找异常决策链”“零代码换皮”和真机发布闭环。

### 审计后完成度估算（非自动验收，不按测试数量）

| 能力 | 本轮前估算 | 初步修复后 | 说明 |
|---|---:|---:|---|
| 单款电梯状态生存原型 | 65% | **75%** | 成功/失败结算、假结局跨局计数和视觉基线已修正 |
| 完整“找异常”玩法 | 40% | **45%** | CCTV 可建立正常基线，但仍缺识别/报告/判定闭环 |
| IAA 三触点跨平台闭环 | 30% | **60%** | 发布模式失败不发奖；Canvas 解码必须经过广告奖励回调 |
| 多皮肤零代码换皮 | 25% | **25%** | 仍固定 elevator 构建，Canvas 场景和动作语义仍电梯化 |
| 小游戏合集平台 | 15% | **15%** | 仍只有一个 game manifest，无合集入口/registry/第二游戏 |
| 留存与内容运营 | 20% | **25%** | H5 档案可用；小游戏端档案、埋点和分享仍未闭环 |
| 正式发布准备度 | 受阻 | **仍受阻** | 真实 AppID、3 个广告位、签名和真机验收均缺失 |

## 2. 用户要求汇总与真实状态

| 用户/项目要求 | 状态 | 证据或差距 |
|---|---|---|
| 中文优先、竖屏、无键盘、单局约 60 秒 | **已实现/自动验证** | `gameConfig.js`、触摸按钮、portrait 配置与测试 |
| CCTV 是第一视觉焦点，界面像游戏而不是后台表单 | **已实现（桌面）** | 桌面预览中 CCTV 占主画面；HUD/监控资源已接入 |
| 手机竖屏控制可达、避免右侧裁切 | **自动契约已修复，真机待验** | 常规 portrait 使用 `100%` + `100dvh` 固定网格；高度 ≤620px 时改为 shell 内滚动防裁切；字体放大、安全区和真机仍需验收 |
| 正常画面与异常画面可辨，不能常态显示完整异常答案 | **本轮修复** | clear 态隐藏门缝、影子、热源、检测框和异常循环；active 态再显示 |
| 成功值守与失败必须有不同结算 | **本轮修复** | `state.result = playing/success/failure`；H5/Canvas 成功态无广告复活按钮 |
| 假结局连续失败 N 次可真实到达 | **本轮修复** | 重开保留跨局失败计数/冷却，只清理本局状态 |
| IAA：复活、解码、假结局真相三个触点 | **初步闭环** | H5 三触点已有；Canvas 解码已改为广告回调后解锁 |
| 正式模式广告失败或重复回调不能重复发奖励 | **本轮修复/自动验证** | H5 微信/抖音与 Canvas 均采用单次 attempt 结算；重复 close/error、乱序回调和并发 show 已有测试；发布检查要求 `releaseMode=true` |
| 所有展示文案来自皮肤 JSON | **未完成** | `src/game.js`、`uiLabels.js`、`index.html` 仍有展示文案/回退文本硬编码 |
| 换皮只改 JSON，不改逻辑 | **未完成** | `skinManager.js` 和 `build.js` 默认固定 elevator；Canvas CCTV/状态/动作语义仍偏电梯 |
| 5+ 内容皮肤真正可玩 | **仅数据和契约通过** | 多份 `skin.json` 可通过 schema/单测，但没有玩家可见皮肤选择及逐皮肤端到端验收 |
| MINIGAME 是小游戏合集平台 | **未完成** | `games/` 只有一个首发游戏，没有全局 registry、合集首页、第二独立 game-id/runtime |
| 微信、抖音、Android 多端 | **构建链存在，真机未验证** | 微信 strict bundle 和 Android APK 可自动验证；抖音/微信开发者工具及真机尚未验收 |
| 全自动验证、不得伪造结果 | **已遵守** | 本轮新增测试均先失败后修复；最终结果以真实命令输出为准 |

## 3. 本轮初步修复清单

### P0：结算正确性

- 新增显式 `state.result`：`playing | success | failure`。
- 60 秒倒计时结束后进入绿色成功结算，而不是“系统崩溃”。
- 成功结算隐藏激励复活，只保留重新开始。
- 成功态关闭危险抖动、故障噪声和红色视觉基调。
- H5 与 Canvas 使用同一结果语义。

### P0：激励广告防绕过

- 微信/抖音平台广告 `show/load` 失败时，发布模式不再发奖励。
- Canvas 运行时广告使用单次 attempt 状态，只有 `onClose({isEnded:true})` 发奖。
- Canvas “解码加密记录”不再直接调用 `performAction`，必须走 decode 广告奖励回调。
- `release:check` 新增 `releaseMode=true` 阻断条件。
- `release.config.example.json` 默认使用 `releaseMode: true`。

### P0：假结局可达性

- 重开使用 `restartRuntimeSession({ state })`。
- 保留 `consecutiveFailures`、`fakeEndingCooldownRemaining`、`fakeEndingCount`。
- 清理本局 elapsed、gameOver、result、触发/解锁展示状态。
- 成功值守仍会重置连续失败计数。

### P0：移动端和 CCTV

- 常规高度 portrait 使用固定一屏控制台；高度 ≤620px、字体放大或安全区挤压时，shell 内滚动作为防裁切回退。
- `width: 100vw` 改为 `width: 100%`，避免滚动条宽度造成右侧裁切。
- 主网格固定顺序：CCTV → 主操作 → 状态 → 日志；日志内部滚动。
- 调试用“触发异常”按钮默认隐藏，仅 `?debug=1` 显示。
- clear 态隐藏异常实体，active 态才显示异常线索和动画。

### 自动化测试

测试数由 **125** 增至 **156**（含同步远端 `ddd1ee1` 后新增的资源覆盖测试与 UI V3 契约测试），新增覆盖：

- 成功/失败/复活结果状态；
- 成功结算 H5/Canvas 分支；
- 成功态视觉；
- 假结局跨局计数；
- 正式模式广告失败不发奖；
- Canvas 广告只完整观看发奖一次；
- Canvas 解码广告门禁；
- clear CCTV 基线；
- 最终移动 portrait 规则和默认隐藏调试按钮；
- 同一 tick 倒计时归零与资源越界时，成功结算具有明确优先级；
- 微信/抖音重复 close/error、乱序回调和并发 show 只结算一次；
- H5/Canvas 广告 attempt 携带发起局 `runToken`，重开后到达的旧 revive/decode/truth 回调会被拒绝；
- Canvas CCTV 向量场景消费共享 `cctvState`，对断电、信号故障、实体与高威胁状态采用不同处理；
- ≤620px 短竖屏使用 shell 内滚动防止固定视口裁切；
- UI V3 桌面三列驾驶舱、移动四按钮操作轨和可达开始层；
- Canvas V3 使用 CCTV-first 纵向布局、88 设计像素按钮和共享点击热区；
- 发布检查要求 fail-closed 模式。

### UI V3 全量视觉重构

`MINIGAME_UI_All_Assets_Pack_v2.zip` 已实测审查：428 PNG 中存在高比例近重复、AI 伪文字、边缘零留白和自动切片残片，因此未直接入库。已改用原生 CSS/Canvas 组件与项目现有无文字 CCTV 状态图，完整规格及尺寸证据见：

- `docs/UI_V3_FULL_REDESIGN_2026-07-12.md`
- 桌面：1365×768，CCTV 实测 845×676px；
- 竖屏：390×844 无横向溢出；
- 短屏：360×640 无横向/纵向页面溢出，四键均为 81×56px；
- Android WebView 与微信 bundle 已由 `npm run verify` 重新生成。

## 4. 尚未完成的问题（下一轮按顺序处理）

### P0：真正“找异常”决策链

当前异常由系统自动施加，玩家主要做状态处置；还不是完整的“观察 → 识别 → 报告/选择 → 判定 → 奖惩”玩法。

下一步应新增：

1. 每个事件的正常规则和可观察线索；
2. “报告异常/判定正常”动作或目标区域选择；
3. 识别正确、误报、漏报、超时四类结果；
4. 线索与 CCTV 具体视觉层一一对应；
5. 每局至少形成 3–5 个明确判断回合，而不只是数值压力。

验收：固定随机种子下，可自动证明正确识别得分、误报受罚、漏报受罚，且 60 秒内存在完整胜负闭环。

### P0：多皮肤不是零代码换皮

需要：

- 建立 `skinCatalog` 和玩家可见选择入口；
- `build.js --skin=<id>` 或环境变量选择构建皮肤；
- Canvas 场景、状态字段和动作图标从 skin/content-pack 描述生成；
- 每套皮肤至少做 H5 + Canvas 冒烟和截图验收；
- 移除逻辑层剩余玩家可见硬编码文本。

### P1：真正的合集平台

需要：

- `games/catalog.json` 或等价全局 registry；
- 合集首页、进入游戏、返回合集、恢复上次游戏；
- 至少第二个独立 game-id/runtime（不能只是另一套 skin）；
- manifest schema 与契约测试；
- 构建目标按 game-id 选择，而不是始终构建首发游戏。

### P1：H5/Canvas 功能对齐

Canvas 端仍缺或不完整：

- 开始接管门禁；
- H5 档案库等价能力；
- 完整埋点；
- 皮肤选择；
- 局后复盘信息量；
- 无障碍替代方案和平台振动/音效一致性。

### P1：发布与真机

外部阻塞项：

1. 微信小游戏真实 AppID；
2. revive/decode/truth 三个真实激励广告位；
3. 抖音小游戏 AppID/广告位；
4. Android 正式签名、versionCode/versionName 和 release APK/AAB；
5. 微信开发者工具、抖音开发者工具、Android 真机触摸/返回键/生命周期验收。

这些值不得写入公开仓库；使用 ignored 的 `release.config.json` / `project.private.config.json`。

### P2：文档和工程债

- `docs/WECHAT_REGRESSION_REPORT.md` 记录的是旧 DOM bundle 阻塞，已被当前 Canvas strict bundle 状态取代，应重写或标注历史。
- 游戏 manifest 仍写 5 套皮肤及 hotel candidate，与当前目录可能不一致，应由 catalog 自动生成。
- `styles.css` 存在多轮视觉覆盖叠加，后续应在截图基线稳定后合并为单一 desktop/tablet/portrait 结构。
- Android WebView 需补弹层优先返回、生命周期清理及真机验证。

## 5. 本轮验收命令

```bash
npm test
npm run skins:check
node build.js wechat
node scripts/check-wechat-bundle.mjs --strict
npm run android:build
npm run android:inspect
npm run verify
npm run release:check
```

预期：

- `npm test`：156/156 通过；
- `npm run verify`：单元测试、微信 strict、Android APK build/metadata 全部通过；
- `npm run release:check`：在没有私有发布配置时应**失败关闭**，列出 `releaseMode/AppID/adUnits` 等 blocker，这不是测试失败，而是发布保护生效。

## 6. 接手执行顺序

1. 从本文 P0“真正找异常决策链”开始，不先堆新皮肤。
2. 以测试固定一条完整识别回合，再扩展异常目录。
3. 完成 H5 后同步 Canvas，不允许只改一端。
4. 然后实现 skin catalog/build skin 选择。
5. 最后建立第二独立游戏和合集 registry。
6. 每轮结束必须运行 `npm run verify`；涉及 UI 必须保留真实桌面/竖屏截图证据。

## 7. 禁止误报

在以下证据补齐前，不得对外声称：

- “已经是完整小游戏合集平台”；
- “5/6 套皮肤均零代码可玩”；
- “微信/抖音真机可发布”；
- “广告已完成正式商业接入”；
- “Android 已完成商店发布”；
- “找异常玩法已完整”。
