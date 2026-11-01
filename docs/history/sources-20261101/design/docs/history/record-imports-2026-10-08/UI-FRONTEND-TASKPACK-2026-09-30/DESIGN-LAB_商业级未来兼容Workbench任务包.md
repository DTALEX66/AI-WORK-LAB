# DESIGN-LAB — 商业级未来兼容Workbench任务包

日期：2026-09-30。交付范围：现有前端改造；不是研究报告，也不宣称本包附带已实现源码。

## DESIGN-LAB 产品裁决
现有 apps/workbench/ 是唯一正式前端，strict TypeScript + Vite + pnpm + browser E2E，Python 保持现有 service/runtime。没有 ADR 不整体引入 React/Vue/Electron/Tauri/Avalonia。Lite 是默认轻入口，与 Workbench 共用 Project/Asset/Brief/Task/Evidence/Host state，不创建第二产品。继续 9/28 W00–W17、41 项映射及 R5 ledger，先读取原文件再逐项对账，不重建第四份实时账本。

## 最终 IA 与布局
全局：Lite/Home、Projects、Research、Brand Systems、Design Domains、Creative Tools/Hosts、Preflight/QA、Deliverables、Evidence、Settings。Collaboration 无真实 backend 时仅 feature gate。
项目内固定：Brief→References→Research→Directions→Design System→Create/Production→Versions→Review/Jury→Preflight→Handoff→Evidence。
Shell 左侧全局导航，顶栏项目/保存状态/命令，项目内横向阶段导航，中心专业工作面，右侧可折叠 Inspector。Lite 显示 Continue Project、Recent、Pending Review、Active Production、Recent Deliverables、Host/Capability Status、Quick Launch。不把专业生产面改成通用 SaaS dashboard。

## 实际产品操作
Projects：搜索/筛选/排序、CJK 全标题、recent/pin/lifecycle/stage、saving/conflict/recovery。Brief：create/open/edit/autosave/save/dirty/saving/saved/conflict/draft restore/version/lineage。
References/Assets：drag/drop、batch、progress/cancel/partial failure、完整预览/zoom/透明棋盘格、不默认裁剪、source/rights/license/provenance/dimensions/color space/project isolation。
Directions：多方向 compare/choose/reject/stale/rationale/references，后端支持才 regenerate/revise；Human Choice 必须单独确认。
Design System：现有 DTCG transformer；tokens/typography/color/spacing/radius/components/asset rules/version/diff/publish/rollback/project binding，权限走现有服务，不新建第二 token 格式。
Production：task/host/adapter/permission/plan/progress/object plan/outputs/logs/readback；queued/running/cancel requested/cancelled/failed/timeout/outcome unknown/receipted 明确区分，cancel/retry 依真实能力。
Versions：timeline/preview/compare/lineage/change summary/open source/duplicate 和支持的 restore。Review：automated critique、human jury、issue locator/severity/rationale/accept/reject/revision/compare/re-score；自动评分不等于人工验收。
Preflight：dimensions/resolution/color/bleed/fonts/links/rights/editability/BOM/limitations，每项 issue→locate→fix→rerun→resolved。Deliverables：复用已有 bundle，展示 source/preview/version/hash/size/format/rights/quality/font/links/BOM/provenance/evidence，可重新打开源文件。Evidence 绑定项目、brief、direction、design system、task、host、artifact、version、review、preflight、handoff。

## Host 与设计诊断
Lite/Creative Tools 的 Launcher 检测已配置 Photoshop/Illustrator/Figma/Penpot/ComfyUI/Blender/其他 approved host：path/version/eligibility/launch/project handoff/status/adapter 可支持的 readback，不自动安装。
设计域 MCP diagnostics 显示 endpoint/schema/connection/version/latency/timeout/error/cancel/sanitized logs/supported design actions；全局 MCP 注册、Agent 配置和跨项目路由属于 WORK-LAB。

## 组件策略与动态 VI
首先复用现有 primitives。UI08 Spectrum 和 UI09 Web Awesome Core 只做同一控件矩阵兼容试验：Button/Input/Select/Tabs/Dialog/Drawer/Tooltip/Table/Progress/Toast，检查 CSP/Shadow DOM/offline/Vite/wheel/IME/keyboard/focus/bundle/startup。最多采用一个，失败继续现有组件。UI01/UI03/UI04/UI05/UI06 不能成为引入 React 的理由；UI02 可选许可明确的原生 CSS，UI11/SVG/Canvas 可承担轻量关系图。UI12 只参考专业资产浏览器、Inspector 和版本行为。
近黑/charcoal、white/cool gray、Electric Blue；紫色主要属于作品，不变成 AAOS 金青或 WORK-LAB cyan console。主区是可互动真实作品预览、资产和工具；星环可表示方向对比/版本关系，不能盖住作品或用动画冒充 preflight 进度。hover 120ms/base180ms/drawer280ms/emphasis≤420ms，保存/导入/host/生产/preflight/review 动画连接真实 process。生成静态 hero 不承担核心工作面，优先交互矢量和状态组件。业务参考图片与作品预览保留，不误删。

