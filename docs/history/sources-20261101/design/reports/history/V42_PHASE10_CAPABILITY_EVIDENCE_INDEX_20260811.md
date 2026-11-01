# V4.2 Phase 10 — Capability Evidence Index 交接文档

> **HISTORICAL SNAPSHOT — NOT CURRENT EVIDENCE.** This dated report is
> retained for audit traceability. Its E-level/runtime wording describes
> the recorded tree only and does not qualify the current checkout.


> 日期：2026-08-11
> 目标仓库：`DTALEX66/DESIGN-LAB`
> 基线：`d4716a4`（V4.2 main 权威，双端一致）
> 关联遗留：V42_PROBLEM_SUMMARY_20260811.md 遗留项 5

## 交付：capability-evidence-index.json

**新增** `design-lab/config/capability-evidence-index.json`

- schemaVersion `design-lab/capability-evidence-index/v2`
- 绑定 tree SHA `d4716a4`
- 8 个能力族如实标定 E0-E5 级 + run/artifact/reviewer
- 提供 `records` 视图（与 `verify_capability_evidence_v4.py` 兼容）

### 8 能力族 E 级标定（如实，不虚标）
| 能力族 | 级 | 依据 |
|---|---|---|
| source-governance | E1 | 结构性：registry + 治理规则 + REUSE |
| brief-routing | E1 | 结构性：atoms + 6 scenarios + 测试 |
| visual-quality | E1 | 结构性：rubrics + scoring（V4.2 Axe E3 证据不在仓库，未升 E3）|
| style-master-method | E0 | Phase 7 范围 |
| domain-scenarios | E1 | 结构性：uiux-design Domain Pack 5 案例 PASS |
| production-handoff | E1 | 结构性：preflight/handoff schema |
| runtime-integration | E0 | V4.2 报告记录 E3 但运行证据不在树、daemon 未运行，未复现不虚标 |
| release-evidence | E1 | 结构性 + 记录 exact-SHA CI |

## 接入验证

1. `verify_capability_evidence_v4.py` 无参默认指向 `capability-evidence-index.json`（增强，不破坏 test_oda4_0205）
2. 主验证链 secondary verifiers 新增该脚本

### 验证结果
- `verify_capability_evidence_v4.py` → `CAPABILITY_EVIDENCE_V4=PASS records=8`
- 主验证链 → `VERIFY_RESULT=OK total=466 failed=0`（原 465 + 新增 1）
- 全 Python 测试 → `60 passed, 5 subtests passed`
- `verify_evidence_cards.py` → PASS（12 卡保持 not-run/E0，未虚标）

## 12 evidence card（诚实保留，未人工提升）
- 全部 `card_status=not-run / evidence_level=E0`
- 依 `verify_evidence_cards.py` 规则：`human_calibration_policy.required_for_promotion=true`，not-run 卡必须保持 E0
- **提升被 V42-0409 人工专业 Jury 硬性阻塞**，未虚标

## 诚实性声明
- 所有 E 级基于**当前树中存在的工件**或显式"记录未复现"注记
- `runtime-integration`、`visual-quality` 的 V4.2 报告 E3 声明**未在此重述**，因运行证据不在树、daemon 未运行
- 12 evidence card 未人工提升（需真人 Jury）

## 边界遵守
- 未访问 E:\、未读取凭据、未改 Open Design 私有配置
- 未历史重写/force-push/破坏性 reset
- 未改动 v4.1 或 V4.2 既有测试断言
