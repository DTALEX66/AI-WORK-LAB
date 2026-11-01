# 全局工作流 · 部署回读 · 三项目规范规则索引（2026-09-30）

生成（UTC）：2026-09-30T15:05:34Z

只读索引：不复制权威正文、不新建平行账本。凭据值与记忆/会话正文**未被读取**。

## 1. 全局策略 SSOT（唯一的跨软件语义源）

- 文件：`config/global-agent-policy.yaml`（7172 B，sha256 `928a9989f41b1808…`，声明 revision 2）
- 机器合同：`packages/contracts/schemas/workflow/global-agent-policy.schema.json`
- 语义域 20 个：ownership, communication, execution, authority_discovery, authorization, task_grant, workspace_boundary, protected_storage, credentials, session_privacy, network, git_safety, dependency_policy, evidence_semantics, verification, parallelism, skills, model_neutrality, tool_truth, historical_record_policy
- 所有权：`USER_OVERLAY / MANAGE`，明确 **不是**第二权威、第二配置治理、第二账本、第二适配器登记表。
- 渲染契约：渲染器读取「中性核心 + 该软件扩展」→ 产出原生资产 + `ProjectionLossReport`（NATIVE_ENFORCED / NATIVE_GUIDANCE / WORKFLOW_GUARD / OBSERVE_ONLY / UNSUPPORTED）。

## 2. 每客户端投影矩阵（权威：`config/adapter-registry.json` → `policy_projection`）

| 客户端 | supported | projection_mode | 成熟度 | 原生渲染器 | 扩展文件 |
|---|---|---|---|---|---|
| `hermes` | True | `managed-overlay` | **READBACK_VERIFIED** | `integrations/executors/hermes/sync_hermes_workflow_assets.py` | `integrations/executors/hermes/hermes-policy-extension.yaml` |
| `codex` | True | `managed-block` | **READBACK_VERIFIED** | `integrations/executors/codex/sync_codex_global_assets.py` | `integrations/executors/codex/codex-policy-extension.yaml` |
| `cc-switch` | True | `observe-only` | **OBSERVE_ONLY** | `—` | `—` |
| `github` | True | `git-delivery-projection` | **PLAN_SUPPORTED** | `—` | `—` |
| `openhuman` | False | `observe-only` | **OBSERVE_ONLY** | `—` | `—` |
| `open-design` | False | `observe-only` | **OBSERVE_ONLY** | `—` | `—` |
| `deepseek-harness` | True | `observe-plan` | **PLAN_SUPPORTED** | `integrations/executors/dsh/dsh_adapter.py` | `—` |
| `cursor` | False | `manifest-only` | **OBSERVE_ONLY** | `—` | `—` |
| `claude-code` | False | `manifest-only` | **OBSERVE_ONLY** | `—` | `—` |
| `workbuddy` | False | `manifest-only` | **OBSERVE_ONLY** | `—` | `—` |

**结论**：10 个客户端的投影模式与 19 个语义域的能力状态**全部显式声明**，无空缺；2 个客户端（hermes / codex）达到 `READBACK_VERIFIED`（具备 detect/plan/apply/readback/rollback/drift 六项）；其余 8 个按声明为 OBSERVE/PLAN/MANIFEST（`capability_coverage_complete: true`），**属设计内状态而非缺口**。

> DSH（`deepseek-harness`）无扩展文件是**声明内**的：`observe-plan` / `PLAN_SUPPORTED`，须待「稳定官方原生接口 + 所有权定义 + 隔离 fixture + readback + rollback + 负向测试」齐备后才允许 apply。

## 2.2 机器可读矩阵（`global-workflow-coverage.json → client_projection_matrix`）