## 两条 Golden Flow
A：DESIGN-LAB designs DESIGN-LAB：Brief→References→Research→3 Directions→Human Choice→Design System→Workbench Implementation→Browser E2E→Quality→Accessibility→Human Jury→Preflight→Handoff。
B：真实商业视觉：Brief→References→Directions→Design System→DesignIR→Photoshop/Illustrator→editable artifact→readback→patch→critique→Human Jury→preflight→handoff→reopen。PNG-only 不算完成。缺 host 或 contract 标记阻塞，不造 readback。

## DESIGN-LAB DoD
pnpm frozen install、strict typecheck/build/unit/Playwright；CSP/offline/keyboard/IME/save-reload/conflict/import-cancel/partial failure/Direction selection/token edit-diff-rollback/production states/review revision/preflight rerun/bundle readback。重点 Windows 2560×1440/1920×1080、125%/150% DPI、clipboard/drag-drop，tablet 收折 Inspector，mobile 只保 review/approval/status。
正式链路必须验证 packaged Workbench resources→production Python service/wheel→browser；包含 assets packaging、API origin、refresh/deep link、offline resources 和 restart persistence。不能只启动 Vite。只有全条件通过才标记 `DESIGNLAB_FRONTEND_COMMERCIAL_RC_READY`。
输出 DESIGNLAB_FRONTEND_COMPLETION_REPORT.md、DESIGNLAB_FINAL_IA.md、DESIGNLAB_VISUAL_QA.md、DESIGNLAB_HOST_UI_MATRIX.md、DESIGNLAB_ASSET_MANIFEST.json、DESIGNLAB_FRONTEND_GOLDEN_FLOWS.md、DESIGNLAB_MERGE_READY_HANDOFF.md；不自行 merge/release。

## 执行权威与边界
本包依据本轮完整对话编制，是前端实施指令，不宣称已重新审计云端仓库，也不替代仓库 Authority。执行器必须先读取 LIVE origin/main、AUTHORITY.md、authority index、AGENTS.md、当前 TaskPack、真实 API/contracts 和正式前端代码，再读取 2026-09-28–29 的本项目 Master Atlas、历史补充与 UI 包。未能读取的来源登记 MISSING，不得编造。历史蓝图不是实现证据；最新 Authority 决定是否可执行，用户当前要求决定本轮产品范围。冲突列明具体文件、条款及代码证据，在不受影响的范围继续推进。

只在现有正式前端修复、集成和更新，不创建第二 frontend、runtime、task ledger、evidence store、config authority 或全局 design system。保留 route、API、contract、索引 ID、路径、深链及持久化 identity。使用独立 UI 分支/worktree；先记录 branch/SHA/dirty，保护未提交工作，不直接修改 main，不自行 merge/release。执行器可用 Codex、Hermes、DSH，模型不锁死。

## 接口和未来能力契约
改代码前生成逐项兼容矩阵：原 route/别名、组件实际路径、API method/path、request/response schema、service authority、权限、deep link、存储 key、现有测试、变更后位置、兼容策略。本包不虚构项目内部路径。重组导航只改变展示分组，旧 route 保持或采用有测试的兼容别名，不静默删除。
能力条目复用现有 schema；确需扩展时提交最小 ADR。字段至少含稳定 capabilityId、domain、来源、owner、route、contractRef、implementationState、availability、permission、lastProbe、evidenceRef、reason、nextAction。实施状态与运行可用状态分离：PLANNED/EXPERIMENTAL/IMPLEMENTED 和 UNKNOWN/AVAILABLE/STALE/OFFLINE/BLOCKED。无 backend 的蓝图页提供目标、依赖、接入点、来源及只读说明，不伪造成功或可执行按钮。未来能力只引用单一现有登记表，不创建平行账本。

## 开源供应链：先复用，再定制
按以下索引先读取官方组件和源码；只下载实际需要的组件，不把整个示例应用复制为新前端。每项集成记录索引 ID、official URL、固定 commit/version、LICENSE 和文件级版权、source 文件、目标路径、token remap、依赖、大小、修改点与测试。免费展示不等于允许源码再分发；付费模板不下载不打包。第三方 logo 遵循商标要求，不确定时用通用 glyph + text。

