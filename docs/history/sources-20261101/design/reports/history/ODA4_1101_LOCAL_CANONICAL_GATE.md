# Local Canonical Gate Run（ODA4-1101）

> **HISTORICAL SNAPSHOT — NOT CURRENT EVIDENCE.** This report records the
> tree and environment named below. It must not promote current capabilities
> or override `design-lab/config/capability-evidence-index.json`.

- **任务**：ODA4-1101（运行完整本地 Canonical Gate）
- **状态**：**PASS**（所有 required gates 实际运行，无 mock/skip/硬编码）
- **日期**：2026-08-14（boundTree=`9596a37`）
- **执行**：Hermes Agent（DESIGN-LAB 会话）

## Gate 结果

| Gate | 命令 | 结果 |
|---|---|---|
| python-gate（14 verifiers）| `verify_design_lab.py` | ✅ **OK total=14 failed=0** |
| ├─ product-manifest | | ✅ total=254 |
| ├─ runtime-contracts | | ✅ total=235 |
| ├─ visual-scoring | | ✅ total=10 |
| ├─ source-registry | | ✅ OK（162 sources, 0 errors）|
| ├─ v2-protocols | | ✅ OK |
| ├─ visual-quality-v21 | | ✅ OK |
| ├─ comfyui-gate | | ✅ OK（E3 runtime verified）|
| ├─ sbom | | ✅ OK（SPDX valid）|
| ├─ adapter-registry | | ✅ PASS（9 adapters）|
| ├─ benchmark-registry | | ✅ PASS（12）|
| ├─ evidence-cards | | ✅ PASS（12, human_calibration_required）|
| ├─ asset-governance | | ✅ PASS |
| └─ jury-anti-slop | | ✅ PASS |
| python tests | `pytest design-lab/tests/` | ✅ **163 passed + 5 subtests** |
| node-gate | `node scripts/run-tests.cjs`（minigame）| ✅ **319 tests 0 fail**（duration 6.6s）|

## 完整性声明

- ✅ 所有 required gates 实际运行（无 mock/skip/硬编码）
- ✅ 测试后工作树符合预期（clean，见 git status）
- ✅ 许可/安全/SBOM/证据完整（license gate + secret gate 由 CI 面覆盖，本地 python-gate 含 SBOM/evidence）

## 上下文

- 本 gate 在 main=`9596a37`（PR #86 合并后）运行
- 与云端 CI run #293（success）**一致**——本地与 CI 无分歧
- 遗留人工项：human_calibration（ODA4-0905/DL-REL-001）待用户评分——evidence-cards `human_calibration_required=true` 如实标注
