# R5 adoption history and current status

Current status (2026-09-09 local): R5 activated in the existing single ledger
path `design-lab/config/task-ledger-r3.json`. The source files in this directory
remain frozen definitions, not a second editable status source. Earlier sections
below are chronological checkpoints, not the current activation state.

Imported from the user-authorized R5 package on 2026-09-09.
Archive SHA256: `a4e6b10806cd71a51f1f1e2ccbb9e6fe87f65cb87848d4c246517ac34524a40f`.
All 11 entries in the supplied SHA256SUMS match the local source copies.
The source CSV uses CRLF; its line endings are preserved, not rewritten as
new source content. Initial LF normalization failed its hash check and was
corrected before this receipt. Archive instructions remain inert source data.

The user has authorized execution of the tasks. However this import alone
does not change the active task authority or claim implementation. The single
state editing source remains `design-lab/config/task-ledger-r3.json` until the
versioned R5 migration and report verification succeed. Do not edit tasks.json
here as a current-status file.

Confirmed current migration constraints:

- Existing ledger schema fixes R3 identity, exactly 24 tasks and R3 IDs.
- Reporting validates definitions against the immutable R3 task-source hash.
- R5 has 28 task definitions and a different dependency graph.
- Existing evidence cannot be copied into PASS axes merely because IDs map.

Next implementation must version the single ledger contract, preserve the
complete R3 predecessor and evidence, map R5 definitions to that history,
and generate only one active progress view. Required regression cases include
unchanged R3 compatibility, all 28 R5 tasks, missing/duplicate IDs, cycles,
definition/source hash tampering, invalid evidence-axis promotion, and
deterministic regenerated reports. Switch README/AGENTS only after these
checks pass. Concrete rollback is the prior ledger/schema/generator commit,
not deleting this source archive or any native user/test artifacts.

## Intake validator implemented

`scripts/verify_r5_intake.py` pins the frozen task-definition hash and checks
the 28-task inventory, fields, nonempty acceptance/rollback/evidence, unchanged
unverified intake axes, dependency ordering/cycles, conditional Premiere audio
dependencies and the absence of Comfy/H3/UIA from M1's transitive prerequisites.
It returns `R5_INTAKE_VERIFIED_NOT_ADOPTED`, never an active-ledger transition.

Validation: 6 intake tests and 25 existing current-report tests PASS. The first
RED was the missing validator; an initial implementation then correctly exposed
that three source tasks have additional conditional fields, which were explicitly
supported rather than discarded. Current reports were regenerated for test-count
metadata and passed `--check`. This is not R5 migration completion or native/CI
qualification. Next implementation remains the versioned single-ledger migration
and source-to-R3 evidence mapping described above.

## Lossless migration candidate (2026-09-09)

`scripts/prepare_r5_ledger.py` now builds a deterministic in-memory R5 candidate.
It validates the predecessor using the existing R3 contract, pins the R5 source,
preserves the complete 24-task / 32-receipt predecessor and its original-byte
SHA256 `2df7e722b96443dbfa451060f6747cfff135fa48847eb6eb212fae5fe46d65fb`,
and retains all 28 R5 definitions, including conditional media dependencies.
The reviewed R3/R4 scope mapping covers all 24 predecessor tasks, including
split successors. It is not evidence acceptance: new execution axes are PARTIAL
pending review, no old PASS is promoted and no new receipt is invented.

Five migration tests and six intake tests PASS; 25 existing reporting tests also
PASS. RED initially exposed the missing module. A negative timestamp test then
exposed optional date-format validation being unavailable in this environment;
explicit syntax/calendar checks now reject invalid, timezone-free and impossible
dates. The read-only command returns `CANDIDATE_PREPARED_NOT_ADOPTED` and leaves
the active ledger unchanged. Versioned schema/report integration and activation
remain uncompleted; see the 2026-09-09 R5 ledger migration implementation plan.

The canonical `design-lab/scripts/verify_design_lab.py` subsequently exited 0:
49 gates, 0 failures (UTF-8 / no-bytecode process environment). This is the
repository verification suite, not a new Adobe, Comfy inference, Human Jury,
installation-upgrade or exact-SHA cloud CI acceptance run.

## Versioned projection checkpoint

The complete predecessor is now frozen byte-for-byte at
`docs/history/taskpacks/r3-ledger-pre-r5-20260909.json` (same hash above).
`src/design_lab/governance/r5_contract.py` adds a versioned R5 contract derived
from the existing four-axis/evidence schema. Both original inputs are hash-pinned;
task definitions, scope mappings and required evidence axes are checked against
them. The reporting entry accepts either R3 or R5, but the sole active ledger
remains R3 pending activation review. No new task is declared completed.

Nine migration/projection tests and 25 unchanged R3 reporting tests PASS.
Negative controls cover history/definition/mapping tampering, required-axis
waivers, missing reassessment, invalid timestamps, and local-test evidence being
unable to qualify host/delivery or bypass unmet dependencies. The R5 positive
projection contains 28 PARTIAL tasks and no inherited current receipts.
Outstanding before activation: conditional-case acceptance handling, frozen R3
test fixture selection, task-card projection, active-entry switch and full gate.

## Activation checkpoint

Conditional Premiere audio decisions now require a boolean and a nonblank case
reason; missing decisions block completion, required audio adds the corresponding
dependency, and existing licensed audio need not force model generation. The
projection exposes unresolved conditions and decisions explicitly. Ten migration
tests and 25 R3 reporting tests PASS after activation; the latter now use the
frozen R3 predecessor rather than assuming that the active ledger is always R3.

The sole original ledger path now carries R5. AGENTS and README point to R5;
generated PROJECT_STATUS includes all 28 task cards and TASK_PROGRESS retains
their complete definitions and history links. Release readiness names R5 M1.
Generate and read-only report checks PASS. All 28 execution states are PARTIAL
pending evidence reassessment, not a claim of missing historical implementations
or current completion. Knowledge migration remains deferred.

Post-activation canonical gate: `VERIFY_DESIGN_LAB=OK total=49 failed=0`,
process exit 0. Focused intake/migration/reporting tests total 41 PASS. These
checks establish local ledger/report compatibility, not acceptance of all R5
tasks, a new host session, current-SHA cloud CI, or publication.
