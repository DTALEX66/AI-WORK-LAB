# WORK-LAB 通用协作差集任务包 20260916 — 登记清单（PLAN-ONLY，未授权执行）

- 包：`WORK-LAB-UNIVERSAL-WORKFLOW-TASKPACK-20260916`｜mode=**plan_only**｜plan_only
- 来源：用户桌面 4 份权威文件，逐字登记（source==repo SHA 一致，见 MANIFEST.json）。
- **执行授权：本包不授予任何执行权限**（START-ANY-AGENT.md 明示「此文件不授予执行权限」；TASKS.json 全部 `execution_authorized_by_this_package=false`）。
- **执行前必读**：`WORK-LAB-FULL-PROJECT-SCOPE-20260916.md`（范围更正）——本包是全项目的一个**专项增量**，不是新定义；12 条历史主线职责必须保留；**专项完成 ≠ 全项目完成**；不得借新包删除旧职责。
- 基线：`r4-recovery-exec @ 7e19fb5`；main `e5231f0`。前序包：`WORK-LAB-INTEGRATED-TASKPACK-20260916`。
- 交付状态：`PLAN_READY`（不 = 全项目完成）。20 张差集卡 / 40 AT，全部 `PLANNED_DELTA`，未实施。

## 逐字登记文件
| 文件 | 作用 | SHA256 |
|---|---|---|
| WORK-LAB-FULL-PROJECT-SCOPE-20260916.md | 范围更正与历史主线保留清单 | 483ae11f59e1dda1… |
| TASKPACK.md | 通用协作差集规划（20 卡叙述版） | c636bf8a4768ee2a… |
| TASKS.json | 机器可读任务图（20 卡 / 40 AT / carry_forward） | d1664f1e99731581… |
| START-ANY-AGENT.md | 执行入口说明（明示不授权执行） | 26ca7d0af967fa5c… |

## 登记而非执行的边界
- 仅把这 4 份权威规划文件 + 本清单提交进 tracked 仓库并推送，使双端一致。
- **未**执行任何差集卡、**未**修改 12 条历史主线代码、**未**改全局规则/软件、**未**读凭据、**未**远端发布、**未**调模型。
- 只有当用户明确要求实施且当前工具/目录授权有效时，才按 START-ANY-AGENT 顺序领取对应卡。
