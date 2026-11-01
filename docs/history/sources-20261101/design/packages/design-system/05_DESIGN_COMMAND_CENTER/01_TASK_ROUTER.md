# 01｜TASK ROUTER

Hermes 收到任务后，先进行任务类型判断。

## Graphic Design｜平面设计
关键词：封面、海报、小红书、抖音、作品集、宣传图、KV、长图、招聘、排版、视觉。
调用：GPT → DeepSeek → Qwen → Figma/Photopea/PS → Vision → Hermes。
不默认调用 Codex。

## Game UI｜游戏界面
关键词：界面、按钮、弹窗、状态栏、监控窗口、UI、主界面、结算页、广告弹窗。
调用：GPT → CC Switch → Figma → Hermes生成 UI Schema + Tokens → Codex → Vision → Hermes。

## Content｜内容
关键词：剧情、文案、日志、事件、标题、脚本、规则、结局、小红书文案、抖音脚本。
调用：DeepSeek → Qwen → GPT → Hermes。
不调用 Codex。

## Code｜代码
关键词：实现、接入、读取JSON、绑定按钮、修bug、运行、构建、导出。
调用：CC Switch → Codex → Hermes。
