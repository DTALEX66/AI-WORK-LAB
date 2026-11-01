# Open Design Enhancement Research｜2026-07-04

## 目标

用户要求：

```text
现在思考怎么增强 OPEN，去网上找找
```

本文件记录对 `nexu-io/open-design` 官方仓库、README、docs、tree、issues、releases 的在线调研，并转成 `DESIGN-LAB` 后续可执行增强方向。

## 在线调研来源

- GitHub repo: <https://github.com/nexu-io/open-design>
- 官方站点: <https://open-design.ai>
- Latest release: <https://github.com/nexu-io/open-design/releases/tag/open-design-v0.13.0>
- Agent adapters doc: <https://github.com/nexu-io/open-design/blob/main/docs/agent-adapters.md>
- Plugin fixture/schema evidence:
  - `apps/daemon/src/plugins/scaffold.ts`
  - `apps/daemon/tests/fixtures/plugin-fixtures/sample-plugin/open-design.json`
  - `docs/schemas/open-design.plugin.v1.json`
  - `docs/schemas/open-design.marketplace.v1.json`

## 官方能力判断

从 README 和 repo tree 看，Open Design 当前不是单纯“设计稿工具”，而是：

```text
local-first desktop design workspace
+ agent CLI runtime
+ DESIGN.md design systems
+ plugin / skill layer
+ MCP server
+ media providers
+ artifact export
```

官方 README 明确提到：

- 本地优先桌面应用。
- 设计产物包括 web / desktop / mobile prototypes、dashboards、decks、images、video、HyperFrames。
- 支持 HTML / PDF / PPTX / MP4 export。
- 支持 Claude Code / Codex / Cursor / Gemini / OpenCode / Qwen / Copilot / Hermes 等 20+ CLI。
- 支持 BYOK 和 OpenAI-compatible endpoint。
- 存在 skills、design systems、plugins、MCP server。
- `od mcp install <agent>` 可把 Open Design MCP server 接入各种 agent。

## 可增强入口

### 1. Plugin / Skill 层是最直接入口

官方 `apps/daemon/src/plugins/scaffold.ts` 显示本地插件最小形态：

```text
<plugin-id>/
  SKILL.md
  open-design.json
  README.md
```

`open-design.json` 关键字段：

```json
{
  "$schema": "https://open-design.ai/schemas/plugin.v1.json",
  "specVersion": "1.0.0",
  "name": "sample-plugin",
  "title": "Sample Plugin",
  "version": "1.0.0",
  "description": "...",
  "license": "MIT",
  "tags": ["sample"],
  "od": {
    "kind": "skill",
    "taskKind": "new-generation",
    "useCase": {
      "query": "Generate a {{topic}} brief for {{audience}}."
    },
    "context": {
      "skills": [{ "ref": "open-design-landing" }],
      "atoms": ["todo-write", "discovery-question-form"]
    },
    "inputs": [],
    "capabilities": ["prompt:inject"]
  }
}
```

因此本仓库最应优先做的是：

```text
packages/capabilities/plugins/
  minigame-ui-director/
  anomaly-monitor-hud/
  design-qa-critic/
  asset-to-skin-pack/
  open-design-portability-doctor/
```

这些插件不是替代 Open Design，而是让 Open Design 在软件内调用时直接获得更强的项目语境。

### 2. DESIGN.md / design-systems 是第二入口

Open Design 官方内置大量 `design-systems/*/DESIGN.md`，并有：

```text
design-systems/_schema/manifest.schema.ts
design-systems/_schema/tokens.schema.ts
apps/daemon/src/design-systems/*
```

本仓库已有：

```text
packages/design-system/DESIGN.md
packages/design-system/05_DESIGN_COMMAND_CENTER/design-tokens/*.json
packages/design-system/05_DESIGN_COMMAND_CENTER/component-rules/*.json
```

后续应把 `Anomaly Monitor Dark` 进一步整理成 Open Design 原生 design system 包，而不是只当项目文档：

```text
design-lab/design-systems/anomaly-monitor-dark/
  DESIGN.md
  manifest.json
  design-tokens.json
  components.html
  components.manifest.json
  preview/
```

目标：在 Open Design 的 Design System 页面里更容易选择、预览、复用。

### 3. MCP / agent adapter 是第三入口

官方 README 写明：

```text
od mcp install hermes
od mcp install codex
od mcp install claude
...
```

`docs/agent-adapters.md` 说明 Open Design 的核心设计是把 agent loop 委托给本地 agent CLI，Open Design 负责检测 CLI、注入 skill/prompt/design system、显示 stream。

对本仓库的意义：

- 继续强化 Codex CLI subscription/OAuth 路线。
- 增加 `doctor` 脚本，检查 Open Design / Codex / Git / proxy / project root。
- 增加 Hermes MCP 接入说明，让 Open Design 能和 Hermes/Codex 双向协作。
- 不碰用户 token，不存 API key。

