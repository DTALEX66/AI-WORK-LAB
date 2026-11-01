# Error Governance and Programming-Correctness Loop

## Purpose

The error ledger is the canonical record for execution mistakes that can cause
entrypoint drift, behavior drift, contract drift, evidence drift, or unsafe
recovery. It is not a dump of logs. It contains sanitized, reproducible facts
only and must never contain credentials, raw logs, auth data, prompts,
responses, or private configuration values.

Canonical files:

- `taskpacks/current/error-ledger.json` (the live ledger; verified by `scripts/ci/verify_error_ledger.py`)
- `scripts/ci/verify_error_ledger.py`
- `tests/ci/test_error_ledger.py`

> 2026-10-07 更正：本节此前把 `.project-local/artifacts/error-ledger-20260806.json` 列为 canonical file。
> 那个 2026-08-06 快照早已被并入上面的在册台账，磁盘上也不存在该文件；照旧说明去读它会失败。
> 保留这条更正，是为了让"文档里的路径就是一句会被执行的命令"这件事留下痕迹（见 ERR-131）。

## Required record fields

Every failure record must include:

`error_id`, `task_id`, `phase`, `classification`, `entrypoint`, `command`,
`exit_code`, `observed_error`, `root_cause`, `fix`, `regression_test`,
`evidence_level`, `repeat_prevention`, `remaining_boundary`, `status_before`,
and `status_after`.

The original non-zero exit code is retained. A later successful run is a new
fact, not a replacement for the original failure.

## Failure classes

- `entrypoint`: wrong file, wrong command, wrong module path, wrong arguments,
  or wrong working directory.
- `contract_drift`: schema, manifest, verifier, registry, or field-name mismatch.
- `test_behavior_alignment`: test references a missing production symbol or
  asserts guessed behavior.
- `working_directory_recovery`: cleanup or generated-file restoration runs from
  the wrong root or hides its own failure.
- `evidence_state`: counts or status claims are not derived from canonical data,
  or a post-suite edit was not retested.

## Mandatory loop for future failures

1. **Preflight** — verify repository root, module root, entrypoint existence,
   arguments, and working directory before executing the command.
2. **RED** — preserve the first failing command and exact sanitized error;
   create a tight regression probe that fails for the reported symptom.
3. **Root cause** — inspect the caller, definition, manifest/schema and current
   working tree. Do not patch a guessed symbol or historical path.
4. **GREEN** — make one minimal root-cause change and rerun the focused probe.
5. **Negative control** — prove the guard rejects a malformed path, schema,
   count, status, or sensitive record as applicable.
6. **Regression** — run the affected module gate, then the root gate when the
   change crosses a contract boundary.
7. **Recovery readback** — after generators/tests, verify root, status, diff
   check, exact generated files and ignored artifact boundaries independently.
8. **Evidence update** — update canonical task state only after the final tree
   has been tested. Recompute counts; never hand-edit summary totals alone.
9. **Boundary label** — separately report local, isolated, live, cloud-CI, Git,
   platform, and release evidence.
10. **Ledger** — append a sanitized record and run the error-ledger verifier.

## Anti-repeat rules

- Never execute a documented command until its file exists in the current tree.
- Never assume a nested `workdir` persists into a root-relative recovery command.
- Never use `rc=$?; cleanup; exit $rc` without independently checking cleanup.
- Never report a full suite as validating a production edit made after that suite.
- Never promote a local pass to live, cloud, Git, platform, or release evidence.
- Never replace an original failure with a vague `PARTIAL` note.
