# AAOS Windows 原生 UI 深度优化：资源调研与 Codex 执行方案

日期：2026-09-28。范围：ArcheAxis / AAOS；不扩展 WORK-LAB 或 DESIGN-LAB。

本文件是本轮研究与执行建议，不是新的项目权威、TaskPack 或 current state。未读取用户尚未上传的 Windows 工作树，未对本地 Codex 的实际代码质量作结论，未安装插件或修改项目。最终依赖版本由本地实际锁文件和兼容验证决定。

## 1. 结论

Windows 和 Avalonia 能实现精细的品牌桌面界面，可以采用自然语言驱动的 AI 迭代开发。有效组合是：既有视觉资料 + 原生设计系统 + 适配版本的组件库 + 设计/框架技能 + 真实窗口截图与交互反馈。只给“做得好看一点”、只通过编译、只装一堆技能，都不足以保证结果。

推荐路线：保留 C#/Avalonia → Rust authoritative Core → isolated Python workers。优先沿用已有主题体系并建立 AAOS ControlTheme；若现有控件层几乎为空，以 Semi.Avalonia + Ursa 做一个小范围兼容试验，与官方 FluentTheme 路线比较后选一。已经深入使用 FluentAvalonia 的工程应优先沿用它，避免重建。不要同时挂载 Semi、Material、FluentAvalonia 多套全局控件样式。

## 2. 原始资料实读结果

已找到《三项目_全部47个压缩包_按批次总归档.zip》，大小 230,688,271 字节。检查外层目录和公共索引，仅深入阅读 AAOS 专属资料；13 个 AAOS 专属内嵌 ZIP 的 SHA-256 全部与归档清单一致。未把三项目合并包当成本项目输入。

13 包为：B01 的 UI、VI、VI+UI 三包；B02 细节包；B03 页面包与配色纠正包；B04 组件/Tokens；B05 12 页面；B06 交互状态；B07 工程规范；B08 React 原型；B09 交互 Demo；B10 最终静态 UI。

重点读取了公共批次规则、AAOS 专用开发提示词、B04/B06/B07 Tokens、B10 README 与 HTML 实现，并查看配色母版和 L5 Home/Evidence Detail/Review 页面。四张本轮附件也已打开：两张三项目展板只采纳中列 AAOS；两张浅色界面参考布局与细节。

### 实际发现

| 证据 | 观察 | 对本次研发的影响 |
|---|---|---|
| B05 Home 图 | 所有侧栏入口采用近似相同的圆点，内容主要为矩形、KPI、简化图形 | 它是结构参考，视觉精度不能作为上限 |
| B05 Evidence Detail 图 | 原文区域大量横线占位，证据详情页面选中“原创” | 正式 UI 需要真实正文、证据定位、正确导航状态 |
| B05 Review 图 | 以数字和柱状图为主，选中“设置” | 应升级成可作答/揭示答案/评分的学习工作区 |
| B10 index.html | 1013 行、42376 字节；README 明确静态前端与 localStorage | 不是 Avalonia 产品代码，也不是真实业务闭环 |
| B10 renderHome | 存在固定“12”“72%”展示值 | 不得继承到正式 KPI |
| B10 graph drawer | 关联条目与活动使用 Math.random | 仅为演示，不是证据关系 |
| B10 gradeBtn | 所有评分均 reviewDeck.shift，然后写 localStorage | 不是真实 FSRS；必须接现有 Rust 调度 |
| B06 hover.border | 指向 secondary，secondary 是金色 | 与“金色仅极少证据强调”冲突，建议改为 teal/中性 hover |
| B10 primary-btn | 主色与 secondary 混合，并使用白色文字 | 需要重新校验品牌语义与文字对比度 |

这些发现不证明本地 Codex 已复制这些错误；它们说明“照包做”仍需要设计判断和原生适配。

### 资料优先级

1. Owner 最新明确要求、仓库现行权威、真实契约与最新代码事实。
2. 2026-09-28 任务文档规定的原生架构、真实状态、M0 范围。
3. 归档中的视觉继承顺序 B10 > B09 > B08 > B07 > B06 > B05 > B04 > B03 > B02 > B01；颜色额外核对 B03 纠正母版。
4. 本轮附件补充视觉质量目标。浅色图不自动替换既定深色主品牌；需要时可作为之后的 Light Theme 参考。

