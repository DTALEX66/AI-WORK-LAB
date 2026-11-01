# Open Design Enhancement Roadmap

本路线图基于 `docs/OPEN_DESIGN_ENHANCEMENT_RESEARCH.md`。

## 项目原则

```text
Open Design 软件 = 设计流程、AI 调用、主窗口画布的实际入口。
DESIGN-LAB = 增强 Open Design 的插件、脚本、设计系统、资产包和参考样板。
```

不把本仓库重新变成工作流中心；所有增强都服务于 Open Design 软件本体。

## Phase 1：可用性与迁移复用

状态：完成第一版。

已有：

```text
design-lab/scripts/configure_open_design_windows.py
design-lab/scripts/doctor_open_design_windows.py
design-lab/usage-notes/PORTABLE_OPEN_DESIGN_SETUP.md
design-lab/templates/open-design-app-config.template.md
```

下一步：把 doctor 输出接入 Open Design usage note，形成新电脑安装后的固定验收清单。

检查内容：

- Open Design 安装路径。
- app-config JSON。
- Codex CLI 可执行文件。
- Codex OAuth 登录态是否存在但不打印凭据。
- 默认 project location 是否指向本仓库。
- proxy launcher 是否存在。
- daemon log / local API 端口是否可探测。

## Phase 2：本地插件化

目标：让 Open Design 软件里能直接选择/安装我们的项目增强能力。

状态：完成第一批专项设计插件。

创建：

```text
packages/capabilities/plugins/minigame-ui-director/
packages/capabilities/plugins/anomaly-monitor-hud/
packages/capabilities/plugins/uiux-layout-director/
packages/capabilities/plugins/graphic-design-director/
packages/capabilities/plugins/brand-visual-director/
packages/capabilities/plugins/spatial-exhibition-director/
packages/capabilities/plugins/design-qa-critic/
```

每个插件遵循 Open Design 官方结构：

```text
SKILL.md
open-design.json
README.md
```

### minigame-ui-director

用途：面向小游戏/HUD/IAA 变现界面生成。

输入：

```text
platform: h5 | wechat | douyin | android-webview
screen: start | main | failure | archive | skin-select
theme: anomaly-monitor-dark | custom
```

### anomaly-monitor-hud

用途：专门生成监控终端 / CCTV / HUD 风格 UI。

输入：

```text
scene: elevator | hospital | security | factory | subway | hotel
riskLevel: low | medium | high | critical
```

### uiux-layout-director

用途：专项增强菜单、网站、产品页、dashboard、信息架构与响应式布局。

重点：

```text
- 导航分组与状态
- 页面主次层级
- mobile/tablet/desktop 响应式
- 产品化布局节奏
- 避免普通表单/后台感
```

### graphic-design-director

用途：专项增强平面设计、海报、封面、banner、社媒图和视觉 campaign。

重点：

```text
- 构图网格
- 字体层级
- 视觉焦点
- 出图尺寸
- 安全/高级/传播型三种方向
```

### design-qa-critic

用途：在 Open Design 内对生成结果做审美和落地检查。

检查：

```text
- 是否像游戏/HUD，而不是表单/问卷
- CCTV/主视觉是否占据核心区域
- 移动端可读性
- 控件是否 icon-first / short chips
- 是否可被 minigame-runtime 落地
```

## Phase 3：Open Design-native design system

创建：

```text
design-lab/design-systems/anomaly-monitor-dark/
```

目标文件：

```text
DESIGN.md
manifest.json
design-tokens.json
components.html
components.manifest.json
preview/index.html
```

来源：

```text
packages/design-system/DESIGN.md
packages/design-system/05_DESIGN_COMMAND_CENTER/design-tokens/anomaly_monitor_dark.tokens.json
packages/design-system/05_DESIGN_COMMAND_CENTER/component-rules/monitor_console.components.json
```

## Phase 4：视觉资产包

创建：

```text
design-lab/assets/visual-packs/anomaly-monitor-cctv/
```

先不复制大图，使用 manifest 指向仍保留的运行必需资产：

```text
fixtures/domains/game-visual/assets/generated/*
```

输出：

```text
manifest.json
README.md
prompts.md
```

用途：Open Design 生成 CCTV/HUD 视觉时引用真实资产和提示词。

## Phase 5：开源技能吸收与专项模板库

状态：完成第一批吸收清单和模板。

已创建：

```text
design-lab/research/open-source-absorption/ABSORPTION_CANDIDATES.md
design-lab/templates/qa/anti-ai-slop-checklist.md
design-lab/templates/layouts/landing-page.md
design-lab/templates/layouts/dashboard.md
design-lab/templates/layouts/mobile-menu.md
design-lab/templates/graphic/poster-cover.md
design-lab/templates/layouts/product-page.md
design-lab/templates/layouts/settings-panel.md
design-lab/templates/layouts/pricing-page.md
design-lab/templates/graphic/social-card.md
design-lab/templates/decks/pitch-deck.md
design-lab/templates/motion/motion-system.md
design-lab/templates/brand/brand-identity-system.md
design-lab/templates/spatial/culture-wall.md
design-lab/templates/spatial/exhibition-hall.md
design-lab/templates/visual/art-direction.md
design-lab/templates/visual/2d-design.md
design-lab/templates/visual/3d-design.md
design-lab/templates/typography/cjk-ui-typography.md
design-lab/templates/design-systems/style-reference-index.md
```

吸收来源类型：

```text
- Open Design 官方 plugins/spec、design-templates、design-systems
- Hallmark 类 anti-AI-slop 审查规则
- VoltAgent/awesome-design-md 类 DESIGN.md 风格库
- Nothing Design 类工业/HUD/点阵/机械控件语言
- Baoyu/StyleSeed/Material/Stitch 类高保真与组件判断方法
```

原则：先吸收方法、模板、审查门槛和风格索引，不批量复制第三方仓库。

## Phase 6：插件可维护性与本地安装闭环

状态：完成第一批维护工具。

已创建：

```text
design-lab/usage-notes/OPEN_DESIGN_PLUGIN_INSTALL.md
packages/capabilities/plugins/INDEX.md
design-lab/templates/INDEX.md
design-lab/scripts/generate_open_design_indexes.py
design-lab/scripts/scaffold_open_design_plugin.py
```

用途：

- 固定本地插件安装、调用、smoke test 和排查流程。
- 从 `open-design.json` 自动生成插件索引。
- 从 `templates/**/*.md` 自动生成模板索引。
- 新增插件时用脚手架生成 `SKILL.md`、`open-design.json`、`README.md` 三件套。
- 统一验证器覆盖索引和脚本编译。

## Phase 7：上游贡献候选

低风险方向：

- Codex subscription/OAuth + Windows proxy launcher 文档。
- Open Design plugin 示例：game HUD / CCTV console。
- 中文 i18n 缺口。
- Windows 本地 CLI detection/diagnostic 改进。

高风险方向暂缓：

- daemon runtime 核心改造。
- agent adapter 核心逻辑。
- BYOK streaming parser。
- media provider fallback。

## 下一刀建议

直接做：

```text
brand-to-design-system 插件 + 插件发布/打包说明 OPEN_DESIGN_PLUGIN_PUBLISHING.md
```

原因：

- 插件安装说明、索引和脚手架已经完成。
- 下一步可以把“品牌输入 → DESIGN.md/tokens/应用规则”的能力做成可复用插件。
- 同时补发布规范，避免本地插件未来扩展时 manifest/README/SKILL 结构漂移。