| ID | 官方入口 | 用途与集成限制 |
|---|---|---|
| UI01 | https://github.com/shadcn-ui/ui ; https://ui.shadcn.com/docs | React 正式栈的 Button/Dialog/Drawer/Command/Table/Sidebar primitives；已有实现优先保留 |
| UI02 | https://github.com/uiverse-io/galaxy ; https://uiverse.io | GALAXY 指 UI 元素库，不代表星空引擎；选择 CSS/Tailwind 状态控件、进度和卡片，逐项确认许可 |
| UI03 | https://github.com/magicuidesign/magicui ; https://magicui.design | Orbiting Circles/Animated Beam 等动态元素候选；先核实官方当前 registry 和组件文件，不猜安装 URL |
| UI04 | https://github.com/DavidHDev/react-bits ; https://reactbits.dev | 粒子/星空/交互效果参考；核查当前 LICENSE，React 代码不能直接塞入非 React 前端 |
| UI05 | https://ui.aceternity.com/components ; https://ui.aceternity.com/licence | Stars/Beams/Card 效果候选；免费与 Pro、产品使用与源码分发须分开核查 |
| UI06 | https://github.com/DouyinFE/semi-design ; https://semi.design | 成品表格/表单/布局参考；React 项目也不整体引入第二设计系统，非 React 项目只参考行为 |
| UI07 | https://tailwindcss.com/docs | 只沿用仓库现有 Tailwind 版本，禁止为素材强行升级全项目 |
| UI08 | https://github.com/adobe/spectrum-web-components ; https://opensource.adobe.com/spectrum-web-components/ | DESIGN-LAB 原生 Web Components 兼容试验候选 |
| UI09 | https://github.com/shoelace-style/webawesome ; https://webawesome.com | DESIGN-LAB Web Awesome Core 兼容试验候选；只选择允许使用的 Core 部分 |
| UI10 | https://github.com/xyflow/xyflow ; https://reactflow.dev | React 节点工作流候选；只有既有 contract 和明确编辑权限才提供写操作 |
| UI11 | https://github.com/d3/d3 ; https://d3js.org | 非 React 数据网络、布局和可视化候选；SVG/Canvas 可保留原技术栈 |
| UI12 | https://github.com/penpot/penpot | 专业设计工作台布局与 Inspector 行为参考；不复制整个产品，核查具体源码许可 |
| UI13 | https://github.com/langgenius/dify ; https://github.com/n8n-io/n8n | 工作流、执行详情和治理 UX 参考；并非统一宽松开源授权，不直接复制受限制素材 |
| UI14 | https://github.com/lucide-icons/lucide ; https://lucide.dev | 优先复用现有图标体系，非 React 使用对应 vanilla 入口 |

执行顺序：读取官方源码/registry→确认许可和依赖→固定版本→下载到临时来源目录→复制最小文件到既有 components 路径→替换品牌 tokens→连接真实 adapters→测试→移除未采用临时素材。源码可用 `git clone --depth 1 <上表官方仓库URL> <临时来源目录>` 获取，随后记录 `git rev-parse HEAD`，不要把浮动 main 当长期锁定版本。React 项目若已配置 shadcn，可使用 `pnpm dlx shadcn@<已核实版本> add button dialog sheet command tabs tooltip table`，运行前核查 components.json 和覆盖清单。其他 registry 必须以官方当前命令为准；不猜 URL，不盲目运行远程 shell。依赖安装使用仓库锁文件和包管理器，不自动下载新工具链。最终保留 license attribution。

## 动态视觉统一要求
产品主体必须是可交互组件，不用生成的静态配图承载数据、状态、流程或能力地图。星空、星环、轨道、粒子、星座节点可以复用，作为局部品牌氛围和有意义的数据视图；布局、文字、卡片和主要操作始终清晰。点击节点进入已有详情，hover/focus 显示真实证据，筛选影响真实数据。轨道运动不可伪装执行进度；无数据使用明确 empty/unknown。
按组件登记静态旧图→替换位置→真实数据源→交互→动效→降级方案。装饰动画与语义动画分开：装饰可关闭，语义对应真实状态。优先 SVG/CSS/Canvas，WebGL 仅在有测量收益时采用。后台/不可见时暂停，避免每张卡独立渲染循环。支持 prefers-reduced-motion、高对比度、键盘和读屏；简化动画后仍能理解所有状态。不自动引入重型 3D runtime。

## 商业级状态与验收
所有页面覆盖 loading、empty、success、partial、error、offline、stale、permission denied、conflict 和 recovery；无数据不造 KPI。真实写操作统一经现有服务→执行→receipt→readback，处理重复提交、超时 outcome unknown、重启恢复；不能用 toast 当成功证据。保留用户上下文和选中项。
先完成 shell/核心工作面，再按合同接通页面，再加动效和供应链元素。每阶段提交可审查 diff，记录文件、接口、截图、命令结果和阻塞。执行仓库已有 typecheck/unit/build/E2E；不在脚本未知时杜撰命令。验证 route 深链、刷新、持久化、offline、CSP、键盘、焦点恢复、Escape、Ctrl/Cmd+K、aria-current/live、中文 IME、125%/150% DPI、深浅色和 reduced motion。Windows 专属测试须真实 Windows 执行；Linux 结果不得写成 Windows PASS。缺环境可完成其余工作并交付明确 BLOCKED，不虚报 RC_READY。
截图保留 1280×820、1920×1080、2560×1440 和指定窄屏，覆盖关键成功/失败/空状态。最终交付源码 diff、兼容矩阵、来源许可清单、测试证据、截图矩阵、回滚路径及 merge-ready handoff；报告可由执行器在仓库生成，本下载包本身只含两份 Markdown。只有所有实际 DoD 达成才标记各项目 COMMERCIAL_RC_READY。
