# Open Design UI 交接说明

这份文件给后续接手的 AI / 开发者使用，目标是把 Open Design 预览里的移动端可玩布局和视觉美化，安全地推回 MINIGAME 游戏源码。

## 当前仓库状态

- 项目根目录：`D:\All projects\MINIGAME`
- 当前已有未提交改动：`index.html`、`styles.css`、`src/game.js`、`tests/preview.test.js`、`android-webview/app/src/main/assets/*`
- 本文件只做交接说明，不覆盖现有游戏源码。
- 最近一次完整验证结果：`npm test` 通过，125 项测试全绿。

## 数量化范围

- 测试文件：28 个，位于 `tests/`
- 皮肤包：5 个，位于 `src/skins/*/skin.json`
- 文档 / manifest：7 个，包含根 `README.md`、Android README、玩法 README、runtime-map、manifest
- 主要脚本入口：6 个，见 `package.json`
  - `npm test`
  - `npm run serve`
  - `npm run android:prepare`
  - `npm run verify`
  - `npm run verify:summary`
  - `npm run skins:check`

## Open Design 产出位置

- 预览 HTML：`D:\All projects\DESIGN-LAB\1d864770-e234-43fe-8994-27bf9350690a\index.html`
- 评分文件：`D:\All projects\DESIGN-LAB\1d864770-e234-43fe-8994-27bf9350690a\critique.json`
- 初版迁移说明：`D:\All projects\DESIGN-LAB\1d864770-e234-43fe-8994-27bf9350690a\implementation-handoff.md`

## 已经在 MINIGAME 落地的部分

这些已经被写入生产源码，不要重复做一遍，只需要复查：

- `index.html`
  - 新增 `#moreActions`
  - 新增 `#secondaryActionsSheet`
  - 新增 `#secondaryActions`
  - 保留 `#forceAnomaly` 为隐藏式诊断入口
- `src/game.js`
  - 新增 `PRIMARY_ACTION_IDS`
  - 主控只保留 `closeDoor`、`moveUp`、`emergencyStop`
  - `openDoor`、`moveDown`、`restartSystem`、`inspectLog`、`unlockHiddenLog` 进入低频层
  - 推荐动作如果在低频层，会点亮“更多”
- `styles.css`
  - 手机竖屏主控改为三键 + 更多按钮
  - 低频操作改为底部层
  - 保持 48px 触控目标
- `tests/preview.test.js`
  - 旧“四列全部按钮”断言已改为“三主控 + 次级底部层”断言
- Android WebView 资产
  - `npm test` / 构建链已同步 `android-webview/app/src/main/assets/*`

## 仍待同步的视觉资源 / 界面美化

Open Design 预览后续做了更完整的视觉美化，这些还没有同步进 MINIGAME 生产源码：

### 1. 视觉系统

把下列思路迁移到 `styles.css`，不要整文件覆盖：

- 深色监控台背景：保留当前深色 HUD，但增加轻微网格背景和玻璃层。
- 面板材质：顶部 HUD、状态卡、操作区、侧栏、底部层统一使用半透明玻璃、内高光、柔和阴影。
- CCTV 主画面：继续使用真实底图资源，不要退回纯 CSS 占位。
- 状态色：沿用当前绿色 / 黄色 / 红色语义，不新增第二套主色。

建议迁移的关键类：

- `body::before`
- `.top-hud`
- `.monitor-card`
- `.monitor-feed`
- `.anomaly-card`
- `.stat`
- `.control-dock`
- `.action-btn:hover`
- `.action-btn:focus-visible`
- `.side-panel`
- `.action-sheet`
- `.feed-top span`
- `.feed-top .rec`
- `.directive-card`

### 2. 原 CCTV 图片引用

生产源码已有这些资源，必须用相对路径，不要用 `file:///`：

- `assets/generated/cctv-elevator-corridor-clear.png`
- `assets/generated/cctv-elevator-corridor-warp.png`
- `assets/generated/cctv-elevator-corridor-figure.png`

生产 `styles.css` 中已有变量：

```css
--cctv-feed: url("assets/generated/cctv-elevator-corridor-clear.png");
--cctv-feed-anomaly: url("assets/generated/cctv-elevator-corridor-warp.png");
--cctv-feed-danger: url("assets/generated/cctv-elevator-corridor-figure.png");
```

不要把 Open Design 里的 `../../MINIGAME/...` 路径同步到生产项目。

### 3. REC 时间码

Open Design 预览新增了 `REC` 时间码。生产同步建议：

- 在监控 HUD 内增加一个 `#recLabel` 或同等元素。
- 在 `src/game.js` 的 `render()` 中根据 `state.elapsed` 或剩余时间刷新。
- 文案格式建议：`REC 02:17:03` 或 `REC 00:42`，保持等宽字体。

### 4. 桌面侧栏建议卡

Open Design 把桌面侧栏底部的说明段落改成两张建议卡：

- “先看 CCTV，再按推荐键”
- “低频动作收进更多”

生产同步建议：

- 不要在手机主界面显示这些说明。
- 只放在桌面侧栏或开始界面的轻量提示区域。
- 样式使用 `.directive-grid` / `.directive-card`，避免长段落。

### 5. 低频操作层 polish

Open Design 对底部层做了这些美化：

- 统一低频按钮高度。
- 移除收起按钮的内联样式，改为 CSS 管理。
- 更多按钮如果承载推荐动作，右上角显示提示点。

生产同步时优先检查：

- `#moreActions[data-recommended="true"]`
- `#secondaryActionsSheet`
- `#closeSecondaryActions`
- 遮罩点击关闭
- Escape 关闭

## 建议执行顺序

1. 从 Open Design `index.html` 中只摘取视觉类，不要整页覆盖。
2. 先改生产 `styles.css`，确保现有 DOM 不变。
3. 再补少量 DOM：`REC` 标签、桌面建议卡。
4. 最后补 `src/game.js` 的 REC 时间刷新。
5. 跑测试。
6. 若测试通过，再同步 Android WebView 资产。

## 必跑验证

```powershell
npm test
npm run android:prepare
npm run verify:summary
```

建议额外人工看三个宽度：

- 360px：主控是否可点，CCTV 是否仍是第一视觉焦点
- 390px：状态条是否单行、不挤压画面
- 430px：更多操作层是否不会遮住主控反馈

## 禁止事项

- 不要整文件覆盖 `styles.css`。
- 不要把 Open Design 的 `file:///` 或 `../../MINIGAME/...` 路径写进生产源码。
- 不要恢复“四列全部按钮”的旧移动端布局。
- 不要把 `#forceAnomaly` 放回主操作区。
- 不要为了视觉效果新增一堆说明文字或设计器控件。
- 不要改 `.env`、系统配置、全局依赖或任何 E 盘路径。

## 推荐给其他 AI 的任务提示

请在 `D:\All projects\MINIGAME` 内工作，只做小步、可回退修改。当前已有 Open Design 交接文件 `OPEN_DESIGN_UI_HANDOFF.md`。请把 Open Design 预览中的视觉 polish 同步到生产 H5：

1. 保留现有“三主控 + 更多操作底部层”的结构。
2. 把玻璃 HUD、CCTV 边框辉光、REC 时间码、桌面建议卡、按钮 hover/focus 样式迁移到 `styles.css` / `index.html` / `src/game.js`。
3. 不要整文件覆盖，不要改无关逻辑。
4. 完成后运行 `npm test`，再运行 `npm run android:prepare`，最后报告 `git diff --stat` 和 `git status --short`。