| client | mode | apply | maturity | 六项能力(detect/plan/apply/readback/rollback/drift) | 19 域状态分布 | 扩展/渲染器 |
|---|---|---|---|---|---|---|
| `hermes` | managed-overlay | True | READBACK_VERIFIED | `✓✓✓✓✓✓` | NATIVE_ENFORCED×1, NATIVE_GUIDANCE×9, OBSERVE_ONLY×2, WORKFLOW_GUARD×7 | integrations/executors/hermes/hermes-policy-extension.yaml |
| `codex` | managed-block | True | READBACK_VERIFIED | `✓✓✓✓✓✓` | NATIVE_ENFORCED×1, NATIVE_GUIDANCE×9, OBSERVE_ONLY×2, WORKFLOW_GUARD×7 | integrations/executors/codex/codex-policy-extension.yaml |
| `cc-switch` | observe-only | False | OBSERVE_ONLY | `✓✗✗✗✗✗` | UNSUPPORTED×19 | — |
| `github` | git-delivery-projection | False | PLAN_SUPPORTED | `✓✓✗✗✗✗` | UNSUPPORTED×19 | — |
| `openhuman` | observe-only | False | OBSERVE_ONLY | `✓✗✗✗✗✗` | UNSUPPORTED×19 | — |
| `open-design` | observe-only | False | OBSERVE_ONLY | `✓✗✗✗✗✗` | UNSUPPORTED×19 | — |
| `deepseek-harness` | observe-plan | False | PLAN_SUPPORTED | `✓✓✗✗✗✗` | UNSUPPORTED×19 | integrations/executors/dsh/dsh_adapter.py |
| `cursor` | manifest-only | False | OBSERVE_ONLY | `✓✗✗✗✗✗` | UNSUPPORTED×19 | — |
| `claude-code` | manifest-only | False | OBSERVE_ONLY | `✓✗✗✗✗✗` | UNSUPPORTED×19 | — |
| `workbuddy` | manifest-only | False | OBSERVE_ONLY | `✓✗✗✗✗✗` | UNSUPPORTED×19 | — |

> 判据：`apply` 为 ✓ 的客户端必须六项能力齐备 + **原生回读证据**；其余只能停在 OBSERVE/PLAN/MANIFEST，且必须显式声明 `capability_coverage_complete`。`19 域状态分布` 取自 `capability_states`（NATIVE_ENFORCED / NATIVE_GUIDANCE / WORKFLOW_GUARD / OBSERVE_ONLY / UNSUPPORTED）。

## 3. 部署回读（仓库源 vs 原生 live 目标）

### 3.1 Hermes 受管技能：13 项 → 一致 **12** / 不一致 **1** / 缺失 **0**

| 技能 | 仓库源 sha16 | live sha16 | 状态 |
|---|---|---|---|
| `autonomous-ai-agents/codex/SKILL.md` | `5dda48acc2075b89` | `5dda48acc2075b89` | MATCH |
| `github/github-auth/SKILL.md` | `5a4463dc0f70b3a8` | `5a4463dc0f70b3a8` | MATCH |
| `github/github-code-review/SKILL.md` | `9c45fad547ebd9a7` | `9c45fad547ebd9a7` | MATCH |
| `github/github-issues/SKILL.md` | `4a50f1606618e4b0` | `4a50f1606618e4b0` | MATCH |
| `github/github-pr-workflow/SKILL.md` | `a359651470c607f7` | `a359651470c607f7` | MATCH |
| `github/github-repo-management/SKILL.md` | `af0da4c8b9d62935` | `af0da4c8b9d62935` | MATCH |
| `model-switch/SKILL.md` | `37aed9558bc16be5` | `37aed9558bc16be5` | MATCH |
| `software-development/agent-workflow-fortress/SKILL.md` | `4fafb79ace30a62d` | `4fafb79ace30a62d` | MATCH |
| `software-development/project-data-boundary/SKILL.md` | `405e16d3a8f6490e` | `405e16d3a8f6490e` | MATCH |
| `software-development/python-testing/SKILL.md` | `207fe5e98f6c5459` | `207fe5e98f6c5459` | MATCH |
| `software-development/requesting-code-review/SKILL.md` | `d506d7eddd42931d` | `d506d7eddd42931d` | MATCH |
| `software-development/sleep-mode/SKILL.md` | `bc42141d57ccd8b4` | `bc42141d57ccd8b4` | MATCH |
| `software-development/windows-development-environment/SKILL.md` | `2e1fc6dcdf51ee89` | `39bbb61a723914d5` | DIFFERS |

