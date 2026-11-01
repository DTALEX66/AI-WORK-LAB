# 实施与验证说明

本包参考前端使用普通 HTML/CSS/JavaScript，不依赖框架、在线字体、API密钥或外部服务。它是用于明确视觉与交互的源参考；生产沿用仓库当前可维护技术栈。

## 文件与代码落点

| 本包文件 | 生产建议落点 | 处理原则 |
|---|---|---|
| prototype/styles.css | 现有样式与设计Token模块 | 提取变量和组件规则，不整段覆盖其他业务 |
| prototype/app.js | 现有路由、视图与控制逻辑 | 拆出对应组件；删演示数据与假动作，映射真实服务 |
| assets/art | 现有媒体资源目录 | 保持版本/许可/用途；卡片图可换获准真实案例 |
| assets/icons | 现有Icon组件或图标目录 | SVG currentColor，统一描边与焦点；优先复用现有图标库 |
| specs/design_tokens.json | 现有变量来源 | 避免多源维护；由上游生成时改生成源 |
| contracts/UI_DATA_CONTRACT.json | 既有对象/API的映射文档 | 是语义提案，不直接建立第二套Schema/API |
| specs/page_tasks.json | 既有唯一任务账本 | 12项工作分解映射父任务，保留已有完成证据 |
| screens / slice_map | 视觉基线与媒体参考 | 不成为当前业务事实或永久菜单断言 |

## 原型预览

直接打开 `prototype/index.html`；可用 hash 切换页面，如 `#catalog`、`#teaching`、`#jury`。浅色主题添加 `?theme=light`。`gallery.html` 是截图目录与源参考入口。

为避免浏览器对 file 页面下载或剪贴板的限制，也可在此目录启动已有本地静态服务。剪贴板被禁时可以选中文案复制。原型读取本地文件选择后只显示名称，不上传；localStorage 中仅保存演示意见，无真人签名或生产回执。

演示低频按钮会提示接入位置。生产应实现该按钮的实际行为或隐藏尚不支持的动作，不能复制提示按钮作为“功能已完成”。

## 复现效果图

本次画面由 Chromium 在 1920 × 1080 CSS 像素下真实渲染，4K输出使用 deviceScaleFactor=2；独立SVG以3840 × 2400视口渲染。长页面另有 fullPage 输出，不把被截断的首屏当全部规格。移动端390 × 844 CSS、像素密度2，并提供完整长图。

需要已有 Node.js、Playwright 与可用的 Chromium。渲染脚本优先读 `UI_CHROMIUM_PATH`，未设置时用 Playwright 的默认浏览器。依赖不随交付压缩包打入，也不需要用户为预览安装这些依赖；只有重新导出图时需要。

```bash
python scripts/build_art.py
node scripts/render.mjs
python scripts/build_specs.py
python scripts/build_gallery.py
node scripts/check_ui.mjs
```

如当前环境只有 `python3`，将 `python` 替换为 `python3`。Windows 可用已安装的 Chromium/Chrome 可执行文件设置 `UI_CHROMIUM_PATH`；不得把本次 `/tmp/` 的路径复制到用户电脑。本次临时渲染依赖和浏览器不属于 DESIGN-LAB 的业务安装要求。

## 本次证据

- `evidence/render_report.json`：16页、4窄屏的尺寸、素材加载和页面错误记录。
- `evidence/interaction_report.json`：参考原型本地交互检查；只覆盖明确列出的场景。
- `evidence/package_report.json`：文件清单、资源引用、JSON、PNG尺寸、工作分解依赖与完整性检查。
- `MANIFEST.json`：交付文件的SHA256；不用于重新计算仓库 Authority 通过。

验证原型不等于验证生产：没有进行当前仓库迁移、用户Windows软件操作、双宿主原生往返、真人审美确认、三方知识和学习实联、发布或付费调用。父任务书的历史审计事实保持原来的证据等级，本包未升级它们。

## 避免审计漂移

这份 UI 包的作用是“怎么实施这批前端变化”，不覆盖“产品要做什么”“实际实现到哪里”“允许操作什么”。若仓库当前有效文档仍与最新定位冲突，先按总包完成决定差量、索引、生成器与校验同步，再迁移页面。不要仅改文案或绕过校验，不把本包演示数据写入实际资格记录。
