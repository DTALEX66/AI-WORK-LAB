# MiniMax Design 适配调研 — Open Design 冻结后技能/插件内容去向

- 日期：2026-09-04
- 项目：DESIGN-LAB
- 状态：调研完成（D1）——待任务包化（DL-* 新任务）
- 用户决策：**OPEN DESIGN 暂时冻结**；其自带技能/插件等内容适配到 **MiniMax Design**；MiniMax Design 软件已安装（本机）

## 一、结论摘要

MiniMax Design（v3.0.10，Windows x64，Electron/Squirrel）是 MiniMax 官方的**本地化多模态 AI 创作 Agent 平台**（产品页标题："多模态创作 Agent，你的 AI 创作工作室"），产品架构与 DESIGN-LAB 已管理的 Open Design 客户端能力面**高度同构**：

| MiniMax Design 能力 | 对应 DESIGN-LAB / Open Design 面 | 适配方向 |
|---|---|---|
| AGENT MODE（灵感/简报/任务拆解） | packages/capabilities/atoms（brief-normalizer、source-intake-gate…） | 技能平移 |
| CANVAS FLOW（多模态画布/节点） | Open Design 画布 + fixtures/domains/game-visual 节点资产 | 参考实现 |
| **SKILL READY（专属 Skill + 插件，含广场）** | **Open Design expert-suite 15 技能 + packages/capabilities/{plugins,bundles,atoms,scenarios}** | **直接适配目标** |
| LOCAL INDEX（本地资产中心 + 专业工具直连） | integrations/hosts/* + assets 中心 | 资产对接 |
| OUTPUT SYNC（审核节点/交付） | packages/capabilities/quality + design-lab jury/gates | 流程对齐 |

关键差异：Open Design 是**外部 Web 宿主**（需网络 sidecar/云端），MiniMax Design 是**本地 Electron 桌面宿主**（本地 gateway + opencode agent 运行时）——适配后 DESIGN 工作流可完全本地闭环。

## 二、本机安装事实（只读调研，2026-09-04）

| 项 | 值 |
|---|---|
| 安装根 | `C:\Users\ALEX\AppData\Local\com.minimax.hub\` |
| 主程序 | `MiniMax Design.exe`（ProductVersion 3.0.10.1014） |
| 更新器 | `Update.exe`（Squirrel）；packages/ 含 `com.minimax.hub-3.0.11-hilo-desktop-1033-full.nupkg` |
| 应用数据 | `C:\Users\ALEX\AppData\Roaming\@hilo\desktop\`（Chromium 用户数据 + ai-runtime + output_files + logs/gateway） |
| app 代码 | `current/resources/app.asar`（`@hilo/desktop`，main=out/main/index.js，renderer 打包产物） |
| 内置插件 | `current/resources/bundled-plugins/`：`3d-director-stage`、`clip-studio`、`comfyui` |
| Agent 运行时 | ai-runtime 内 **opencode**（config-home/data-home/state-home/cache-home，opencode.db 会话库）+ bun |
| 本地 Gateway | NestJS 双实例（app-level + workspace），Main bridge `127.0.0.1:58452`，云端经 cloud_gateway（conf/external_api_conf.yaml） |

## 三、插件/技能契约（适配的核心接口——来自内置插件实证）

MiniMax Design 插件 = **目录 + manifest.json**，目录含静态页（index.html iframe 嵌入 gateway origin）+ skill + agent 声明：

```jsonc
// bundled-plugins/<id>/manifest.json 结构（以 3d-director-stage v0.24.8 实证）
{
  "id": "3d-director-stage",
  "name": {"zh-CN": "导演台", "en-US": "Director Stage"},
  "version": "0.24.8",
  "entry": "index.html",                // iframe 页面，经 gateway /api/plugins/<id>/static/index.html
  "displayMode": "launcher",            // 或 canvas/editor 形态
  "width": 350, "height": 400,
  "skill": {                            // 插件声明技能（on-demand 加载）
    "entry": "skills/SKILL.md",
    "name": "plugin.3d-director-stage.craft",
    "load": "on-demand",
    "fallback": "inline"
  },
  "agent": {                            // Agent 方法（MCP 风格 RPC 清单）
    "editorSurface": true,
    "sessionName": {"zh-CN": "导演台 Agent", "en-US": "Stage Agent"},
    "methods": [
      {"name": "scene.get", "timeoutMs": 15000, "description": "…结构化读写说明…"}
    ]
  }
}
```

- **skill 文件格式**：标准 SKILL.md（frontmatter: `name/description/version`）+ `references/*.md` 子文档 —— **与 Open Design expert-suite / DESIGN 自有技能完全同构**
- **技能加载**：manifest `skill.entry` → `skills/SKILL.md`；on-demand + inline fallback
- **插件桥（hub-bootstrap.js 实证，comfyui 插件）**：
  - iframe 运行在 gateway origin 下，经 `/api/plugins/<id>/data/` 读写插件数据（JSON 状态轮询）
  - `hub.python.run` RPC（10 分钟硬顶，detached worker 长任务）；`hub.config` 键存储
  - 内置后端统一下发（backend-bundle.json 版本 + install/start-backend.py，专用端口避免撞本机）
- **技能市场**：应用内有 skills.market（安装/卸载/更新/社区/creator plan 上传）——UI 文案实证 `skills.market.uninstallPluginSuccess`、creatorPlanCover（PNG/GIF/MP4 ≤10MB）
- **本地落盘**：skillPath 本地目录 + `platform.shell.showItemInFolder`（实证 renderer 代码）

## 四、与 DESIGN-LAB 的适配映射建议

### A. Open Design 技能内容（冻结后仍应平移）
来源（DESIGN-LAB 内，均为 tracked、带许可/来源）：
1. `integrations/hosts/open-design/expert-suite/skills/` —— 15 个专家技能（brand-identity-director、visual-art-direction-director、production-handoff-specialist…）
2. `packages/capabilities/{plugins,bundles,atoms,scenarios}/` —— DESIGN 自有能力目录（open-design.json manifest + SKILL.md）
3. `design-lab/design-systems/` + `packages/capabilities/typography` 等资产体系

目标形态：为 MiniMax Design 生成**插件包**（manifest.json + index.html + skills/SKILL.md + agent.methods），按 MiniMax 契约转换。注意 Open Design manifest 的 `od.*` 字段 → MiniMax 的 `skill.*/agent.*` 字段映射。

### B. 适配工作分解（建议任务包 DL-MMD-*）
1. **契约桥**：写 Open Design manifest → MiniMax 插件 manifest 的转换器（od.kind/context/atoms/assets → skill.name/entry/agent.methods）
2. **首批 3-5 插件**：选 expert-suite 中与 MiniMax 画布/创作链路最契合的（visual-art-direction-director、brand-identity-director、production-handoff-specialist、uiux-commercial-light-system）
3. **Agent 方法桥**：packages/capabilities 的 schema/verifier 语义 → MiniMax agent.methods 描述 + timeout + 读写回读
4. **本地 gateway 对接**：确认 `/api/plugins/<id>/data/` 写读回、静态资源托管、python RPC（若插件需脚本）
5. **证据与验收**：真实用例（brief→生成→审核→交付）在 MiniMax Design 内闭环；插件安装/卸载/重启回读

### C. 冻结 OPEN DESIGN 的执行含义
- 冻结 ≠ 删除：`integrations/hosts/open-design/` 保留为**技能内容源**（已 tracked、已验证），不再作为活跃宿主驱动
- adapter-registry.json 中 open-design 条目标记 frozen/observe（不新装、不活跃写）
- 新活跃宿主 = minimax-design（host），skill 内容经转换器输出

## 五、风险与注意

- **官方契约未公开**：插件市场/creator plan 文档在飞书 wiki（`my.feishu.cn/wiki/VEoVwpfCKiTHvHkAGQ7cQJxCncf`，需登录）；本文契约来自**内置插件逆向**（3d-director-stage/comfyui manifest + hub-bootstrap.js + renderer 代码）——需用官方 UI/文档交叉验证后再批量生产插件
- **技能市场安装路径**：用户级插件/skill 的磁盘落点尚未从代码中 100% 确认（bundled 在 resources/bundled-plugins；用户安装版可能走 gateway /api/plugins 持久化 + skillPath），落地前需一次**真实安装实验**取证
- **版本**：3.0.10/3.0.11，Squirrel 自动更新——适配要跟随官方接口变动
- **opencode 运行时**：MiniMax 内置 opencode 做 agent——DESIGN 的 skills 若含 CLI/脚本调用需匹配 opencode 能力
- 与既有 `integrations/generators/minimax-h3`（视频生成）**不同角色**：H3 是 generator（模型生成），MiniMax Design 是 host（桌面创作平台）——注意命名空间区分，勿混淆

## 六、待办（下一步）

1. 用户确认适配范围（首批插件清单、是否保留 open-design 内容源）
2. 真实安装实验：在 MiniMax Design UI 内装/建 1 个插件，取证用户级落盘路径与安装 API（需应用运行 + UI 操作）
3. 建立 DL-MMD-* 任务包（契约桥 → 首批插件 → 证据验收）
4. 更新 adapter-registry：open-design=frozen；新增 minimax-design host（待资格化）
