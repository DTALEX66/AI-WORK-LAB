# 开源 UI 组件池：选型与受控吸收/部署方案

## 目标

优先检查当前仓库已有 UI 组件、原生控件和视觉系统；缺少时从开源供体吸收，适配到各自品牌 token。不开工前不安装新包，不拉动大版本升级，不把组件系统或 UI kit ZIP 误当成生产依赖。

## 从历史 UI 组件研究池捞出的候选

| 项目/用途 | 第一候选 | 第二候选 | 适用界限 |
|---|---|---|---|
| WORK-LAB 管理/控制台 | **shadcn/ui 源码模式** + 一个可访问 primitives 供体（当前仓库若已有 Radix 则延用，否则评估 Radix 或 React Aria Components） | Mantine 或 Semi 二选一，只有基础 primitives 覆盖不了大量专业控制组件时做小型替补比较 | shadcn 是源代码/registry 分发和可定制模式，不是把 `@shadcn/ui` 当完整生产套件安装；保留 WL 自己的表/时间线/审批/状态组件合同。官方仓库标 MIT。 |
| DESIGN-LAB Workbench 管理区 | **Semi Design** 做表单、筛选、数据列表、Dialog 等小试片；在现有 React 版本兼容且主题/无障碍通过时考虑纳入 | Mantine（若现有栈和现有组件更契合）作为对照，不与 Semi 并装 | Semi 在官方仓库说明 MIT；适合先测表单/面板，不代替 DesignIR、创作 Host、资产管理、图层/画布、方向/Jury 等领域设计。 |
| 两项目共同开发辅助 | Storybook（开发期组件图谱/状态文档/隔离测试） | Vitest/Playwright/Axe 采用仓库现有工具链 | Storybook 是组件开发与文档环境，不是应用组件库；可各仓单独配置，不做运行依赖。 |
| 共通低层图标/primitive | 仓库已有 icon；若缺失先试 Lucide；Radix/React Aria 按组件逐个引用 | Flowbite 可做静态布局灵感，不与 Tailwind 插件同时堆叠 | 相同图标语义可共享指引，最终资产来自各自 VI；仅在各自依赖清楚/可审查时安装。 |

历史研究列过 DaisyUI、FlyonUI、Flowbite、Ant Design、Mantine、Semi、shadcn/ui、Radix/React Aria、tsParticles 等。它们不是一套一起部署的组件栈：DaisyUI + FlyonUI 会叠加 Tailwind 设计约束；Ant + Semi + Mantine 会带来重复 Form/Table/Modal 与 theme reset；tsParticles 有动画/性能和 reduced-motion 审核需求。除非明确的特定交互缺口，不安装它们。

## 许可证/来源当前复核要点

- [shadcn/ui 官方 GitHub](https://github.com/shadcn-ui/ui)：项目采用 MIT；其源码分发与 registry 工作方式应按当前 CLI/docs 使用。逐个被复制组件和附属依赖仍需来源、license 和升级记录。
- [Semi Design 官方 GitHub](https://github.com/DouyinFE/semi-design)：官方 README 标明 Semi UI MIT；运行目标 React 大版本需锁定兼容发行包。
- [Mantine 官方 GitHub](https://github.com/mantinedev/mantine)：官方仓库标明 MIT；对比时按当前仓库 React/Node 支持版本核验。
- [Storybook 官方 GitHub](https://github.com/storybookjs/storybook)：组件/页面隔离开发、文档和测试工作台；只作为开发依赖。
- MIT 只描述上游代码许可。截图、图标资产、字体、生成模型、图片、客户设计案例各自核许可；维护 SBOM/NOTICE 和版本/commit。

## 吸收决策门

1. 确认当前项目入口、React/TS/Node/package manager、CSS/Tailwind、Tauri/浏览器支持、现有 Radix/Headless primitives 和 lockfile。
2. 写一页短对比记录：bundle 大小/依赖数量、主题 token 映射、dark mode、中文字体/IME、键盘/屏幕阅读器、Focus/Modal、RTL或移动支持、维护/发布、MIT 等许可证、退出和回滚。
3. 只做一个真实任务的可撤销实验分支：WL 选 Table + Approval Dialog + command palette；DL 选 Project filters + Brief form + Rights/Preflight dialog。
4. 建立 `vendor/component` / package 记录：上游 URL、固定 tag/commit、package version、license、hash、采用的组件、修改 diff、禁止升级或依赖影响、UI/API 映射、上游更新负责人。Copied source 保留 LICENSE/NOTICE。
5. 通过现有主题 tokens 映射本项目颜色；禁用 library default theme reset 造成全局覆盖。抽出语义状态/contrast，不把品牌色塞进其他 app 的 token。
6. 测试 keyboard/focus/contrast/IME/zoom/reduced-motion/loading-empty-error-permission; 桌面宽窗口与小窗口；做 visual snapshot 和真实页面 smoke。
7. 只有当集成结果优于现有自研或缺失能力、没有权限/API 边界冲突、回归通过，才进入正式分支并更新 Authority/Architecture/lockfile。否则撤销试片，保留证据与候选状态。

## 示例安装/锁定流程（须先确认 package manager 与版本）

### WORK-LAB：源码复制模式

```bash
# 在新 branch 中执行，先查看官方当前初始化说明，并确认当前 Tailwind/React 配置
pnpm dlx shadcn@latest init
pnpm dlx shadcn@latest add button dialog dropdown-menu table command
```

选择项目实际所需 primitive 后可评估单一依赖，例如已采用 Radix 的项目只添加缺少的具体 `@radix-ui/react-*` 包。先不要同时加 `daisyui`、`flyonui`、`@mantine/*` 与整套 `antd`。

### DESIGN-LAB：Semi 小范围对照

```bash
# 仅在现有 React 版本兼容且 UI spike 通过后，按 Semi 官方当前安装文档选择准确 package
pnpm add @douyinfe/semi-ui
```

再核对是否应使用该版本的 React 19 专用包，勿自行猜版本。不引入 Semi 后又并装 Mantine/Ant。

### 各项目组件目录

把被采用/定制的组件放入该项目当前规范的 `src/components` 或 feature module，不跨仓引用；保留 tokens、license 和可升级路径。Storybook 如已存在则扩展；未存在先确认 build 门与依赖预算，再添加 dev-only。

## 视觉素材吸收/部署

- 导出源素材前登记原始压缩包、内部文件、尺寸、hash、来源/授权、修改（裁剪/去背景/放大）。
- Logo/品牌图形尽量用项目原始 vector/source，不从截图二次描摹；位图用作 preview/empty art 时以本项目主题校准。
- 不因 B01/B02 写有“2x 放大”就把缩放 PNG 视为矢量源；文字/小图标优先找原文件或重新用 SVG/CSS 构造并保持可审查。
- DESIGN-LAB 所用作品主图需 rights/来源可追溯；第三方 UI 库示例/屏幕不作为项目商业主视觉。
