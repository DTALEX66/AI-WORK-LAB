# WORK-LAB 资产索引（中立 / client-neutral）

生成时间（UTC）：2026-09-30T14:04:25Z

本文件是**只读索引**：引用现有权威登记表，不新建平行账本，不复制权威内容。
隐私：凭据文件（`.env`/`auth.json`/`.credentials.yaml`/`.sandbox-secrets`）与记忆正文**未被读取**，仅记录名称/大小/时间。

## 1. 权威登记表（本项目）

| 资产面 | 权威文件 | 字节 | sha256(前16) |
|---|---|---|---|
| skill-provenance.yaml | `config/skill-provenance.yaml` | 6330 | `6816b73f616bf73e` |
| plugin-inventory.json | `config/plugin-inventory.json` | 2417 | `60fd5219b48d32e3` |
| skills-inventory.json | `config/skills-inventory.json` | 3727 | `b858208ededf6827` |
| config-ownership.json | `config/config-ownership.json` | 21535 | `d799c9925d32b1e1` |
| adapter-registry.json | `config/adapter-registry.json` | 24343 | `245e7e1829757d2d` |
| software-registry.json | `config/software-registry.json` | 4703 | `3a60543fdbd538e3` |
| client-evidence.json | `config/client-evidence.json` | 7675 | `1f1db25b8805ff73` |
| machine-registry.json | `config/machine-registry.json` | 212 | `6c696d72f78c2fee` |
| config-authority-index.json | `.project/governance/config-authority-index.json` | 6525 | `eea9f10c34b384e2` |
| runtime-registry.json | `.project/governance/runtime-registry.json` | 22657 | `ad74bc7c21919203` |
| project-authority-index.json | `.project/governance/project-authority-index.json` | 2334 | `448e994e41309ba1` |
| taskpack-authority-index.json | `.project/governance/taskpack-authority-index.json` | 13998 | `fa88e13b82d7dd59` |
| module-ownership.json | `.project/governance/module-ownership.json` | 522 | `db866bab3cc01e97` |
| project-data-boundary.json | `.project/governance/project-data-boundary.json` | 3203 | `54a0e5c4c03a6f4c` |
| provider-registry.json | `.project/governance/provider-registry.json` | 19032 | `d6fc30b7af23c85a` |
| model-registry.json | `.project/governance/model-registry.json` | 24409 | `0ee88689a46dff6f` |
| three-project-boundary.json | `.project/governance/three-project-boundary.json` | 6444 | `1833136debe98bdd` |
| external-libraries-index.json | `.project/governance/external-libraries-index.json` | 5236 | `e9d8e0653f524906` |

## 2. 技能（skills）

- **本项目受管技能**（权威 `config/skill-provenance.yaml`）：13 项
  - `packages/client-neutral-core/skills/autonomous-ai-agents/codex/SKILL.md` — 5064 B — `5dda48acc2075b89`
  - `packages/client-neutral-core/skills/github/github-auth/SKILL.md` — 8247 B — `5a4463dc0f70b3a8`
  - `packages/client-neutral-core/skills/github/github-code-review/SKILL.md` — 7061 B — `9c45fad547ebd9a7`
  - `packages/client-neutral-core/skills/github/github-issues/SKILL.md` — 4038 B — `4a50f1606618e4b0`
  - `packages/client-neutral-core/skills/github/github-pr-workflow/SKILL.md` — 3879 B — `a359651470c607f7`
  - `packages/client-neutral-core/skills/github/github-repo-management/SKILL.md` — 3765 B — `af0da4c8b9d62935`
  - `packages/client-neutral-core/skills/model-switch/SKILL.md` — 4250 B — `37aed9558bc16be5`
  - `packages/client-neutral-core/skills/software-development/agent-workflow-fortress/SKILL.md` — 5650 B — `4fafb79ace30a62d`
  - `packages/client-neutral-core/skills/software-development/project-data-boundary/SKILL.md` — 8531 B — `405e16d3a8f6490e`
  - `packages/client-neutral-core/skills/software-development/python-testing/SKILL.md` — 12012 B — `207fe5e98f6c5459`
  - `packages/client-neutral-core/skills/software-development/requesting-code-review/SKILL.md` — 1263 B — `d506d7eddd42931d`
  - `packages/client-neutral-core/skills/software-development/sleep-mode/SKILL.md` — 7759 B — `bc42141d57ccd8b4`
  - `packages/client-neutral-core/skills/software-development/windows-development-environment/SKILL.md` — 21982 B — `2e1fc6dcdf51ee89`