旧提示词要求另建审计文档、允许 Mock fallback、使用 React/Canvas/WebGL 或同步模块的地方，不覆盖 9 月 28 日现行边界。截图中的社区、Agent、Training、Palace 等入口不自动进入 M0。旧“Machine Learning”页面应映射到真实任务/人工 Correction/Retest，而非再次扩成模型控制台。

## 3. 资源评估：技能、MCP、控件是三种不同东西

Skill 提供设计或实现方法；MCP 提供检索、检查、截图等工具；UI 库提供运行在产品内的控件。设计技能不能代替组件库，组件库不能代替审美判断，截图也不能代替真实交互验收。

### AI 辅助开发资源

| 资源 | 已核实能力 | AAOS 决策 | 限制 |
|---|---|---|---|
| Avalonia Build MCP | 官方文档/API 检索、开发规则、recreate-ui 工作流；免费远程服务 | 首选框架知识入口 | 截图复刻流程的 DevTools 部分另需许可；文档版本仍需核对 |
| Avalonia DevTools MCP | 运行中 App/预览器控件树、属性、截图、输入事件 | 有现成许可时优先使用 | Plus 或更高许可，Community 不包含；需 DiagnosticsSupport 接入 |
| UI UX Pro Max | 当前 README 明确支持 Codex，包含 Avalonia 栈、设计系统、排版与交互规则 | 主设计技能候选 | 输出必须服从既有 AAOS Tokens；不能自动另立品牌规范 |
| Impeccable | critique/audit/polish/layout/typeset/harden 等设计工作流，支持 Codex | 第二轮视觉审查候选 | live/browser 与部分检测面向 Web；不能当 Avalonia UIA 验收工具。当前实现含引擎/首次下载及 hooks，不应默认为纯文本 |
| Anthropic frontend-design | 前端视觉构思、布局与设计质量指导 | 可选审美参考 | 偏 Web；不保证 AXAML API 正确，也不能把桌面改回 React |
| linuxdevel/Avalonia-skills | XAML、布局、样式、绑定、MVVM、自定义控件等分主题资料 | 按需参考 | 社区项目，README 明确面向 Avalonia 12；11.x 不能照抄，优先用版本对应的官方文档 |

精简加载：一个主设计技能 + Avalonia 官方资料；出现具体布局/绑定问题时再读专门章节。Impeccable 仅在视觉复核时启用。不要同时让多个技能各生成一套设计系统。

Build MCP 官方地址：https://docs-mcp.avaloniaui.net/mcp 。这是待配置服务，并非本轮已经连接。DevTools 的通用启动方式为 avdt mcp；配置需要由本地执行器按已安装客户端版本处理，本报告不假定其已具备权限、许可或连接。

### 原生组件及资产资源

| 资源 | 在 AAOS 中的用途 | 采用建议 |
|---|---|---|
| 官方 Avalonia FluentTheme / ControlTheme | 基础按钮、输入、列表、颜色资源与品牌模板 | 最小依赖路线；已有实现优先保留 |
| FluentAvalonia | WinUI 风格控件与桌面导航/对话框等 | 若工程已采用，优先继续定制；README 的 2.x 最低版本信息不能证明任意最新版本兼容 |
| Semi.Avalonia + Ursa | 统一基础主题和补充控件，表单/标签/抽屉/通知等场景 | 缺少成熟组件层时优先试验；选定兼容组合后单一主题运行 |
| Material.Avalonia | Material 风格控件主题 | 备选，不建议为了“更漂亮”直接替换 AAOS 品牌 |
| Projektanker Icons.Avalonia | 统一图标接入 | 可选，核实实际图标集与包装库各自许可；已有 PathIcon 足够时无需新增 |
| Fluent System Icons | 文件、搜索、学习、状态等统一图标源 | 挑选同一尺寸与风格；保留具体资产包的许可与 NOTICE，不借此更换 Logo |
| Svg.Skia / Avalonia 适配包 | AAOS 标识、复杂 SVG 与插图 | 复杂 SVG 按需；简单图标优先 PathIcon，避免额外依赖 |
| LiveCharts2 | 真实学习趋势、小型图表 | 有真实数据与明确需求再引入；核心 MIT，增强付费功能单独区分 |
| Markdown.Avalonia | Markdown 资料/课程呈现 | 先确认版本、锚点映射与不可信内容处理；不是 Source/Evidence 存储层 |
| AvaloniaEdit | 文本/Markdown 原文编辑 | 需要编辑时再评估，不等于富文档编辑器或 PDF 阅读器 |
| FlaUI | Windows UIA2/UIA3 原生自动化、交互回归 | 免费路线的重要工具；必须检查控件实际 AutomationPeer/Pattern 暴露 |

