# SPEC 2/3 — de-Stage3 结构解耦 + taskpacks/current 归档（WS-4，P1）
repo: D:/All projects/WORK-LAB, branch u17 (HEAD 00f45a1). Do NOT: commit/push/branch switch; do NOT touch services/authority, services/policy, config/global-agent-policy.yaml, .project/governance/project-data-boundary.json, README.md L85 区, packages/client-neutral-core/skills/** (SPEC 1 域); do NOT move any file referenced by the A03 authority verifier.

## mainline 已亲验的事实
- scripts/ci/generate_current_state.py L25 CANONICAL_FILES 仍含 3 个 Stage3 文件:
  .project/governance/generated/STAGE3_BASELINE.json, taskpacks/current/TASKPACK_SUMMARY.md, taskpacks/current/WORK-LAB-STAGE-3-TASK-GRAPH.json
  且 L232-233 _read_json 强读 stage3_graph/stage3_baseline, 输出进 compatibility_history（语义已降级 PASS）。
- .project/governance/project-authority-index.json operationalCompatibilityAllowlist 列了 3 条
  (error-ledger.json / WORK-LAB-STAGE-3-TASK-GRAPH.json / WORK-LAB-EXECUTION-EFFICIENCY-REPAIR-HANDOFF.md), 均注明 "remove after A04"; A04 已 IMPLEMENTED@0600d6f → 现在轮到移除。
- taskpacks/current/ 物理 82 blob, 其中 27 个在 taskpack-authority-index.json classification 的 SUPERSEDED/HISTORICAL/OUT_OF_SCOPE 名单内（样本: AGENT-WORKFLOW-ENHANCEMENTS-20260812.md, 全部 WORK-LAB-*-HANDOFF*.md, TP-20260819-TASKPACK-WORKLAB.md, INT-002-006*.md 等）。
- README.md L92 仍把 taskpacks/current/TASKPACK_SUMMARY.md 列进 active onboarding 引用（需随本次解耦改为指向 convergence taskpack 的 summary 或删去该引用）。

## 任务（严格顺序：先解结构依赖 → 再归档 → 最后清 allowlist）
1. 先定位所有 Stage3 结构消费方：git grep -n "STAGE3_BASELINE\|WORK-LAB-STAGE-3-TASK-GRAPH\|TASKPACK_SUMMARY" 排除 docs/history 与 taskpacks/ 本身；逐一定性（generator 强读 / 测试 / 文档引用 / CI step）。
2. scripts/ci/generate_current_state.py: 从 CANONICAL_FILES 移除 3 个 Stage3 条目; 删除/降级 L232-233 强读; 若 compatibility_history 段仍要输出, 改为 OPTIONAL read（文件缺失→role=historical_only + 值为 null + 不 fail）, 保持 --check 语义: 文件存在则重算 digest, 缺失不报错。检查 _canonical_doc_paths（L361 附近）是否也引用 TASKPACK_SUMMARY, 同步移除。
3. 跑 python scripts/ci/generate_current_state.py（无 --check, 重绑快照）确认通过; 再看 --check 行为符合第 2 条的新语义（读代码确认为 STALE/DRIFT 而非 error）。
4. 归档: 把 taskpacks/current/ 中 27 个非-current 分类 blob 移到 taskpacks/history/（git mv 语义: 只是工作树文件移动, 不 commit）。硬规则:
   - 移动前先 git grep 该文件名, 若被 taskpack-authority-index.json / FROZEN-LEGACY-INDEX / A03 verifier / 其他 machine contract 以路径引用 → 不移动, 列入报告"留置"。
   - 保留: CURRENT taskpack (WORK-LAB-UNIFIED-PRODUCT-CONVERGENCE-TASKPACK-20260918.md), OPEN-TASK-REGISTER.md, error-ledger.json（allowlist 若未清完之前先保留）。
   - TASKPACK_SUMMARY.md 与 STAGE-3-TASK-GRAPH.json 在第 2 步解除依赖后随批移入 taskpacks/history/。
5. 清 allowlist: .project/governance/project-authority-index.json operationalCompatibilityAllowlist 中已归档/已解依赖的条目移除（保留仍物理存在的）。JSON 合法 + 尾换行 + 无 BOM。
6. README.md L90-92 区: 把对 TASKPACK_SUMMARY.md 的 active 引用改为指向 taskpacks/current/WORK-LAB-UNIFIED-PRODUCT-CONVERGENCE-TASKPACK-20260918.md（保持 U02 read-only convergence 已做的指向规范: packages/…, .project/governance, taskpacks/current）。
7. 负控: 制造一次"缺失 CANONICAL_FILES 文件"的临时场景验证 fail-closed 语义未被你改坏（原 fail 的还要 fail; 你新增的 optional 缺失不 fail）, 用临时文件或临时 monkey 说明, 不提交临时物。

## 本地验证（terminal 走 wrapper, workdir = repo 根）
- python services/orchestration/run_quality_gate.py verify （全量 exit 0; 若 A03/authority 相关 gate 因归档报 referenced-path 缺失 → 该 blob 必须留置并重试, 不许弱 gate）
- python scripts/ci/generate_current_state.py --check 的行为符合新语义
- git status 只含预期文件（移动 + 上述编辑）, 不碰 SPEC 1 域文件

## 报告
- 移动文件清单（27 中实际移动 N 个, 留置 K 个 + 原因）
- generator 改动 diff 摘要 + 重绑证据
- 全量 gate 结果 + 负控证据
改动留工作树, 不 commit/push。
