# dl-deep-audit — batch-completion delta（B/C/D 完整 JSON 补记）

生成：2026-09-21 主线程汇总（deleg_30d9d21a 批次 settled，5/5）
来源 handle（verifiable，完整 transcript/summary）：
- B: C:\Users\ALEX\AppData\Local\hermes\cache\delegation\live\deleg_30d9d21a\task-1.log
- C: .../task-2.log ; summary: C:\Users\ALEX\AppData\Local\hermes\cache\delegation\subagent-summary-2-20260921_221443_824513.txt
- D: .../task-3.log ; E: .../task-4.log

## NEW P1 — release-gate tag 触发缺失（卡 E5 最短路线）
- .github/workflows/release-gate.yml L3：`on: [workflow_dispatch]` —— 无 `push: tags`
- L94 preflight step：`if: startsWith(github.ref, 'refs/tags/')`
- 结果：打 tag 不自动触发 release gate；手动 dispatch 的 ref=branch 非 tag → if 永假
- 影响：release tag gate 实际未激活态，比"无 tag"更深
- 修复：`on:` 增加 `push: tags`（additive，不弱化）；读回确认 tag push 触发 + preflight 可达
- TaskPack：并入 F-02 前置（先修 on: 再打 tag）

## NEW P2
- pyproject.toml [tool.ruff] 自述 CONFIGURED_NOT_ENFORCED；CI 无 ruff gate（canonical-verify + release-gate 均无 ruff step）
- canonical-verify.yml 无 wheel-smoke job → packaging 仅本地实证、无 CI 覆盖（TaskPack C-01 补 wheel-smoke.yml）

## B 精化（P2，不阻塞；TaskPack C-02/缓存已覆盖）
- CI 无 pnpm/playwright/uv actions/cache（时间成本，非正确性）
- _find_browser()（test_workbench_design_layer_e2e.py:57-82）CI 上返回 None：Chromium 由 playwright install 装入非 LOCALAPPDATA/ms-playwright → 靠 playwright 自身 revision lookup 兜底，隐式依赖
- failure artifact 无 trace.zip（仅 fail.png + browser-e2e-summary.json）
- Workbench = mature 12-panel product UI，TS strict=true，API 类型全覆盖（contracts.ts 227 行无 any），不重写不迁框架

## C 分支计数精化（报告 §17 数据）
- 35 remote branch：28 MERGED_CLEANUP_CANDIDATE/HISTORICAL（unique 已 squash 进 main）
- 4 PARTIAL_RESIDUAL：fix/design-lab-governance-closure-r4(22 commits)、fix/r4-h3-prod-e3(2)、feat/ucr-workbench-strict-ts(3 含 WIP 01476f5 "in-flight, NOT closed")、migration/dl-directory-convergence-r1(31)
- 1 DO_NOT_MERGE_WHOLE：migration/dl-directory-convergence-r1（DL-DIR-000~120 完整链，PR#112/113/114 已 squash，保留历史参考）
- branch protection required_status_checks 7 项（strict=true）缺：workbench-browser-e2e(no-skip) + DeepSeek authority gate chain

## reports/current 精化（51 文件）
- 全部 LAST_GENERATED_PROJECTION（subjectSha=042ac635 或 9f89452e，均 main 6a16c40 祖先）
- CONTRACT-GRAPH.json / LANGUAGE-BOUNDARY-SCAN.json：subject_sha=''（空）→ STALE
- current-report-index.json：gitObservation.sha=9f89452e（feat/p1-control-spike，worktree_clean=false）→ STALE（checkScope 声明 not current = self-reference 正常态，非缺陷）

## wheel 构建精化
- 命令：PYTHONPATH=<build-deps> python -m build --wheel -o .hermes/task-runtime/dl-ad-pkg-ci/dist（hatchling==1.27.0，非 uv build）
- 产物 design_lab-0.1.0a0-py3-none-any.whl = 6.27MB，node_modules ~180 条目占 91%
- isolated venv repo 外 smoke = SMOKE_PASS（catalog 4 系统 + Project/Brief/Direction/choose/bind/readback 全链）
- 库权威索引命中：design_lab/resources/design-systems/（H6 manifests 已入）；消费方 runtime/paths.py L17 PROJECT_ROOT=Path(__file__).resolve().parents[3]
