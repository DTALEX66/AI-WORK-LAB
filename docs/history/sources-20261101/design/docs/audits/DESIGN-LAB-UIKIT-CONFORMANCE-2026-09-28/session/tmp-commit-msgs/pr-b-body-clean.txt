## Scope

CROSSWALK 2026-09-24 旗舰结构缺口 **G-A + G-B + G-C** 合并为单一 fail-closed 门
（路径引用漂移 + 机器安装策略 + DL-GOV-130 接 CI 自举）。

## 交付

| 文件 | 作用 |
|---|---|
| `scripts/verify_path_refs.py` | GA-1 门：AUTHORITY.md/AGENTS.md 路径引用全命中；机器安装策略（no auto-install / 官方发布 / E 盘保护 / D 盘外置根）；双索引一致性（paths.json ↔ external-assets-index.json）；allowlist 须 reviewed；DL-GOV-130 守卫接 CI 自举 |
| `.project/governance/path-ref-policy.json` | 单一机器策略源（v1 schema），不建第二 ledger |
| `design-lab/tests/test_path_ref_gate.py` | 12 个 fail-closed 回归（合成 fixture 11 + live 冒烟 1） |
| `.github/workflows/canonical-verify.yml` | top-authority-gate 追加 2 步（纯 stdlib，无新依赖） |

## 验证

- 本地 `verify_path_refs.py` = `PATH_REF_GATE=PASS checks=10 failed=[]`
- 本地 `test_path_ref_gate` = 12/12 OK
- 门自举：拆掉 DL-GOV-130 的 CI 接线 → 本门 FAIL（test_unwired_drift_guard_fails 锁死）

## Rollback

revert 单 commit；新增文件为 additive（删 3 文件 + 还原 1 workflow），不影响既有 9 required 检查。

## 与既有设施关系（不建第二系统）

- 机器索引 = 既有 `.project/governance/authority-index.json`（v2 + CI gate），本 PR 只加**路径引用/安装策略**维度，不复制索引。
- 双索引一致性 = 复用既有 `paths.json` + `external-assets-index.json` 真值，本门只断言它们与策略文件一致。
- Host E3 / Human Jury E4 owner-gated，本 PR 不 EXECUTE。
