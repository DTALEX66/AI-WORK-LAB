# Phase 01 Gate 0 — Trusted Foundation 验收报告

- 阶段：`Phase 01`（安全、许可、CI、生成物、体量）｜Gate：`GATE_0_TRUSTED_FOUNDATION`
- 日期：2026-08-07｜状态：**PASS**
- 分支：`migration/work-lab-minigame-cutover-20260807`（工作树 clean，ahead origin 8）

## 完成的 P0 任务

| 任务 | 提交 | 结果 |
|---|---|---|
| ODA4-0105 MiniGame Android 导出安全 + 生成物漂移 | `a060e6a` | E2：bundle 含 SENSITIVE_KEYS，drift gate 确定性 |
| ODA4-0101 移除凭据读取/私有配置写入/宽根权限 | `c5b4ac4` | E2：9/9 安全回归测试 |
| ODA4-0103 可复现 Python/Node 依赖 | `2568e14` | E2：16→21 测试通过 |
| ODA4-0104 根级 Canonical CI | `5cc8a81` | 结构：覆盖 V3/单测/MiniGame/drift/secrets |
| ODA4-0106 媒体去重 + 体量治理 | `5dcf65f` | E2：363→113 文件，-106.55 MB 重复 |
| ODA4-0108 迁移交接记录与分支事实 | `95bf834` | E1：最终状态表 + LICENSE 事实纠正 |
| ODA4-0107 分支/PR/exact-SHA 证据合同 | `0023837` | E2：schema + readback + 5/5 测试 |

## Gate 0 逐项验收

| # | 要求 | 状态 |
|---|---|---|
| 1 | 危险 Windows 配置/doctor 行为已移除或隔离 | ✅ `SECURITY_BLOCK` 宽根拒绝 |
| 2 | 不读凭据、不修改私有配置、不授予宽根权限 | ✅ presence-only auth 检查 |
| 3 | 根许可证状态明确 | ✅ MIT（用户选择）+ NOTICE + REUSE |
| 4 | Python 依赖可复现、全部单测通过 | ✅ requirements.txt + 21 单测 |
| 5 | 根 CI 覆盖完整 V3/MiniGame/secrets/license/生成物漂移 | ✅ canonical-verify-v4.yml |
| 6 | MiniGame 生成后工作树干净 | ✅ 重建后 0 dirty |
| 7 | Android 导出含源码安全与敏感数据保护 | ✅ SENSITIVE_KEYS 已入 bundle |
| 8 | 媒体去重方案及 LFS/Artifact 策略落地 | ✅ -106.55 MB，>80% 达标 |
| 9 | 当前 exact tree 基线证据完整 | ✅ baseline.json + capability-census.json |

## 验证链（全部通过）

```
VERIFY_PRODUCT_MANIFEST_V3=OK total=203 failed=0
VERIFY_RUNTIME_CONTRACTS_V3=OK total=223 failed=0
VERIFY_VISUAL_SCORING_V3=OK total=10 failed=0
VERIFY_RESULT=OK total=456 failed=0
python scripts/run_python_tests.py  -> 21 tests OK
node scripts/run-tests.cjs          -> 321 tests OK
check-android-drift.mjs             -> all bundles match committed
```

## 边界确认

- 未访问 E:\、未读凭据、未写项目外目录、未改私有配置。
- 未执行任何未授权远端写操作（无 push / PR / merge / tag / release）。
- 所有 P0 阻断已关闭；Phase 01 达标。**可进入 Phase 02（V4 产品定义与七层架构）。**

## 证据存放
- 全部证据在 `.hermes/task-artifacts/open-design-v4/`（Git-ignored）。
- 交付物在仓库跟踪（schemas/scripts/tests/reports/project-memory）。
