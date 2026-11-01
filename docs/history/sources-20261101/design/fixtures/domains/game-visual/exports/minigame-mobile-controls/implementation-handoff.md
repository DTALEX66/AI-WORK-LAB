# MINIGAME 移动端操作区交接

本轮已把 Open Design 原型里的“少量主控 + 更多操作底部层”迁移到 `D:\All projects\MINIGAME` 生产项目。

## 已落地

- `index.html`：新增 `#moreActions`、`#secondaryActionsSheet`、`#secondaryActions`，保留 `#forceAnomaly` 为隐藏式诊断入口。
- `src/game.js`：新增 `PRIMARY_ACTION_IDS`，仅将 `closeDoor`、`moveUp`、`emergencyStop` 渲染为主控；开门、下行、重启、日志、解码进入低频层。
- `styles.css`：手机竖屏主控改为三键 + 更多按钮；底部层使用遮罩、收起按钮和 48px 触控目标。
- `tests/preview.test.js`：旧“四列全部按钮”断言改为“三主控 + 次级底部层”断言。

## 仍需真机确认

- 360 / 390 / 430px 宽度下，CCTV 区域是否仍是第一视觉焦点。
- 拇指触达区是否符合实机操作习惯。
- 推荐动作为低频操作时，“更多”高亮是否足够明显。
