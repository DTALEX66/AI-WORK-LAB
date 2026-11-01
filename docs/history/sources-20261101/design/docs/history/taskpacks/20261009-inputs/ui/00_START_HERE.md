# DESIGN-LAB UI 前端任务包

版本 UI-20261009-r1。本包是 2026-10-09 最终任务包的前端实施补充：将能力资产、需求响应、专业自动化和成果反馈落实为界面。它不替代仓库当前权威入口，不证明产品或宿主已经上线。

## 给 Agent 的使用顺序

1. 阅读 `01_AGENT_EXECUTION.md`，再读上一份总任务包的 `02_CODEX_EXECUTION.md`。先核对仓库实际 HEAD、当前任务账本与品牌资产。
2. 阅读 `specs/01_PRODUCT_AND_PAGES.md`、`specs/02_INTERACTIONS_AND_STATES.md` 和 `contracts/UI_DATA_CONTRACT.json`。
3. 从 `screens/4k/` 选定页面作为视觉目标；页面编号与本批实施任务见 `specs/page_tasks.json`。
4. 用 `prototype/index.html` 查看可编辑布局与本地演示交互。双击打开即可，不依赖在线字体或 CDN；也可由任意本地静态服务打开。
5. 优先使用 `assets/art/*.svg`；需要位图时使用对应 `_4k.png`。详见 `specs/03_ASSET_USE_AND_GENERATION.md` 与 `specs/asset_manifest.json`。
6. 切片位置见 `specs/slice_map.json`。文字、按钮、状态和表格重建为组件，不能把整页截图当页面部署。

## 包含什么

- 16 个深色桌面页面：能力目录、能力详情、输入、分析、目标包、执行、恢复、成果目录、产物改稿、评审、交付、反馈、教学需求、连接、状态、组件规范。
- 同版式的 1920 × 1080 PNG 与 3840 × 2160 高清 PNG。4K 为 1920 CSS 像素在 2 倍像素密度下重新渲染，文字重新栅格化，不是低清放大。
- 浅色能力目录及 4 个移动端页面；移动端另附完整滚动长图。
- 10 套独立 SVG 插图及 3840 × 2400 高清 PNG，用于 UI 示例、卡片及教学表达展示。
- HTML / CSS / JavaScript 参考、设计变量、组件合同、页面任务、数据合同、验收清单、再生成说明与本地渲染记录。
- 上一份任务书、任务索引与前端规格的只读参考快照，以及已核对品牌概念板。

## 状态与范围

本包中的数值、知识 ID、任务 ID、案例与评审均是明确标识的演示数据。原型能导航、搜索筛选、选择本地文件、下载示例、保存本地意见草稿及演示暂停/取消；它不调用真实宿主、AAOS、WORK-LAB 或生产评审接口。其他低频动作只提示其真实接入位置。

产品实现仍应复用当前 TS/Vite、Python、NativeWorkers 与已有对象。本包不强制 React，不删除项目数据结构，不开第二套运行时、知识主库、课程平台或任务账本。

本次没有访问用户 Windows 的 `D:\All projects\UI套件`，也没有重新审计 Git 远端。已有确认的品牌/组件资产若与本包视觉细节不同，应先核对并复用；本包里的旧品牌参考不是重新设计 LOGO 的授权。

## 推荐本地摆放

可解压到 `D:\All projects\UI套件\DESIGN-LAB_UI_Frontend_20261009`，再把该目录、`01_AGENT_EXECUTION.md` 与上一份总任务包一起交给 Codex / Hermes。解压路径是建议，本次没有写入本机目录。

总体预览见 `DESIGN-LAB_UI_总览_20261009.png`，页面缩略图库见 `gallery.html`。效果图数量是本批交付范围，不作为产品菜单数量或永久测试约束。
