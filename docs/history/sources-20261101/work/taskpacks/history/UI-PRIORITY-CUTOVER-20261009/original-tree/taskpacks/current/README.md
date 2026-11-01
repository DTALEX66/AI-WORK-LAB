# taskpacks/current

This directory is the **current execution surface**, not the history archive.

Target normative current files:
- `WORK-LAB-UNIFIED-PRODUCT-CONVERGENCE-TASKPACK-20260918.md`
- `OPEN-TASK-REGISTER.md`

Operational compatibility files may remain only when explicitly allowlisted by
`.project/governance/project-authority-index.json`.

IMPORTANT: do not physically delete the legacy files until A04 migrates
`generate_current_state.py`, Stage3 CI/test dependencies, stale-reference inputs,
and fixed historical skill-count assumptions.

Historical retrieval is defined by:
`taskpacks/history/FROZEN-LEGACY-INDEX-20260918.md`.

## P0-03 subordinate current task-card model (2026-09-25)

The task authority model is: `CURRENT TaskPack -> OPEN Register + currentTaskCards`.
Subordinate task cards (e.g. the Product UI / Control Surface roadmap card and the
Orca Pilot card) are **planning records inside this directory**, NOT a second
CURRENT taskpack. Their machine authority lives in
`.project/governance/taskpack-authority-index.json` under `currentTaskCards[]`
and is verified by `scripts/ci/verify_project_authority_reference.py`:

```text
CURRENT TaskPack (exactly 1, per taskpack-authority-index classification)
├─ OPEN Register (taskpacks/current/OPEN-TASK-REGISTER.md, single live register)
└─ currentTaskCards
   ├─ WORK-LAB-PRODUCT-UI-CONTROL-SURFACE-TASKCARD-20260925 (roadmap, no execution grant)
   ├─ ORCA-PILOT-TASK-CARD-20260925 (registry FUT-001 binding, execution individually authorized)
   └─ WORK-LAB-ATLAS-GAP-REMEDIATION-TASKCARD-20261001 (verified-gap delta + AG-01..AG-20 breakdown, no execution grant)
```

Invariant (fail-closed): a card path exists on disk; the card is referenced by the
single OPEN Register; the card never self-claims top-level authority; the card
grants no more authority than its task grant (an explicit deferral /
no-execution-authorization marker is required); a declared `registry_entry`
binding is reciprocated by the future-candidate-registry entry's `task_card`;
and a card id is never classified in a taskpack bucket.

## P2-05 current/history re-convergence record (2026-09-25)

Three dated one-off records with **no live or machine references** were moved
from this directory to `taskpacks/history/` (register row P2-05):

- `POST-MERGE-FOLLOWUP-AUDIT-20260923.md`
- `DRIFT-AUDIT-CLOSURE-20260923.md`
- `V2-FINAL-ACCEPTANCE-REPORT.md`

The dated files retained here (e.g. `WORK-LAB-MASTER-2.0-APPROVAL-PACKAGE.md`,
`WORK-LAB-HERMES-TASKPACK-RECONCILIATION.json`, `BRANCH-CONVERGENCE-ANTI-REGRESSION-20260917.md`,
`BRANCH-RETIREMENT-LEDGER-20260917.json`, `HERMES-UPDATE-AND-FIXES-20260917.md`,
`HERMES-UPDATE-AND-MAINTENANCE-20260927.md`)
are retained because they carry live consumers — machine authority-index
references and code/test imports — so moving them would break the gates.
`U19-HEADLESS-REQUALIFICATION-HANDOFF-20260923.md` is retained as
unresolved-acceptance evidence for the still-open U19 desktop layer.

Before executing anything, read `/WORK-LAB-AUTHORITY.md`.