许可与兼容的两条具体发现：
- Semi.Avalonia 主仓库 MIT，但 README 特别说明其 Dock/Tabalonia/AvaloniaEdit 主题适配扩展免费分发但不开放源码，不能把整个家族统称为 MIT。该说明不等于上游 AvaloniaEdit 编辑器闭源。
- Ursa README 仍有 11.x 兼容说明，同时维护者发布了 Ursa 2.0/Avalonia 12 破坏性变更文档，包括标题栏、Drawer/Dialog、输入属性等变化。以所选版本的依赖元数据和实际编译为准，不凭 README 装 latest。

## 4. Windows 能做成什么样

参考图里的层次、留白、渐变、圆角、图标、轻量阴影、侧栏选中态、抽屉和动效可在原生 Avalonia 中实现。官方窗口能力包括 Mica/AcrylicBlur 等请求；最终效果受系统、版本和透明度设置影响，要有纯色回退。

建议保留：AAOS 深色品牌、精细排版、统一圆角、轻层次、稳定阅读面。Mica 只用于窗体背景或壳层，正文与表格保持清晰的实体底色。不要为复刻 CSS 的 backdrop-filter 强行给每张卡片上实时模糊。

新附浅色图提供了好的内容主次、学习卡占比、右侧进度与图标表达；不应机械复制 macOS 红黄绿窗口按钮、底部重复 Dock、全局 ⌘K 文案或庞大的侧栏功能。Windows 使用原生窗口行为与 Ctrl+K；同一页面保留一个主要导航体系。

用户显卡同时承担本地推理时，UI 要保持低开销：隐藏页面停止动画，虚拟化长列表，封面异步解码和缓存，实时图表节流，避免常驻星空粒子、全屏模糊和循环发光。

## 5. 具体视觉改造规范

### 保留的历史品牌色

| Token | 归档值 | 用途 |
|---|---|---|
| Background | #061118 | 应用背景 |
| Surface / Raised | #0C1C26 / #102630 | 内容层级 |
| Primary | #1FC8C5 | 主操作、选中、焦点 |
| Text | #F3EFE6 | 主文字 |
| Muted | #96AAB4 | 次级信息 |
| Evidence accent | #E6BE73 | 少量证据强调；不等于已验证状态 |

计算检查：纯白字放在 #1FC8C5 上的对比度约 2.07:1；Ivory 字约 1.81:1；深色 #061118 字约 9.20:1。这是纯色组合计算，不是对所有实际渐变像素的测量。建议 teal 实心主按钮用深色字，或改深底描边按钮。实际控件的所有状态仍需截图检查。

以下为本轮优化建议，需并入既有主题资源，不另造权威体系：
- 普通页面不再用四张大 KPI 开头。首页以“继续学习/待处理资料/最近知识”为主，统计做辅助信息。
- 侧栏宽度建议 224–248 DIP；折叠态约 64 DIP；顶部内容工具栏约 56–64 DIP，标题栏另按现有窗口方案处理。
- 页内边距 24–32 DIP；组件间距采用已有 4/8/12/16/24/32 标尺。
- 小控件圆角 6–8 DIP，卡片 12–16 DIP，主学习卡可 18–24 DIP；不要每层都套卡片。
- UI 正文建议 14–16 DIP，阅读正文 16–18 DIP，页标题 26–32 DIP。历史 L4 的 body=18 适合阅读，不能强行套到所有表格。
- Segoe UI 与中文系统字体回退先保证可读性；品牌标识可保留既有字形，不为“设计感”下载大量字体。
- 图标统一线宽/尺寸，默认 18/20/24 DIP；语义图标替换重复圆点。Emoji 不作正式功能图标。
- 使用语义状态：Raw Source、Machine Candidate、Human Accepted、Provider Degraded。颜色+标签+图标共同表达。
- Hover 约 120ms、基础过渡约 180ms、Drawer 约 220–280ms，沿用 B04/B06 节奏；Reduced Motion 下保留最终状态与焦点。
- FSRS 卡优先采用稳定淡入/轻位移；没有合适原生 3D 支持时无需为翻牌另加引擎。

## 6. 页面研发顺序与验收

