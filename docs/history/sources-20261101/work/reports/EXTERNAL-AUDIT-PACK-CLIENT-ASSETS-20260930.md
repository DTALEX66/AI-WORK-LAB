# WORK-LAB 客户端中立资产清点 · 外部审计包（2026-09-30）

| 项 | 值 |
|---|---|
| 包 ID | `assets-20260930` |
| 采集时间（UTC） | 客户端元数据探针 `2026-09-30T14:02:29Z`；全量清点 `2026-09-30T14:02:48Z`；清理候选 `2026-09-30T14:04:25Z` |
| 证据锚定提交 | `d43d07a75ef8c556344e9b3a99f9257dd2db7b5c` |
| 分支 | `audit/client-asset-inventory-20260930`（基于 `main` = `cd4daa8`） |
| 审计对象 | Hermes / Codex(又名 ChatGPT Agent 侧代理运行时) / DSH(DeepSeek Harness) / CC Switch / Open Design / OpenHuman / GitHub 客户端面，以及本项目（WORK-LAB）全部工作流增强·治理·管理·全局部署·配置·技能·插件·记忆资产 |
| 性质 | **只读元数据清点 + 只读内容归档**（元数据：名称/路径/类型/字节/时间/哈希；内容归档：规则·规范·技能·配置文本的 LF 副本，源文件未修改），引用现有权威登记表，不新建平行账本 |
| 目的 | 为「清理垃圾与过时技能/插件」与「重新部署软件相关内容」提供可审计基线；**并为网页 GPT 审计收敛提供可逐字核对的文本层** |
| 是否已执行清理 | **否**。13 条候选全部 `executed: false`，需逐路径逐操作显式授权 |
| 内容归档 | `reports/audit-archive/20260930/`（476 文件 / 4.45 MiB，见 `ARCHIVE-README.md`） |

## 0. 给审计者的最短路径（URL）

1. 本包（索引层入口）：`https://raw.githubusercontent.com/DTALEX66/WORK-LAB/audit/client-asset-inventory-20260930/reports/EXTERNAL-AUDIT-PACK-CLIENT-ASSETS-20260930.md`
2. 归档说明（**内容层入口**）：`…/reports/audit-archive/20260930/ARCHIVE-README.md`
3. 归档逐文件索引与 sha256：`…/reports/audit-archive/20260930/ARCHIVE-INDEX.json`
4. 证据清单与哈希：`…/reports/audit-evidence/assets-20260930/MANIFEST.json`
5. 原始清点数据：`…/reports/audit-evidence/assets-20260930/asset-inventory.json`

把上面 `…` 替换为 `https://raw.githubusercontent.com/DTALEX66/WORK-LAB/d43d07a75ef8c556344e9b3a99f9257dd2db7b5c` 即为**不可变锚点 URL**（路径为**仓库相对路径**，可直接替换为任意包内文件）：

```
https://raw.githubusercontent.com/DTALEX66/WORK-LAB/d43d07a75ef8c556344e9b3a99f9257dd2db7b5c/<repo-relative-path>
```

| 文件（仓库相对路径） | 用途 | 字节（仓库字节，LF） |
|---|---|---|
| `reports/audit-evidence/assets-20260930/asset-inventory.json` | 全量元数据清点（客户端 + 仓库侧） | 73,749 |
| `reports/audit-evidence/assets-20260930/inventory-verification.json` | 清点表 vs live 逐文件哈希比对 | 6,712 |
| `reports/audit-evidence/assets-20260930/CLEANUP-CANDIDATES.json` | 13 条清理候选（证据/风险/授权要求）+ 1 条审计中发现并修复的外溢 | 9,771 |
| `reports/audit-evidence/assets-20260930/REPO-ASSET-INDEX.md` | 仓库侧人类可读索引（技能/插件/治理/部署映射） | 6,971 |
| `reports/audit-evidence/assets-20260930/three-project-probe.json` | 三项目（WORK-LAB / ArcheAxis-Knowledge-OS / DESIGN-LAB）只读元数据探针 | 12,070 |
| `reports/audit-evidence/assets-20260930/THREE-PROJECT-AND-NORMS-INDEX.md` | 三项目边界 + 规范规则 + 决策文档索引（人类可读） | 7,680 |
| `reports/audit-evidence/assets-20260930/global-workflow-coverage.json` | 全局策略 SSOT + 10 客户端投影矩阵（模式/六项能力/19 域状态分布/扩展路径）+ 三项目规范面 | 26,819 |
| `reports/audit-evidence/assets-20260930/global-deployment-readback.json` | 仓库源 vs 原生 live 目标的哈希/标记回读（hermes 13 技能、codex 4 目标） | 4,471 |
| `reports/audit-evidence/assets-20260930/GLOBAL-WORKFLOW-AND-PROJECT-NORMS-INDEX.md` | 全局工作流完成度判定 + 逐项缺口 G1–G4 + 三项目规范索引（人类可读） | 12,104 |
| `reports/audit-archive/20260930/ARCHIVE-README.md` | **内容层**入口：归档口径、覆盖、排除项、脱敏、配额与校验方法 | 5,246 |
| `reports/audit-archive/20260930/ARCHIVE-INDEX.json` | 归档逐文件索引（来源/归档路径/字节/sha256/状态/脱敏） | 见文件 |
| `reports/audit-archive/20260930/SECRET-SCAN-REPORT.json` | 归档安全报告（排除项、脱敏项、占位符保留项） | 见文件 |
| `reports/audit-evidence/assets-20260930/MANIFEST.json` | 上述 12 个文件的 sha256（仓库字节口径）+ 32 个引用权威文件的 HEAD blob sha256 | 见文件 |

