# DeepSeek Harness (DSH) — 配置指南（供 Hermes / Codex / CC Switch 等其他软件接入）

> 目的：告诉 WORK-LAB 管理的其他软件（Hermes、Codex、CC Switch、OpenHuman、
> Open Design 及未来客户端）**DSH 的规则、技能、边界如何配置**，以及 WORK-LAB
> 当前已为 DSH 做了什么、其他软件应该遵守什么、不应碰什么。
>
> 依据：`WORK-LAB-LOCAL-MODEL-CONTROL-PLANE-DEEPSEEK-HARNESS-TASKPACK-2026-08-15.md`
> （SHA-256 `8981e59b...`）、DSH 官方 skills/settings 子系统文档、AGENTS.md。
> 状态：2026-08-16 实测核对；2026-09-02 数据根/部署形态更新（DSH 2.0.x 社区版，`~/.dsh`）。

---

## 1. DSH 是什么（一句话）

DSH（DeepSeek Harness）是一个 **Agent 运行时（agent runtime）**，不是配置层管理器、
不是模型网关、不是 Hermes 替代品。它执行隔离的、任务级 Git worktree 中的代理任务；
**不写客户端配置、不完成 Task Ledger 任务、不让凭据进入仓库**。

因此：**DSH 不需要“像 Hermes 一样”的整套全局配置**。它只消费四样东西：

| 配置载体 | 位置 | DSH 怎么读 |
|---|---|---|
| 规则/站立命令 | 项目根 `AGENTS.md`（及模块 AGENTS.md） | 自动注入会话（`dsh-agent-instructions`，maxBytes 65536） |
| 技能 | 官方发现路径（见 §3） | 会话技能目录（`<system-reminder>` 注入） |
| 用户设置 | `~/.dsh/settings.yaml`（2.0.x 社区版固定数据根） | 命名空间解析（locale 等） |
| 项目注册 | `~/.dsh/storages/workspace.json` | 工作区注册 |

---

## 2. 规则（AGENTS.md）——其他软件需要知道的事

### 2.1 WORK-LAB 已注入的规则（DSH 自动读取，无需其他软件转发）

DSH 会话会自动加载项目根与模块的 AGENTS.md。WORK-LAB 根 AGENTS.md 目前包含：

- **Scope**：单根 monorepo，规范模块根仅 `packages/client-neutral-core`（Workflow）与
  `apps/observer`（Observer，严格只读）；`10-workflow/workflow-assistance` 与
  `30-observer/work-lab-observer` 是 2026-09 目录收敛前的历史路径，已不再被跟踪。