- Hermes `SOUL.md`：仓库 `config/SOUL.md` 与 live `%LOCALAPPDATA%/hermes/SOUL.md` **哈希一致**（9da0bd4884af9fdb）→ 已同步。

### 3.2 Codex 原生目标（扩展声明的 4 个）

| 目标 | 存在 | 字节 | sha16 | 受管标记 |
|---|---|---|---|---|
| `AGENTS.md` | True | 16805 | `cf73c8e58ba8fbf9` | False |
| `config.toml` | True | 6912 | `72fd5f7b31baa610` | True |
| `rules/workflow-assistance.rules` | True | 5908 | `89fe3ad055c76092` | False |
| `skills/workflow-assistance-*` | 目录存在=True | — | — | live 匹配目录数 **0** |

## 4. 覆盖判定：完成了吗？

| 层面 | 状态 | 依据 |
|---|---|---|
| 全局策略 SSOT + 机器合同 | **完整** | `global-agent-policy.yaml` rev2 + `global-agent-policy.schema.json` |
| 客户端投影声明（10 客户端 × 19 域） | **完整** | `adapter-registry.json → policy_projection.capability_states` |
| 项目自身规范/规则（WORK-LAB） | **完整** | 14 规范文件 + 18 决策文档，逐一哈希 |
| 另两项目自身规范/规则 | **已索引** | ArcheAxis：`AGENTS.md` + `DIRECTORY_AUTHORITY.yaml`；DESIGN-LAB：`AGENTS.md` + `AUTHORITY.md`（结构 + 摘要） |
| 原生**已渲染资产**（hermes / codex） | **不一致（2 处）** | hermes 13 技能中 1 项 live≠仓库；codex `AGENTS.md` 无受管 overlay 块、`skills/workflow-assistance-*` live 为 0 |
| 登记表与 live 的一致 | **陈旧 3 处** | `skill-provenance.yaml`（windows-development / model-switch 记录）、`skills-inventory.json`（6/14）、`plugin-inventory.json`（缺 revision） |

**逐项缺口（可判定）**：

1. G1 codex：登记称 `CODEX_HOME/AGENTS.md` 有 Managed BEGIN/END 块（maturity=READBACK_VERIFIED），live 实测**无任何受管块标记**（`WORKFLOW-ASSISTANCE MANAGED` 命中 0；`WORK-LAB` 命中 0）。
2. G2 codex：扩展声明的 `skills/workflow-assistance-*` 原生目标，live `%USERPROFILE%/.codex/skills/` 下匹配目录数 **0**。
3. G3 hermes：`windows-development-environment` live sha `39bbb61a…` ≠ 仓库源 `2e1fc6dc…`（live 23,825 B vs 仓库 21,982 B）→ 部署落后或已被本地改写。
4. G4 记录漂移：`skill-provenance.yaml` 的 `model-switch.live_sha256=0a02c1fc…` 与实际（37aed955…）不符；`windows-development-environment` 的 source/live 记录仍等于旧值 2e1fc6dc…。

> 判定纪律：以上 G1–G4 均为**登记/声明与 live 的不一致**，不等于「产品不可用」。修复须经被授权通道（`sync_hermes_workflow_assets.py` / `sync_codex_global_assets.py`）并做原生回读；**本包未执行任何写入**。

## 5. 三项目自身的规范/规则（结构索引，只读）

### WORK-LAB

- 目录：`%PROJECTS_ROOT%/WORK-LAB`｜远端 `git@github.com:DTALEX66/WORK-LAB.git`｜分支 `audit/client-asset-inventory-20260930`｜HEAD `de04206cfd37`
- **规范/规则面 14 项**（角色 + 字节 + sha16 + 关键结构）：

