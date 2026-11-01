# WORK-LAB PRODUCT UI / CONTROL SURFACE — TASK CARD（2026-09-25）

**Task ID:** `WORK-LAB-PRODUCT-UI-CONTROL-SURFACE-TASKCARD-20260925`
**Status:** PLANNED-ENTERED-CURRENT — the frontend is now the main product
line. This card enters the roadmap into the CURRENT planning layer; it does
NOT authorize writing UI code or installing anything (feature scope frozen §32).
**Authority:** `/WORK-LAB-AUTHORITY.md` → taskpack → this card.
**Architecture:** `docs/decisions/WORK-LAB-LITE-AND-PARALLEL-WORKSPACE-ARCHITECTURE.md` (D 落仓)
**Future candidates:** `.project/governance/future-candidate-registry.json` (E 落仓)

## Supersession note (2026-10-07) — 授权状态已变，原文保留不删

本卡 Status 段的「does NOT authorize writing UI code or installing anything」在 2026-10-07 被 owner 明确
指令更新（先「按照 WORKLAB UI 提示词 开始执行」，后「按照提示词任务包推进 / 将新 UI 任务并入目标」）。
执行授权现由 `WORK-LAB-UI-PROMPT-PACK-EXECUTION-TASKCARD-20261007.md` 承载；本卡的路线登记内容、边界与
feature-scope 说明仍有效，但**不再构成"不许写 UI 码"的阻碍**。两条不变：跨项目边界与单写者规则照旧；
UI 代码本轮仍**不提交、不推送、不开 PR、不合并**（owner 明令）。

## Why this card exists

前端不再视为 Observer 的小修补项（GOAL §6 P1-A）。它正式成为 WORK-LAB 的
主产品线，并作为独立产品任务进入 CURRENT 规划。本轮只**登记路线**，不动
UI 代码。

## What already exists (verify & reuse — 禁止另建)

`apps/observer/frontend` 已经有：React 18 / TypeScript / Vite / Tailwind /
Lucide / Recharts / Tauri / Design Tokens / 15 个 View / Full / Compact /
Dark / Light / Sidebar / Command Palette / 状态组件 / Empty / Unknown /
SSE / Snapshot / Software identity / Audit / Rules / Approvals /
Integrations / Task Packs。

**全部复用。** 禁止另建第二 Task Ledger / 第二 Evidence Store / 第二
Config Authority / 第二 Context Authority / 第二 Agent Runtime / 第二
Usage-Cost truth engine / 第二 CURRENT。

## Roadmap slices (individually authorized, one writer each)

| 卡 | 范围 | 用户落点 | 验收 |
|---|---|---|---|
| P1-01 | 前端 IA 重构：15 lane → 7 一级入口（Home/Work/Agents/Projects/Governance/Integrations/System） | 一级导航收敛 | 7 项一级导航 + 二级结构可达 |
| P1-02 | Work / Execution 成为主工作面（真实 Task ID / Execution ID 深链） | Work 页 | 深链直达任务/执行 |
| P1-03 | Agent 原生能力卡（Codex/Hermes/DSH 原生字段，缺失=UNKNOWN） | Agents 页 | 原生字段卡，无幻影 KPI |
| P1-04 | Context / Evidence Inspector（右侧；不显示私人 prompt/response body） | Inspector | 决定/证据可追溯 |
| P1-05 | Compact HUD 收敛（440×780 alwaysOnTop skipTaskbar；只答 7 类状态） | HUD | 7 类状态可读 |
| P1-06 | 最小 writable Control Surface 薄壳（复用 design tokens/components/status/truth rendering；Observer 仍只读） | Control Surface | 写操作经现有 Authority/Task/Approval/Receipt 服务 |
| P2-01 | Orca Pilot（第一优先；详见 ORCA-PILOT-TASK-CARD-20260925.md） | Orca 入口 | project launch/worktree identity/task correlation/exit-readback |
| P2-02 | Native Software Launcher（统一入口 ≠ 统一运行壳） | Launcher | 7 个原生/Orca 入口可达 |
| P2-03 | Omnigent / Argos 保持对照候选（DEFERRED） | — | 不阻塞现阶段 |
| P2-04 | Impact planner / local `--changed` SSOT（one canonical impact planner） | CI/local | 单一 changed-path truth，分类精度提升，fail-safe |
| P2-05 | CURRENT / HISTORY 再收口 | taskpacks/current | current=TaskPack/Register/operation records/unresolved evidence；其余→history |
| P2-06 | Future Candidate Registry 落仓（已完成，见 registry） | Registry | 落仓时 14 条目 DEFERRED、schema 校验 PASS；2026-10-07 判定轮补齐为 22 条候选并逐行加 `discovery`/`native_evidence`/`decision`（15 退役 / 7 保留 / 0 晋升，台账 ERR-126）——当时的 schema PASS 只校形状，不证明内容 |

## Hard boundaries (do not break)

- **Observer 永久只读**（§8）：`apps/observer` 不得变写控制面。
- **Control Surface 薄壳**（§9）：不复制全部 Observer frontend；真实目录
  当前不存在，本轮只落规划。
- **统一入口 ≠ 统一运行壳**（§15）：原生软件保留原生 Harness/模型/Provider/
  认证/推理强度/内部 Agent 能力。
- **每个后台能力必须有用户落点**（§27）：没有 UI 落点 =
  `backend_complete != product_complete`。
- **成熟能力优先吸收，不能吸收才自研**；WORK-LAB 做轻，Workspace 做重，
  Native Agent 保持原生。
- 任何安装/下载/克隆/模型拉取/外部写操作 → individually authorized +
  user per-operation approval；E:/F:/ 访问需 per-path 授权。

## Acceptance (when all slices are later authorized & executed)

GOAL §32 产品验收标准：Governance / Runtime / Frontend（逐页 usable）/
Execution / Transparency / External Workspace（至少一个真实 Pilot）/
Recovery / Installation safety。本卡本身只证明**路线进入 CURRENT 规划**，
不代表 UI 已实现。
