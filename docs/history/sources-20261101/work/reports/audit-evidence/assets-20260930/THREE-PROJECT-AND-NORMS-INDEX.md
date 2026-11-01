# 三项目边界 · 规范规则 · 中立索引（2026-09-30）

生成（UTC）：2026-09-30T14:58:27Z

本文件是**只读索引**：只记录路径、定位、git 引用与文件摘要；不复制权威正文，不新建平行账本。
`ArcheAxis-Knowledge-OS` 与 `DESIGN-LAB` **未被修改**（仅元数据探测）。

## 1. 三个项目与各自权威

| 项目 | 目录 | 远端仓库 | 当前分支 | HEAD | 定位（来自 three-project-boundary.json） |
|---|---|---|---|---|---|
| **WORK-LAB** | `%PROJECTS_ROOT%/WORK-LAB` | `git@github.com:DTALEX66/WORK-LAB.git` | `audit/client-asset-inventory-20260930` | `049cf406a66d` | 控制面：谁 / 何时 / 什么权限 / 通过什么软件 / 如何执行 / 如何验证 / 如何恢复（跨项目、跨软件、跨运行时） |
| **ArcheAxis-Knowledge-OS** | `%PROJECTS_ROOT%/ArcheAxis-Knowledge-OS` | `git@github.com:DTALEX66/ArcheAxis-Knowledge-OS.git` | `codex/Audit` | `43c2cafa1bfe` | 知识面：长期记忆、学习、蒸馏、知识真值、分类、晋升、存储、召回 |
| **DESIGN-LAB** | `%PROJECTS_ROOT%/DESIGN-LAB` | `git@github.com:DTALEX66/DESIGN-LAB.git` | `feat/ui-commercial-workbench-20260930` | `0fbb67439755` | 设计面：设计代理、设计软件执行、设计资产、生成策略、质量体系、Adobe 领域逻辑 |

> 三仓**各自独立**：独立仓库、独立业务数据库。允许通过 Schema / API / Manifest / Adapter / Receipt / Candidate 协作，并共享外置模型与工具资源。

## 2. 所有权边界与禁止新所有者

权威：`.project/governance/three-project-boundary.json`（gate `three-project-boundary`，验证器 `scripts/ci/verify_three_project_boundary.py`）

| 边界项 | WORK-LAB 保留 | 移交/忽略 |
|---|---|---|
| MEMORY_BACKEND（`services/memory`） | 会话隐私边界、上下文导出/胶囊、记忆查询契约、ArcheAxis 客户端与交接、溯源、权限门、回执 | 保留/召回/反思、长期记忆存储、记忆提供者、仓库/文档导入、知识记录与存储、记忆晋升 → **ArcheAxis** |
| KNOWLEDGE_TRUTH（`services/knowledge`） | 知识导出守卫（涉密/原始会话/原始日志/脚本记录、必须有溯源、证据等级、来源身份、导出许可、载荷完整性） | 知识分类与接纳、已验证经验、架构知识、晋升决策、长期知识状态 → **ArcheAxis**（WORK-LAB 只产出 `KnowledgeCandidate`，不产出知识真值） |
| KNOWLEDGE_STAGING（`knowledge-staging`） | — | 根级目录属**历史遗留**，需收敛出根 |
| EVOLUTION（`services/evolution`） | M1 提示/M2 技能/M3 工作流/M4 工具运行时/M5 治理 变更 + 沙箱、安全评估、独立审批、回滚、追踪、回执 | 持续学习、知识演化、记忆整合、人类学习、长期认知成长 → **ArcheAxis** |
| ARCHIVE_90（`90-archive`） | 根目录仅保留 `BOUNDARY.md` 门禁标记（`CONVERGED_20260923`） | 第二套历史系统 → 收敛至 `docs/history` |
| DESIGN_LAB（`config/adapter-registry.json` 的 open-design 适配器） | Open Design **客户端**：规则、技能、插件、能力发现、工作流策略、适配器、软件状态（`MANAGE`，`apply_supported=false`） | 设计知识/提示真值/资产/生成策略/质量体系/Adobe 领域逻辑（**IGNORE**，属 DESIGN-LAB） |

**禁止出现的新所有者**：把 `services/memory` 做成完整记忆系统；把 `services/knowledge` 做成晋升真值所有者；`knowledge-staging` 作为根级活动目录；`90-archive` 作为根级活动目录；第二个 Agent 运行时；第二套配置治理系统；第二个 Task Ledger；第二个用量/成本真值引擎。

> 关键身份区分：**Open Design 客户端 ≠ DESIGN-LAB 项目**（两个不同身份）。

## 3. 规范与规则（本项目权威面，含摘要哈希）