| 顺序 | 改造内容 | 必须展示的真实结果 |
|---|---|---|
| 1 | Shell、导航、Tokens、Button/Input/Tag、Focus | 所有后续页面拥有同一视觉语言 |
| 2 | Library | 封面/格式图标、列表密度、筛选、真实 Source 状态与空态 |
| 3 | Reader/Evidence | 左侧结构/页定位，中部可读正文，右侧来源与 Anchor；宽度不足时侧栏折叠 |
| 4 | Review | 单个问题主视区、答案揭示、真实四级评分与 due；统计适度收起 |
| 5 | Import、Knowledge、Search | 真实 job、来源绑定、人工 Accept、语义检索降级 |
| 6 | Learning、Machine、Recovery | Course/Assessment、Correction/Retest、恢复校验与审批 |

第一批拿出 Library、Reader、Review 三页的运行截图，是视觉与产品切片验收；不改变原有 Import→Evidence→Knowledge→Search 的功能关键路径，也不绕过未就绪合同。后端未提供时呈现明确不可用/空态，不以假数据冒充可用。

不要求先完成所有页面再评审。每页循环：参考图和功能约束 → 原生 AXAML → 运行当前 Candidate → 截图 → UIA 交互 → 修正 → restart/readback。截图质量与业务真实性分别记录，均通过才关闭任务。

测试维度：主显示器 2560×1440；100%/125%/150%/200% DPI；另测窄窗口和 1920×1080 场景。记录物理像素、逻辑尺寸与缩放，不用固定坐标把 2K 截图直接映射到 DIP。

验收至少覆盖：无裁切重叠、长标题与中文输入、正文可读、导航一致、焦点可见、键盘路线、关闭弹窗后焦点恢复、真实取消/重试、Provider 降级、重启后读回。记录 actual SHA、dirty diff 身份、构建路径、运行进程与 Candidate 身份，防止检验旧 DLL。

设计预览可以使用独立测试 fixture，但必须醒目标记、与产品运行态隔离，不能当正式状态或完成证据。像素对比允许屏蔽时间等动态区域，但保留未加工原图；不要用一个随意的像素误差阈值替代设计与功能验收。

## 7. 可直接给本地 Codex 的执行提示词

以下作为正在执行任务的 UI 优化补充，不是重启项目、不覆盖已有任务，不另建 TaskPack/current state。

```text
你正在本地开发 AAOS / ArcheAxis。继续现有工作，将当前原生界面提升到可交付的视觉质量。

先保护现场：读取 AGENTS、现行权威、现有 R6-EXECUTION/R6-STATE、HEAD、dirty/untracked、worktree、前端 owner。用户当前未提交 UI 是必须保护的工作成果，不 reset、不覆盖、不自动切分支。比较 current main，但不能拿云端覆盖正在进行的本地工作。与已有 writer 保持同文件 single writer。

只读取 D:\All projects\UI套件 中 AAOS/ArcheAxis 的资料。总归档里只取名称以 ArcheAxis/archeaxis/AAOS 开头的 13 个专属 ZIP 及必要公共索引，不加载另两项目。先读 B10、B09、B07、B04/B06、B03 配色纠正母版，再查看关键页面图。实际目录以现场发现为准，不假造路径。

资料中的旧 React、localStorage、mock fallback、简化 FSRS、固定 KPI、随机关联数量一律不进入正式产品。架构继续 C#/Avalonia → Rust authoritative writer → Python workers；WORK-LAB Provider 和 AAOS 数据边界不变。旧截图/海报里的社区、Agent 管理、3D/云同步不进入本轮 M0。

第一步只做针对性检查：项目 .NET/Avalonia 版本、锁文件、现有主题、控件库、图标、窗口壳、已配置 Skills/MCP、真实 API/projection 接线、原生测试工具。输出极短的版本/现有库/dirty protection/首批页面/blocker 回执。不要重新做全仓历史审计。

能力补充：优先使用 Avalonia 官方 Build MCP 或对应版本文档。检查 UI UX Pro Max 的 Avalonia 栈是否适用于当前版本，作为设计辅助；可按需用 Impeccable 的 critique/layout/typeset/polish 方法复核，但其 Web 检测不能作为原生 UIA 证据。社区 Avalonia-skills 当前面向 12，不要把 12 API 写进 11 工程。

先报告现有工具是否能用，不自动下载另一套 Node/Python/.NET 工具链，不全局覆盖技能/MCP配置，不一次安装多个设计技能。选择第三方依赖前读取所选版本依赖与 license，锁定版本。存在版本冲突时继续使用已有 FluentTheme 完成视觉改造，不强制升级框架。

主题决策：已有 FluentAvalonia 深度使用则保留；只有默认控件且无成熟基础时，对 Semi.Avalonia+Ursa 做最小兼容验证后再采用。保持一个全局主题体系，AAOS 自己的 semantic tokens/ControlTheme 覆盖品牌。不要同时引入 Material/Semi/Fluent 多主题。图标、Markdown、图表只补当前页面实际缺口。

视觉执行：Background #061118、Surface #0C1C26/#102630、Primary #1FC8C5、Text #F3EFE6、Muted #96AAB4；金色 #E6BE73 仅少量证据强调。主按钮 teal 背景用可读的深色文字。取消普通 hover 变金色；不做满屏星空、金青渐变按钮、默认圆点菜单、巨大 KPI 以及所有区块套卡片。

新附浅色学习/仪表盘图仅借鉴排版层次、留白、图标、主学习卡与辅助栏；不搬 macOS 窗口按钮、重复底部 Dock、无合同导航或假数据。Windows 窗口按钮、最大化/拖动、Ctrl+K、IME、DPI、键盘与无障碍正常工作。Mica/透明度只作可关闭增强，纯色回退同样完整。

先精修 Shell + Library + Reader/Evidence + Review：
1. 壳层、标题/工具栏、侧栏选中、图标、间距与字体先统一。
2. Library 使用真实资料列表、格式/封面、来源、状态和密度切换。
3. Reader/Evidence 提供清晰正文、定位锚点、可折叠来源面板，不以横线占位当完成。
4. Review 提供当前真实问题、答案揭示、四级评分、实际 due/队列与重启读回；不自行写简化 FSRS。
5. 后端未就绪显示明确空态/不可用，不假成功。随后复用组件覆盖 Import/Knowledge/Search/Learning/Machine/Recovery。

每页完成后运行当前原生构建并截图检查。可用且有授权许可时使用 DevTools MCP；否则用现有 Windows UIA/FlaUI 与窗口截图。不要把 Playwright 的 Web 截图当成 Avalonia 验收。测试 fixture 仅隔离预览使用且明确标注，不能进入产品证据。

必须绑定实际运行的 Candidate、构建路径和源代码身份，保护未提交差异。覆盖关键页正常/空/错误/降级，测试中文 IME、键盘、长文本、DPI、缩放、Reduced Motion。关键数据写入后做 restart/readback。

在现有 R6 状态中记录本轮结果，报告三页前后真实截图、修改文件、使用的库与版本、已验证结果和未完成项。不要仅交付建议、独立网页 Demo 或“build green”。不要替换 Green、不要解冻 Release。
```

