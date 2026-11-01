# 来源与核验边界

调研日期：2026-09-28（Asia/Shanghai）。下列为官方文档、上游仓库或用户项目源码；选型结论是工程判断，不是上游背书。未实装比较、未声称性能实测、未按星数判成熟。接入时锁定稳定版本、revision和依赖许可。

|编号|来源|链接|本次用途|
|---|---|---|---|
|R01|当前仓库权威|https://github.com/DTALEX66/DESIGN-LAB/blob/d116b14995fcdbba1b165ec5bc3124f5daed3d15/AUTHORITY.md|GitHub全文读取；顶层架构与证据规则|
|R02|Workbench package|https://github.com/DTALEX66/DESIGN-LAB/blob/d116b14995fcdbba1b165ec5bc3124f5daed3d15/apps/workbench/package.json|Vanilla TS/Vite/Playwright|
|R03|现有界面与路由|https://github.com/DTALEX66/DESIGN-LAB/blob/d116b14995fcdbba1b165ec5bc3124f5daed3d15/apps/workbench/shell.ts|全文取得，定向检查路由/离线/未开放状态|
|R04|CSP和资源路由|https://github.com/DTALEX66/DESIGN-LAB/blob/d116b14995fcdbba1b165ec5bc3124f5daed3d15/src/design_lab/workbench.py|全文检查|
|R05|设计业务|https://github.com/DTALEX66/DESIGN-LAB/blob/d116b14995fcdbba1b165ec5bc3124f5daed3d15/src/design_lab/design_layer.py|对象与方法检查|
|R06|任务账本|https://github.com/DTALEX66/DESIGN-LAB/blob/d116b14995fcdbba1b165ec5bc3124f5daed3d15/design-lab/config/task-ledger-r3.json|28项顶层任务解析；旧前继不重复计数|
|R07|当前CI|https://github.com/DTALEX66/DESIGN-LAB/actions/runs/36336694172|run 407 success；artifact只查元数据未下载|
|S01|Spectrum Web Components|https://opensource.adobe.com/spectrum-web-components/|官方文档|
|S02|Spectrum许可|https://github.com/adobe/spectrum-web-components/blob/main/LICENSE|GitHub LICENSE全文读取 Apache-2.0|
|S03|Spectrum AI技能|https://opensource.adobe.com/spectrum-web-components/build-with-ai/|官方 Gen1/Gen2 skills 和 llms.txt|
|S04|Spectrum Design Data AI|https://opensource.adobe.com/spectrum-design-data/ai/|设计数据查询不等于生成组件|
|S05|Web Awesome|https://webawesome.com/support|Core与Pro范围|
|S06|Web Awesome许可|https://github.com/shoelace-style/webawesome|官方仓库 MIT；Pro独立|
|S07|Fluent UI|https://github.com/microsoft/fluentui|React/Web Components；LICENSE实读MIT|
|S08|shadcn/ui|https://ui.shadcn.com/|官方可定制组件源码|
|S09|shadcn MCP|https://ui.shadcn.com/docs/mcp|组件registry/MCP|
|S10|Radix Primitives|https://www.radix-ui.com/primitives/docs/overview/introduction|无样式React控件|
|S11|Base UI|https://base-ui.com/|React无样式；MIT；非无框架组件|
|S12|React Aria|https://react-spectrum.adobe.com/react-aria/|官方搜索返回；直接页面抓取失败，不引用具体版本|
|S13|Mantine|https://mantine.dev/getting-started/|官方React指南；@mantine包MIT|
|S14|Ant Design许可|https://github.com/ant-design/ant-design/blob/master/LICENSE|GitHub LICENSE实读MIT|
|S15|MUI X许可|https://mui.com/x/introduction/licensing/|Community MIT/Pro Premium商业许可|
|S16|Vaadin许可范围|https://vaadin.com/pricing/faq|核心Apache-2.0；部分商业组件|
|S17|TanStack Table|https://tanstack.com/table/latest/docs/overview|headless；core支持Vanilla，版本API须锁定|
|S18|Uppy|https://uppy.io/docs/dashboard/|导入UI；需适配本项目API|
|S19|PhotoSwipe|https://photoswipe.com/|图像预览；MIT|
|S20|Tiptap|https://tiptap.dev/docs/editor/getting-started/overview|OSS与付费扩展分开|
|S21|AG Grid|https://www.ag-grid.com/javascript-data-grid/key-features/|Community/Enterprise分开|
|S22|Playwright可访问性|https://playwright.dev/docs/accessibility-testing|axe不能替代人工评估|
|S23|Tauri WebView|https://v2.tauri.app/reference/webview-versions/|Windows WebView2|
|S24|Tauri权限|https://v2.tauri.app/reference/config/|IPC capability|
|S25|Photoshop UXP|https://developer.adobe.com/photoshop/uxp/2022/|官方插件脚本与API|
|S26|Illustrator扩展|https://developer.adobe.com/illustrator/|官方脚本/面板API|
|S27|Figma Plugin API|https://developers.figma.com/docs/plugins/|节点读写；用户发起动作；不是后台常驻进程|
|S28|ComfyUI API|https://docs.comfy.org/development/comfyui-server/comms_routes|prompt/history/ws/interrupt|
|S29|Penpot|https://penpot.app/|外部编辑宿主候选；非嵌入本项目画布|
|S30|Shoelace继任说明|https://github.com/shoelace-style/shoelace|官方指向Web Awesome|

补充：原始三份2026-09-28附件已在本会话完整读取，TXT与启动Word一致。本轮未刷新Drive原件；其角色为用户给定输入，不冒充源端最新版本。旧47包UI总归档仅定位到文件，未解包核对；不得宣称完成原稿一比一核验。库的许可证摘要不覆盖图标、字体、模板和付费扩展；以实际锁定文件为准。Blender当前API页及DTCG版本页直接抓取未成功，相关后续项要求执行器查实，不据此指定新版本或承诺兼容。
