# Batch F-1 规格：把 effective evidence 接入 Release Gate

## 背景（事实）
- P1-B（已合并，PR #127 → main `eea6701`）新增 `design-lab/scripts/effective_evidence.py`：
  - `LEVEL` E0–E5；`effective_evidence(record, current_sha, structural_pass)`（`requiresRequalification` 为真，或 `subjectSha` 存在且 != current_sha → `E1`（structural_pass 时）否则 `E0`；否则返回 recorded）
  - `structural_pass_from_recorded(recorded)`（>=E1 为真）、`meets_floor(level, floor)`、`load_index(repo)`、`requalified(index)`
- 但 **Release Gate 仍按 recorded 比较 floor**：`design-lab/scripts/verify_release_gate.py` 的 `capability_floor_findings(...)`（第 126 行被调用）产出 `EVIDENCE-BELOW-MINIMUM <id> actual=.. minimum=..`。
- 报告 `docs/research/full-maturity-audit-2026-09-19.md` 的 Batch F 要求 release gate 比较 **effective**。

## 交付物
1. 改 `design-lab/scripts/verify_release_gate.py`：
   - 用 `effective_evidence` 计算每个 capability 的 **effective** 级别（structural_pass 代理 = recorded >= E1；current_sha 经 `git rev-parse HEAD`）。
   - floor 比较改用 effective：`EVIDENCE-BELOW-MINIMUM <id> actual=<effective> minimum=<floor>`，并把 recorded 一并写出供人读（如 `recorded=<rec> effective=<eff>`）。
   - 因 requalification 降级的单独给可区分的 finding：`EVIDENCE-REQUALIFICATION-REQUIRED <id> recorded=<rec> effective=<eff>`（语义是"需重新取得运行时证据"，而非"从未达到"）。
   - 保持既有结尾契约 `RELEASE_GATE=<verdict> findings=N`；纯计算，无网络、无新依赖。
2. 测试：新建 `design-lab/tests/test_release_gate_effective.py`（不改动既有 27 个用例的语义）：
   - requalified capability（recorded E3、floor E3）→ 产出上述 finding，且 actual/effective 为 E1
   - clean capability（recorded >= floor、无 requalification、subjectSha == current_sha）→ 不产出该 finding
   - 未知/缺失级别 → 保持 fail-closed（有 finding）
3. 禁区：不碰 `reports/`、`AUTHORITY.md`、`.project/`、`docs/`、`AGENTS.md`、`.project/governance/authority-index.json`、`docs/architecture/LANGUAGE-POLICY.md`；除非必要不改 `capability-evidence-index.json`（若改必须说明理由）。

## 验证（贴原始输出）
- `design-lab/scripts/verify_release_gate.py` **改动前后各一次**（注意：它会因 dirty worktree / 分支态 SHA 报 BLOCKED，这些是既有 finding —— 总结里必须逐条区分「本次新增」与「既有」）
- 新测试文件全绿
- `design-lab/scripts/verify_design_lab.py` → `VERIFY_DESIGN_LAB=OK total=49 failed=0`
- `scripts/verify_authority_gates.py --zero-spill` → `AUTHORITY_GATES=PASS gates=7 failed=none`
- `git status --short` + `git diff --stat`

## 命令纪律
- 全部经 wrapper 单命令：`python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- <单命令>`，workdir=`D:/All projects/DESIGN-LAB`；禁 shell 串联（`&&`/`;`/`|`/`>`）。
- 不 commit / 不 stash / 不 push / 不建分支；不装依赖；不联网。改动留给主线提交。
- 总结里每个"通过"必须配真实输出；无法完成项明确写「未完成：<原因>」，不得虚构。