| 文件 | 角色 | 字节 | sha16 |
|---|---|---|---|
| `WORK-LAB-AUTHORITY.md` | top_human_authority | 10777 | `0938ff2452da5c5a` |
| `AGENTS.md` | execution_rules | 9879 | `e5cb346ea56e6e1b` |
| `docs/decisions/PROJECT_POSITIONING.md` | positioning | 5243 | `ab89d055e04fca5c` |
| `docs/decisions/global-execution-standard.md` | execution_standard | 6320 | `6a6fdd30a1fab839` |
| `docs/decisions/LESSONS_LEARNED.md` | lessons | 9516 | `4e0bdd64c3ba0105` |
| `.project/governance/project-authority-index.json` | machine_authority_root | 2334 | `448e994e41309ba1` |
| `.project/governance/taskpack-authority-index.json` | taskpack_authority | 13998 | `fa88e13b82d7dd59` |
| `.project/governance/config-authority-index.json` | config_authority | 6525 | `eea9f10c34b384e2` |
| `.project/governance/module-ownership.json` | module_ownership | 522 | `db866bab3cc01e97` |
| `.project/governance/projects.json` | project_roster | 1199 | `10c4d141e14aa4c8` |
| `.project/governance/project-data-boundary.json` | data_boundary | 3203 | `54a0e5c4c03a6f4c` |
| `.project/governance/three-project-boundary.json` | three_project_boundary | 6444 | `1833136debe98bdd` |
| `config/config-ownership.json` | config_ownership | 21535 | `d799c9925d32b1e1` |
| `config/global-agent-policy.yaml` | global_workflow_policy_ssot | 7172 | `928a9989f41b1808` |

- 决策记录 `docs/decisions/`：**18 篇**（`ARCHEAXIS_API_CONTRACT_SURVEY.md, CONTROL_PLANE_CONVERGENCE.md, DSH_PLUGIN_EVALUATION.md, ECOSYSTEM_AUDIT_COMPARISON.md, LESSONS_LEARNED.md, PROJECT_POSITIONING.md` …）
- 强制 bootstrap 顺序（8 步）与优先级（7 级）见 `AGENTS.md`；机器校验器 `scripts/ci/verify_project_authority_reference.py`。

### ArcheAxis-Knowledge-OS

- 目录：`%PROJECTS_ROOT%/ArcheAxis-Knowledge-OS`｜远端 `git@github.com:DTALEX66/ArcheAxis-Knowledge-OS.git`｜分支 `codex/Audit`｜HEAD `43c2cafa1bfe`
- 顶层权威类文件：`AGENTS.md`（10132 B，`dbaa61d05d5d0134`）；`DIRECTORY_AUTHORITY.yaml`（20601 B，`310096407363c3cb`）；`README.md`（25189 B，`9ee45ef082ac7e34`）
- 规则规范面：`AGENTS.md`（10132 B）；`DIRECTORY_AUTHORITY.yaml`（20601 B）；`README.md`（25189 B）；`docs/decisions/`（5 项）；`config/`（15 项）

### DESIGN-LAB

- 目录：`%PROJECTS_ROOT%/DESIGN-LAB`｜远端 `git@github.com:DTALEX66/DESIGN-LAB.git`｜分支 `feat/ui-commercial-workbench-20260930`｜HEAD `0fbb67439755`
- 顶层权威类文件：`AGENTS.md`（10055 B，`7531838c75adb665`）；`AUTHORITY.md`（15036 B，`7b29d3ea90122b74`）；`README.md`（6257 B，`5b1ba5b0f383699d`）
- 规则规范面：`AGENTS.md`（10055 B）；`AUTHORITY.md`（15036 B）；`README.md`（6257 B）；`docs/decisions/`（25 项）；`.project/governance/`（6 项）

