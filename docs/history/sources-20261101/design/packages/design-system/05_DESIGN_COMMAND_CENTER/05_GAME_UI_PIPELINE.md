# 05｜GAME UI PIPELINE

## 适用范围
游戏首页、监控室主界面、按钮、弹窗、状态栏、日志窗口、广告复活弹窗、隐藏线索弹窗、结算页、分享页。

## 标准流程
1. Hermes 识别 UI 任务
2. GPT 生成 UI 信息结构
3. CC Switch 审查是否可实现
4. Figma 设计界面
5. Hermes 生成 UI Schema
6. Hermes 生成 Design Tokens
7. Codex 按 Schema 实现
8. 运行截图
9. Vision 审查
10. Hermes 更新设计记忆

## 禁止
Codex 自由发挥、临时改颜色、每个页面单独设计、不通过 tokens 写 UI、大量本地图片、复杂字体包。
