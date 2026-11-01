---
name: performance-baseline-measurement
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/performance-baseline-measurement/SKILL.md
---

---
name: performance-baseline-measurement
description: "Measure perf/bloat baselines; judge PASS/PENDING/FAIL."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [perf, baseline, benchmark, bloat, p50, p95, read-only, evidence]
    related_skills: [project-data-boundary, hermes-jsonl-ledger-care, runtime-baseline-audit]
---

# Performance / Bloat Baseline Measurement

## Trigger

Task asks to 测基准 / 性能 / 延迟 / 膨胀 / baseline 报告, run `perf_baseline` /
`repo_size_audit` / `regression_report` style scripts, or produce performance
evidence a later task will consume (WORK-LAB pattern: WL3-810 baseline files
are the acceptance evidence for WL3-820). Also any "record baseline, judge
PASS/PENDING/FAIL, don't fabricate" measurement request.

## Workflow

1. **Inventory first** (read-only, batch independent searches):
   - Find measurement scripts: `search_files` for `perf_baseline|repo_size_audit|regression_report|benchmark` (target=files, then content).
   - Find CI steps: grep `.github/workflows` for perf/bench/baseline. **Absence of a step is evidence** → record "not wired into CI = PENDING", never assume it runs.
   - Find HISTORICAL baselines before declaring "no baseline": grep delivery records (`TASKPACK_SUMMARY.md`, `*-APPROVAL-PACKAGE.md`, handoffs) for tracked-file counts / MiB / duplicate-group counts / prior P50-P95.
   - Read the task's own checklist doc (e.g. `.hermes/task-runtime/wl3-810-perf-checklist.md`) — it defines the criteria AND the artifact landing spot.
2. **Run read-only measurements** through the project-data wrapper (one command per call; wrapper fixes cwd=project root; shell chaining blocked):
   ```bash
   python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- python <script>
   ```
   - Scripts with own `sys.path` handling run with plain `python` — no uv/venv needed.
   - perf: capture p50/p95/max + sample counts; bloat: tracked files/bytes/dup groups; git object stats need a SEPARATE `git count-objects -v` (repo_size_audit's `main()` does NOT call `audit_git_objects()`).
3. **Judge per verdict semantics** (as the task defines them; WORK-LAB convention):
   - **PASS** = has a baseline/budget AND meets it.
   - **PENDING** = no baseline recorded → record the current value as first baseline, keep PENDING.
   - **FAIL** = has a baseline/budget AND exceeded it (e.g. tracked files +36.8% vs reference with no approval record).
4. **Write the report + raw JSON evidence**:
   - Report: `.hermes/task-runtime/<task>-baseline.md` (Chinese for WL3-xxx tasks); raw JSON in `.hermes/task-runtime/artifacts/` (git-ignored — verify with `git check-ignore`).
   - Include: env (date / OS / python / HEAD sha), per-item measured value + budget + verdict, evidence inventory, honest notes on FAIL items (likely causes, approval/archive path), summary table.
   - Never fabricate; external-dependent or unmeasured items = PENDING with the exact reason (e.g. canary env var missing).

## Pitfalls

- **`read_file` may misdetect UTF-8 markdown as "Binary file"** — confirm via wrapper `cat` or `file`; content is fine, don't rewrite it.
- Wrapper blocks shell chaining (`&&`, `;`, `|`, heredocs) — one command per call; use `write_file` for temp scripts.
- Historical baselines hide in delivery records (TASKPACK_SUMMARY.md etc.), not only JSON artifacts — grep before concluding "no prior baseline".
- Measurement scripts may hardcode repo roots (e.g. `perf_baseline.py` `WORK = Path(r"D:\...")`) — works when the path exists, but note it as a portability defect (PENDING fix), don't silently rewrite the script.
- Trust a "read-only" claim only after verifying: git env (`GIT_OPTIONAL_LOCKS=0`), no writes, boundary assertions in the script's own gate (network/credentials/externalWrites false).
- Distinguish verdict axes: perf latency vs repo bloat vs CI integration are separate items — a PASS perf script can still be FAIL on bloat or PENDING on CI wiring.
- **"skills <10KB" budget measures the SKILL.md BODY, not the directory.** Baseline-4 ("skills ~<10KB each") constrains the injected-context payload = `SKILL.md` itself; `references/`+`scripts/`+`templates/` are on-demand and don't block startup. When measuring, report `skill_md_bytes` and `auxiliary_bytes` separately (not just a directory `total`) — a skill whose directory is 23KB may be compliant if its SKILL.md body is 5KB with 18KB of on-demand references. (2026-08-15: 3 of 13 WORK-LAB managed skills had SKILL.md bodies over 10KB — python-testing 51KB, windows-development-environment 31KB, agent-workflow-fortress 21KB — flagged as baseline-4 FAIL, fix = move detail to references/.)
- **Context-pack size has soft + hard ceilings; truncation at the hard ceiling is BY DESIGN, not a failure.** `build_context_pack` uses `DEFAULT_MAX_CHARS=12000` (soft, new-session handoff) and `HARD_MAX_CHARS=30000` (audit ceiling). Render at `max_chars=10**7` to read the UNtruncated length; if it exceeds 30k the hard-limit output is clipped with a `[truncated at N]` marker — record the raw length as the bloat signal, and PASS the truncation-protection (idempotency still holds).
- **Gate wall-time = job `started_at`→`completed_at` from the CI jobs endpoint, NOT the workflow `timeout-minutes` constants.** The 10m/20m timeouts are ceilings; real wall-clock comes from `actions/jobs/<run-id>` step/job timestamps. token-monitor (Cargo build) routinely dominates (~5m) while every other job is <90s — read the bottleneck job by name before judging wall-time regression.

## References

- `references/worklab-wl3-810.md` — WORK-LAB WL3-810 specifics: script paths, budget constants, 2026-08-15 measured values, historical baselines, artifact locations, CI integration status.