- **Ownership**：单写者；只读审查者不得编辑；跨模块变更需显式任务卡。
- **Safety（2026-08-16 强化）**：
  - 凭据/`.env`/auth store/私钥/浏览器数据/token/prompt/response 正文禁读禁传；
  - **`E:\` 读或写一律禁止**，除非逐路径逐操作显式授权；
  - **本项目产生的构建/缓存/临时文件/证据/下载全部锁定在项目 Git 根内**
    （TMP、npm/uv/pip 缓存、node_modules → `.project-local/runs/`；证据 →
    `.project-local/artifacts/` 或 `reports/`），不外溢到用户目录/其他项目/共用库；
  - 任何外溢必须可追溯、可定位、可清理、可迁移（project-data-boundary.json）；
  - 禁止破坏性 reset/clean/force-push。
- **Managed global configuration (Hermes)**：WORK-LAB 管理的 Hermes overlay 字段、
  13 skills、SOUL.md、bin；部署只走 sync-plan；preserve_unknown。
- **Workflow Assistance 执行契约**：质量门禁命令、证据分级、Codex 未经批准不得
  提交/推送/改全局配置。
- **五维运行时基线**：入口唯一、桌面可达、官方基线赢、无阻塞开销、模型满血。

### 2.2 其他软件如何给 DSH 配置规则

- **项目级规则**：写在 DSH 会打开的项目根 `AGENTS.md`（如 WORK-LAB 根）。DSH
  自动注入，无需在 DSH 里额外注册。
- **模块级规则**：`<模块>/AGENTS.md`，DSH 在对应模块工作区自动注入。
- **不要做**：不要试图把 Hermes 的 `config.yaml` / `SOUL.md` / `$HERMES_HOME/bin/` 复制成
  DSH 的配置——DSH 不消费它们。Hermes 的 SOUL.md 是 Hermes 专属机制。
- **DSH 自身**：`~/.dsh/settings.yaml` 只应含 DSH 自己的用户设置（当前：
  `ui-onboarding` + `locale.preference: zh`）。其他软件不得改写它。

---

## 3. 技能——其他软件需要知道的事

### 3.1 DSH 官方技能发现路径（优先级从高到低）

DSH 的本地技能提供者按以下 rank 扫描（DSH 侧目录名 packages/skill/skill-filesystem，**不是本仓路径**，故不加反引号）：

| Rank | 来源 | 根路径 |
|---|---|---|
| 100 | project-dsh | `<projectRoot>/.dsh/skills` |
| 200 | project-agents | `<projectRoot>/.agents/skills` |
| 300 | custom | `Config.customSkillDirs`（组合配置） |
| 400 | user-dsh | `<dshHome>/skills` |
| 500 | user-agents | `<agentsHome>/skills`（默认 `~/.agents` 或 `$DSH_AGENTS_HOME`） |
| 600 | bundled | `Config.bundledSkillDir` / `$DSH_BUNDLED_SKILL_DIR` |

- 技能名 kebab-case；目录包 `<name>/SKILL.md` 或扁平 `<name>.md`。
- 重复名：rank 低者胜（同层内按 provider 顺序/本地顺序）。
- 项目根 = 最近的含 `.git` 的祖先目录。
- **其他软件配置 DSH 技能 = 把技能放进上述任一目录即可，无需注册表**。

### 3.2 WORK-LAB 当前已部署的 DSH 技能（2026-08-16 实测）

| 技能 | 数量 | 来源 | DSH rank |
|---|---|---|---|
| `work-lab-workflow` | 1 | `D:\All projects\WORK-LAB\.agents\skills\` | 200 (project-agents) |
| `workflow-assistance-*`（5 个：github-delivery / project-data-boundary / safe-project-execution / update-safety / windows-development） | 5 | `C:\Users\ALEX\.agents\skills\` | 500 (user-agents) |

2026-10-05 来源收敛为上述 6 个入口；本次只验证 Codex 侧文件，不宣称 DSH 新会话已发现。**部署源是仓库**
`integrations/executors/codex/skills/`（5 个）与根
`.agents/skills/`（1 个）；实际加载以各客户端新会话 readback 为准。

### 3.3 其他软件如何维护 DSH 技能

- 新增/更新 DSH 技能 = 更新仓库 `integrations/executors/codex/skills/<name>/SKILL.md`，然后
  **部署到 `~/.agents/skills/<name>/`**（user-agents rank 500）或项目
  `.agents/skills/`（rank 200）。DSH 无需重启即可发现（目录 watcher）。
- 不要往 `<dshHome>/skills` 或 `<projectRoot>/.dsh/skills` 放 Hermes 的 13 个
  skills——它们不是 DSH 技能，放进去只会造成重复/混淆。
- 技能 body 保持 lean（DSH 文档：skills ~<10KB each）；引用资源用 `resourceBase`
  相对路径。

---

## 4. 边界与安全——其他软件必须遵守

| 边界 | 规则 |
|---|---|
| 凭据 | DSH 的 `.credentials.yaml`、Hermes `auth.json`、Codex auth 均禁读；其他软件不得代读 |
| E 盘 | 禁止访问（读或写），除非逐路径逐操作显式授权 |
| 内容外溢 | 本项目产生的所有产物锁在项目 Git 根内；不外溢到用户目录/其他项目/共用库 |
| 其他项目/共用库 | 不写（`Model library`、`OS External Configuration` 等只读或经授权） |
| 客户端配置 | DSH 不写 Hermes/Codex/CC Switch 配置；反之其他软件也不写 DSH 的 `~/.dsh` |
| 模型下载 | 走直连，**绕过 VPN/代理**（当前系统代理 127.0.0.1:7890 = FlClash，下载时必须清 HTTP(S)_PROXY） |
| 模型存储 | Ollama 模型存 `D:\All projects\Model library\runtimes\ollama`（OLLAMA_MODELS） |
| 审批 | DSH 会话 approval policy 可 `ask` 或 `never`；写操作按任务包逐动作批准 |
| 沙箱 | 文件策略 danger-full-access 时靠规则纪律；收紧时可 workspace-write |

---

## 5. 部署与同步（其他软件接入时的操作流程）

### 5.1 Hermes 便携同步（已有官方脚本）

`integrations/executors/hermes/sync_hermes_workflow_assets.py`：
- dry-run：`python ... sync_hermes_workflow_assets.py --plan-json <path>`
- apply：`python ... sync_hermes_workflow_assets.py --apply --approved`
- 部署 21 步：13 skills + 6 bin + SOUL.md + .env.template → Hermes Home；
  更新 `config/skill-provenance.yaml` live 哈希；备份保留最近 2 个。
- 不整文件覆盖 live `config.yaml`（混合所有权，只推管理字段）。

### 5.2 Codex 全局 overlay（官方脚本）

`integrations/executors/codex/sync_codex_global_assets.py`：
- `plan` → 审查 plan_digest → `apply --approved --approved-plan-digest <digest>` → `verify`。
- 管理 5 个 `workflow-assistance-*` 技能（→ `~/.agents/skills`）、
  `rules/workflow-assistance.rules`、`AGENTS.md` managed block、
  `config.toml` 的 3 个字段（approval_policy / sandbox_mode / project_doc_max_bytes）。
- fail-closed：managed block 被外部改写时 BLOCKED；恢复 = 注入期望块 → 重新 plan。

### 5.3 DSH 技能部署（新增，供其他软件）

DSH 无独立同步脚本；部署 = 复制技能目录到 rank 路径（§3.1）。建议其他软件
（Hermes/Codex）接入 DSH 时：把 DSH 技能源统一放
`integrations/executors/codex/skills/`，部署目标
`~/.agents/skills/`（与 Codex 共用 user-agents 层，避免重复维护）。

---

## 6. 模型下载（当前状态 2026-08-16）

| 项 | 状态 |
|---|---|
| Ollama 服务 | 已重启（直连），OLLAMA_MODELS=`D:\All projects\Model library\ollama` 已持久化（User 级） |
| 已装（推理验证 OK，2026-08-16） | `qwen3:8b`（5.2 GB 通用）、`qwen3-coder:30b-a3b-q4_K_M`（18 GB 代码）、`qwen2.5vl:7b`（6.0 GB 视觉 OCR）、`qwen3-embedding:0.6b`（639 MB 检索）、`qwen3-reranker`（494 MB 重排，HF GGUF 导入）、faster-whisper large-v3-turbo（1.5 GB ASR，`Model library\whisper\`） |
| 已退役（被替代删除） | `qwen2.5-coder:7b`（→ qwen3-coder:30b）、`qwen3:4b`（→ qwen3:8b） |
| 约束 | 任何下载走直连；下载前检查 HTTP(S)_PROXY 未指向 VPN 端口；H3 为视频模型不装 Ollama |

---

## 7. 一句话总结

**DSH 不需要 Hermes 那套配置**（config.yaml/SOUL/bin/projects.db 均不消费）；
它只消费 **AGENTS.md 规则（自动注入）+ 技能目录（rank 发现）+ `~/.dsh/settings.yaml` +
workspace 注册**。其他软件接入 DSH 的要点：**规则写进项目 AGENTS.md，技能放进
`.agents/skills`（项目级）或 `~/.agents`（用户级），模型下载走直连绕过 VPN，
内容与凭据边界遵守项目规则**。WORK-LAB 已就位：根 AGENTS.md 规则强化、
15 个 DSH 技能、Ollama 直连下载、locale zh。

> 2026-10-05 技能收敛：本机全局个性化规则使用 personal-guidance.md 的单一文件；只更新技能时运行同步器 --skills-only，保留 config/AGENTS/rules。普通全量 overlay 不应重建已由用户替换的旧 managed block。项目专属说明见 docs/current/workflow-assistance/skill-references/。历史运行记录不代表本次部署。
