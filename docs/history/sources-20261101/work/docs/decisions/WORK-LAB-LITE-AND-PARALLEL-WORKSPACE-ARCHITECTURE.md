# WORK-LAB Lite + Parallel Workspace 架构（2026-09-25）

**Status:** LANDED — CURRENT planning layer (GOAL §34 D)
**Authority:** `/WORK-LAB-AUTHORITY.md` (top) → this doc is a planning/architecture layer under it.
**Task:** `taskpacks/history/pre-convergence-20261019/WORK-LAB-PRODUCT-UI-CONTROL-SURFACE-TASKCARD-20260925.md` (archived 2026-10-19; originally in `taskpacks/current/`)

> This document lands the **architecture** of the WORK-LAB product direction.
> It is a planning/decision record — it does NOT build UI code and does NOT
> grant execution. Feature scope is frozen (§32); productization work proceeds
> through individually authorized task cards, one writer per task.

---

## 1. 产品方向（锁定，不重新争论）

WORK-LAB 从「控制面后台工程」推进为「轻量核心控制前端 + 可替换开源重型
Workspace + 原生 Agent 执行」的可用产品。结构：

```text
用户
 │
 ▼
WORK-LAB Lite / Control Core        ← 本轮落仓的规划层
 │  Project / Work / Agents / Approval / Context /
 │  Evidence / CI-Delivery / Software Health / Launcher
 │
 ├──────────────────────────────┐
 ▼                              ▼
开源重型 Parallel Workspace     原生 Software 入口
（可替换、桥接或启动）           （保留原生 Harness）
 ├ Orca（第一 Pilot 候选）       ├ Codex
 ├ Omnigent（机器编排层）        ├ Hermes
 ├ Argos（对照候选）            ├ DSH
 └ OpenHands Agent Canvas       ├ GitHub
                                ├ ChatGPT Web
                                └ Open Design
```

设计原则（三条铁律）：

```text
WORK-LAB 控治理、任务、上下文、证据、权限、协调。
开源 Workspace 承担终端、文件、Worktree、Agent Chat、Diff 等重交互。
原生软件保留原生 Harness / 模型 / Provider / 认证 / 推理强度 / 内部 Agent 能力。
```

## 2. 禁止重写（成熟能吸收，能桥接，能启动）

```text
WORK-LAB 不自研：IDE / Terminal / Git Client / Agent Chat /
                 文件编辑器 / 通用 Agent Runtime。
```

候选统一走外部能力摄取管线（`governance.intake`）：
`DISCOVER → CLASSIFY → NATIVE_OVERLAP → LICENSE → VERSION → PERMISSION →
DATA BOUNDARY → WINDOWS SUPPORT → INSTALL SIDE EFFECT → PILOT → EVIDENCE → DECISION`，
决策 `PROMOTE / KEEP_CANDIDATE / REJECT`。机器真值：
`.project/governance/future-candidate-registry.json`（E 落仓）。

## 3. 前端产品形态：重型信息架构 + 轻量操作体验

产品只有一个 Design System（WORK-LAB Design System：Segoe UI/Inter、
深海军蓝、电光蓝、青色辅助、4–10px 圆角、细边框、高信息密度、精确状态色、
dark/light；气质 = Windows 11 Fluent + shadcn density + Agent Operations
Console；**专业工作台，不是展示稿**），三个 surface：

```text
1. WORK-LAB Lite / Control Center   （主工作台）
2. Compact HUD                      （440×780 alwaysOnTop skipTaskbar；只回答
                                     Running / Need Action / Failed / Current
                                     Project / Current Agents / CI / Warnings）
3. Tray                             （系统托盘）
```

### 3.1 一级导航收敛到约 7 项（不再无限加一级菜单）

```text
Home / Work / Agents / Projects / Governance / Integrations / System
```

二级结构示例（Work / Governance / System 展开，见 taskcard）：

```text
Work      → Tasks / Executions / Task Packs / Delivery
Governance→ Rules & Skills / Approvals / Audit / Trust / Evidence
System    → Software / Models / Usage / Settings
```

### 3.2 Home 只回答五个问题

```text
现在谁在干什么？哪个项目？做到哪？有没有失败？有没有需要我决定的事？
```

KPI 仅：`Running / Need Action / Failed / Projects / CI / Data Quality`
（不做 KPI 展览馆）。

### 3.3 Work = 产品最重要的页面

展示 `Task / Goal / Project / Planner / Agent Routes / Execution Timeline /
Diff / Tests / CI / Receipts / Evidence / Approval / Handoff`，必须支持真实
Task ID 与 Execution ID 深链。