### 4. Media provider / visual asset 是第四入口

官方 repo 有：

```text
apps/daemon/src/media-adapters/*
apps/daemon/src/media/*
apps/web/src/media/*
docs/external-media-orchestration.md
```

当前我们已有精选 CCTV / HUD 视觉资产：

```text
fixtures/domains/game-visual/assets/generated/
```

后续可以增强成：

```text
design-lab/assets/visual-packs/anomaly-monitor-cctv/
  manifest.json
  prompts.md
  selected-assets.md
```

在 Open Design 里作为视觉参考包使用，而不是继续堆在 runtime 目录里。

### 5. Upstream bug/issue 暴露的增强机会

近期 issue/PR 显示社区痛点集中在：

- Windows agent/tool launch 安全与兼容。
- BYOK / third-party model 输出为空、tool calling 不兼容。
- media generation fallback/provider 选择错误。
- local model / OpenCode / Ollama 生成文件没有写入。
- model selector UX。
- i18n / 中文本地化。
- Kiro/ZCode 等新 CLI 接入。
- 内存占用和启动问题。

这说明我们自己的增强优先级应该偏实用：

```text
配置可复用 > agent 可用性检测 > 插件/设计系统导入 > 视觉资产包 > 上游贡献
```

## 推荐增强路线

### P0：先做本仓库对 Open Design 的“安装复用 + 可用性诊断”

已经有：

```text
design-lab/scripts/configure_open_design_windows.py
design-lab/usage-notes/PORTABLE_OPEN_DESIGN_SETUP.md
```

建议补：

```text
design-lab/scripts/doctor_open_design_windows.py
```

检查：

- Open Design.exe 是否存在。
- app-config.json 是否存在且 JSON 有效。
- `agentId == codex`。
- `CODEX_BIN` 存在并可运行。
- `CODEX_HOME/auth.json` 存在，但不打印 token。
- 默认 project location 是否指向本仓库。
- proxy 是否可选存在。
- 端口/daemon 日志是否能找到。

### P1：做 3 个本地 Open Design 插件

优先插件：

1. `minigame-ui-director`
   - 用途：在 Open Design 中生成小游戏 UI / HUD / 监控终端原型。
   - 输入：theme、platform、screen、monetization mode。
   - 上下文：引用 `fixtures/domains/game-visual/` 和 `packages/design-system/`。

2. `anomaly-monitor-hud`
   - 用途：专门生成 Anomaly Monitor Dark 风格 UI。
   - 输入：scene、risk level、screen size。
   - 输出：HTML prototype / visual spec。

3. `design-qa-critic`
   - 用途：对 Open Design 生成结果做审美和落地验收。
   - 检查：不是表单/问卷、CCTV 主视觉占比、HUD 氛围、移动端可读性、可落地性。

### P2：把 Anomaly Monitor Dark 做成 Open Design 原生 design system 包

目标目录：

```text
design-lab/design-systems/anomaly-monitor-dark/
```

从现有内容吸收：

```text
packages/design-system/DESIGN.md
packages/design-system/05_DESIGN_COMMAND_CENTER/design-tokens/anomaly_monitor_dark.tokens.json
packages/design-system/05_DESIGN_COMMAND_CENTER/component-rules/monitor_console.components.json
```

输出：

```text
DESIGN.md
manifest.json
design-tokens.json
components.html
preview/index.html
```

### P3：资产包化精选视觉素材

把 `fixtures/domains/game-visual/assets/generated/` 中仍保留的 8 个运行必需资产转成 Open Design 可读资产包：

```text
design-lab/assets/visual-packs/anomaly-monitor-cctv/
  manifest.json
  README.md
  prompts.md
```

不一定复制二进制，可先用相对路径 manifest 引用，避免重复占空间。

### P4：探索上游贡献

如果后续要直接增强 Open Design 官方软件，可从低风险开始：

- 文档补充：Codex subscription/OAuth + Windows proxy launcher。
- i18n：中文本地化缺口。
- plugin examples：游戏 HUD / CCTV design plugin 示例。
- Kiro/ZCode/Windows discovery 类 issue 如果和用户环境相关再做。

## 当前结论

`DESIGN-LAB` 下一步不应先改 Open Design 源码，而应先做“贴近 Open Design 官方扩展机制”的增强包：

```text
1. doctor/configure scripts
2. local Open Design plugins
3. Open Design-native design system package
4. visual asset pack manifest
5. optional upstream PR
```

最优第一刀：

```text
创建 packages/capabilities/plugins/minigame-ui-director/
```

因为它能最快把原 MINIGAME / Design-system 的价值变成 Open Design 软件里可直接调用的增强能力。