- **Codex 执行器技能**（`integrations/executors/codex/skills`）：14 项
  - `workflow-assistance-evidence-verification`
  - `workflow-assistance-github-delivery`
  - `workflow-assistance-observer-delivery`
  - `workflow-assistance-open-design-integration`
  - `workflow-assistance-openhuman-integration`
  - `workflow-assistance-project-data-boundary`
  - `workflow-assistance-python-testing`
  - `workflow-assistance-safe-project-execution`
  - `workflow-assistance-self-improvement`
  - `workflow-assistance-single-writer-delivery`
  - `workflow-assistance-systematic-debugging`
  - `workflow-assistance-update-safety`
  - `workflow-assistance-verification-hardening`
  - `workflow-assistance-windows-development`
- **漂移**：1 项 → model-switch

## 3. 插件（plugins）

| id | 类型 | 上游 | 生命周期 | 安全扫描 |
|---|---|---|---|---|
| chrome-profiles | agent-plugin | anpicasso/hermes-plugin-chrome-profiles | enabled | PASSED |
| security-guidance | desktop-plugin | bundled | enabled | bundled |
| web-ddgs | desktop-plugin | bundled | enabled | bundled |
| hermes-media-studio | agent-plugin | yimisunrise/hermes-media-studio | **quarantined** | DANGEROUS (89 findings, CRITICAL persistence) |
| hermes-telegram-business | agent-plugin | NousResearch/hermes-telegram-business | **quarantined** | DANGEROUS (2 findings, CRITICAL persistence + supply_chain) |

## 4. 治理 / 配置 / 服务（目录级）

| 目录 | 子项数 |
|---|---|
| `config` | 25 |
| `governance` | 33 |
| `contracts_schemas` | 40 |
| `managed_skills` | 4 |
| `codex_executor_skills` | 14 |
| `services` | 14 |
| `apps` | 3 |
| `scripts` | 4 |
| `reports` | 9 |
| `docs_audits` | 1 |

## 5. 全局部署映射（重新部署用）

| 目标 | 源 | 通道 | 受管字段 |
|---|---|---|---|
| Hermes 技能（13） | `packages/client-neutral-core/skills/**` | `scripts/sync_hermes_workflow_assets.py`（备份后发布，同步更新 skill-provenance 哈希） | 全部受管技能 |
| Hermes SOUL/规则 | `config/SOUL.md` | 同上 | 提示层 |
| Hermes 启动器 | `bin/`（codex / hermes-npx / 守卫脚本） | 同上 | 启动器 |
| Hermes 配置字段 | 仅 `display.language`、`display.busy_input_mode` | 同上 | 其余全部 OBSERVE，不覆盖 |
| Codex 执行器技能 | `integrations/executors/codex/skills/**` | Codex 侧通道（本项目只读登记） | — |
| DSH 桌面 | `%DSH_ROOT%\DSH Desktop.exe` + `.lnk` 三字段 | 覆盖部署脚本 + `--user-data-dir` 重 pin | 保留用户数据/会话/插件/技能 |

## 6. 记忆（memory）——仅元数据

| 侧 | 路径 | 文件 | 大小 |
|---|---|---|---|
| hermes | `%LOCALAPPDATA%\hermes\memories` | MEMORY.md | 3345 |
| hermes | `%LOCALAPPDATA%\hermes\memories` | MEMORY.md.lock | 0 |
| hermes | `%LOCALAPPDATA%\hermes\memories` | USER.md | 2743 |
| hermes | `%LOCALAPPDATA%\hermes\memories` | USER.md.lock | 0 |
| dsh | `%DSH_ROOT%\.dsh\memory` | (目录，3 子项) | — |

> 记忆正文**未采集**（私有状态）。如需审计记忆内容，须由用户显式授权按文件逐项读取。