### 3.4 Agents = 原生能力卡（不抹平成统一 Chat Bot）

每个 Agent 展示其原生字段（Codex: model/reasoning/session/worktree/subagents/
tests/native status；Hermes: provider/model/session/skills/tools/native status；
DSH: version/install identity/trajectory/subagents/workflow/replay/native
status）。**禁止伪造不存在的字段**（字段缺失显示 UNKNOWN）。

### 3.5 Context / Evidence Inspector（右侧）

展示 `Authority / Constraints / Context / Decision / Source / Receipt /
Artifact / Evidence / Diff / Tests`，让用户看到「Agent 为什么做这个决定」
和「它根据什么完成」。**不显示私人 prompt / response body。**

## 4. 硬边界：Observer 永久只读（§8）

`apps/observer` 是严格只读投影，不得通过加按钮变写控制面。可显示
`Approval waiting / Task state / Software drift / Evidence / Rules /
Integration`，但**不能**自己 `approve / reject / cancel / retry / apply /
rollback / install / delete / commit / push / merge`。

## 5. Control Surface = 授权写操作薄壳（§9，本轮只落规划）

若建立 `apps/control-surface/`，**只建薄壳**，不得复制全部 Observer
frontend。优先抽取/复用：`design tokens / shared components / status
semantics / navigation primitives / icons / truth rendering / snapshot
types`。定位：

```text
Observer       = read-only projection
Control Surface = authorized operations（经现有 Authority/Task/Approval/Receipt
                 服务执行）
```

Control Surface **当前真实目录尚不存在**；本轮只把路线放进 CURRENT 规划，
不建 UI 代码（§32 冻结特性范围）。

## 6. Parallel Workspace 第一优先 = Orca Pilot（§12）

理由：Windows 成熟度高、开源、Codex 支持强、Worktree/Terminal/File/Diff/
多 Agent、用户自己的订阅、可省掉 WORK-LAB 大量 IDE 开发。

第一轮 Pilot 只做（**不改 Orca 内核**）：

```text
WORK-LAB → Open Workspace → Orca → current project/worktree
          → Codex → git/test/evidence → WORK-LAB readback
```

验证四件：`project launch / worktree identity / task correlation /
exit/readback`。任务卡：`taskpacks/history/pre-convergence-20261019/ORCA-PILOT-TASK-CARD-20260925.md`（F 落仓；2026-10-19 归档）。

定位对照：Omnigent = 未来机器编排层（DEFERRED）；Argos = ACP/MCP/Skills
多模型桌面对照组（DEFERRED）；OpenHands Agent Canvas = 平行工作台候选
（DEFERRED）。任何候选都不是永久依赖。

## 7. 原生 Software Launcher（§15）

即使使用 Orca，也不能把全部软件塞进去。Launcher 支持：
`Open in Orca / Open native Codex / Open native Hermes / Open native DSH /
Open GitHub / Open ChatGPT Web / Open Open Design`。

核心原则：**统一入口 ≠ 统一运行壳。**

## 8. 本轮（§34）边界

本轮交付：C（前端路线进 CURRENT 规划）+ D（本架构落仓）+ E（Future
Candidate Registry 落仓）+ F（Orca Pilot 独立任务卡）。**不写前端/Control
Surface 代码，不安装 Orca/Omnigent/OpenViking**（§34 明确「本轮不是要求一次
安装」）。产品化开发在后续 individually-authorized task cards 推进。

## 9. 验收标准映射（§32）

```text
Governance: Authority single / Task register single / machine SSOT single /
            history non-normative
Runtime    : Codex/Hermes/DSH native / no provider-model override
Frontend   : Home/Work/Agents/Projects/Governance/Integrations/System/
             Compact HUD usable（逐页用户落点）
Execution  : Task → Agent → Execution → Verify → Evidence
Transparency: UNKNOWN stays UNKNOWN / SKIPPED != PASS / CI != desktop /
              plan != write / callback != readback
External WS: 至少一个成熟平行工作台完成真实 Pilot（Orca）
Recovery   : 新会话/执行器能恢复 goal/constraints/authority/task/revision/
             owner/known failures/evidence/next action
Install    : discover before download / update != relocation / no silent
             C-drive fallback
```

每个后台能力必须有用户落点（§27）：`在哪看到 / 如何理解 / 如何操作 /
如何确认成功 / 失败在哪显示 / 证据在哪查看`。没有 UI 落点 =
`backend_complete != product_complete`。
