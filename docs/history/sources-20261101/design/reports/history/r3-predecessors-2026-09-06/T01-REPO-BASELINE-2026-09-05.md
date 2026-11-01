# T01 — 当前仓库与历史对照（2026-09-05）

> 任务来源：DESIGN-LAB-MULTIMODAL-TASK-PLAN-2026-09-05（T01）：核对执行时 main/分支/PR SHA、原任务包与归档索引；旧任务标保留/吸收/替代/暂缓，保留原 ID；复现 PR115 审计问题，已修复项附当前证据。
> 性质：对照与证据台账，不是功能声明。

## 1. 当前 SHA / 分支 / PR（2026-09-05 记录时）

| 项 | 值 |
|---|---|
| 本地分支 | `feat/r0-freeze-baseline`（HEAD `0ca80d1`） |
| 本地相对 cloud main `2aca27f` | 38 个提交 |
| PR #115 | OPEN、MERGEABLE；head ref `feat/r0-freeze-baseline`，云端 head OID 仍 `3dd0a13`（**本地 F01–F10 整改尚未推送**；全套 Python 门绿后 push 更新） |
| 任务包 | DL-TP-20260904-STANDALONE-FIRST（`docs/taskpacks/DESIGN-LAB-TODAY-EXECUTION-TASKPACK-2026-09-04.md` v1.4） |
| 历史冻结 | `reports/history-baseline.json`（baseline 2aca27f；history CSVs 已入树 `docs/history/`，hash 一致） |
| 本 MULTIMODAL 方案 | `D:\All projects\DESIGN-LAB-MULTIMODAL-TASK-PLAN-2026-09-05.md`（新，T01–T18） |

## 2. PR115 审计（2026-09-05 外部审计）逐项当前证据

| 发现 | 状态 | 当前证据（本分支已提交） |
|---|---|---|
| F01 H3 status 破坏 schema 枚举 | **已修复** | adapter-contract.schema.json 加 `BLOCKED_BY_LICENSE` + 合法-不可执行 allOf；test_oda4_0206_adapters 10 OK |
| F02 job-spec $defs 悬空 | **已修复** | 内联 operationIntentRef；test_contract_schema_integrity `test_no_local_ref_points_to_nowhere` 通过 |
| F03 契约过弱 | **已修复** | job-attempt/capability-evidence/asset-ref/rights-decision/delivery-receipt 收紧；integrity 8 OK |
| F04 锁文件缺依赖/CI 绕锁 | **已修复** | uv.lock 20 包；CI `uv sync --locked` |
| F05 sealed-bundle 死代码 | **已修复** | seal 接入生产 `_promote`；test_reconstruction_evidence 37 OK（含 seal 失败注入） |
| F06 .project-local 迁移遗漏 | **已修复（本轮）** | runtime_roots.py 中央解析器 + 主链/夹具迁移；reconstruction 全套 243 OK |
| F07 manifest ref gate 读错结构 | **已修复** | 按 `capabilityFamilies[].paths[]` 扫描；VERIFY_PRODUCT_MANIFEST_V3=OK(493) |
| F08 CI 触发缺 src/** | **已修复** | push+pull_request 均含 src/** |
| F09 history CSVs 缺失/AGENTS 旧 | **已修复** | CSVs 字节入树(hash=sealed)；AGENTS/README standalone-first |
| F10 声称夸大 | **已修复（本轮）** | TASKPACK_PROGRESS 改 evidence 口径；PR 描述已重写 |

## 3. 旧任务→新任务映射（MULTIMODAL 视角）

- 原 DL-TP-20260904 Wave 0/1/2 契约代码层 → 保留为**基础设施基线**（T01 验证对象）。
- 计划 §“生成/宿主/多模态”能力（AI/PS 实机重建、ComfyUI 入口、音频、视频、Premiere、Blender、OpenDesign/MiniMax 协作）→ 由 MULTIMODAL T02–T17 **吸收/扩展**（原注册任务不删除，保留原 ID）。
- H3 本地运行、真实宿主 E3、Review Console、Local Runtime 等 → **暂缓/阻塞**（权利门/未实机/未安装），保留原 ID 与状态。

## 4. 可复现阻塞项（当前，非伪造完成）

1. PR #115 云端 head 未更新 → **全套 Python 门（进行中）绿后 push**（本条为流程阻塞，非代码阻塞）。
2. ComfyUI 未安装（T02 盘点）→ T09 生成入口待部署/指向；不阻塞 AI/PS 与结构层。
3. Blender 未安装 → T15 阻塞（实机）。
4. H3 权利/地域门未清 → H3 本地 `BLOCKED_BY_LICENSE`。
5. RTX 5060 显存 ~8 GB → 任务排队纪律必须执行（§8）。

## 5. 交付物指针

- 本报告：`reports/current/T01-REPO-BASELINE-2026-09-05.md`（本文件）
- 审计整改明细：`reports/current/PR115-AUDIT-FIX-STATUS-2026-09-05.md`
- 机器盘点：`reports/current/T02-MACHINE-INVENTORY-2026-09-05.md`
- 交接拆解：`D:\All projects\DESIGN-LAB-MULTIMODAL-CODEX-HANDOFF-2026-09-05.md`
