# Superseded / stale "CURRENT" projections (retired 2026-09-19)

P0-04 — CURRENT STATE de-duplication.

WORK-LAB allows **one machine CURRENT projection** plus **one human-readable
projection**. Two historical files had drifted from that rule and were retired
by `git mv` into this archive directory (moved, **not deleted**, so the
evidence trail is preserved).

## Retired here

- `CURRENT_STATE-2026-09-01-STALE.md`
  - Source: `docs/decisions/CURRENT_STATE.md`
  - A second, human-readable current-state projection dated 2026-09-01 that
    duplicated the generated `.project/governance/generated/CURRENT_STATE.md`.
    It still pointed at the historical module layout
    (`10-workflow/`, `30-observer/`, contracts `30`) and is no longer the
    current identity.
  - Superseded by: `.project/governance/generated/CURRENT_STATE.{json,md}`.

- `CURRENT_EXECUTION_BASELINE-r4-2026-09-05-STALE.json`
  - Source: `.project/governance/generated/CURRENT_EXECUTION_BASELINE.json`
  - Described branch `r4-recovery-exec` @ `bf52df0`,
    taskpack `WORK-LAB-DR-R4-20260904`, status `IN_PROGRESS_R4`. That branch
    was retired on the 2026-09-17 cutover; the record is historical only and
    must not be an agent start-of-authority pointer.

## The single live machine CURRENT projection

- `.project/governance/generated/CURRENT_STATE.json`
  (+ its human-readable sibling `.project/governance/generated/CURRENT_STATE.md`)

## Files intentionally NOT retired

- `.project/governance/generated/CURRENT_STATE_TP20260819.json` — a git-state
  snapshot (head/tree/dirty) for the SUPERSEDED `TP-20260819` taskpack,
  referenced **by task id** from
  `taskpacks/current/TP-20260819-TASKPACK-WORKLAB.md` and its archive copy.
  It is not a current-identity projection, so it stays to keep those
  SUPERSEDED-layer references intact.
