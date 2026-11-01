---
name: delegation-batch-orchestration
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/delegation-batch-orchestration/SKILL.md
---

---
name: delegation-batch-orchestration
description: "Use when orchestrating parallel delegate_task batches."
version: 1.0.0
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [delegation, subagents, parallel-batches, verification, orchestration]
    related_skills: [windows-development-environment]
---

# Parallel Delegation Batches（delegate_task 多子代理编排）

## When to use

- User asks to push many independent tasks in parallel（"任务包全部开启/全部并行推进/全部推进，开始"）。
- Work splits into independent workstreams touching disjoint files/modules — serializing would flood context.
- Validated repeatedly on ArcheAxis TaskPack batches (deleg_149dd4e1, deleg_739fe7e6): 3 leaf children + main thread in parallel.

## Brief construction (children know NOTHING of this conversation)

Each task must be fully self-contained. A brief that assumes shared context produces duplicate work or guard-blocked loops. Include:

1. **Project root + branch + HEAD sha** (so the child can confirm state).
2. **Existing-facilities inventory** — every module already built that the child must REUSE, with exact file paths ("勿重复造"). The #1 failure mode is a child rebuilding what exists.
3. **Forbidden zones** — regions/files the orchestrator owns and is editing in parallel (e.g. a byte-patched CORS/middleware block in main.py): "不要动 X 区；若必须改，用 <specific pattern>（文件尾部追加 import+include_router）". This is what prevents edit collisions.
4. **Exact test command** (iron rule):
   `python "<guard-wrapper>" --project . run -- env -u PYTHONPATH uv run --frozen --group ci --group ci-adapters pytest <files> -q --tb=short -p no:cacheprovider`
5. **Discipline block**: ruff must pass (I001/UP035/F401/F541/UP009 → `ruff check --fix` then re-run tests); no shell chaining/redirection/absolute paths (guard blocks); `git add` only specific files; E-drive ban; temp files only under `.hermes/task-runtime/`; do NOT write project truth logs (orchestrator owns LOG entries — prevents concurrent LOG appends).
6. **Evidence requirement**: "print the test command + passed count in your summary; list the files you git add'ed." Self-reports without numbers are worthless.
7. **Default-resolution clause**: children cannot ask questions — resolve ambiguity in the brief ("如无法 X，则做 Y 并说明原因").

## While children run

- Do NOT poll/wait — continue orchestrator-side work on files the children are NOT touching (e.g. docs, packaging, frontend skeleton, release workflows).
- Children finish at different times; the consolidated result re-enters the conversation only when ALL finish. Work as if they might take 10-20 min.
- Tail live transcripts via a SCRIPT file (the guard blocks inline absolute paths like `C:\Users\ALEX\AppData\Local\hermes\cache\...`). Transcripts live at
  `C:\Users\ALEX\AppData\Local\hermes\cache\delegation\live\<delegation_id>\task-{0,1,2}.log` — decode `utf-8` with `errors="replace"` (they can be UTF-16 or UTF-8 mixed).

## Verification (MANDATORY before commit)

- **Child summaries are self-reports, not facts.** Independently re-run each child's test files before committing. In LOG-178 the child claimed completion but its final full re-run never executed — the orchestrator's independent 55-passed run closed the gap.
- Check deliverables actually landed on disk (files exist, non-empty) — do not trust "created".
- Re-`git add` files the child staged IF you modified them afterwards (lint fixes etc. → status shows `AM`, staged content is stale).
- Run the full suite + ruff + repo-conventions gate before pushing the batch.

## Pitfalls discovered in the field

- **Async results arrive against a STALE baseline.** A batch is dispatched at time T but its consolidated result re-enters the conversation minutes later, by which point the orchestrator (or another writer) may have committed/merged the very tree the children reviewed. Before acting on any finding, verify *which baseline the child actually froze*: check the dispatch time vs the child's stated HEAD/tree SHA vs the current `git rev-parse HEAD`. A batch that "reviewed main@<old-sha>" is evidence about that old sha only — it neither proves a gap still exists on current main, nor is it safe to dismiss as "already fixed" without re-checking. This session saw 4+ such batches all frozen on superseded SHAs; each had to be triaged by baseline, not by headline severity.
- Children's scripts may `sys.path.insert` project root → architecture guard `forbidden-sys-path-mutation` fails CI. Fix: importlib `spec_from_file_location` + `sys.modules` registration (see windows-development-environment "Cross-platform path & module traps").
- Children test on Windows locally; CI runs Linux. Windows-only path assertions (e.g. `os.path.isabs` on `C:/x`) pass locally, fail in CI — cross-platform guards required (same section).
- Children can produce code violating project-specific architecture guards (forbidden-absolute-path: hardcoded `C:\Program Files` etc.) — budget a guard-fix pass after merge.
- Write launcher/script files BEFORE background-launching them (launching first → "No such file or directory").
- A child that ran out of tool calls mid-verification leaves "all tests pass except the last step" — the orchestrator re-run covers it; do not treat the child's summary as final CI evidence.
