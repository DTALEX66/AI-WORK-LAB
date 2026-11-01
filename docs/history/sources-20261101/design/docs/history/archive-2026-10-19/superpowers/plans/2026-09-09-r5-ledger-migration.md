# R5 single-ledger migration implementation plan

Execute inline under the user's autonomous execution authorization. One writer
owns the existing clean `codex/r3-runtime-correctness` checkout. No main merge,
release, Human Jury signature, external asset upload or global configuration change.

**Goal:** adopt all 28 R5 tasks without losing R3 history or promoting old evidence.

**Architecture:** retain the existing active ledger path. Introduce a versioned
R5 contract with immutable task definitions, separate execution axes and a complete
hash-bound R3 predecessor. The existing evidence evaluator remains authoritative.
Build and test a candidate before changing the active ledger or its entry points.

**Spec:** `docs/history/taskpacks/r5-20260908/tasks.json`, task DL-R5-001;
`ADOPTION-STATUS.md`; the R4.1/R3 mapping in the package's references directory.

## Acceptance and execution sequence

- [x] Candidate migration: `scripts/prepare_r5_ledger.py` consumes validated R3
  bytes and the pinned R5 source, returns a deterministic candidate and never
  writes the active ledger. Preserve all 24 old tasks and every evidence record.
  Map every R3 ID through the documented R4 mapping; language governance is new.
  Keep baseline observations, conditional dependencies and all acceptance text.
  New execution axes start PARTIAL pending reassessment, with no claimed PASS.
- [x] RED/GREEN: `design-lab/tests/test_r5_migration.py` rejects modified source,
  invalid predecessor and duplicate JSON keys; checks lossless predecessor,
  complete mappings, immutable inputs and no transferred completion.
  Run `.venv/Scripts/python.exe -B -X utf8 -m unittest discover -s design-lab/tests -p test_r5_migration.py -v`.
- [x] Versioned contract/reporting: derive the R5 schema in `r5_contract.py` and add a validation branch in
  `src/design_lab/governance/reporting.py`. Validate pinned source, predecessor,
  mappings, required axes and conditional acceptance without weakening R3.
  Preserve old reporting tests against a frozen R3 fixture and add R5 negative
  controls for source tampering, unknown dependencies and wrong-kind evidence.
- [x] Activation: preserve predecessor bytes in history, write the validated
  candidate to the sole existing ledger path, regenerate current reports, then
  update AGENTS/README and adoption status. No second active state file.
- [x] Run focused migration/intake/report tests, canonical gate and report
  `--check`; inspect final diff before committing explicit owned paths.

Rollback: restore the prior ledger, schema, reporting implementation and entry
point documents through a reviewed inverse change. Keep the frozen R5 source,
predecessor, native assets and failed-run evidence. A successful migration is
structural/local evidence only, not completion of R5 production tasks.
