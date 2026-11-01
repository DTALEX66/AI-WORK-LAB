# 通用多 Agent 并行执行框架（2026-08-23）

> 用户需求：**一套规则同时适配部署到所有软件**（Hermes/Codex/DSH 及未来软件），
> 支持 ①单软件项目内多实例并行 ②多软件同项目分任务并行——分离写、审计、合并。
> 状态：**提案，未部署**。WORK-LAB 作为全局工作流负责方产出并部署此规则。

## 1. 核心模型（一条流程，适用于所有软件 + 所有项目）

```text
任务分片 → 并行执行（独立副本）→ 审计 → 合并
     │            │                    │       │
 拆成独立单元  每个软件/实例在      CI/质量   队列/评审
 (模块/路径)   自己的 worktree     门禁     顺序落地
              同时写不同分片
```

## 2. 并行能力（每个软件通用）

- **每个软件**（Codex / Hermes / DSH / 未来软件）都支持：一个项目内多实例并行
- 规则软件无关——同一套 R1-R5 部署到所有软件

## 3. 两种并行场景（同一套规则）

### 场景 A：单软件项目内多实例并行（Codex 一个项目）

```text
Codex 项目 X（一个仓库）
├── 任务1 → worktree-A（codex-task1）   并行写
├── 任务2 → worktree-B（codex-task2）   ──→ 审计（CI/质量）──→ 队列合并
└── 任务3 → worktree-C（codex-task3）

= Codex 内部自己拆任务，多实例同时写不同分片，最后统一审计合并
```

### 场景 B：多软件同项目协作（Codex + Hermes + DSH 写同一项目）

```text
项目 Y（一个仓库）
├── Codex  认领 模块A/任务组1 → worktree-codex    ─┐
├── Hermes 认领 模块B/任务组2 → worktree-hermes   ──→ 审计 ──→ 合并
└── DSH    认领 模块C/任务组3 → worktree-dsh      ─┘

= 每个软件认领自己的任务分片，各自 worktree 并行写，最后审计合并
```

## 3. 规则内容（一套，部署所有软件）

### R1 任务分片
- 项目启动时把任务拆成独立单元（按模块/路径/依赖边界）
- 每个分片可独立完成、独立测试、独立合并

### R2 认领（advisory）
- 软件写前认领分片：`.workflow/claims/<project>.json`（path/owner/status）
- 认领是君子协定（不强制锁）；同路径重叠才排队

### R3 独立工作副本（worktree）
- 每个软件/实例一个 worktree + 分支（`<owner>-<task>`）
- 互不干扰；不共享 checkout

### R4 审计（合并前）
- 每个分片必须过：本地测试 + CI（如果项目有）+ 质量门
- 审计通过才允许入队（不通过的退回重写）

### R5 合并（队列）
- 审计通过的分片进落地队列（mainline 式：CI 绿后顺序合并）
- 合并自动化，不依赖 agent 谈判；冲突在队列内消解

## 4. WORK-LAB 的角色（全局工作流负责方）

- **规则定义**：R1-R5 一套规则（软件无关、项目无关）
- **工具提供**：认领脚本 / worktree 管理 / 合并队列（放 10-workflow/workflow-assistance/scripts）
- **部署**：Hermes（hook/skill）/ Codex（AGENTS.md 引用）/ DSH（工作流模块）引用同一套
- **审计**：落地前审计（质量门 + CI）

## 5. 与现状对比

| 维度 | 现在（单写者+只读） | 通用框架 |
|---|---|---|
| 规则范围 | WORK-LAB 仓库 | 任意项目 + 所有软件 |
| 并行 | 全局一次一个写者 | 分片级并行（单/多软件）|
| 落地 | 抢 main | 审计 → 队列合并 |
| Codex 单项目内 | 串行（一任务一写）| 多实例并行 |
| 多软件同项目 | 只读+轮流 | 分任务并行 |

## 6. 实施（待批准）

1. 建工具：claims 脚本 + worktree 管理器 + 合并队列（workflow-assistance）
2. 规则文档：AGENTS.md 全局规则更新（R1-R5 通用）
3. 部署：Hermes skill / Codex 引用 / DSH 工作流模块引用同一套
4. 试点：Codex 项目内多实例并行 → 验证 → 多软件同项目 → 全量

## 7. 风险

- 认领 advisory（依赖自觉——多软件信任模型，WORK-LAB 作为治理方监督）
- 审计必须严格（否则合并坏代码）——CI 已有基础
- worktree 磁盘开销（按分片数量，每个 1-2GB）
- 先试点不部署全局
## 8. 明确：每个软件都支持一个项目多并行

- Codex 一个项目内：多实例并行（任务1/2/3 → 各自 worktree）✅
- Hermes 一个项目内：多实例并行 ✅
- DSH 一个项目内：多实例并行 ✅
- 任意软件组合：多软件同项目分任务并行 ✅
- 规则同一套（R1-R5），能力人人有——不是某个软件的特权
## 9. 行业方案调研（2026-08-23 补充）

| 方案 | 特点 | 对应 R1-R5 |
|---|---|---|
| **pact**（zekariasasaminew）| 多 agent 编排 CLI：隔离（Claude/Codex/Copilot）worktree + 依赖准备 + **文件认领协调** + 自动合并 | R2+R3+R5 一站式 |
| **cas**（codingagentsystem）| agent 协调：持久记忆/任务/规则/skills——让 agents 真正配合 | R1+R4 |
| **multi-agent-orchestrator-skill**（hyw007726）| 并行 agent：worktree 隔离 + scoped prompts + validation + 重启 + 多 CLI 支持 | R3+R4 |
| **agent-teamflow**（lkim0402）| Claude skills：并行 agents + 共享仓库 + 无碰撞 | R2+R3 |
| **mainline**（recallnet）| worktree 落地串行化队列（防 clobber main）| R5 |
| **claim-plane**（SkeinRank）| 可验证 AI 工程控制面 | R2 强化 |
| **OpenAI codex #13554** | 实体级合并（entity-level merge）——并行编辑的合并方案 | R5 深化 |
| gwtree / dmux / Neon / Baton 指南 | worktree + tmux 并行 agents 模式 | R3 实践 |

## 10. 结论（工具化路径）

- **worktree 隔离 + 文件认领 + 自动合并** = 行业共识（pact/cas/orchestrator 都验证）
- WORK-LAB 框架 R1-R5 与行业一致；落地可借鉴/集成 pact（多软件）+ cas（协调层）
- 单软件多实例：worktree 每实例一个 + 实体级合并（codex #13554 思路）
- 一套规则部署所有软件 = pact 的 CLI 编排 + 各软件 skill/引用

## 11. 落地建议（更新）

1. 评估集成 **pact**（多软件 worktree+认领+合并 现成 CLI）或自建同等能力
2. 协调层参考 **cas**（任务分片/状态/记忆）
3. 单软件多实例：实例级 worktree + 实体级合并（借鉴 codex #13554）
4. 审计 = 现有质量门 + CI（R4 已有基础）
5. 试点：Codex 项目内多实例 → 多软件（pact 编排）→ 全量部署