> 哈希口径：`MANIFEST.json` 内的 sha256 一律按**仓库字节（LF 归一化后）**计算。审计者下载 raw 内容后直接对**下载到的字节**重算，应逐字匹配（本地 Windows 工作区的 CRLF 字节不算作基准）。

> 锚定说明：`证据锚定提交` 是**包含全部最终证据文件**的提交（不可变）；本包文本的最新修订位于分支 tip。合并到 `main` 后，稳定 URL 应改用合并提交 SHA。

## 1. 摘要（被审计的结论）

| # | 结论 | 关键数字 |
|---|---|---|
| 1 | 客户端软件面共 **7** 个受管客户端（`config/software-registry.json`）：hermes / codex / deepseek-harness / cc-switch / open-design / openhuman / github | CC Switch = `LEGACY_OBSERVE`（只观察，无活动写入） |
| 2 | Hermes 技能面实为 **26 个技能分类目录 + 6 个内部项**，**无空目录垃圾** | 见 §2-A1 与 §4-1（Windows 目录 `st_size=0` 是假象） |
| 3 | 本项目受管技能 **13** 项（权威 `config/skill-provenance.yaml`）；Codex 执行器技能 **14** 项 | 两者是不同面，不是重复 |
| 4 | 发现**真实陈旧/漂移 3 处**：`config/skills-inventory.json` 6/14 哈希不符；`config/plugin-inventory.json` 缺 chrome-profiles revision；`skill-provenance.yaml` 的 `model-switch` source≠live | 全部是可判定、可复核的事实 |
| 5 | 发现**可回收冗余候选 13 条**（≈1.5 GiB Codex 历史库、20 个 Codex 临时/守卫文件、Hermes `state.db` 4.2 GiB、DSH 两套历史备份等） | **未执行删除** |
| 6 | 隐私：凭据与记忆正文**未被读取**；包内 **0** 处密钥命中（正则扫描 6 文件，含本文件） | 见 §2-G |
| 7 | 外部数据盘 `E:\` `F:\` **未访问** | 见 §2-G |
| 8 | 清点过程本身产出价值证据：**发现并修复 2 处真实缺陷**（`apps/.project-local` 边界外溢 → ERR-093；证据哈希 CRLF/LF 口径错误 → ERR-094），门禁与完整性校验均已恢复 | 见 §2-C5、§2-C6 |
| 9 | **三项目边界与规范规则已纳入**：3 个独立仓库、6 条边界切分、8 条禁止新所有者、规范/规则 14 文件 + 决策文档 18 文件 | 见 §2-H 与 `THREE-PROJECT-AND-NORMS-INDEX.md` |
| 10 | **全局工作流**：策略 SSOT + 10 客户端 × 19 域投影声明**完整**；原生**部署层 4 处缺口**（codex overlay/skills 缺失、hermes 1/13 技能与源不一致、登记记录陈旧），已登记 ERR-095/ERR-096 | 见 §2-I 与 `GLOBAL-WORKFLOW-AND-PROJECT-NORMS-INDEX.md` |
| 11 | **内容归档已建立（只读）**：8 个面（hermes/codex/dsh/cc-switch/open-design/openhuman + 两项目规则面）共 **476 文件 / 4.45 MiB** 文本副本；源文件**未修改**；0 密钥泄漏、0 误报；所有 SKILL.md 完整（仅附属 references 受配额裁剪） | 见 §2-J 与 `reports/audit-archive/20260930/ARCHIVE-README.md` |

## 2. 逐条可判定声明

### A. 客户端软件面（元数据，均为本机实测）

| # | 声明 | 证据字段 | 预期 |
|---|---|---|---|
| A1 | Hermes 技能目录 32 个子项 = 26 个分类目录 + 6 个内部项（`.archive`/`.curator_backups`/`.hub`/`.locks`/`.bundled_manifest`/`.usage.json` 等），**全部非空** | `clients.hermes.skills.children[].child_count` | 目录项 `child_count ≥ 1`；最小者 `apple`/`quality-assurance`/`social-media`/`yuanbao` = 1 |
| A2 | Hermes 用户插件目录只有 **1** 个插件 `chrome-profiles`，其安装元数据记录 `revision=5b9c3257b464c0f926d4355149a8aed9c8f307b4`、`pinned=false`、源 `github.com/anpicasso/hermes-plugin-chrome-profiles` | `inventory-verification.json: hermes_plugin_install_metadata` | 与该字段逐字一致 |
| A3 | Hermes 记忆为 4 个文件（`MEMORY.md` 3,345 B、`USER.md` 2,743 B + 2 个 0 字节 lock），**正文未采集** | `clients.hermes.memories.children[].size` | 仅名称/大小/时间 |
| A4 | Hermes `state.db` = **4,518,653,952 B（≈4.2 GiB）**，为单项最大运行态数据 | `clients.hermes.state_db_size_bytes` | 数值一致 |
| A5 | Codex 主目录 **92** 个子项，其中 **20** 个为 `..codex-global-state.json*.tmp-*` / `.codex-provisioning-*.guard` 残留（**17 个 0 字节**） | `clients.codex.home.children` | 计数一致 |
| A6 | Codex 历史库：`logs_2.sqlite` 675,295,232 B、`thread_history_1.sqlite` 930,263,040 B（≈1.5 GiB） | 同上 `.size` | 数值一致 |
| A7 | DSH `.dsh` 状态目录 16 项，含 `settings.yaml` 61,987 B、`memory/`(3)、`profiles/`(4)、`sessions/`(5)、`skin-center`、`task-board`、`storages`(3)、`llm-deepseek`、`.agent-presets`(2)；`.credentials.yaml` 标记 **SECRET_NOT_READ** | `clients.dsh.state.children` | 密钥文件仅记录"存在"，无内容 |
| A8 | DSH 安装根 12 项：`DSH Desktop.exe` 289,313,640 B、`desktop-user-data`(35)、`locales`(55)、`resources`(3)、**两套历史备份** `.dsh-backup-20260918`(26)/`.dsh-backup-20260920-data`(14)、`.migration`(4)、`.research-20260918`(3)、`pnpm-store`(1) | `clients.dsh.root.children` | 计数与数值一致 |

### B. 本项目（WORK-LAB）资产面

| # | 声明 | 证据 | 预期 |
|---|---|---|---|
| B1 | 目录规模：`config` 25、`.project/governance` 33、`packages/contracts/schemas/workflow` 40、`services` 14、`apps` 3、`scripts` 4、`reports` 9 | `repo_assets.dirs` | 数值一致 |
| B2 | 受管技能 13 个 `SKILL.md` 全部具名并含 sha256 | `repo_assets.managed_skill_files` | 13 条 |
| B3 | Codex 执行器技能 14 个目录（`integrations/executors/codex/skills`），与 `config/skills-inventory.json` 记录条数一致 | `repo_assets.codex_executor_skill_files`、`codex_executor_live` | 14 = 14 |
| B4 | 18 个关键权威文件全部存在（config 8 + governance 10），逐一附字节数与 sha256 | `inventory-verification.json: key_authority_files` | `exists=true` ×18 |
| B5 | 插件登记：3 启用（chrome-profiles / security-guidance / web-ddgs）+ 2 隔离（hermes-media-studio、hermes-telegram-business，均 `DANGEROUS`） | `config/plugin-inventory.json` | 与文件一致 |

### C. 陈旧与漂移（"垃圾/过时"的可判定证据）

| # | 声明 | 核验方法 | 预期 |
|---|---|---|---|
| C1 | `config/skills-inventory.json`（生成于 `2026-09-04T16:49:43Z`）与 live 不一致：**8 项匹配、6 项哈希已变、0 缺失** → 该清点表**已陈旧** | 读 `inventory-verification.json: skills_inventory_check`，逐项比对 `sha256` | `verdict = DRIFT_OR_STALE`；变更项为 observer-delivery / project-data-boundary / safe-project-execution / self-improvement / verification-hardening / windows-development |
| C2 | `config/plugin-inventory.json`（生成于 `2026-08-26`）对 `chrome-profiles` 记 `commit: null`，而 live 安装元数据已有 `revision=5b9c3257…` → **登记不完整** | 比对两文件 | `commit=null` vs live revision 非空 |
| C3 | `config/skill-provenance.yaml` 的 `model-switch`：`source_sha256=37aed9558bc1…` ≠ `live_sha256=0a02c1fc8b65…`，其余 12 项完全一致 → **单点漂移** | 读 `repo_assets.skill_provenance_drift` | 仅 `model-switch` 的 `drift=true` |
| C4 | 两个清点表的 `generatedAt` 均早于本轮（09-04 / 08-26），而 live 已在 09-27~09-30 变动 | 时间戳比对 | 表旧于 live |
| C5 | 清点过程**发现并修复**一处真实边界外溢：`apps/.project-local/runs/frontend-baseline.json`（206 B，早期失败基线），已被仓库门禁 `test_nf11_manifests_present_and_apps_clean` 判为 `unexpected_apps=['.project-local']` → 登记为 **ERR-093**（`path_boundary`） | 读 `CLEANUP-CANDIDATES.json: resolved_during_audit[0]`；`ls apps/`；`taskpacks/current/error-ledger.json` 的 ERR-093 | 现存 `observer` + `token-monitor`；副本在 `.project-local/runs/frontend-baseline.failed-attempt-20260930.json` |
| C6 | 发布前自检**发现并修复**证据哈希口径错误：初版 `MANIFEST.json` 按工作区 **CRLF** 字节计算，与仓库实际存储/分发的 **LF** 字节不符（例：`asset-inventory.json` 本地 76,293 B vs 仓库 73,749 B），导致 4/4 完整性校验失败 → 登记为 **ERR-094**（`evidence_state`） | 读 `error-ledger.json` 的 ERR-094；用 §5 的网络回读命令复核 | 修正后 **4/4 通过**（本机实测） |

### D. 清理候选（**仅候选，未执行**）

候选全量见 `CLEANUP-CANDIDATES.json`。摘要：

| id | 面 | 类型 | 规模/计数 | 风险 | 建议动作 |
|---|---|---|---|---|---|
| CC-1 | codex | 陈旧临时文件 | 14 个 `..codex-global-state.json*.tmp-*` | 低 | 删除（先列清单） |
| CC-2 | codex | 失效守卫 | 6 个 0 字节 `.codex-provisioning-*.guard` | 低 | 删除 |
| CC-3 | codex | 备份 | 10 个 `*.bak*`（config.toml×5、AGENTS.md×2 等） | 中 | 保留最近 1 份，余归档 |
| CC-4 | codex | 大历史库 | `logs_2.sqlite` + `thread_history_1.sqlite` ≈1.5 GiB | 中 | 走官方清理机制，勿手工删活动库 |
| HH-1 | hermes | 大状态库 | `state.db` ≈4.2 GiB | 中 | **属 OBSERVE 字段**，由用户设置决定，本项目不覆盖 |
| HH-2 | hermes | 策展产物 | `.archive`(71)、`.curator_backups`(5)、账本 1.6 MB | 低 | 归档旧条目；账本属审计证据，保留 |
| HH-3 | hermes | 自动备份 | `backups/` | 低 | 保留最近 N 份 |
| DD-1 | dsh | 历史备份 | 两套（26/14 子项，09-18/09-20 迁移期） | 中 | 新 2.0.13 稳定后归档 |
| DD-2 | dsh | 历史快照 | `.research-20260918`(3)、`.migration`(4) | 低 | 保留 `.migration` 日志，快照可归档 |
| DD-3 | dsh | 缓存 | `pnpm-store`(1) | 低 | 确认无活动安装后删（可再生） |
| RR-1 | repo | 陈旧登记 | `skills-inventory.json` 6/14 不符 | 低 | **重新生成**（非删除） |
| RR-2 | repo | 登记不全 | `plugin-inventory.json` 缺 revision | 低 | 补录（非删除） |
| RR-3 | repo | 漂移 | `model-switch` source≠live | 低 | 确认基准后单向对齐 |

### E. 重新部署映射（"重新部署软件相关内容"的通道）

| 目标面 | 源 | 唯一通道 | 受管/观察 |
|---|---|---|---|
| Hermes 受管技能（13） | `packages/client-neutral-core/skills/**` | `scripts/sync_hermes_workflow_assets.py`（备份后发布 + 同批更新 `skill-provenance.yaml` 哈希） | 受管 |
| Hermes 提示层 | `config/SOUL.md` | 同上 | 受管 |
| Hermes 启动器 | `bin/`（codex / hermes-npx / 守卫脚本） | 同上 | 受管 |
| Hermes 配置字段 | 仅 `display.language`、`display.busy_input_mode` | 同上 | **其余字段 OBSERVE，绝不覆盖**（`config-ownership.json`, `preserve_unknown: true`） |
| Codex 执行器技能（14） | `integrations/executors/codex/skills/**` | Codex 侧通道；本项目仅只读登记 | 观察 |
| DSH 桌面 | `%DSH_ROOT%\DSH Desktop.exe` + `.lnk` 三字段 | 覆盖部署脚本 + `--user-data-dir` 重 pin（ERR-087 回退见 runbook） | 受管（保留用户数据/会话/插件/技能） |

### F. 仓库一致性（审计者可公开验证）

| # | 声明 | 核验方法 | 预期 |
|---|---|---|---|
| F1 | 锚定提交存在 | `https://api.github.com/repos/DTALEX66/WORK-LAB/commits/d43d07a75ef8c556344e9b3a99f9257dd2db7b5c` | HTTP 200 |
| F2 | 证据文件确在该提交树内 | 直接抓 §0 的 raw URL | HTTP 200 且非空 |
| F3 | 证据未被篡改 | 用 `MANIFEST.json` 内 sha256 对每个文件**下载到的字节**重算（含 12 个证据/归档索引文件；32 个引用权威文件按同一 SHA 的 blob 复核；归档 476 个副本按其自身索引复核） | 逐一相符 |
| F4 | 分支存在 | `https://api.github.com/repos/DTALEX66/WORK-LAB/branches/audit/client-asset-inventory-20260930` | HTTP 200 |

### G. 隐私与边界声明

| # | 声明 | 核验方法 | 预期 |
|---|---|---|---|
| G1 | 包内无凭据值 | 对 5 个包文件跑密钥正则（`sk-…`/`gh[pousr]_…`/`AKIA…`/`BEGIN … PRIVATE KEY`/`bearer …`） | **0 命中**（本机实测 `total_hits=0`） |
| G2 | 未读取凭据正文 | 检查清点结构：`.env`、`auth.json`、`.credentials.yaml`、`.sandbox-secrets` 仅以 `SECRET_NOT_READ` 出现 | 无对应内容字段 |
| G3 | 未读取记忆正文 | `clients.hermes.memories` 仅含名称/大小/mtime | 无正文 |
| G4 | 未访问 `E:\` `F:\` | 包内路径令牌集合仅含 `%WORKLAB_ROOT%`/`%USERPROFILE%`/`%LOCALAPPDATA%`/`%APPDATA%`/`%DSH_ROOT%` | 无 E/F 路径 |
| G5 | 清理零执行 | `CLEANUP-CANDIDATES.json` 每条 `executed: false` | 全为 false |

### H. 三项目边界与规范规则（放行清理/重部署前的所有权前提）

| # | 声明 | 证据 | 预期 |
|---|---|---|---|
| H1 | 三项目为**各自独立仓库**，且 ArcheAxis 的本地目录名不等于俗称 | `three-project-probe.json: projects` | WORK-LAB=`DTALEX66/WORK-LAB`；ArcheAxis=`DTALEX66/ArcheAxis-Knowledge-OS`，本地目录 `%PROJECTS_ROOT%/ArcheAxis-Knowledge-OS`（**不存在** `%PROJECTS_ROOT%/ArcheAxis`）；DESIGN-LAB=`DTALEX66/DESIGN-LAB` |
| H2 | 各自当前 git 引用（本包采集时点事实） | 同上 `head`/`branch`/`dirty_entries` | WORK-LAB `049cf40…`@`audit/client-asset-inventory-20260930`（dirty 6）；ArcheAxis `43c2cafa1bfe…`@`codex/Audit`（**dirty 111**）；DESIGN-LAB `0fbb67439755…`@`feat/ui-commercial-workbench-20260930`（dirty 0） |
| H3 | 另两项目**只读探测**，未被修改 | `three-project-probe.json: policy` | 仅记录存在性、git 引用、顶层清单与权威类文件摘要；无写入 |
| H4 | 边界权威与门禁 | `.project/governance/three-project-boundary.json` + `scripts/ci/verify_three_project_boundary.py` | 6 条 `boundary_splits`（MEMORY_BACKEND / KNOWLEDGE_TRUTH / KNOWLEDGE_STAGING / EVOLUTION / ARCHIVE_90 / DESIGN_LAB）+ 8 条 `forbiddenNewOwners` |
| H5 | 规范规则权威面已索引 | `THREE-PROJECT-AND-NORMS-INDEX.md`；`MANIFEST.json: referenced_repo_files` | 规范/规则 14 文件 + `docs/decisions/` 18 文件，逐一附字节与摘要 |
| H6 | **Open Design 客户端 ≠ DESIGN-LAB 项目** | `three-project-boundary.json` 的 `DESIGN_LAB` 条目 | 客户端层 `MANAGE`（`apply_supported=false`）；设计能力/资产/质量体系 `IGNORE` |
| H7 | 记忆与知识类资产的真值归属 | 同上 `MEMORY_BACKEND` / `KNOWLEDGE_TRUTH` | 长期记忆/知识真值/学习演化属 **ArcheAxis**；WORK-LAB 只保留边界守卫与 `KnowledgeCandidate` |

> 对**清理与重部署**的直接约束：任何待清理/待重部署资产必须先落入三者之一的所有权内；跨边界搬迁须走 §H4 的 seam/gate；`memories/`、`memory/`、`services/memory` 不得在 WORK-LAB 内被当作长期记忆真值处理。

### I. 全局工作流：覆盖判定与部署回读（结论：**权威层完整，部署层有 4 处缺口**）

| # | 声明 | 证据 | 预期 |
|---|---|---|---|
| I1 | 存在唯一的跨软件语义 SSOT，且受机器合同约束 | `config/global-agent-policy.yaml`（revision 2）+ `packages/contracts/schemas/workflow/global-agent-policy.schema.json` | 20 个语义域；所有权 `USER_OVERLAY/MANAGE`；显式声明"非第二权威/非第二配置治理/非第二账本/非第二适配器登记" |
| I2 | 每个客户端的投影模式与 19 域能力状态**全部显式声明**，无空缺 | `config/adapter-registry.json → entries[].policy_projection`；机器可读副本见 `global-workflow-coverage.json: client_projection_matrix`（含六项能力位与 19 域状态分布直方图） | 10 客户端；hermes/codex = `READBACK_VERIFIED`（detect/plan/apply/readback/rollback/drift 六项齐）；其余 8 个按声明为 OBSERVE/PLAN/MANIFEST 且 `capability_coverage_complete: true` |
| I3 | DSH 无扩展文件属**声明内**状态，不是缺口 | 同 I2 的 `deepseek-harness` 条目 | `observe-plan` / `PLAN_SUPPORTED`，apply_supported=false，前置条件写在 note 中 |
| I4 | Hermes 原生目标部分一致 | `global-deployment-readback.json: hermes_managed_skills` | 13 项中 **12 一致 / 1 不一致（`windows-development-environment`）/ 0 缺失**；`SOUL.md` 仓库与 live **哈希一致** |
| I5 | Codex 原生目标**部分缺失** | `global-deployment-readback.json: codex_native_targets` | `config.toml` 有受管标记 ✓；**`AGENTS.md` 无受管 overlay 块** ✗；`skills/workflow-assistance-*` live 目录数 **0** ✗ |
| I6 | 两处漂移已登记错误账本 | `taskpacks/current/error-ledger.json` 的 ERR-095（codex）、ERR-096（hermes） | 均 `UNVERIFIED → FAIL`，`currentApplicability=DRIFT_OPEN_20260930` |
| I7 | 三项目**自身**的规范/规则已索引（只读） | `global-workflow-coverage.json: project_norms`、`three-project-probe.json` | ArcheAxis-Knowledge-OS：`AGENTS.md` + `DIRECTORY_AUTHORITY.yaml`；DESIGN-LAB：`AGENTS.md` + `AUTHORITY.md`；WORK-LAB：14 规范文件 + 18 决策文档 |

**逐项缺口（G1–G4）**：

| id | 面 | 事实（live 实测） | 修复通道（未授权执行） |
|---|---|---|---|
| G1 | codex | `CODEX_HOME/AGENTS.md`（16,805 B）**无** `WORKFLOW-ASSISTANCE MANAGED` 块标记，`WORK-LAB` 命中 0，而登记称 `READBACK_VERIFIED` + BEGIN/END + hash fencing | `sync_codex_global_assets.py` + 原生回读（或按用户意愿改写登记成熟度） |
| G2 | codex | 扩展声明的 `skills/workflow-assistance-*` 在 `CODEX_HOME/skills/` 匹配 **0** 个 | 同上 |
| G3 | hermes | `windows-development-environment/SKILL.md` live `39bbb61a…`(23,825 B) ≠ 仓库源 `2e1fc6dc…`(21,982 B) | `sync_hermes_workflow_assets.py` + 回读 |
| G4 | 记录 | `skill-provenance.yaml`：`model-switch.live_sha256` 已不符实际；`windows-development-environment` 记录仍为旧值；另 `skills-inventory.json` 6/14、`plugin-inventory.json` 缺 revision | 由部署通道同批重算，手改禁止 |

> 纪律：I4–I6 与 G1–G4 均为**声明/登记与 live 不一致**的已核实事实，不等于"产品不可用"；本包**未执行任何写入**，修复必须走被授权通道并附原生回读。

### J. 内容归档层（只读副本，供逐字审计）

| # | 声明 | 证据 | 预期 |
|---|---|---|---|
| J1 | 归档为**只读复制**，源文件零修改 | `ARCHIVE-INDEX.json: policy.mode = READ_ONLY_COPY` | 归档在 `reports/audit-archive/20260930/`；本机源路径未发生写入（只读打开） |
| J2 | 归档覆盖 8 个面，含全部技能主文件 | `ARCHIVE-INDEX.json: summary` | hermes 363 / design-lab 61 / codex 18 / dsh 17 / archeaxis 8 / openhuman 4 / open-design 3 / cc-switch 2；**SKILL.md 无缺失**（186 个） |
| J3 | 归档不含凭据 | `SECRET-SCAN-REPORT.json` + 独立复扫 | 名称策略排除 `.env`/`.credentials.yaml`/`auth*.json`/`*.sqlite*`/`Local State` 等；内容扫描 0 排除、0 命中 |
| J4 | 凭据类配置文件以**脱敏**而非排除处理 | 同 J3 | 命中即整值替换 `[REDACTED_BY_WORKLAB]`；本次仅 1 个技能文件 1 处（`kv_secret`），清单在报告中 |
| J5 | 误报防护有据 | 扫描器含词边界 + 占位符判定 | `task-2026-…` 之类的 `sk-` 假命中不会触发排除；文档示例令牌（3 个文件）**原样保留**并在报告中列明 |
| J6 | 配额裁剪**未伤及技能主文件** | `ARCHIVE-INDEX.json` 中 `EXCLUDED_CLIENT_BUDGET` 明细 | 494 个被裁文件**全部**为 `skills/**/references/*.md`（附属文档）；`SKILL.md` 丢弃数 = **0** |
| J7 | 归档逐文件可校验 | `ARCHIVE-INDEX.json` 内每文件 sha256（LF 仓库字节） | 下载任意归档副本重算 sha256 应逐字匹配 |

> 使用方式（给网页 GPT）：先读 `ARCHIVE-README.md` 了解口径与排除项，再按 `ARCHIVE-INDEX.json` 的 `archive_path` 逐个取原文核对声明；**不要**把"未归档的凭据/会话/记忆"读成"不存在"。

## 3. 审计者**无法**从公开信息验证的部分（请据此调整结论强度）

| 无法公开验证 | 原因 | 本机自证方式 |
|---|---|---|
| 元数据采集时刻之后的状态 | 客户端数据是**时点事实**，且不随仓库发布 | 每文件含 `generated_at_utc`；重跑 `client_roots_probe.py` 可比对 |
| 未上传的本地实体（如 `state.db` 4.2 GiB、Codex 92 项内容） | 体积与隐私，故意不发布 | 包内提供大小/计数/哈希前缀，不提供内容 |
| "私有面确实无凭据" | 未发布的本地文件不在包内，自然不可核 | 只能验证"包内 0 命中"（G1） |
| DSH/Codex 客户端的运行时行为 | 运行时状态不可从仓库推断 | 需用户在本机手动验证（本包不声称已验） |
| Hermes 记忆是否"过时" | 正文未读（隐私），无法判断质量 | 需用户显式授权逐文件读取后才能评估 |

## 4. 一致性自检（审计者可能发现的矛盾点，先说清）

| 可能的疑问 | 说明 |
|---|---|
| 为什么 Hermes 技能目录里有些项"0 字节"，却没被列为垃圾？ | Windows 下**目录** `st_size` 恒为 0，与内容无关。补测 `child_count` 后 26 个分类目录全部非空，故**撤回**"空目录垃圾"的初判（见 `CLEANUP-CANDIDATES.json: corrections[0]`）。 |
| 为什么 `plugin-inventory.json` 记 3 个启用插件，而 live 用户插件目录只有 1 个？ | `security-guidance`、`web-ddgs` 是 **bundled**（随 Hermes 发行版），不在用户插件目录。这是**记录口径差异，不是缺失**（见 `corrections[1]`）。 |
| `skills-inventory.json`（14 Codex 技能）与 `skill-provenance.yaml`（13 受管技能）为何数量不同？ | 二者是**不同面**：前者登记 Codex 执行器技能，后者登记部署到 Hermes Home 的受管技能。不是重复账本，无需合并。 |
| 本包是否构成"平行账本"？ | 否。本包只**引用**现有权威登记表（`config/*`、`.project/governance/*`），不定义新权威字段；`schema` 为 `workflow/neutral-asset-inventory/v1`，属证据层。 |
| 为什么把 `%USERPROFILE%` 等令牌化，而不是绝对路径？ | 中立化要求：产物需跨机器可读；同时避免把用户名写进公开仓库。本机绝对路径仅存在于 `.project-local/`（不跟踪）。 |
| 为什么包内存在一个"再锚定"提交（pack 文本晚于证据提交）？ | 证据文件与 `MANIFEST.json` 先冻结为提交 `636d5ece`，再由 pack 把 URL 指向该提交，因此 `636d5ece` 是**证据的可信锚点**；本包文本的最新修订位于分支 tip。锚点提交内的 pack 文本可能引用更早的锚点，这属预期，不是缺失。 |
| 为什么引用权威文件的 sha256 以 HEAD blob 为准？ | 只有按仓库存储的字节计算，审计者用 raw URL 下载后重算才能逐字匹配；曾因按工作区 CRLF 字节计算而全部不匹配（见 ERR-094）。 |
| 第 10 条里"部署层 4 处缺口"是否等于项目失败？ | 否。它表示**声明/登记与 live 原生面不一致**（G1–G4），已按纪律登记为 ERR-095/ERR-096 且状态为 `DRIFT_OPEN_20260930`；修复需被授权写入通道，本包未执行任何写入。 |
| 归档是"复制"还是"改写"？源文件会受影响吗？ | 源文件**零修改**（只读打开）：归档把文本按 LF 写入本项目，仅对 1 个技能文件做了 1 处模式级脱敏（公开仓库不得含可疑令牌）。原始 CRLF 差异不影响内容语义，且 `ARCHIVE-INDEX.json` 记录的是**副本** sha256。 |
| 为什么有 494 个文件被"丢弃"？会漏审计吗？ | 它们是 `skills/**/references/*.md` 附属文档，因客户端配额裁剪；**技能主文件 `SKILL.md` 一个未丢**（186/186）。若某结论依赖附属文档，请标注"依据缺失"而非推断内容。 |
| 归档里有"任务/状态"类文件吗？ | 有少量状态文件（如 hermes `.workflow-assistance-baseline.json`、openhuman `window_state.toml`）——它们是**本机运行状态的只读快照**，用于核对部署声明，不是新的权威账本。 |

## 5. 复核命令（公开可做 / 本机可做）

公开（无需本机）：

```bash
curl -s https://api.github.com/repos/DTALEX66/WORK-LAB/commits/d43d07a75ef8c556344e9b3a99f9257dd2db7b5c | jq -r .sha
curl -s -o /dev/null -w '%{http_code}\n' https://raw.githubusercontent.com/DTALEX66/WORK-LAB/d43d07a75ef8c556344e9b3a99f9257dd2db7b5c/reports/audit-evidence/assets-20260930/MANIFEST.json
```

一次跑完完整性校验（下载 MANIFEST → 逐个重算 sha256，含 12 个证据/归档索引文件与 32 个引用权威文件；随后校验归档 476 个副本）：

```bash
python - <<'PY'
import json, hashlib, urllib.request
SHA = "d43d07a75ef8c556344e9b3a99f9257dd2db7b5c"
B = f"https://raw.githubusercontent.com/DTALEX66/WORK-LAB/{SHA}"
g = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "audit"}), timeout=60).read()
ok = bad = 0

mf = json.loads(g(f"{B}/reports/audit-evidence/assets-20260930/MANIFEST.json"))
for f in mf["files"]:
    b = g(f"{B}/{f['rel']}")
    good = hashlib.sha256(b).hexdigest() == f["sha256"] and len(b) == f["bytes"]
    ok, bad = (ok + 1, bad) if good else (ok, bad + 1)
    print("OK " if good else "FAIL", f["rel"])
for r in mf["referenced_repo_files"]:
    good = hashlib.sha256(g(f"{B}/{r['rel']}")).hexdigest() == r["sha256"]
    ok, bad = (ok + 1, bad) if good else (ok, bad + 1)
    print("OK " if good else "FAIL", r["rel"])

idx = json.loads(g(f"{B}/reports/audit-archive/20260930/ARCHIVE-INDEX.json"))
aok = abad = 0
for r in idx["files"]:
    if not r["status"].startswith("COPIED"):
        continue
    good = hashlib.sha256(g(f"{B}/reports/audit-archive/20260930/{r['archive_path']}")).hexdigest() == r["sha256"]
    aok, abad = (aok + 1, abad) if good else (aok, abad + 1)
print(f"authority verified={ok} failed={bad} | archive verified={aok} failed={abad}")
PY
```

缺陷登记核验（ERR-093 / ERR-094 / ERR-095 / ERR-096）：

```bash
curl -s https://raw.githubusercontent.com/DTALEX66/WORK-LAB/d43d07a75ef8c556344e9b3a99f9257dd2db7b5c/taskpacks/current/error-ledger.json | jq -r '.errors[-4:][] | "\(.error_id) \(.classification) \(.status_before)->\(.status_after)"'
```

本机（可复现清点）：

```bash
python .project-local/runs/client_roots_probe.py        # 客户端元数据
python .project-local/runs/build_asset_inventory.py      # 全量清点
python .project-local/runs/verify_inventories.py         # 清点表 vs live 哈希比对
python .project-local/runs/secret_scan_package.py        # 密钥扫描
```

## 6. 下一步（达到"清理 + 重新部署"目标所需授权）

1. **清理授权**：对 `CLEANUP-CANDIDATES.json` 逐条给出"路径 + 操作"授权（默认全拒）。
2. **登记修复授权**：重建 `config/skills-inventory.json`、补录 `plugin-inventory.json`、对齐 `model-switch`（均需确认基准侧）。
3. **重新部署授权**：经 `sync_hermes_workflow_assets.py` 重新发布受管技能/SOUL/启动器（本会话未执行）。
4. **合并授权**：本分支 → `main`（合并后本节 URL 应改用合并 SHA 以求稳定）。
