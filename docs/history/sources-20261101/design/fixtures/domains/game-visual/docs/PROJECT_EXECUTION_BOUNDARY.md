# MINIGAME 项目执行边界

> 本文件是 `D:/All projects/MINIGAME` 的项目级执行约束；不修改、不覆盖 Hermes 全局规则。

## 允许范围

- 仅修改本仓库：`D:/All projects/MINIGAME`。
- 当前产品范围仅为 Game001《异常电梯》V5「夜班协议」。
- 当前开发分支：`feat/game001-v5-night-protocol`。
- 允许修改 V5 的 Canvas Runtime、玩法状态、内容、音效/震动、测试、构建产物和项目文档。
- 每个功能切片必须有真实验收标准，按 RED → GREEN → 全量门禁 → commit → push 闭环。
- 正式发布配置只能通过本机 ignored 配置注入；公开仓库只保留可移植的项目配置和构建逻辑。

## 数据与产物边界

- 临时截图、headless profile、测试输出、缓存和运行态只允许写入项目内 `.tmp/`、`.tmp-chrome*/`、`test-output/`、`coverage/` 或 `.hermes/`。
- 保留 `.git/`、源代码、测试、运行时资产、音频、截图验收证据和唯一恢复文件。
- `release.config.json`、`douyin-minigame/project.private.config.json`、`wechat-minigame/project.private.config.json` 不上传云端。
- 不把任务状态、agent 输出、缓存或日志散落到 `C:/Users/ALEX`。

## 明确禁止

- 不修改 Hermes 全局 config、skills、plugins、memory、cron 或其他 profile。
- 不访问、修改、删除、迁移其他项目，尤其是 Cognitive-Loop-OS 等 OS 系统项目。
- 不开发第二个游戏、小游戏合集、商城、排行榜、皮肤扩张或 Unity/Cocos 重构。
- 不把 `ui-v5-full` 的 393×852/360×640 完整参考图整张贴入 Runtime。
- 不缩短 CCTV 窗口适配图片；必须让图片适配既有 CCTV 主布局。
- 不制造 mock、占位截图、假 CI、假真机测试或重复空跑提交。
- 不强推、不覆盖用户未提交内容。
- 用户已打开抖音开发工具时，不重启、关闭或重新打开它；只能使用现有窗口进行编译/截图/交互验证。

## 当前依赖顺序

1. V5 身份回合正式结算（已完成）。
2. 三条三阶段事件链正式 Runtime 调度、推进、后果与复盘接线（当前任务）。
3. 事件链真实运行路径和双尺寸状态回归。
4. 抖音开发工具现有窗口的完整 V5 实机路径验收（窗口不可用时必须明确标注未验收）。
5. 包体、声光电和发布门禁收口。

## 完成声明门禁

只有同时具备以下证据，才能声明一个切片完成：

- 代码路径被正式入口调用，而不只是文件或单元测试存在；
- 失败路径和恢复/回滚行为有测试；
- `npm test`、内容校验、`npm run douyin:check` 等适用门禁通过；
- 生成 Bundle 与源代码一致；
- commit SHA 已推送并通过远端 SHA 回读；
- 官方模拟器/实机证据与测试证据分开陈述，未执行的部分不得伪称完成。