| 优先级 | 文件 | 字节 | sha256(前16) |
|---|---|---|---|
| — | `AGENTS.md` | 9879 | `e5cb346ea56e6e1b` |
| — | `WORK-LAB-AUTHORITY.md` | 10777 | `0938ff2452da5c5a` |
| — | `docs/decisions/PROJECT_POSITIONING.md` | 5243 | `ab89d055e04fca5c` |
| — | `docs/decisions/global-execution-standard.md` | 6320 | `6a6fdd30a1fab839` |
| — | `docs/decisions/LESSONS_LEARNED.md` | 9516 | `4e0bdd64c3ba0105` |
| — | `.project/governance/project-authority-index.json` | 2334 | `448e994e41309ba1` |
| — | `.project/governance/taskpack-authority-index.json` | 13998 | `fa88e13b82d7dd59` |
| — | `.project/governance/config-authority-index.json` | 6525 | `eea9f10c34b384e2` |
| — | `.project/governance/module-ownership.json` | 522 | `db866bab3cc01e97` |
| — | `.project/governance/projects.json` | 1199 | `10c4d141e14aa4c8` |
| — | `.project/governance/project-data-boundary.json` | 3203 | `54a0e5c4c03a6f4c` |
| — | `.project/governance/three-project-boundary.json` | 6444 | `1833136debe98bdd` |
| — | `config/config-ownership.json` | 21535 | `d799c9925d32b1e1` |
| — | `config/global-agent-policy.yaml` | 7172 | `928a9989f41b1808` |

**读取顺序（强制 bootstrap，来自 `WORK-LAB-AUTHORITY.md`）**：

```text
1 解析 live origin/main 的 exact commit/tree
2 WORK-LAB-AUTHORITY.md
3 .project/governance/project-authority-index.json
4 AGENTS.md
5 taskpack-authority-index.json 指向的 CURRENT TaskPack
6 taskpacks/current/OPEN-TASK-REGISTER.md
7 范围内机器合同
8 仅在需要时点名查阅历史记录
```

**优先级（precedence）**：最新用户明确决定 > `WORK-LAB-AUTHORITY.md` > `project-authority-index.json` > 当前 taskpack / open register > `AGENTS.md` + 范围内机器权威 > 当前 exact-SHA 代码与 CI/运行回读 > 历史记录（冻结、非规范）。

## 4. 决策与规范文档清单（docs/decisions/）

| 文件 | 字节 | sha256(前16) |
|---|---|---|
| `docs/decisions/ARCHEAXIS_API_CONTRACT_SURVEY.md` | 2537 | `4227ba78d5cd7872` |
| `docs/decisions/CONTROL_PLANE_CONVERGENCE.md` | 6653 | `0c608f54c2a521b5` |
| `docs/decisions/DSH_PLUGIN_EVALUATION.md` | 2923 | `064dd55aa3bee4a7` |
| `docs/decisions/ECOSYSTEM_AUDIT_COMPARISON.md` | 5048 | `2cdde7ff93a58a7a` |
| `docs/decisions/global-execution-standard.md` | 6320 | `6a6fdd30a1fab839` |
| `docs/decisions/instruction-precedence.md` | 668 | `af4c55f54dcc2c8b` |
| `docs/decisions/language-architecture.md` | 4363 | `751ceeefd0de502d` |
| `docs/decisions/LESSONS_LEARNED.md` | 9516 | `4e0bdd64c3ba0105` |
| `docs/decisions/PROJECT_POSITIONING.md` | 5243 | `ab89d055e04fca5c` |
| `docs/decisions/README.md` | 247 | `e99e5380770a2322` |
| `docs/decisions/REVERSE_ARCHIVE_TEMPLATE.md` | 2190 | `6b0fd36a56d11bbd` |
| `docs/decisions/SUBTRACTION_AUDIT_2026-08-18.md` | 2329 | `4565e033103a6429` |
| `docs/decisions/THREE_PROJECT_FEDERATION_CONTRACT.md` | 1865 | `b409f322686633e5` |
| `docs/decisions/THREE_PROJECT_FUTURE_BLUEPRINT_ANALYSIS.md` | 4783 | `598d07da4c62f5a6` |
| `docs/decisions/THREE_PROJECT_LAYERING_AUDIT.md` | 7932 | `57541c650b33e0bc` |
| `docs/decisions/THREE_PROJECT_LAYERING_DECISION.md` | 4737 | `db0d44163e33ec8e` |
| `docs/decisions/TP_20260819_FEDERATION_ANALYSIS.md` | 3576 | `80c3a32a58880993` |
| `docs/decisions/WORK-LAB-LITE-AND-PARALLEL-WORKSPACE-ARCHITECTURE.md` | 8438 | `8c97932361a29c75` |

## 5. 与清点/清理目的的关系

- 需要清理或重部署的任何资产，都必须先落在**三者之一**的所有权内；跨边界搬迁需按 §2 的 seam/gate 走 `verify_three_project_boundary`。
- 记忆/知识类候选（Hermes `memories/`、DSH `memory/`、`services/memory`）**不得**在 WORK-LAB 内被当成长期记忆真值处理；真值属 ArcheAxis。
- 设计类资产（Open Design 客户端的设计能力面）在本项目内为 **IGNORE**。