## 8. 原始官方/维护者来源

下列链接于 2026-09-28 检索或读取。网页 README 与实际发布包可能不同；本轮未对所有候选库进行本地集成测试，推荐为基于资料与 AAOS 需求的工程判断。

1. Avalonia AI Tools：https://docs.avaloniaui.net/tools/ai-tools/
2. Build MCP：https://docs.avaloniaui.net/tools/ai-tools/build-mcp
3. DevTools MCP / 许可：https://docs.avaloniaui.net/tools/developer-tools/mcp
4. 窗口/透明度：https://docs.avaloniaui.net/docs/how-to/window-how-to
5. FluentTheme：https://docs.avaloniaui.net/docs/styling/themes
6. FluentAvalonia：https://github.com/amwx/FluentAvalonia
7. Semi.Avalonia：https://github.com/irihitech/Semi.Avalonia
8. Ursa：https://github.com/irihitech/Ursa.Avalonia
9. Ursa 2.0 破坏性变更：https://github.com/irihitech/Ursa.Avalonia/discussions/960
10. UI UX Pro Max：https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
11. Impeccable：https://github.com/pbakaus/impeccable
12. frontend-design：https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md
13. Avalonia-skills：https://github.com/linuxdevel/Avalonia-skills
14. Material.Avalonia：https://github.com/AvaloniaCommunity/Material.Avalonia
15. Icons.Avalonia：https://github.com/Projektanker/Icons.Avalonia
16. Fluent System Icons：https://github.com/microsoft/fluentui-system-icons
17. Svg.Skia：https://github.com/wieslawsoltes/Svg.Skia
18. LiveCharts2：https://github.com/Live-Charts/LiveCharts2
19. Markdown.Avalonia：https://github.com/whistyun/Markdown.Avalonia
20. AvaloniaEdit：https://github.com/AvaloniaUI/AvaloniaEdit
21. FlaUI：https://github.com/FlaUI/FlaUI

交付边界：本轮完成归档核验、AAOS 资料分析、公开资源调研和本地执行方案。未声称本机 UI 已改造、插件已安装、Windows Candidate 已通过测试。
