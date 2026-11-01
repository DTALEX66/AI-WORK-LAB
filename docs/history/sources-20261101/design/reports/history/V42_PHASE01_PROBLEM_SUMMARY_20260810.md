# V4.2 问题总结（Problem Summary）— 2026-08-10

> **HISTORICAL SNAPSHOT — NOT CURRENT EVIDENCE.** This dated report is
> retained for audit traceability. Its E-level/runtime wording describes
> the recorded tree only and does not qualify the current checkout.


> 依据 `DESIGN-LAB-Final-TaskPack-v4.2-2026-08-10`（Phase 0 事实冻结 + Phase 1 P0 修复）
> 基线：`4ae0981b1d75ac1d20cac3a231b7e157854a4fb9` → 当前：`c2f5fbc`（main）

## 一、Phase 0 审计发现的问题（基线 `4ae0981`）

### 已确认 P0 缺陷（9 项，均复核属实）

| # | 问题 | 证据位置 | 影响 |
|---|---|---|---|
| 1 | 兼容矩阵仍含 Open Design 0.13.0，而 canonical 文档使用 0.18.1 | `config/compatibility-baseline.json`、`config/OPEN_DESIGN_COMPATIBILITY_MATRIX.md`、`docs/OPEN_DESIGN_VERSION_BASELINE.md` | 版本口径分裂，E3 对齐目标不明 |
| 2 | README 使用不存在的 `--permission-root` 参数 | `README.md:203` | 文档命令不可执行 |
| 3 | 配置脚本 `--apply` 仍会写 Open Design 私有 app-config.json 与 launcher | `scripts/configure_open_design_windows.py` | 违反"plan-only"集成边界 |
| 4 | clean-tree workflow 只打印 `wc -l` 数量，脏树不失败 | `.github/workflows/canonical-verify-v4.yml` `generated-artifact-gate` | clean-tree 门禁形同虚设 |
| 5 | workflow path filter 漏触发：README、THIRD_PARTY_SOURCES、LICENSING_DECISION_REQUIRED、handoff 指针等 root 文件不触发；PR 分支更缺 requirements/LICENSE/LICENSES/NOTICE | `canonical-verify-v4.yml` | canonical 状态变更可能无 CI 覆盖 |
| 6 | 插件/Bundle/Domain Pack 人工计数与真实目录不一致（README 说 21 atoms/7 plugins，inheritance-matrix 说 8 plugins，实际 7） | `README.md`、`entrypoint-convergence.json`、`inheritance-matrix.json` | 计数失真 |
| 7 | Figma/Penpot/browser 等适配器声明 `available` 但无版本、任务、Artifact 证据 | `adapters/adapter-registry.json` | 声明高于证据 |
| 8 | 缺少 `capability-evidence-index.json` | 全仓无此文件 | 能力证据不可追踪 |
| 9 | 许可证 Gate 未覆盖 REUSE/SBOM/第三方 BOM/二进制 sidecar | `canonical-verify-v4.yml` `license-secret-gate` | 供应链/许可风险不可见 |

### 附加结构性问题（本机新发现，2 项）

| # | 问题 | 位置 |
|---|---|---|
| 10 | `capability-status.json` 的 `capabilityStates` 字段被误用为字符串枚举列表，缺实际能力状态记录 | `config/capability-status.json` |
| 11 | adapter-registry 的 4 个 `available` 适配器无版本/任务/Artifact 证据字段 | `adapters/adapter-registry.json` |

### 证据等级现状（Phase 0 快照）

- 12 张 evidence card 全部 `not-run` / E0
- 112 通用来源 + 22 视觉来源（V2.0-draft / V2.1，需迁移 V3 字段）
- 497 条大师记录、77 张方法卡草稿（需分层核验）
- **全仓无 E3 声明**；当前 HEAD 无 exact-SHA CI

## 二、Phase 1 修复结果（全部闭环）

| 任务 | 修复 | 验证 |
|---|---|---|
| V42-0101 | 兼容基线统一 0.18.1（minimum=tested=latest）；0.13.0 降为 `historically_known` | JSON 校验 + verify 全过 |
| V42-0102 | README 移除 `--permission-root` | diff 确认 |
| V42-0103 | configure 脚本改 **plan-only**：永不写私有 app-config/launcher；新增 `--export-plan`；保留 fail-closed SECURITY_BLOCK | 9 安全测试通过 |
| V42-0104 | clean-tree 门禁 **fail-closed**（脏树 exit 1） | workflow YAML 校验 |
| V42-0105 | workflow path filter 补全（push+PR 覆盖 root 文档/指针/忽略文件） | path 对照分析 |
| V42-0106 | 新增 `asset-counts.json` 单一计数源 + verify 防漂移 | 465 checks 通过 |
| V42-0107 | adapter 状态改 `declared/structural/runtime/missing` + 强制 evidence 块；schema v2 | 7 adapter 测试通过 |
| V42-0108 | 新建 `MINIGAME_FROZEN_BOUNDARY.md`；README 改 fixture 口径；4 旧文档 DEPRECATED | 321 minigame 测试通过 |

## 三、遗留问题（未在 Phase 1 处理，属后续 Phase）

1. **`capability-evidence-index.json` 缺失** → Phase 10（V42-1001）建立
2. **许可证 Gate 覆盖 REUSE/SBOM/BOM/sidecar** → Phase 11（V42-1102/1103）
3. **497 大师记录 + 77 方法卡来源治理** → Phase 7（V42-0704/0705）
4. **112+22 来源迁移 V3 字段** → Phase 7（V42-0701/0702）
5. **三 Bundle Open Design 真实注册（E3）** → Phase 3（V42-0301..0306）
6. **capability-status.json 字段修复** → 建议并入 Phase 2 数据模型（V42-0204）一并重构
7. **12 张 evidence card 升级** → Phase 10 绑定真实 Artifact
