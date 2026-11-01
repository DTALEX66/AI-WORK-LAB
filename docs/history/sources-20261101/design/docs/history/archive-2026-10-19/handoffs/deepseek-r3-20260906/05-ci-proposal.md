# DS-05 CI 触发候选建议（候选材料，非正式 CI 变更）

> 任务：DS-05｜支持 R3-04｜2026-09-06
> 只列候选修改；本文件不修改任何 workflow。正式 CI 变更、renderer 来源/hash、Python 环境取舍归 GPT。

## 观测（来自当前 `.github/workflows/canonical-verify.yml`，未改文件）

| 探针路径 | push | pull_request | 命中规则 |
|---|---|---|---|
| `apps/workbench/example.ts` | ❌ | ❌ | 无 `apps/**` 规则 |
| `src/design_lab/runtime/paths.py` | ✅ | ✅ | `src/**` |
| `integrations/hosts/adobe/adapter.manifest.json` | ✅ | ❌ | push `integrations/**`；PR 无 `integrations/**` |
| `packages/capabilities/reconstruction/contracts.py` | ✅ | ❌ | push `packages/capabilities/**`；PR 无 |
| `pyproject.toml` | ✅ | ❌ | push 有 `pyproject.toml`；PR 无 |
| `uv.lock` | ✅ | ❌ | push 有 `uv.lock`；PR 无 |
| `AGENTS.md` | ❌ | ❌ | 无 `AGENTS.md` 规则 |
| `.project/paths.json` | ✅ | ❌ | push `.project/**`；PR 无 |
| `scripts/design_lab_doctor.py` | ✅ | ✅ | `scripts/**` |

PR 侧相对 push 缺失的规则：`.project/**`、`integrations/**`、`packages/capabilities/**`、`pyproject.toml`、`uv.lock`。

## 候选修改（按最小改动排序；仅候选）

1. **对齐 PR paths 到 push paths**：把 PR 段补上 `.project/**`、`integrations/**`、`packages/capabilities/**`、`pyproject.toml`、`uv.lock`，使"只改 pyproject/uv.lock/integrations/AGENTS 的 PR 都触发必须门"成立（R3-04 验收）。
2. **新增 `apps/**` 规则**（push+PR）：当 `apps/workbench` 首次落地时保证触发。
3. **新增 `AGENTS.md` 显式规则**（push+PR）：当前 AGENTS.md 修改不触发任何门（R3-01 的"从 README 与 AGENTS 能到同一执行包"验收依赖其受检）。
4. 保留既有 gate（license/secret、node、generated-artifact、open-design-host）；不要为了变绿删除原本有效的门。

## 局限声明

- 静态 glob 匹配不等于 CI 已触发或已通过；真实触发证据需 workflow run 记录。
- 本矩阵基于当前工作区 workflow 文本；`release-gate.yml` 仅 `workflow_dispatch`（人工触发），不在本表逐条覆盖。
